# encoding: utf-8
import os
import re
from contextlib import contextmanager
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import _copy_attr, _copy_attrs, numlike
from .colors import Color
from .geometry import Point
from . import _cg_context, _cg_layer, _cg_port

_ctx = None
__all__ = ("Effect", "Shadow", "Stencil",)

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
        with _cg_context(), self.applied():
            if not self._grobs:
                return
            for grob in self._grobs:
                grob._draw()

    @property
    def contents(self):
        return self._grobs or []

class Effect(Frob):
    kwargs = ('blend','alpha','shadow')

    def __init__(self, *args, **kwargs):
        self._fx = {}

        if kwargs.pop('rollback', False):
            self._rollback = {eff:getattr(_ctx._effects, eff) for eff in kwargs}

        for eff, val in kwargs.items():
            self._fx[eff] = Effect._validate(eff, val)

    def __repr__(self):
        return 'Effect(%r)'%self._fx

    def __enter__(self):
        # if this isn't the first pass through the context manager, snapshot the current
        # state for all the effects we're changing so they can be restored in __exit__
        if not hasattr(self, '_rollback'):
            self._rollback = {eff:val for eff,val in _ctx._effects._fx.items() if eff in self._fx}

        # concat ourseves as a new canvas container
        _ctx.canvas.push(self)

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
            shadow._nsShadow.set() # don't mess with cg for shadows

        # i *think* it's better to skip the transparency layer when only blending,
        # but am bracing for the discovery that it's not...
        return bool(fx) and fx.keys() != ('blend',)
        # return bool(fx) # return whether any state was just changed

    @contextmanager
    def applied(self):
        """Apply compositing effects (if any) to any drawing inside the `with` block"""
        if self._fx:
            if self.set('blend', 'alpha'):
                with _cg_layer():
                    if not self.set('shadow'):
                        yield # if there's no shadow, we don't need a second layer
                    else:
                        with _cg_layer():
                            yield # if there is, we do
            else:
                # no blend or alpha changes, but since _fx exists there must be a shadow
                self.set('shadow')
                with _cg_layer():
                    yield
        else:
            # nothing to be done
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
            self._nsShadow = _copy_attr(args[0]._nsShadow)
            for attr, val in kwargs.items():
                if attr not in Shadow.kwargs: continue
                setattr(self, attr, val)
        else:
            self._nsShadow = NSShadow.alloc().init()
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

    def _get_color(self):
        return Color(self._nsShadow.shadowColor())
    def _set_color(self, spec):
        if isinstance(spec, Color):
            self._nsShadow.setShadowColor_(spec.nsColor)
        elif spec is None:
            self._nsShadow.setShadowColor_(None)
        else:
            if not isinstance(spec, (tuple,list)):
                spec = tuple([spec])
            self._nsShadow.setShadowColor_(Color(*spec).nsColor)
    color = property(_get_color, _set_color)

    def _get_blur(self):
        return self._nsShadow.shadowBlurRadius()
    def _set_blur(self, blur):
        self._nsShadow.setShadowBlurRadius_(blur)
    blur = property(_get_blur, _set_blur)

    def _get_offset(self):
        x,y = self._nsShadow.shadowOffset()
        return Point(x,-y)
    def _set_offset(self, offset):
        if numlike(offset):
            x = y = offset
        else:
            x,y = offset
        self._nsShadow.setShadowOffset_((x,-y))
    offset = property(_get_offset, _set_offset)

class Stencil(Frob):
    def __init__(self, stencil, invert=False, channel=None):
        from .text import Text
        from .bezier import Bezier
        from .image import Image
        if isinstance(stencil, Text):
            self.path = stencil.path
            self.evenodd = invert
        if isinstance(stencil, Bezier):
            self.path = stencil.copy()
            self.evenodd = invert
        elif isinstance(stencil, Image):
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
                CGContextAddRect(port, ((0,0),(_ctx.WIDTH, _ctx.HEIGHT)))
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
            maskRef = ci_ctx.createCGImage_fromRect_(greyscale, ((0,0), self.bmp.size))

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
    def applied(self):
        self.set()
        yield

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
