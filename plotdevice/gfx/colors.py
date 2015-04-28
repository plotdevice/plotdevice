# encoding: utf-8
import os
import re
import json
import warnings
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import _copy_attr, _copy_attrs, _flatten, trim_zeroes, rsrc_path, numlike
_ctx = None
__all__ = ("RGB", "HSV", "HSB", "CMYK", "GREY",
           "Color", "Pattern", "Gradient",)

# color/output modes
RGB = "rgb"
HSV = HSB = "hsv"
CMYK = "cmyk"
GREY = "greyscale"

_CSS_COLORS = json.load(open(rsrc_path('colors.json')))

class Color(object):

    def __init__(self, *args, **kwargs):

        # flatten any tuples in the arguments list
        args = _flatten(args)

        # if the first arg is a color mode, use that to interpret the args
        if args and args[0] in (RGB, HSV, CMYK, GREY):
            mode, args = args[0], args[1:]
        else:
            mode=kwargs.get('mode')

        if mode not in (RGB, HSV, CMYK, GREY):
            # if no mode was specified, interpret the components in the context's current mode
            mode = _ctx._colormode

        # use the specified range for int values, or leave it as None to use the default 0-1 scale
        rng = kwargs.get('range')

        params = len(args)
        if params == 1 and args[0] is None:                 # None -> transparent
            clr = Color._nscolor(GREY, 0, 0)
        elif params == 1 and isinstance(args[0], Color):    # Color object
            _copy_attrs(args[0], self, ['_rgb','_cmyk'])
            return
        elif params == 1 and isinstance(args[0], Pattern):  # Pattern object
            self._cmyk = self._rgb = args[0]._nsColor
            return
        elif params == 1 and isinstance(args[0], Gradient): # Gradient (use first shade)
            first_clr = args[0]._colors[0]
            _copy_attrs(first_clr, self, ['_rgb','_cmyk'])
            return
        elif params == 1 and isinstance(args[0], NSColor):  # NSColor object
            clr = args[0]
        elif params>=1 and isinstance(args[0], basestring):
            r, g, b, a = Color._parse(args[0])              # Hex string or named color
            if args[1:]:
                a = args[1]
            clr = Color._nscolor(RGB, r, g, b, a)
        elif 1<=params<=2:                                  # Greyscale (+ alpha)
            gscale = self._normalizeList(args, rng)
            if params<2:
                gscale += (1,)
            clr = Color._nscolor(GREY, *gscale)
        elif 3<=params<=4 and mode in (RGB, HSV):           # RGB(a) & HSV(a)
            rgba_hsba = self._normalizeList(args, rng)
            if params<4:
                rgba_hsba += (1,)
            clr = Color._nscolor(mode, *rgba_hsba)
        elif 4<=params<=5 and mode==CMYK:                   # CMYK(a)
            cmyka = self._normalizeList(args, rng)
            if params<5:
                cmyka += (1,)
            clr = Color._nscolor(CMYK, *cmyka)
        else:                                               # default is the new black
            clr = Color._nscolor(GREY, 0, 1)

        self._cmyk = clr.colorUsingColorSpaceName_(NSDeviceCMYKColorSpace)
        self._rgb = clr.colorUsingColorSpaceName_(NSDeviceRGBColorSpace)

    @trim_zeroes
    def __repr__(self):
        args = repr(self.hexa) if self.a!=1.0 else '(%r)'%self.hex
        return '%s%s'%(self.__class__.__name__, args)

    def set(self):
        self.nsColor.set()

    # fill() and stroke() both cache the previous canvas state by creating a _rollback attr.
    # act as a context manager if there's a fill/stroke state to revert to at the end of the block.
    def __enter__(self):
        if not hasattr(self, '_rollback'):
            badcontext = 'the with-statement can only be used with fill() and stroke(), not arbitrary colors'
            raise DeviceError(badcontext)
        return self

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
            setattr(_ctx, statevar, val)

    @property
    def nsColor(self):
        return self._rgb if _ctx._outputmode==RGB else self._cmyk

    @property
    def cgColor(self):
        mode = _ctx._outputmode
        components = self._values(mode)
        space = (self._rgb if mode==RGB else self._cmyk).colorSpace().CGColorSpace()
        return CGColorCreate(space, components)

    def _values(self, mode):
        outargs = [None] * 4
        if mode is RGB:
            return self._rgb.getRed_green_blue_alpha_(*outargs)
        elif mode is HSV:
            return self._rgb.getHue_saturation_brightness_alpha_(*outargs)
        elif mode is CMYK:
            return (self._cmyk.cyanComponent(), self._cmyk.magentaComponent(),
                    self._cmyk.yellowComponent(), self._cmyk.blackComponent(),
                    self._cmyk.alphaComponent())

    def copy(self):
        new = self.__class__()
        new._rgb = self._rgb.copy()
        new._updateCmyk()
        return new

    def _updateCmyk(self):
        self._cmyk = self._rgb.colorUsingColorSpaceName_(NSDeviceCMYKColorSpace)

    def _updateRgb(self):
        self._rgb = self._cmyk.colorUsingColorSpace_(NSColorSpace.sRGBColorSpace())

    def _get_hue(self):
        return self._rgb.hueComponent()
    def _set_hue(self, val):
        val = self._normalize(val)
        h, s, b, a = self._values(HSV)
        self._rgb = Color._nscolor(HSV, val, s, b, a)
        self._updateCmyk()
    h = hue = property(_get_hue, _set_hue, doc="the hue of the color")

    def _get_saturation(self):
        return self._rgb.saturationComponent()
    def _set_saturation(self, val):
        val = self._normalize(val)
        h, s, b, a = self._values(HSV)
        self._rgb = Color._nscolor(HSV, h, val, b, a)
        self._updateCmyk()
    s = saturation = property(_get_saturation, _set_saturation, doc="the saturation of the color")

    def _get_brightness(self):
        return self._rgb.brightnessComponent()
    def _set_brightness(self, val):
        val = self._normalize(val)
        h, s, b, a = self._values(HSV)
        self._rgb = Color._nscolor(HSV, h, s, val, a)
        self._updateCmyk()
    v = value = brightness = property(_get_brightness, _set_brightness, doc="the brightness of the color")

    def _get_hsba(self):
        return self._values(HSV)
    def _set_hsba(self, values):
        h, s, b, a = self._normalizeList(values)
        self._rgb = Color._nscolor(HSV, h, s, b, a)
        self._updateCmyk()
    hsba = property(_get_hsba, _set_hsba, doc="the hue, saturation, brightness and alpha of the color")

    def _get_red(self):
        return self._rgb.redComponent()
    def _set_red(self, val):
        val = self._normalize(val)
        r, g, b, a = self._values(RGB)
        self._rgb = Color._nscolor(RGB, val, g, b, a)
        self._updateCmyk()
    r = red = property(_get_red, _set_red, doc="the red component of the color")

    def _get_green(self):
        return self._rgb.greenComponent()
    def _set_green(self, val):
        val = self._normalize(val)
        r, g, b, a = self._values(RGB)
        self._rgb = Color._nscolor(RGB, r, val, b, a)
        self._updateCmyk()
    g = green = property(_get_green, _set_green, doc="the green component of the color")

    def _get_blue(self):
        return self._rgb.blueComponent()
    def _set_blue(self, val):
        val = self._normalize(val)
        r, g, b, a = self._values(RGB)
        self._rgb = Color._nscolor(RGB, r, g, val, a)
        self._updateCmyk()
    b = blue = property(_get_blue, _set_blue, doc="the blue component of the color")

    def _get_alpha(self):
        return self._rgb.alphaComponent()
    def _set_alpha(self, val):
        val = self._normalize(val)
        r, g, b, a = self._values(RGB)
        self._rgb = Color._nscolor(RGB, r, g, b, val)
        self._updateCmyk()
    a = alpha = property(_get_alpha, _set_alpha, doc="the alpha component of the color")

    def _get_rgba(self):
        return self._values(RGB)
    def _set_rgba(self, values):
        r, g, b, a = self._normalizeList(values)
        self._rgb = Color._nscolor(RGB, r, g, b, a)
        self._updateCmyk()
    rgba = property(_get_rgba, _set_rgba, doc="the red, green, blue and alpha values of the color")

    def _get_cyan(self):
        return self._cmyk.cyanComponent()
    def _set_cyan(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = Color._nscolor(CMYK, val, m, y, k, a)
        self._updateRgb()
    c = cyan = property(_get_cyan, _set_cyan, doc="the cyan component of the color")

    def _get_magenta(self):
        return self._cmyk.magentaComponent()
    def _set_magenta(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = Color._nscolor(CMYK, c, val, y, k, a)
        self._updateRgb()
    m = magenta = property(_get_magenta, _set_magenta, doc="the magenta component of the color")

    def _get_yellow(self):
        return self._cmyk.yellowComponent()
    def _set_yellow(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = Color._nscolor(CMYK, c, m, val, k, a)
        self._updateRgb()
    y = yellow = property(_get_yellow, _set_yellow, doc="the yellow component of the color")

    def _get_black(self):
        return self._cmyk.blackComponent()
    def _set_black(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = Color._nscolor(CMYK, c, m, y, val, a)
        self._updateRgb()
    k = black = property(_get_black, _set_black, doc="the black component of the color")

    def _get_cmyka(self):
        return (self._cmyk.cyanComponent(), self._cmyk.magentaComponent(), self._cmyk.yellowComponent(), self._cmyk.blackComponent(), self._cmyk.alphaComponent())
    cmyka = property(_get_cmyka, doc="a tuple containing the CMYKA values for this color")

    def _get_hex(self):
        r, g, b, a = self._values(RGB)
        s = "".join('%02x'%int(255*c) for c in (r,g,b))
        if all([len(set(pair))==1 for pair in zip(s[::2], s[1::2])]):
            s = "".join(s[::2])
        return "#"+s
    def _set_hex(self, val):
        r, g, b, a = Color._parse(clr)
        self._rgb = Color._nscolor(RGB, r, g, b, a)
        self._updateCmyk()
    hex = property(_get_hex, _set_hex, doc="the rgb hex string for the color")

    def _get_hexa(self):
        return (self.hex, self.a)
    def _set_hexa(self, clr, alpha):
        a = self._normalize(alpha)
        r, g, b, _ = Color._parse(clr)
        self._rgb = Color._nscolor(RGB, r, g, b, a)
        self._updateCmyk()
    hexa = property(_get_hexa, _set_hexa, doc="a tuple containing the color's rgb hex string and an alpha float")

    def blend(self, otherColor, factor):
        """Blend the color with otherColor with a factor; return the new color. Factor
        is a float between 0.0 and 1.0.
        """
        if hasattr(otherColor, "color"):
            otherColor = otherColor._rgb
        return self.__class__(color=self._rgb.blendedColorWithFraction_ofColor_(
                factor, otherColor))

    def _normalize(self, v, rng=None):
        """Bring the color into the 0-1 scale for the current colorrange"""
        r = float(_ctx._colorrange if rng is None else rng)
        return v if r==1.0 else v/r

    def _normalizeList(self, lst, rng=None):
        """Bring the color into the 0-1 scale for the current colorrange"""
        r = float(_ctx._colorrange if rng is None else rng)
        if r == 1.0: return lst
        return [v / r for v in lst]

    @classmethod
    def recognized(cls, blob):
        if isinstance(blob, Color):
            return True

        valid_str = lambda s: isinstance(s, basestring) and (s.strip() in _CSS_COLORS or \
                                                             re.match(r'#?[a-z0-9]{3,8}$', s.strip()) )
        if isinstance(blob, (tuple, list)):
            demoded = [b for b in blob if b not in (RGB,HSV,CMYK,GREY)]
            if all(numlike(n) and len(demoded)<=5 for n in blob):
                return True

            if demoded and valid_str(demoded[0]):
                if len(demoded) < 2:
                    return True
                if len(demoded)==2 and numlike(demoded[1]):
                    return True
        elif isinstance(blob, basestring):
            return valid_str(blob)

    @classmethod
    def _nscolor(cls, scheme, *components):
        factory = {RGB: NSColor.colorWithSRGBRed_green_blue_alpha_,
                   HSV: NSColor.colorWithHue_saturation_brightness_alpha_,
                   CMYK: NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_,
                   GREY: NSColor.colorWithGenericGamma22White_alpha_}
        return factory[scheme](*components)

    @classmethod
    def _parse(cls, clrstr):
        """Returns an r/g/b/a tuple based on a css color name or a hex string of the form:
        RRGGBBAA, RRGGBB, RGBA, or RGB (with or without a leading #)
        """
        if clrstr in _CSS_COLORS: # handle css color names
            clrstr = _CSS_COLORS[clrstr]

        if re.search(r'#?[0-9a-f]{3,8}', clrstr): # rgb & rgba hex strings
            hexclr = clrstr.lstrip('#')
            if len(hexclr) in (3,4):
                hexclr = "".join(map("".join, zip(hexclr,hexclr)))
            if len(hexclr) not in (6,8):
                invalid = "Don't know how to interpret hex color '#%s'." % hexclr
                raise DeviceError(invalid)
            r, g, b = [int(n, 16)/255.0 for n in (hexclr[0:2], hexclr[2:4], hexclr[4:6])]
            a = 1.0 if len(hexclr)!=8 else int(hexclr[6:], 16)/255.0
        else:
            invalid = "Color strings must be 3/6/8-character hex codes or valid css-names (not %r)" % clrstr
            raise DeviceError(invalid)
        return r, g, b, a

class Pattern(object):
    def __init__(self, img):
        if isinstance(img, Pattern):
            self._nsColor = img._nsColor
        else:
            from .image import Image
            img = Image(img) if isinstance(img, basestring) else img
            self._nsColor = NSColor.colorWithPatternImage_(img._nsImage)

    # fill() and stroke() both cache the previous canvas state by creating a _rollback attr.
    # act as a context manager if there's a fill/stroke state to revert to at the end of the block.
    def __enter__(self):
        if not hasattr(self, '_rollback'):
            badcontext = 'the with-statement can only be used with fill() and stroke(), not arbitrary colors'
            raise DeviceError(badcontext)
        return self

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
            setattr(_ctx, statevar, val)

    def set(self):
        self._nsColor.set()

    def fill(self, path):
        self._nsColor.set()
        path._nsBezierPath.fill()

    def copy(self):
        return Pattern(self)


class Gradient(object):
    kwargs = ('steps', 'angle', 'center')

    def __init__(self, *colors, **kwargs):
        if colors and isinstance(colors[0], Gradient):
            _copy_attrs(colors[0], self, ('_gradient', '_steps', '_colors', '_center', '_angle'))
            return

        # parse colors and assemble an NSGradient
        colors = [Color(c) for c in colors]
        if len(colors) == 1:
            colors.append(Color(None))
        num_c = len(colors)
        steps = kwargs.get('steps', [i/(num_c-1.0) for i in range(num_c)])
        num_s = len(steps)
        if num_s!=num_c or not all(numlike(n) and 0<=n<=1 for n in steps):
            wrongstep = 'Gradient steps must equal in length to the number of colors (and lie in the range 0-1)'
            raise DeviceError(wrongstep)
        center = kwargs.get('center', [0,0])
        if len(center)!=2 or not all(numlike(n) and -1<=n<=1 for n in center):
            offsides = 'Gradient center must be a 2-tuple or Point using relative values ranging from -1 to 1'
            raise DeviceError(offsides)
        self._steps = steps
        self._colors = colors
        self._center = center
        self._outputmode = None
        self._gradient = None

        # radial if None, otherwise convert angle from context units to degrees
        self._angle = None
        if 'angle' in kwargs:
            self._angle = _ctx._angle(kwargs['angle'], 'degrees')

    # fill() caches the previous canvas state by creating a _rollback attr.
    # act as a context manager if there's a fill to revert to at the end of the block.
    def __enter__(self):
        if not hasattr(self, '_rollback'):
            badcontext = 'the with-statement can only be used with fill() and stroke(), not arbitrary colors'
            raise DeviceError(badcontext)
        return self

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
            setattr(_ctx, statevar, val)

    def __repr__(self):
        return 'Gradient(%s, steps=%r)'%(", ".join('%r'%c for c in self._colors), self._steps)

    @property
    def nsGradient(self):
        c_mode = _ctx._outputmode
        if not self._gradient or self._outputmode!=c_mode:
            c_space = getattr(NSColorSpace, 'deviceRGBColorSpace' if c_mode==RGB else 'deviceCMYKColorSpace')
            ns_clrs = [c.nsColor for c in self._colors]
            ns_gradient = NSGradient.alloc().initWithColors_atLocations_colorSpace_(ns_clrs, self._steps, c_space())
            self._gradient, self._outputmode = ns_gradient, c_mode
        return self._gradient

    @property
    def brightness(self):
        return max(clr._rgb.brightnessComponent() for clr in self._colors)

    def copy(self):
        return self.__class__(self)

    def fill(self, obj):
        if isinstance(obj, tuple):
            if self._angle is not None:
                self.nsGradient.drawInRect_angle_(obj, self._angle)
            else:
                self.nsGradient.drawInRect_relativeCenterPosition_(obj, self._center)
        elif obj.__class__.__name__ == 'Bezier':
            pth = obj._nsBezierPath
            if self._angle is not None:
                self.nsGradient.drawInBezierPath_angle_(pth, self._angle)
            else:
                self.nsGradient.drawInBezierPath_relativeCenterPosition_(pth, self._center)
