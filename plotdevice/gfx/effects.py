# encoding: utf-8
import os
import re
import sys
import math
from copy import copy
from contextlib import contextmanager
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import numlike
from .colors import Color
from .geometry import Point, CORNER
from . import _cg_context, _cg_layer, _cg_bitmap, _cg_port, _canvas_dims, _base_ctm, _visible, _layer_box, \
              _clip_depth, _casting, _render_lock

_ctx = None
__all__ = ("Effect", "Shadow", "Stencil",)

_CG_BLUR_LIMIT = 32  # widest blur handled by Core Graphics
_OPAQUE = (kCGImageAlphaNone, kCGImageAlphaNoneSkipFirst, kCGImageAlphaNoneSkipLast)

# blend modes
_BLEND=dict(
    # basics
    normal=kCGBlendModeNormal,
    clear=kCGBlendModeClear,
    copy=kCGBlendModeCopy,

    # pdf
    multiply=kCGBlendModeMultiply,
    screen=kCGBlendModeScreen,
    overlay=kCGBlendModeOverlay,
    darken=kCGBlendModeDarken,
    lighten=kCGBlendModeLighten,
    colordodge=kCGBlendModeColorDodge,
    colorburn=kCGBlendModeColorBurn,
    softlight=kCGBlendModeSoftLight,
    hardlight=kCGBlendModeHardLight,
    difference=kCGBlendModeDifference,
    exclusion=kCGBlendModeExclusion,
    hue=kCGBlendModeHue,
    saturation=kCGBlendModeSaturation,
    color=kCGBlendModeColor,
    luminosity=kCGBlendModeLuminosity,

    # nextstep
    sourcein=kCGBlendModeSourceIn,
    sourceout=kCGBlendModeSourceOut,
    sourceatop=kCGBlendModeSourceAtop,
    destinationover=kCGBlendModeDestinationOver,
    destinationin=kCGBlendModeDestinationIn,
    destinationout=kCGBlendModeDestinationOut,
    destinationatop=kCGBlendModeDestinationAtop,
    xor=kCGBlendModeXOR,
    plusdarker=kCGBlendModePlusDarker,
    pluslighter=kCGBlendModePlusLighter,
)

BLEND_MODES = """    normal, clear, copy, xor, multiply, screen,
    overlay, darken, lighten, difference, exclusion,
    color-dodge, color-burn, soft-light, hard-light,
    hue, saturation, color, luminosity,
    source-in, source-out, source-atop, plusdarker, pluslighter
    destination-over, destination-in, destination-out, destination-atop"""


### Effects objects ###

def _commit_all(grobs, held=False):
    """The grobs to use for drawing (or copies of any the script still holds references to)"""
    for probe in [object()]:
        unheld = sys.getrefcount(probe) # the refcount of an unreferenced grob
    committed = []
    for grob in grobs:
        copying = held or sys.getrefcount(grob) > unheld # measured before grob._commit adds a reference
        committed.append(grob._commit(copying))
    return tuple(committed)

class Frob(object):
    """A FoRmatting OBject encapsulates changes to the graphics context state.

    It can be appended to the current canvas for a one-shot change or pushed onto the
    canvas to perform a reset once the associated with block completes.
    """
    _grobs = None

    def append(self, grob):
        if self._grobs is None:
            self._grobs = []
        self._grobs.append(grob)

    def _draw(self):
        # apply state changes only to contained grobs
        with _cg_context(), self.applied(self):
            if not self._grobs:
                return
            for grob in _visible(self._grobs):
                _render_lock.checkpoint()
                grob._draw()

    def _commit(self, held):
        """A copy of the container holding its committed contents"""
        frob = copy(self)
        frob._grobs = _commit_all(self.contents, held) # the script can reach a held container's contents
        return frob

    @property
    def contents(self):
        return self._grobs or []

