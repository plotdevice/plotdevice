# encoding: utf-8
import re
import json
import colorsys
import warnings
import objc
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import _copy_attr, _copy_attrs, _flatten, trim_zeroes, rsrc_path, numlike
from . import _output, _frame, _base_ctm, _cg_port
from .profiles import RGB, HSV, HSB, CMYK, GREY, P3, SRGB, REC709, REC2020, GRACOL, GRACOL_UNCOATED, SWOP, FOGRA39, FOGRA47, \
                      Profile, Press

PDGradient = objc.lookUpClass('PDGradient')

_ctx = None
__all__ = ("RGB", "HSV", "HSB", "CMYK", "GREY", "P3", "SRGB", "REC709", "REC2020",
           "GRACOL", "GRACOL_UNCOATED", "SWOP", "FOGRA39", "FOGRA47",
           "Color", "Pattern", "Gradient",)

# extended spaces keep out-of-gamut components
SPACES = {P3: CGColorSpaceCreateWithName(kCGColorSpaceExtendedDisplayP3),
           SRGB: CGColorSpaceCreateWithName(kCGColorSpaceExtendedSRGB)}
SPACE_NAMES = {kCGColorSpaceExtendedDisplayP3:P3, kCGColorSpaceDisplayP3:P3,
                kCGColorSpaceExtendedSRGB:SRGB, kCGColorSpaceSRGB:SRGB}
GENERIC_CMYK = CGColorSpaceCreateWithName(kCGColorSpaceGenericCMYK)
DEVICE_CMYK = CGColorSpaceCreateDeviceCMYK()

# lowercased names for mode= and space=
NAMES = dict(mode={RGB:RGB, HSV:HSV, 'hsb':HSV, CMYK:CMYK, GREY:GREY},
              space={P3:P3, SRGB:SRGB})

CSS_COLORS = json.load(open(rsrc_path('colors.json')))

def _canonical(kind, val):
    """The color mode or space a string case-insensitively names"""
    if val is None:
        return None
    names = NAMES[kind]
    key = val.lower() if isinstance(val, str) else val
    if key not in names:
        unknown = 'Unknown color %s %r (should be one of: %s)' % (kind, val, ', '.join(sorted(set(names.values()))))
        raise DeviceError(unknown)
    return names[key]

def _clamp(v):
    return min(max(v, 0.0), 1.0)

def _components(cg):
    return CGColorGetComponents(cg).as_tuple(CGColorGetNumberOfComponents(cg))

def _matched(cg, space):
    return CGColorCreateCopyByMatchingToColorSpace(space, kCGRenderingIntentDefault, cg, None)

