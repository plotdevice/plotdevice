# encoding: utf-8
import threading, time
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
    if box is None:
        CGContextBeginTransparencyLayer(port, None)
    else:
        to_user = CGAffineTransformConcat(_base_ctm.get(), CGAffineTransformInvert(CGContextGetCTM(port)))
        CGContextBeginTransparencyLayerWithRect(port, CGRectApplyAffineTransform(((box[0], box[1]), (box[2], box[3])), to_user), None)
    yield
    CGContextEndTransparencyLayer(port)

def _cg_port():
    return NSGraphicsContext.currentContext().CGContext()

### render-time state ###

_frame = ContextVar('frame', default=None)
_ctx = None

_base_ctm = ContextVar('base_ctm', default=(1, 0, 0, -1, 0, 0))

_culling = ContextVar('culling', default=None)

# how many clip() or mask() stencils the drawing is inside
_clips = ContextVar('clips', default=0)

_bare = ContextVar('bare', default=None)

@contextmanager
def _rendering(frame, within=None):
    token = _frame.set(frame)
    ctm_token = _base_ctm.set(CGContextGetCTM(_cg_port()))
    cull_token = _culling.set(within)
    try:
        yield
    finally:
        _culling.reset(cull_token)
        _base_ctm.reset(ctm_token)
        _frame.reset(token)

class _RenderLock(object):
    QUANTUM = 0.003 # (3 ms)

    def __init__(self):
        self._cond = threading.Condition()
        self._owner = None # thread holding it
        self._depth = 0    # how many times it's been taken without being let go
        self._since = 0.0  # when it was taken
        self._issued = 0   # tickets handed out (one per waiting or holding thread)
        self._serving = 0  # the ticket whose thread holds it

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
        if self._owner != threading.get_ident():
            return
        waiting = self._issued - self._serving > 1
        if waiting and time.perf_counter() - self._since >= self.QUANTUM:
            depth, self._depth = self._depth, 1
            self.__exit__()
            self.__enter__()
            self._depth = depth

_render_lock = _RenderLock()

def _layer_box(grob):
    frame = _frame.get()
    return None if frame is None or grob is None else frame._layer_box(grob)

def _visible(grobs):
    within = _culling.get()
    return grobs if within is None else _frame.get()._within(within, grobs)

def _outputmode():
    frame = _frame.get()
    return _ctx._outputmode if frame is None else frame.outputmode

def _canvas_dims():
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