class Effect(Frob):
    kwargs = ('blend','alpha','shadow')

    def __init__(self, *args, **kwargs):
        self._fx = {}

        if kwargs.pop('rollback', False):
            self._rollback = {eff:_ctx._effects._fx.get(eff) for eff in kwargs}

        for eff, val in kwargs.items():
            self._fx[eff] = Effect._validate(eff, val)

    def __repr__(self):
        return 'Effect(%r)'%self._fx

    def __enter__(self):
        # if this isn't the first pass through the context manager, snapshot the current
        # state for all the effects we're changing so they can be restored in __exit__
        if not hasattr(self, '_rollback'):
            self._rollback = {eff:val for eff,val in _ctx._effects._fx.items() if eff in self._fx}

        # concat a snapshot of ourselves as a new canvas container
        _ctx.canvas.push(Effect(**self._fx))

        # reset the global per-object effects state within the block (since the effects
        # will be applied to a transparency layer encapsulating all drawing)
        for eff in self._fx:
            _ctx._effects._fx.pop(eff, None)
        return

    def __exit__(self, type, value, tb):
        # step back out to the pre-effects canvas container
        _ctx.canvas.pop()

        # restore the per-object effects state to what it was before the `with` block
        for eff, val in self._rollback.items():
            setattr(_ctx._effects, eff, val)
        del self._rollback

    def set(self, *effs):
        """Add compositing effects to the drawing context"""

        # apply effects specified in the args (or all by default)
        if not effs:
            effs = Effect.kwargs

        fx = {k:v for k,v in self._fx.items() if k in effs}
        if 'alpha' in fx:
            CGContextSetAlpha(_cg_port(), fx['alpha']);
        if 'blend' in fx:
            CGContextSetBlendMode(_cg_port(), _BLEND[fx['blend']])
        if 'shadow' in fx:
            shadow = Shadow(None) if fx['shadow'] is None else fx['shadow']
            shadow.set()

        return bool(fx) # return whether any state was just changed

    @contextmanager
    def applied(self, owner):
        """Apply compositing effects (if any) to any drawing inside the `with` block"""
        if self._fx and _casting.get() is not owner:
            shadowed = 'shadow' in self._fx
            if self.set('blend', 'alpha'):
                if not shadowed and getattr(owner, '_paints_once', False):
                    yield # a lone fill or stroke needs no layer
                else:
                    with _cg_layer(_layer_box(owner)):
                        if not shadowed:
                            yield # if there's no shadow, we don't need a second layer
                        else:
                            with (self.shadow or Shadow(None)).applied(owner):
                                yield # if there is, it needs its own
            else:
                with (self.shadow or Shadow(None)).applied(owner):
                    yield
        else:
            yield

    def copy(self):
        new = Effect()
        new._fx = dict(self._fx)
        return new

    @classmethod
    def _validate(self, eff, val):
        if val is None:
            pass
        elif eff=='alpha' and not (numlike(val) and 0<=val<=1):
            badalpha = 'alpha() value must be a number between 0 and 1.0'
            raise DeviceError(badalpha)
        elif eff=='blend':
            val = re.sub(r'[_\- ]','', val).lower()
            if val not in _BLEND:
                badblend = '"%s" is not a recognized blend mode.\nUse one of:\n%s'%(val, BLEND_MODES)
                raise DeviceError(badblend)
        elif eff=='shadow':
            if isinstance(val, Shadow):
                val = val.copy()
            else:
                val = Shadow(*val)

        return val

    def _get_alpha(self):
        return self._fx.get('alpha', 1.0)
    def _set_alpha(self, a):
        if a is None:
            self._fx.pop('alpha', None)
        else:
            self._fx['alpha'] = Effect._validate('alpha', a)
    alpha = property(_get_alpha, _set_alpha)

    def _get_blend(self):
        return self._fx.get('blend', 'normal')
    def _set_blend(self, mode):
        if mode is None:
            self._fx.pop('blend', None)
        else:
            self._fx['blend'] = Effect._validate('blend', mode)
    blend = property(_get_blend, _set_blend)

    def _get_shadow(self):
        return self._fx.get('shadow', None)
    def _set_shadow(self, spec):
        if spec is None:
            self._fx.pop('shadow', None)
        else:
            self._fx['shadow'] = Effect._validate('shadow', spec)
    shadow = property(_get_shadow, _set_shadow)