class Color(object):

    def __init__(self, *args, **kwargs):
        Color.validate(kwargs)

        # flatten any tuples in the arguments list
        args = _flatten(args)

        # if the first arg is a color mode, use that to interpret the args
        if args and args[0] in (RGB, HSV, CMYK, GREY):
            mode, args = args[0], args[1:]
        else:
            mode = _canonical('mode', kwargs.get('mode'))

        if mode is None:
            # if no mode was specified, interpret the components in the context's current mode
            mode = _ctx._colormode

        # components are in space=, else the current one
        converting = kwargs.get('space') is not None
        space = _canonical('space', kwargs.get('space')) or _ctx._colorspace

        # use the specified range for int values, or leave it as None to use the default 0-1 scale
        rng = kwargs.get('range')

        params = len(args)
        cmyk, values = False, None # known components, or None
        if params == 1 and args[0] is None:                 # None -> transparent
            clr, values = Color._cgcolor(GREY, space, 0, 0)
        elif params == 1 and isinstance(args[0], Color):    # Color object
            self._share(args[0])
            if converting and self.space != space:
                if self._mode is CMYK:
                    self._cmyk = self._src
                    self._space = space # rgb converted on demand
                else:
                    self._rgb = _matched(self._rgb, SPACES[space])
                    self._space = space
                    self._updateCmyk()
            return
        elif params == 1 and isinstance(args[0], Gradient): # Gradient (use first shade)
            self._share(args[0]._colors[0])
            return
        elif params == 1 and isinstance(args[0], (NSColor, CGColorRef)): # NSColor or CGColor object
            clr = args[0].CGColor() if isinstance(args[0], NSColor) else args[0]
            own = SPACE_NAMES.get(CGColorSpaceCopyName(CGColorGetColorSpace(clr)))
            if own is not None:
                # keep p3 or srgb components unless converting
                clr = CGColorCreate(SPACES[own], _components(clr))
                if converting and own != space:
                    clr = _matched(clr, SPACES[space])
                else:
                    space = own
            elif CGColorSpaceGetModel(CGColorGetColorSpace(clr)) == kCGColorSpaceModelCMYK:
                clr, cmyk = CGColorCreate(GENERIC_CMYK, _components(clr)), True
            else:
                clr = _matched(clr, SPACES[space])
        elif params>=1 and isinstance(args[0], str):
            r, g, b, a = Color._parse(args[0])              # Hex string or named color
            if args[1:]:
                a = args[1]
            clr, values = Color._cgcolor(RGB, space, r, g, b, a)
        elif 1<=params<=2:                                  # Greyscale (+ alpha)
            gscale = self._normalizeList(args, rng)
            if params<2:
                gscale += (1,)
            clr, values = Color._cgcolor(GREY, space, *gscale)
        elif 3<=params<=4 and mode in (RGB, HSV):           # RGB(a) & HSV(a)
            rgba_hsba = self._normalizeList(args, rng)
            if params<4:
                rgba_hsba += (1,)
            clr, values = Color._cgcolor(mode, space, *rgba_hsba)
        elif 4<=params<=5 and mode==CMYK:                   # CMYK(a)
            cmyka = self._normalizeList(args, rng)
            if params<5:
                cmyka += (1,)
            (clr, values), cmyk = Color._cgcolor(CMYK, space, *cmyka), True
        else:                                               # default is the new black
            clr, values = Color._cgcolor(GREY, space, 0, 1)

        # the space of the rgb components
        self._space = space
        if cmyk:
            # keep the cmyk, convert to rgb on demand
            self._cmyk = clr
            self._src, self._mode = clr, CMYK
            if values is not None:
                self._to['cmyka'] = values
        else:
            self._rgb = clr # cmyk converted on demand
            self._src, self._mode = clr, RGB
            if values is not None:
                self._to['rgba'] = values

    @trim_zeroes
    def __repr__(self):
        # hex in its own space, named if not current
        r, g, b, a = self._values(RGB)
        args = [repr(Color._hexstring(r, g, b))]
        if a != 1.0:
            args.append(repr(a))
        if self.space != _ctx._colorspace:
            args.append('space=%s' % self.space.upper())
        return '%s(%s)'%(self.__class__.__name__, ', '.join(args))

    # equal if space, rgba & cmyka match to 5 places
    def _key(self):
        return (self.space,) + tuple(round(v, 5) for v in self._values(RGB))

    def __eq__(self, other):
        if not isinstance(other, Color):
            return NotImplemented
        if self._key() != other._key():
            return False
        return [round(v, 5) for v in self.cmyka] == [round(v, 5) for v in other.cmyka]

    def __hash__(self):
        return hash(self._key())

    def set(self):
        port = _cg_port()
        CGContextSetFillColorWithColor(port, self.cgColor)
        CGContextSetStrokeColorWithColor(port, self.cgColor)

    # fill() and stroke() both cache the previous canvas state by creating a _rollback attr.
    # act as a context manager if there's a fill/stroke state to revert to at the end of the block.
    def __enter__(self):
        if not hasattr(self, '_rollback'):
            badcontext = 'the with-statement can only be used with fill() and stroke(), not arbitrary colors'
            raise DeviceError(badcontext)
        param = next(iter(self._rollback))
        statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
        if getattr(_ctx, statevar) is not self._installed:
            # reapply if the state has moved on
            self._rollback = {param:getattr(_ctx, statevar)}
            setattr(_ctx, statevar, self._installed)
        return self

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
            setattr(_ctx, statevar, val)

    @property
    def space(self):
        """The color space of the rgb, hsv & grey components"""
        return self._space

    @property
    def cgColor(self):
        # one per ink
        ink = _output().ink
        try:
            return self._to['cg', ink]
        except KeyError:
            profile = ink.profile
            if profile.key == P3:
                cg = self._rgb
            elif profile.key == CMYK:
                cg = CGColorCreate(DEVICE_CMYK, self._values(CMYK))
            elif isinstance(profile, Press):
                cg = CGColorCreate(profile.space if ink.tagged else DEVICE_CMYK, self._press_values(profile.key))
            else:
                cg = _matched(self._rgb, profile.space)
            self._to['cg', ink] = cg
            return cg

    def _press_values(self, press):
        # cmyk as given, rgb converted into the press
        key = 'press', press
        if key not in self._to:
            if self._mode is CMYK:
                self._to[key] = self._values(CMYK)
            else:
                r, g, b, alpha = _components(self._rgb_as(P3))
                self._to[key] = Profile.named[press].convert((r, g, b)) + (alpha,)
        return self._to[key]

    def _rgb_as(self, space):
        return self._rgb if self.space == space else _matched(self._rgb, SPACES[space])

    def _read_as(self, space):
        # the rgb a script reads
        press = _output().press
        if press is None or self._mode is not CMYK:
            return self._rgb_as(space)
        return _matched(CGColorCreate(press.space, self._values(CMYK)), SPACES[space])

    def _read(self, mode):
        # scripts see cmyk colors through the output press
        press = _output().press if mode is not CMYK else None
        return self._values(mode, press if self._mode is CMYK else None)

    def _values(self, mode, press=None):
        if mode is RGB:
            key = 'rgba' if press is None else ('rgba', press)
            try:
                return self._to[key]
            except KeyError:
                rgba = self._to[key] = _components(self._rgb if press is None else self._read_as(self.space))
                return rgba
        elif mode is HSV:
            # unclamped, out of gamut s & b exceed 1
            r, g, b, a = self._values(RGB, press)
            hsv = colorsys.rgb_to_hsv(r, g, b) if max(r, g, b) > 0 else (0.0, 0.0, max(r, g, b))
            return hsv + (a,)
        elif mode is CMYK:
            try:
                return self._to['cmyka']
            except KeyError:
                cmyka = self._to['cmyka'] = _components(self._cmyk)
                return cmyka

    def copy(self):
        new = self.__class__.__new__(self.__class__)
        new._share(self)
        return new

    def _share(self, other):
        # CGColors are immutable and safe to share
        self._space, self._src, self._mode, self._to = other._space, other._src, other._mode, other._to

    # setting a view drops the other conversions
    @property
    def _rgb(self):
        # converted on demand, once for every copy sharing it
        try:
            return self._to['rgb']
        except KeyError:
            rgb = self._to['rgb'] = _matched(self._src, SPACES[self._space])
            return rgb

    @_rgb.setter
    def _rgb(self, clr):
        self._to = {'rgb':clr}

    @property
    def _cmyk(self):
        # derived on demand from the defining view
        try:
            return self._to['cmyk']
        except KeyError:
            cmyk = self._to['cmyk'] = _matched(self._src, GENERIC_CMYK)
            return cmyk

    @_cmyk.setter
    def _cmyk(self, clr):
        self._to = {'cmyk':clr}

    def _updateCmyk(self):
        self._src, self._mode = self._rgb, RGB

    def _updateRgb(self):
        self._src, self._mode = self._cmyk, CMYK

    def _get_hue(self):
        return self._read(HSV)[0]
    def _set_hue(self, val):
        val = self._normalize(val)
        h, s, b, a = self._read(HSV)
        self._rgb, self._to['rgba'] = Color._cgcolor(HSV, self.space, val, s, b, a)
        self._updateCmyk()
    h = hue = property(_get_hue, _set_hue, doc="the hue of the color")

    def _get_saturation(self):
        return self._read(HSV)[1]
    def _set_saturation(self, val):
        val = self._normalize(val)
        h, s, b, a = self._read(HSV)
        self._rgb, self._to['rgba'] = Color._cgcolor(HSV, self.space, h, val, b, a)
        self._updateCmyk()
    s = saturation = property(_get_saturation, _set_saturation, doc="the saturation of the color")

    def _get_brightness(self):
        return self._read(HSV)[2]
    def _set_brightness(self, val):
        val = self._normalize(val)
        h, s, b, a = self._read(HSV)
        self._rgb, self._to['rgba'] = Color._cgcolor(HSV, self.space, h, s, val, a)
        self._updateCmyk()
    v = value = brightness = property(_get_brightness, _set_brightness, doc="the brightness of the color")

    def _get_hsba(self):
        return self._read(HSV)
    def _set_hsba(self, values):
        h, s, b, a = self._normalizeList(values)
        self._rgb, self._to['rgba'] = Color._cgcolor(HSV, self.space, h, s, b, a)
        self._updateCmyk()
    hsba = property(_get_hsba, _set_hsba, doc="the hue, saturation, brightness and alpha of the color")

    def _get_red(self):
        return self._read(RGB)[0]
    def _set_red(self, val):
        val = self._normalize(val)
        r, g, b, a = self._read(RGB)
        self._rgb, self._to['rgba'] = Color._cgcolor(RGB, self.space, val, g, b, a)
        self._updateCmyk()
    r = red = property(_get_red, _set_red, doc="the red component of the color")

    def _get_green(self):
        return self._read(RGB)[1]
    def _set_green(self, val):
        val = self._normalize(val)
        r, g, b, a = self._read(RGB)
        self._rgb, self._to['rgba'] = Color._cgcolor(RGB, self.space, r, val, b, a)
        self._updateCmyk()
    g = green = property(_get_green, _set_green, doc="the green component of the color")

    def _get_blue(self):
        return self._read(RGB)[2]
    def _set_blue(self, val):
        val = self._normalize(val)
        r, g, b, a = self._read(RGB)
        self._rgb, self._to['rgba'] = Color._cgcolor(RGB, self.space, r, g, val, a)
        self._updateCmyk()
    b = blue = property(_get_blue, _set_blue, doc="the blue component of the color")

    def _get_alpha(self):
        return self._read(RGB)[3]
    def _set_alpha(self, val):
        # keep a cmyk color's components
        val = _clamp(self._normalize(val))
        if self._mode is CMYK:
            self._cmyk = CGColorCreateCopyWithAlpha(self._src, val)
            self._updateRgb()
        else:
            self._rgb = CGColorCreateCopyWithAlpha(self._rgb, val)
            self._updateCmyk()
    a = alpha = property(_get_alpha, _set_alpha, doc="the alpha component of the color")

    def _get_rgba(self):
        return self._read(RGB)
    def _set_rgba(self, values):
        r, g, b, a = self._normalizeList(values)
        self._rgb, self._to['rgba'] = Color._cgcolor(RGB, self.space, r, g, b, a)
        self._updateCmyk()
    rgba = property(_get_rgba, _set_rgba, doc="the red, green, blue and alpha values of the color")

    def _get_cyan(self):
        return self._values(CMYK)[0]
    def _set_cyan(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk, self._to['cmyka'] = Color._cgcolor(CMYK, None, val, m, y, k, a)
        self._updateRgb()
    c = cyan = property(_get_cyan, _set_cyan, doc="the cyan component of the color")

    def _get_magenta(self):
        return self._values(CMYK)[1]
    def _set_magenta(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk, self._to['cmyka'] = Color._cgcolor(CMYK, None, c, val, y, k, a)
        self._updateRgb()
    m = magenta = property(_get_magenta, _set_magenta, doc="the magenta component of the color")

    def _get_yellow(self):
        return self._values(CMYK)[2]
    def _set_yellow(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk, self._to['cmyka'] = Color._cgcolor(CMYK, None, c, m, val, k, a)
        self._updateRgb()
    y = yellow = property(_get_yellow, _set_yellow, doc="the yellow component of the color")

    def _get_black(self):
        return self._values(CMYK)[3]
    def _set_black(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk, self._to['cmyka'] = Color._cgcolor(CMYK, None, c, m, y, val, a)
        self._updateRgb()
    k = black = property(_get_black, _set_black, doc="the black component of the color")

    def _get_cmyka(self):
        return self._values(CMYK)
    cmyka = property(_get_cmyka, doc="a tuple containing the CMYKA values for this color")

    # hex strings use the current color space
    def _get_hex(self):
        r, g, b, a = _components(self._read_as(_ctx._colorspace))
        return Color._hexstring(r, g, b)
    def _set_hex(self, val):
        r, g, b, a = Color._parse(val)
        self._rgb, self._to['rgba'] = Color._cgcolor(RGB, _ctx._colorspace, r, g, b, self.a)
        self._updateCmyk()
    hex = property(_get_hex, _set_hex, doc="the rgb hex string for the color (in the current color space)")

    def _get_hexa(self):
        return (self.hex, self.a)
    def _set_hexa(self, hexa):
        clr, alpha = hexa
        r, g, b, _ = Color._parse(clr)
        self._rgb, self._to['rgba'] = Color._cgcolor(RGB, _ctx._colorspace, r, g, b, self._normalize(alpha))
        self._updateCmyk()
    hexa = property(_get_hexa, _set_hexa, doc="a tuple containing the color's rgb hex string and an alpha float")

    def blend(self, otherColor, factor):
        """Blend the color with otherColor with a factor; return the new color. Factor
        is a float between 0.0 and 1.0. Two cmyk colors blend in cmyk (K100 and K0 make K50)
        and give a cmyk color; otherwise the blend is made component by component in the
        current color space (whatever spaces the two colors are in) and returned in it.
        """
        other = Color(otherColor)
        if self._mode is CMYK and other._mode is CMYK:
            mixed = [v + (w - v) * factor for v, w in zip(self._values(CMYK), other._values(CMYK))]
            return self.__class__(mixed, mode=CMYK, range=1)
        space = _ctx._colorspace
        ours = _components(self._read_as(space))
        theirs = _components(other._read_as(space))
        mixed = [v + (w - v) * factor for v, w in zip(ours, theirs)]
        return self.__class__(mixed, mode=RGB, space=space, range=1)

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
    def validate(cls, kwargs):
        """Reject keywords other than mode, range & space"""
        unknown = [arg for arg in kwargs if arg not in ('mode', 'range', 'space')]
        if unknown:
            badarg = "Unknown Color argument%s '%s'" % ('' if len(unknown)==1 else 's', "', '".join(unknown))
            raise DeviceError(badarg)

    @classmethod
    def recognized(cls, blob):
        if isinstance(blob, Color):
            return True

        def valid_str(s):
            s = s.strip() if isinstance(s, str) else ''
            return s in CSS_COLORS or re.match(r'#?[A-Fa-f0-9]{3,8}$', s)

        if isinstance(blob, (tuple, list)):
            demoded = [b for b in blob if b not in (RGB,HSV,CMYK,GREY)]
            if all(numlike(n) and len(demoded)<=5 for n in blob):
                return True

            if demoded and valid_str(demoded[0]):
                if len(demoded) < 2:
                    return True
                if len(demoded)==2 and numlike(demoded[1]):
                    return True
        elif isinstance(blob, str):
            return valid_str(blob)

    @classmethod
    def _cgcolor(cls, scheme, space, *components):
        # cmyk is clamped, rgb leaves all but alpha
        if scheme == CMYK:
            values = tuple(_clamp(float(v)) for v in components)
            return CGColorCreate(GENERIC_CMYK, values), values
        *values, alpha = components
        if scheme == HSV:
            h, s, v = values
            values = colorsys.hsv_to_rgb(h % 1.0, s, v)
        elif scheme == GREY:
            values = values * 3
        values = (*map(float, values), _clamp(float(alpha)))
        return CGColorCreate(SPACES[space], values), values

    @classmethod
    def _parse(cls, clrstr):
        """Returns an r/g/b/a tuple based on a css color name or a hex string of the form:
        RRGGBBAA, RRGGBB, RGBA, or RGB (with or without a leading #)
        """
        if clrstr in CSS_COLORS: # handle css color names
            clrstr = CSS_COLORS[clrstr]

        if re.search(r'#?[0-9a-fA-F]{3,8}', clrstr): # rgb & rgba hex strings
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

    @classmethod
    def _hexstring(cls, r, g, b):
        # #rrggbb or #rgb, clipped to 0-1
        s = "".join('%02x'%round(255*_clamp(c)) for c in (r,g,b))
        if all([len(set(pair))==1 for pair in zip(s[::2], s[1::2])]):
            s = "".join(s[::2])
        return "#"+s

class Pattern(object):
    def __init__(self, img, *coords, x=None, y=None, width=None, height=None):
        placement = {k: v for k, v in dict(x=x, y=y, width=width, height=height).items() if v is not None}
        placed = coords or placement
        if isinstance(img, Pattern) and not placed:
            self._image = img._image
        else:
            from .image import Image, Snapshot
            src = img._image if isinstance(img, Pattern) else img
            if isinstance(src, Image) and not placed:
                self._image = src.copy() # tiled from where it would draw
            elif isinstance(src, Snapshot) or hasattr(src, 'commit'):
                self._image = Snapshot(src, *coords, **placement) # a canvas tiles its vectors
            else:
                self._image = Image(src, *coords, **placement) # placed as image(src, ...) would be

    @property
    def cgColor(self):
        # cache 'tiles' (based on the pattern's matrix & ink) on the source Image itself
        frame = _frame.get()
        matrix = CGAffineTransformConcat(self._image._screen_matrix, _base_ctm.get())
        key = tuple(matrix), _output().ink, frame and frame.output
        tiles = self._image._tiles
        try:
            return tiles[key]
        except KeyError:
            pass

        # the tile draws the canvas's grobs/image's vector rep (avoiding the NSImage which would rasterize it)
        from .image import PDSVGImageRep, Snapshot
        snapshot = self._image._canvas if isinstance(self._image, Snapshot) else None
        if snapshot is not None:
            size, vectors, rep = snapshot.pagesize, [], None
        else:
            size = self._image._nsImage.size()
            cmyk = frame.output.cmyk_space if frame is not None else None
            reps = self._image._nsImage_as(cmyk).representations()
            vectors = [r for r in reps if isinstance(r, (NSPDFImageRep, PDSVGImageRep))]
            rep = vectors[0] if vectors else max(reps, key=lambda r: r.pixelsWide() * r.pixelsHigh(), default=None)
        filling = frame is not None and snapshot is not None
        if filling and frame.output != snapshot.output:
            from ..context import Frame
            snapshot = Frame(snapshot, frame.output) # in the colors of the frame it fills
        scale = abs(matrix.a * matrix.d - matrix.b * matrix.c) ** .5
        flip = (scale, 0, 0, -scale, 0, size.height * scale) # a y-up tile at the render's scale, for shadows in PDFs

        def cell(info, port):
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithCGContext_flipped_(port, True))
            try:
                if snapshot is not None:
                    CGContextConcatCTM(port, flip)
                    snapshot.draw() # re-enters the render lock
                elif vectors:
                    if isinstance(rep, NSPDFImageRep):
                        CGContextTranslateCTM(port, 0, size.height) # pdf pages draw y-up (svgs flip themselves)
                        CGContextScaleCTM(port, 1, -1)
                    rep.drawInRect_(((0,0), size)) # respectFlipped would rasterize it
                else:
                    NSGraphicsContext.currentContext().setImageInterpolation_(NSImageInterpolationHigh)
                    rep.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(((0,0), size), NSZeroRect,
                                                                                    NSCompositeSourceOver, 1.0, True, None)
            finally:
                NSGraphicsContext.restoreGraphicsState()

        bounds = ((0,0), size)
        if snapshot is not None:
            matrix = CGAffineTransformConcat(CGAffineTransformInvert(flip), matrix)
            bounds = ((0,0), (size.width * scale, size.height * scale))
        (_, _), (w, h) = bounds
        tile = CGPatternCreate(None, bounds, matrix, w, h, kCGPatternTilingConstantSpacing, True, cell)
        if len(tiles) >= 32:
            del tiles[next(iter(tiles))] # drop the oldest (zooms & animations make a new matrix every frame)
        tiles[key] = CGColorCreateWithPattern(CGColorSpaceCreatePattern(None), tile, [1.0])
        return tiles[key]

    # fill() and stroke() both cache the previous canvas state by creating a _rollback attr.
    # act as a context manager if there's a fill/stroke state to revert to at the end of the block.
    def __enter__(self):
        if not hasattr(self, '_rollback'):
            badcontext = 'the with-statement can only be used with fill() and stroke(), not arbitrary colors'
            raise DeviceError(badcontext)
        param = next(iter(self._rollback))
        statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
        if getattr(_ctx, statevar) is not self._installed:
            # reapply if the state has moved on
            self._rollback = {param:getattr(_ctx, statevar)}
            setattr(_ctx, statevar, self._installed)
        return self

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
            setattr(_ctx, statevar, val)

    def copy(self):
        return Pattern(self)


class Gradient(object):
    kwargs = ('steps', 'angle', 'center')

    def __init__(self, *colors, **kwargs):
        if colors and isinstance(colors[0], Gradient):
            _copy_attrs(colors[0], self, ('_gradient', '_ink', '_space', '_steps', '_colors', '_center', '_angle'))
            return

        # parse colors and their stops
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
        self._ink = None
        self._gradient = None

        # interpolate in the space current at creation
        self._space = _ctx._colorspace

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
        param = next(iter(self._rollback))
        statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
        if getattr(_ctx, statevar) is not self._installed:
            # reapply if the state has moved on
            self._rollback = {param:getattr(_ctx, statevar)}
            setattr(_ctx, statevar, self._installed)
        return self

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
            setattr(_ctx, statevar, val)

    def __repr__(self):
        return 'Gradient(%s, steps=%r)'%(", ".join('%r'%c for c in self._colors), self._steps)

    @property
    def pdGradient(self):
        ink = _output().ink
        if not self._gradient or self._ink != ink:
            # rgb in the gradient's space, else the output's
            profile = ink.profile
            if profile.key == P3:
                c_space = SPACES[self._space]
                clrs = [c._rgb_as(self._space) for c in self._colors]
            else:
                if profile.mode == CMYK and not ink.tagged:
                    c_space = DEVICE_CMYK
                else:
                    c_space = profile.space
                clrs = [c.cgColor for c in self._colors]
            pd_gradient = PDGradient.alloc().initWithColors_atLocations_colorSpace_(clrs, self._steps, c_space)
            self._gradient, self._ink = pd_gradient, ink
        return self._gradient

    @property
    def brightness(self):
        return max(clr.brightness for clr in self._colors)

    def copy(self):
        return self.__class__(self)

    def fill(self, obj):
        if isinstance(obj, tuple):
            if self._angle is not None:
                self.pdGradient.drawInRect_angle_(obj, self._angle)
            else:
                self.pdGradient.drawInRect_relativeCenterPosition_(obj, self._center)
        elif obj.__class__.__name__ == 'Bezier':
            if self._angle is not None:
                self.pdGradient.drawInPath_angle_(obj.cgPath, self._angle)
            else:
                self.pdGradient.drawInPath_relativeCenterPosition_(obj.cgPath, self._center)
