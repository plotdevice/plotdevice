# encoding: utf-8
import math, threading, time
from contextlib import contextmanager
from contextvars import ContextVar
from ..lib.cocoa import *

### graphics context mgmt ###

def _save():
    NSGraphicsContext.currentContext().saveGraphicsState()

def _restore():
    NSGraphicsContext.currentContext().restoreGraphicsState()

@contextmanager
def _ns_context():
    ctx = NSGraphicsContext.currentContext()
    ctx.saveGraphicsState()
    yield ctx
    ctx.restoreGraphicsState()

@contextmanager
def _cg_context():
    port = NSGraphicsContext.currentContext().CGContext()
    CGContextSaveGState(port)
    yield port
    CGContextRestoreGState(port)

@contextmanager
def _cg_layer(box=None):
    port = _cg_port()
    if box:
        # limit the transparency layer to the requested rect
        to_user = CGAffineTransformConcat(_base_ctm.get(), CGAffineTransformInvert(CGContextGetCTM(port)))
        CGContextBeginTransparencyLayerWithRect(port, CGRectApplyAffineTransform(((box[0], box[1]), (box[2], box[3])), to_user), None)
    else:
        CGContextBeginTransparencyLayer(port, None)
    yield
    CGContextEndTransparencyLayer(port)

@contextmanager
def _cg_bitmap(rect, scale, ctm):
    # draw into a new bitmap covering `rect`
    port = _cg_port()
    (x, y), (w, h) = rect
    bitmap = CGBitmapContextCreate(None, int(math.ceil(w * scale)), int(math.ceil(h * scale)), 8, 0,
                                   CGBitmapContextGetColorSpace(port),
                                   kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Host)
    CGContextScaleCTM(bitmap, scale, scale)
    CGContextTranslateCTM(bitmap, -x, -y)
    CGContextConcatCTM(bitmap, ctm)
    flipped = NSGraphicsContext.currentContext().isFlipped()
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithCGContext_flipped_(bitmap, flipped))
    to_bitmap = CGAffineTransformConcat(CGAffineTransformMakeTranslation(-x, -y), CGAffineTransformMakeScale(scale, scale))
    moved = _base_ctm.set(CGAffineTransformConcat(_base_ctm.get(), to_bitmap))
    try:
        yield bitmap
    finally:
        _base_ctm.reset(moved)
        NSGraphicsContext.restoreGraphicsState()

def _cg_port():
    return NSGraphicsContext.currentContext().CGContext()

### render-time state ###

# the canvas state used by the currently executing script
_ctx = None

# the Frame being rendered on this thread
_frame = ContextVar('frame', default=None)

# the CTM when the frame started drawing
_base_ctm = ContextVar('base_ctm', default=(1, 0, 0, -1, 0, 0))

# the rect being rendered, for culling
_culling = ContextVar('culling', default=None)

# how many clip() or mask() stencils the drawing is inside
_clip_depth = ContextVar('clip_depth', default=0)

# a grob being redrawn to cast its shadow
_casting = ContextVar('casting', default=None)

# the frame being committed
_committing = ContextVar('committing', default=None)

# the PDF being drawn and its plotted-canvas layers (if any)
_pdf_doc = ContextVar('pdf_doc', default=(None, None))

@contextmanager
def _rendering(frame, within=None):
    token = _frame.set(frame)
    ctm_token = _base_ctm.set(CGContextGetCTM(_cg_port()))
    cull_token = _culling.set(within)
    clip_token = _clip_depth.set(0) # a pattern's tile starts its canvas outside any clip
    cast_token = _casting.set(None) # ...and outside any shadow being cast
    try:
        yield
    finally:
        _casting.reset(cast_token)
        _clip_depth.reset(clip_token)
        _culling.reset(cull_token)
        _base_ctm.reset(ctm_token)
        _frame.reset(token)

class _RenderLock(object):
    """Serializes Core Graphics calls across threads

    Renders run until their time slice elapses, then hand off to the next thread.
    This is only necessary because of FB25219467, which causes cross-thread
    glitches on aarch64.

    A canvas pattern's tile renders from inside a CG call, so whoever makes that
    call holds the lock for it."""
    QUANTUM = 0.003 # 3 ms

    def __init__(self):
        self._cond = threading.Condition()
        self._owner = None # thread holding the lock
        self._depth = 0    # re-entry depth
        self._since = 0.0  # when it was taken
        self._issued = 0   # tickets handed out (one per waiting or holding thread)
        self._serving = 0  # the holder's ticket

    def __enter__(self):
        me = threading.get_ident()
        with self._cond:
            if self._owner == me:
                self._depth += 1
                return
            ticket = self._issued
            self._issued += 1
            while self._serving != ticket:
                self._cond.wait()
            self._owner, self._depth, self._since = me, 1, time.perf_counter()

    def __exit__(self, *exc):
        with self._cond:
            self._depth -= 1
            if not self._depth:
                self._owner = None
                self._serving += 1
                self._cond.notify_all()

    def checkpoint(self):
        """Let a waiting render in once this one's quantum is up"""
        if self._owner != threading.get_ident() or self._depth > 1:
            return # when in the middle of a reentrant CG call, don't hand off the lock
        waiting = self._issued - self._serving > 1
        if waiting and time.perf_counter() - self._since >= self.QUANTUM:
            self.__exit__()
            self.__enter__()

_render_lock = _RenderLock()

def _layer_box(grob):
    """The box a grob's transparency layer needs, or None"""
    frame = _frame.get()
    return None if frame is None or grob is None else frame._bounds.layer_box(grob)

def _visible(grobs):
    """The grobs that may draw inside the rect being rendered"""
    within = _culling.get()
    return grobs if within is None else _frame.get()._bounds.within(within, grobs)

def _outputmode():
    """The RGB/CMYK mode to resolve colors for"""
    frame = _frame.get() or _committing.get()
    return _ctx._outputmode if frame is None else frame.outputmode

def _outputpress():
    """The press colors resolve for, or None for Generic CMYK"""
    frame = _frame.get() or _committing.get()
    if frame is not None:
        return frame.press
    if _ctx._press:
        return _ctx._press
    return _ctx._cli_colors if isinstance(colors.Profile.named.get(_ctx._cli_colors), colors.Press) else None

def _inkmode():
    """The mode to make colors' CGColors & NSColors for"""
    frame = _frame.get() or _committing.get()
    if frame is not None and frame.ink:
        return frame.ink
    return _ctx._outputmode if frame is None else frame.outputmode

def _canvas_dims():
    """The canvas's width & height in canvas units"""
    frame = _frame.get()
    if frame is None:
        return _ctx.canvas.width, _ctx.canvas.height
    return frame.width, frame.height

### submodule init ###

# pool the submodules' __all__ namespaces into our own
from . import atoms, effects, colors, text, typography, bezier, image, geometry
modules = atoms, effects, colors, text, typography, bezier, image, geometry
ns = {}
for module in modules:
  ns.update( (a,getattr(module,a)) for a in module.__all__  )
globals().update(ns)
__all__ = list(ns.keys())

# called by a Context to do the dependency injection™
def bind(ctx):
  global _ctx
  _ctx = ctx
  for module in modules:
    # all of the gfx.* submodules refer to a global called _ctx to access the
    # parent context. before a user script is interpreted, the sandbox resets the
    # context which calls this method as a side-effect.
    setattr(module, '_ctx', ctx)