class Shadow(object):
    kwargs = ('color','blur','offset')

    def __init__(self, *args, **kwargs):
        super(Shadow, self).__init__()
        if args and isinstance(args[0], Shadow):
            self._color, self._blur, self._offset = args[0]._color, args[0]._blur, args[0]._offset
            for attr, val in kwargs.items():
                if attr not in Shadow.kwargs: continue
                setattr(self, attr, val)
        else:
            for attr, val in zip(Shadow.kwargs, args):
                kwargs.setdefault(attr, val)

            self.color = Color(kwargs.get('color', ('#000', .75)))
            self.blur = kwargs.get('blur', 10 if self.color.a else 0)
            offset = kwargs.get('offset', self.blur/2.0)
            if numlike(offset):
                offset = [offset]
            if len(offset)==1:
                offset *= 2
            self.offset = offset

    def __repr__(self):
        return "Shadow(%r, blur=%r, offset=%r)" % (self.color, self.blur, tuple(self.offset))

    def copy(self):
        return Shadow(self)

    @property
    def _device_offset(self):
        a, b, c, d, _, _ = _base_ctm.get()
        x, y = self._offset
        return a*x + c*y, b*x + d*y

    @property
    def _device_blur(self):
        a, b, c, d, _, _ = _base_ctm.get()
        return self._blur * abs(a*d - b*c) ** .5

    def set(self):
        CGContextSetShadowWithColor(_cg_port(), self._device_offset, self._device_blur, self._color.cgColor)

    @contextmanager
    def applied(self, owner):
        """Draw the `with` block's drawing with this shadow behind it"""
        port = _cg_port()
        box = _layer_box(owner)
        (dx, dy), blur = self._device_offset, self._device_blur
        in_bitmap = CGBitmapContextGetWidth(port) > 0
        rgba = in_bitmap and CGBitmapContextGetAlphaInfo(port) not in _OPAQUE \
               and CGColorSpaceGetModel(CGBitmapContextGetColorSpace(port)) == kCGColorSpaceModelRGB
        wide = blur > _CG_BLUR_LIMIT
        reach = None

        # CG's blur is inconsistent (and slows down) as it widens, so for wide blurs scale down first
        if wide and box is not None and rgba and not _clip_depth.get():
            # the target and what can shadow it
            whole = ((0, 0), (CGBitmapContextGetWidth(port), CGBitmapContextGetHeight(port)))
            clip = CGRectApplyAffineTransform(CGContextGetClipBoundingBox(port), CGContextGetCTM(port))
            target = CGRectIntegral(CGRectIntersection(whole, clip))
            drawn = CGRectApplyAffineTransform(((box[0], box[1]), (box[2], box[3])), _base_ctm.get())
            reach = CGRectIntegral(CGRectIntersection(drawn, CGRectInset(target, -(blur + abs(dx)), -(blur + abs(dy)))))
        if reach is None or CGRectIsEmpty(reach):
            self.set()
            with _cg_layer(box):
                yield
            return

        # draw the with-block content at full size
        shown = CGRectIntegral(CGRectIntersection(drawn, target))
        with _cg_bitmap(shown if not CGRectIsEmpty(shown) else ((0, 0), (1, 1)), 1.0, CGContextGetCTM(port)) as drawing_port:
            yield
        drawing = CGBitmapContextCreateImage(drawing_port)

        # redraw scaled down to a _CG_BLUR_LIMIT blur
        scale = _CG_BLUR_LIMIT / blur
        with _cg_bitmap(reach, scale, _base_ctm.get()) as silhouette_port:
            casting = _casting.set(owner)
            try:
                owner._draw()
            finally:
                _casting.reset(casting)
        silhouette = CGBitmapContextCreateImage(silhouette_port)

        # render just the shadow using the scaled silhouette
        (rx, ry), (rw, rh) = reach
        sx, sy, sw, sh = rx + dx - blur, ry + dy - blur, rw + 2 * blur, rh + 2 * blur
        shadow_w, shadow_h = int(math.ceil(sw * scale)), int(math.ceil(sh * scale))
        shadow_port = CGBitmapContextCreate(None, shadow_w, shadow_h, 8, 0, CGBitmapContextGetColorSpace(port),
                                            kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Host)
        CGContextSetShadowWithColor(shadow_port, (shadow_w, 0), _CG_BLUR_LIMIT, self._color.cgColor)
        silhouette_size = (CGBitmapContextGetWidth(silhouette_port), CGBitmapContextGetHeight(silhouette_port))
        CGContextDrawImage(shadow_port, ((blur * scale - shadow_w, blur * scale), silhouette_size), silhouette)
        shadow = CGBitmapContextCreateImage(shadow_port)

        # draw the scaled-up shadow and the with-block content on top
        CGContextSaveGState(port)
        CGContextConcatCTM(port, CGAffineTransformInvert(CGContextGetCTM(port)))
        CGContextSetInterpolationQuality(port, kCGInterpolationHigh)
        CGContextDrawImage(port, ((sx, sy), (shadow_w / scale, shadow_h / scale)), shadow)
        if not CGRectIsEmpty(shown):
            CGContextDrawImage(port, shown, drawing)
        CGContextRestoreGState(port)

    def _get_color(self):
        return Color(self._color)
    def _set_color(self, spec):
        if isinstance(spec, Color):
            self._color = Color(spec)
        elif spec is None:
            self._color = Color(None)
        else:
            if not isinstance(spec, (tuple,list)):
                spec = tuple([spec])
            self._color = Color(*spec)
    color = property(_get_color, _set_color)

    def _get_blur(self):
        return self._blur
    def _set_blur(self, blur):
        self._blur = float(blur)
    blur = property(_get_blur, _set_blur)

    def _get_offset(self):
        return Point(self._offset)
    def _set_offset(self, offset):
        if numlike(offset):
            x = y = offset
        else:
            x,y = offset
        self._offset = Point(float(x), float(y))
    offset = property(_get_offset, _set_offset)

class Stencil(Frob):
    def __init__(self, stencil, invert=False, channel=None):
        from .text import Text
        from .bezier import Bezier
        from .image import Image, Snapshot
        if isinstance(stencil, Snapshot):
            badstencil = "a plotted canvas can't be a clip() or mask() stencil (use image(canvas) instead)"
            raise DeviceError(badstencil)
        if isinstance(stencil, Text):
            self.path = stencil.path
            self.evenodd = invert
        if isinstance(stencil, Bezier):
            self.path = stencil.copy()
            self.evenodd = invert
        elif isinstance(stencil, Image):
            if channel == 'outline':
                # trace the image's vector shapes (or its bounding rect, if raster)
                # into a Bezier and clip/mask against that directly, rather than
                # rasterizing a bitmap mask
                outline = stencil._outline
                outline.transformmode = CORNER
                outline.transform = stencil._screen_transform
                self.path = outline
                self.evenodd = invert
            else:
                # default to using alpha if available and darkness if not
                if not channel:
                    channel = 'alpha' if stencil._nsBitmap.hasAlpha() else 'black'
                if channel=='black':
                    invert = not invert
                self.channel = channel
                self.invert = invert
                self.bmp = stencil

    def set(self):
        port = _cg_port()

        if hasattr(self, 'path'):
            path_xf = self.path._screen_transform
            cg_path = path_xf.apply(self.path).cgPath
            CGContextBeginPath(port)
            if self.evenodd:
                # if inverted, knock the path out of a full-screen rect and clip with that
                CGContextAddRect(port, ((0,0), _canvas_dims()))
                CGContextAddPath(port, cg_path)
                CGContextEOClip(port)
            else:
                # otherwise just color between the lines
                CGContextAddPath(port, cg_path)
                CGContextClip(port)

        elif hasattr(self, 'bmp'):
            # run the filter chain and render to a cg-image
            singlechannel = ciFilter(self.channel, self.bmp._ciImage)
            greyscale = ciFilter(self.invert, singlechannel)
            ci_ctx = CIContext.contextWithOptions_(None)
            maskRef = ci_ctx.createCGImage_fromRect_(greyscale, ((0,0), self.bmp._screen_size))

            # turn the image into an ‘imagemask’ cg-image
            cg_mask = CGImageMaskCreate(CGImageGetWidth(maskRef),
                                        CGImageGetHeight(maskRef),
                                        CGImageGetBitsPerComponent(maskRef),
                                        CGImageGetBitsPerPixel(maskRef),
                                        CGImageGetBytesPerRow(maskRef),
                                        CGImageGetDataProvider(maskRef), None, False);

            # the mask is sitting at (0,0) until transformed to screen coords
            xf = self.bmp._screen_transform
            xf.concat() # apply transforms before clipping...
            CGContextClipToMask(port, ((0,0), self.bmp.size), cg_mask)
            xf.inverse.concat() # ...restore the previous state after

    @contextmanager
    def applied(self, owner):
        self.set()
        token = _clip_depth.set(_clip_depth.get() + 1)
        try:
            yield
        finally:
            _clip_depth.reset(token)

class ClippingPath(Stencil):
    pass # NodeBox compat...


### core-image filters for channel separation and inversion ###

def ciFilter(opt, img):
    _filt = _inversionFilter if isinstance(opt, bool) else _channelFilter
    return _filt(opt, img)

def _channelFilter(channel, img):
    """Generate a greyscale image by isolating a single r/g/b/a channel"""

    rgb = ('red', 'green', 'blue')
    if channel=='alpha':
        transmat = [(0, 0, 0, 1)] * 3
        transmat += [ (0,0,0,0), (0,0,0,1) ]
    elif channel in rgb:
        rgb_row = [0,0,0]
        rgb_row.insert(rgb.index(channel), 1.0)
        transmat = [tuple(rgb_row)] * 3
        transmat += [ (0,0,0,0), (0,0,0,1) ]
    elif channel in ('black', 'white'):
        transmat = [(.333, .333, .333, 0)] * 3
        transmat += [ (0,0,0,0), (0,0,0,1) ]
    return _matrixFilter(transmat, img)

def _inversionFilter(identity, img):
    """Conditionally turn black to white and up to down"""

    # set up a matrix that's either identity or an r/g/b inversion
    polarity = -1.0 if not identity else 1.0
    bias = 0 if polarity>0 else 1
    transmat = [(polarity, 0, 0, 0), (0, polarity, 0, 0), (0, 0, polarity, 0),
                (0, 0, 0, 0), (bias, bias, bias, 1)]
    return _matrixFilter(transmat, img)

def _matrixFilter(matrix, img):
    """Apply a color transform to a CIImage and return the filtered result"""

    vectors = ("inputRVector", "inputGVector", "inputBVector", "inputAVector", "inputBiasVector")
    opts = {k:CIVector.vectorWithX_Y_Z_W_(*v) for k,v in zip(vectors, matrix)}
    opts[kCIInputImageKey] = img
    remap = CIFilter.filterWithName_("CIColorMatrix")
    for k,v in opts.items():
        remap.setValue_forKey_(v, k)
    return remap.valueForKey_("outputImage")
