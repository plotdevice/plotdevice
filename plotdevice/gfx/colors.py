# encoding: utf-8
import os
import re
import json
import zlib
import colorsys
import warnings
import objc
from array import array
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import _copy_attr, _copy_attrs, _flatten, trim_zeroes, rsrc_path, numlike
from . import _inkmode, _outputpress, _frame, _base_ctm, _cg_port

PDGradient = objc.lookUpClass('PDGradient')

_ctx = None
__all__ = ("RGB", "HSV", "HSB", "CMYK", "GREY", "P3", "SRGB", "REC709", "REC2020",
           "GRACOL", "GRACOL_UNCOATED", "SWOP", "FOGRA39", "FOGRA47",
           "Color", "Pattern", "Gradient",)

# color/output modes
RGB = "rgb"
HSV = HSB = "hsv"
CMYK = "cmyk"
GREY = "greyscale"

# spaces for rgb, hsv, & grey components
P3 = "p3"
SRGB = "srgb"
REC709 = "rec709"
REC2020 = "rec2020"

# bundled presses and their zlib'd profiles
GRACOL = "gracol"
GRACOL_UNCOATED = "gracol_uncoated"
SWOP = "swop"
FOGRA39 = "fogra39"
FOGRA47 = "fogra47"
_PRESSES = {GRACOL: 'GRACoL2013_CRPC6.icc', GRACOL_UNCOATED: 'GRACoL2013UNC_CRPC3.icc', SWOP: 'SWOP2013C3_CRPC5.icc',
            FOGRA39: 'ISOcoated_v2_bas.icc', FOGRA47: 'PSO_Uncoated_ISO12647_bas.icc'}

# PDF/X output conditions from color.org's registry
_PRESS_CONDITIONS = {GRACOL: ('CGATS21-2-CRPC6', 'Universal Premium Coated (GRACoL 2013, CGATS21-2 CRPC6)'),
                     GRACOL_UNCOATED: ('CGATS21-2-CRPC3', 'Universal Premium Uncoated (GRACoL 2013, CGATS21-2 CRPC3)'),
                     SWOP: ('CGATS21-2-CRPC5', 'Universal Publication Coated (SWOP 2013, CGATS21-2 CRPC5)'),
                     FOGRA39: ('FOGRA39', 'Offset, gloss or matt coated paper (ISO 12647-2:2004, FOGRA39)'),
                     FOGRA47: ('FOGRA47', 'Offset, uncoated white paper (ISO 12647-2:2004, FOGRA47)')}

# profile folders, in match order
_PROFILE_FOLDERS = ['~/Library/ColorSync/Profiles', '/Library/ColorSync/Profiles', '/Library/ColorSync/Profiles/Profiles',
                    '/Library/ColorSync/Profiles/Recommended', '/Library/Application Support/Adobe/Color/Profiles',
                    '/Library/Application Support/Adobe/Color/Profiles/Recommended']

# system profiles, searched last, and the video spaces
_SYSTEM_PROFILES = '/System/Library/ColorSync/Profiles'
_REC709 = os.path.join(_SYSTEM_PROFILES, 'ITU-709.icc')
_REC2020 = os.path.join(_SYSTEM_PROFILES, 'ITU-2020.icc')
_PROFILE_LISTS = {} # folder mtimes -> (presses, names)

# extended spaces keep out-of-gamut components
_SPACES = {P3: CGColorSpaceCreateWithName(kCGColorSpaceExtendedDisplayP3),
           SRGB: CGColorSpaceCreateWithName(kCGColorSpaceExtendedSRGB)}
_SPACE_NAMES = {kCGColorSpaceExtendedDisplayP3:P3, kCGColorSpaceDisplayP3:P3,
                kCGColorSpaceExtendedSRGB:SRGB, kCGColorSpaceSRGB:SRGB}
_GENERIC_CMYK = CGColorSpaceCreateWithName(kCGColorSpaceGenericCMYK)
_DEVICE_CMYK = CGColorSpaceCreateDeviceCMYK()

# rgb output spaces other than p3, by colors= key
_INKS = {SRGB: CGColorSpaceCreateWithName(kCGColorSpaceSRGB)}

# the colors= each format takes, and its default
_FORMAT_COLORS = dict(png=('rgb',), heic=('rgb',), mov=(P3, SRGB, _REC709, _REC2020), gif=(SRGB,), eps=(SRGB, CMYK),
                      pdf=('rgb', CMYK), tiff=('rgb', CMYK), jpg=('rgb', CMYK))
_FORMAT_DEFAULTS = dict(gif=SRGB, eps=SRGB)

# lowercased names for mode= and space=
_NAMES = dict(mode={RGB:RGB, HSV:HSV, 'hsb':HSV, CMYK:CMYK, GREY:GREY},
              space={P3:P3, SRGB:SRGB})

_CSS_COLORS = json.load(open(rsrc_path('colors.json')))

def _named(kind, val):
    """The color mode or space a string names, in any case"""
    if val is None:
        return None
    names = _NAMES[kind]
    key = val.lower() if isinstance(val, str) else val
    if key not in names:
        unknown = 'Unknown color %s %r (should be one of: %s)' % (kind, val, ', '.join(sorted(set(names.values()))))
        raise DeviceError(unknown)
    return names[key]

def _output_colors(val, format):
    """The colors an export in `format` is written in for colors=`val`"""
    format = 'jpg' if format == 'jpeg' else format
    if val is None:
        return _FORMAT_DEFAULTS.get(format, P3)
    if not isinstance(val, str):
        notpalette = "colors=%r isn't a built-in color space or ICC profile filename" % (val,)
        if numlike(val):
            notpalette += " (it isn't a gif's palette size)"
        raise DeviceError(notpalette)
    key = val.lower().replace('-', '_')
    if key in (P3, SRGB, CMYK):
        kind = key
    elif key in _PRESSES:
        kind = 'press'
        if key not in Press.named:
            Press.named[key] = Press(key)
    else:
        # a path, else an installed profile's name
        path = {REC709: _REC709, REC2020: _REC2020}.get(key, val) # rec709 & rec2020 point to the system's .icc profiles
        key = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(key):
            key = _installed_profiles()[1].get(val.lower(), key)
        try:
            icc = open(key, 'rb').read()
        except OSError:
            searched = ', '.join(_PROFILE_FOLDERS + [_SYSTEM_PROFILES])
            unknown = "%r isn't a built-in color space or ICC profile filename (searched in: %s)" % (val, searched)
            raise DeviceError(unknown)
        model = icc[16:20] if icc[36:40] == b'acsp' else None
        space = CGColorSpaceCreateWithICCData(icc) if model in (b'RGB ', b'CMYK') else None
        if space is None:
            notrgb = "%r isn't an RGB or CMYK ICC profile" % val
            raise DeviceError(notrgb)
        generic = os.path.join(_SYSTEM_PROFILES, 'Generic CMYK Profile.icc')
        if model == b'CMYK' and os.path.exists(generic) and icc == open(generic, 'rb').read():
            # generic cmyk means unlabeled CMYK
            key = kind = CMYK
        elif model == b'CMYK':
            Press.named.setdefault(key, Press(key, space))
            kind = 'press'
        else:
            _INKS.setdefault(key, space)
            kind = 'rgb'
    allowed = _FORMAT_COLORS[format]
    listed = kind in allowed or key in allowed
    rgb_fits = kind in (P3, SRGB) and 'rgb' in allowed
    press_fits = kind == 'press' and CMYK in allowed
    if not (listed or rgb_fits or press_fits):
        names = {'rgb': 'an RGB ICC profile', _REC709: 'REC709', _REC2020: 'REC2020'}
        options = ', '.join(names.get(opt, opt.upper()) for opt in allowed)
        if 'rgb' in allowed:
            options = 'P3, SRGB, ' + options
        if CMYK in allowed:
            options += ', GRACOL, GRACOL_UNCOATED, SWOP, FOGRA39, FOGRA47, a CMYK ICC profile'
        cantfit = "%s %s file can't be exported with colors=%r (it takes %s)" % ('An' if format == 'eps' else 'A', format.upper(), val, options)
        raise DeviceError(cantfit)
    return key

def _output_mode(colors):
    """The output mode an export's colors are drawn in"""
    return CMYK if colors == CMYK or colors in Press.named else RGB

def _output_space(colors):
    """The CGColorSpace an export's file is written in, or None for CMYK"""
    if colors == CMYK:
        return None
    if colors in Press.named:
        return Press.named[colors].space
    return CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3) if colors == P3 else _INKS[colors]

def _icc_text(icc, sig):
    count = int.from_bytes(icc[128:132], 'big')
    for at in range(132, 132 + 12 * count, 12):
        if icc[at:at + 4] == sig:
            offset, size = int.from_bytes(icc[at + 4:at + 8], 'big'), int.from_bytes(icc[at + 8:at + 12], 'big')
            tag = icc[offset:offset + size]
            if tag[:4] == b'mluc':
                length, start = int.from_bytes(tag[20:24], 'big'), int.from_bytes(tag[24:28], 'big')
                return tag[start:start + length].decode('utf-16-be')
            if tag[:4] == b'desc':
                return tag[12:12 + int.from_bytes(tag[8:12], 'big')].split(b'\0')[0].decode('latin-1')
            if tag[:4] == b'text':
                return tag[8:].split(b'\0')[0].decode('latin-1')
    return None

def _profile_header(path):
    # a profile's class, data space & description, or None
    try:
        with open(path, 'rb') as f:
            head = f.read(132)
            # skip truncated files
            if len(head) < 132 or head[36:40] != b'acsp' or int.from_bytes(head[0:4], 'big') > os.path.getsize(path):
                return None
            count = min(int.from_bytes(head[128:132], 'big'), 256)
            table = f.read(12 * count)
            icc = bytearray(head + table)
            for at in range(0, len(table), 12):
                if table[at:at + 4] == b'desc':
                    offset, size = int.from_bytes(table[at + 4:at + 8], 'big'), int.from_bytes(table[at + 8:at + 12], 'big')
                    f.seek(offset)
                    icc = bytes(icc) + b'\0' * (offset - len(icc)) + f.read(min(size, 4096))
            desc = _icc_text(bytes(icc), b'desc') or os.path.splitext(os.path.basename(path))[0]
            return (head[12:16], head[16:20], desc.strip())
    except OSError:
        return None

def _installed_profiles():
    # installed presses, and profiles by lowercased name
    folders = [os.path.expanduser(folder) for folder in _PROFILE_FOLDERS]
    sources = tuple(os.path.getmtime(path) if os.path.exists(path) else None for path in folders)
    lists = _PROFILE_LISTS.get(sources)
    if lists is None:
        found, names = {}, {}
        for folder in folders + [_SYSTEM_PROFILES]:
            for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                stem, ext = os.path.splitext(name)
                if ext.lower() not in ('.icc', '.icm'):
                    continue
                path = os.path.join(folder, name)
                real = os.path.realpath(path) # Adobe links into ColorSync's
                if os.path.isfile(real):
                    names.setdefault(name.lower(), real)
                    names.setdefault(stem.lower(), real)
                header = _profile_header(path) if folder != _SYSTEM_PROFILES else None
                if header and header[:2] == (b'prtr', b'CMYK'):
                    found.setdefault(header[2], path)
        lists = (sorted(found.items(), key=lambda item: item[0].lower()), names)
        _PROFILE_LISTS.clear()
        _PROFILE_LISTS[sources] = lists
    return lists

def _installed_presses():
    """The installed CMYK output profiles, as (description, path) pairs"""
    return _installed_profiles()[0]

class Press(object):
    named = {} # key -> Press, as colors= names it

    def __init__(self, key, space=None):
        self.key = key
        self._icc = self._intent = self._transform = None
        self.space = space if space is not None else CGColorSpaceCreateWithICCData(self.icc)

    @property
    def icc(self):
        """The press's ICC profile bytes"""
        if self._icc is None:
            if self.key in _PRESSES:
                self._icc = zlib.decompress(open(rsrc_path('press/%s.zlib' % _PRESSES[self.key]), 'rb').read())
            else:
                self._icc = open(self.key, 'rb').read()
        return self._icc

    @property
    def intent(self):
        """The press's PDF/X output intent"""
        if self._intent is None:
            if self.key in _PRESS_CONDITIONS:
                identifier, condition = _PRESS_CONDITIONS[self.key]
                registry = 'http://www.color.org'
                profile = open(rsrc_path('press/%s.zlib' % _PRESSES[self.key]), 'rb').read()
            else:
                # the condition its targ tag names, else Custom
                targ = (_icc_text(self.icc, b'targ') or '').strip()
                named = targ and '\n' not in targ and len(targ) < 64 # not the data itself
                identifier, registry = (targ, 'http://www.color.org') if named else ('Custom', '')
                condition = _icc_text(self.icc, b'desc') or os.path.basename(self.key)
                profile = zlib.compress(self.icc, 1)
            self._intent = dict(identifier=identifier, condition=condition, registry=registry, profile=profile)
        return self._intent

    def convert(self, rgb):
        """The inks this press prints for P3 `rgb` components"""
        if self._transform is None:
            # colorsync's transform from p3 into the press
            profile, _ = ColorSyncProfileCreate(self.icc, None) # (profile, error)
            steps = [{kColorSyncProfile: ColorSyncProfileCreateWithName(kColorSyncDisplayP3Profile),
                      kColorSyncRenderingIntent: kColorSyncRenderingIntentRelative,
                      kColorSyncTransformTag: kColorSyncTransformDeviceToPCS},
                     {kColorSyncProfile: profile, kColorSyncRenderingIntent: kColorSyncRenderingIntentRelative,
                      kColorSyncTransformTag: kColorSyncTransformPCSToDevice, kColorSyncBlackPointCompensation: True}]
            self._transform = ColorSyncTransformCreate(steps, {kColorSyncBlackPointCompensation: True})

        # clipped p3 in 16-bit ints. ColorSync's float
        # path tints white with black point compensation.
        rgb = array('H', (round(min(max(v, 0.0), 1.0) * 65535) for v in rgb))
        _, cmyk = ColorSyncTransformConvert(self._transform, 1, 1, array('H', [0] * 4), kColorSync16BitInteger,
                                            kColorSyncAlphaNone, 8, rgb, kColorSync16BitInteger, kColorSyncAlphaNone, 6, None)
        return tuple(0.0 if v < .001 else 1.0 if v > .999 else v for v in (c / 65535 for c in cmyk))

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
            mode = _named('mode', kwargs.get('mode'))

        if mode is None:
            # if no mode was specified, interpret the components in the context's current mode
            mode = _ctx._colormode

        # components are in space=, else the current one
        converting = kwargs.get('space') is not None
        space = _named('space', kwargs.get('space')) or _ctx._colorspace

        # use the specified range for int values, or leave it as None to use the default 0-1 scale
        rng = kwargs.get('range')

        params = len(args)
        cmyk, values = False, None # known components, or None
        if params == 1 and args[0] is None:                 # None -> transparent
            clr, values = Color._cgcolor(GREY, space, 0, 0)
        elif params == 1 and isinstance(args[0], Color):    # Color object
            self._share(args[0])
            if converting and self.space != space:
                if self._from_cmyk:
                    self._cmyk = self._src
                    self._cache['space'], self._rgb_ = space, None # converted on demand
                else:
                    self._rgb = _matched(self._rgb, _SPACES[space])
                    self._cache['space'] = space
                    self._updateCmyk()
            return
        elif params == 1 and isinstance(args[0], Gradient): # Gradient (use first shade)
            self._share(args[0]._colors[0])
            return
        elif params == 1 and isinstance(args[0], (NSColor, CGColorRef)): # NSColor or CGColor object
            clr = args[0].CGColor() if isinstance(args[0], NSColor) else args[0]
            own = _SPACE_NAMES.get(CGColorSpaceCopyName(CGColorGetColorSpace(clr)))
            if own is not None:
                # keep p3 or srgb components unless converting
                clr = CGColorCreate(_SPACES[own], _components(clr))
                if converting and own != space:
                    clr = _matched(clr, _SPACES[space])
                else:
                    space = own
            elif CGColorSpaceGetModel(CGColorGetColorSpace(clr)) == kCGColorSpaceModelCMYK:
                clr, cmyk = CGColorCreate(_GENERIC_CMYK, _components(clr)), True
            else:
                clr = _matched(clr, _SPACES[space])
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

        # values derived from the views, and the space
        self._cache = {'space':space}
        if cmyk:
            # keep the cmyk, convert to rgb on demand
            self._rgb_, self._src = None, clr
            self._cmyk = clr
            if values is not None:
                self._cache['cmyka'] = values
        else:
            self._rgb = clr
            self._src, self._cmyk_ = clr, None # converted on demand
            if values is not None:
                self._cache['rgba'] = values

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
        return self._cache['space']

    @property
    def cgColor(self):
        # one per output mode
        mode = _inkmode()
        try:
            return self._cache['cg', mode]
        except KeyError:
            if mode == RGB:
                cg = self._rgb
            elif mode == CMYK:
                cg = CGColorCreate(_DEVICE_CMYK, self._values(CMYK))
            elif isinstance(mode, tuple):
                press, in_space = mode
                cg = CGColorCreate(Press.named[press].space if in_space else _DEVICE_CMYK, self._press_values(press))
            else:
                cg = _matched(self._rgb, _INKS[mode])
            self._cache['cg', mode] = cg
            return cg

    def _press_values(self, press):
        # cmyk as given, rgb converted into the press
        key = 'press', press
        if key not in self._cache:
            if self._from_cmyk:
                self._cache[key] = self._values(CMYK)
            else:
                r, g, b, alpha = _components(self._rgb_as(P3))
                self._cache[key] = Press.named[press].convert((r, g, b)) + (alpha,)
        return self._cache[key]

    def _rgb_as(self, space):
        return self._rgb if self.space == space else _matched(self._rgb, _SPACES[space])

    def _read_as(self, space):
        # the rgb a script reads
        press = _outputpress()
        if press is None or not self._from_cmyk: # cheaper test first
            return self._rgb_as(space)
        return _matched(CGColorCreate(Press.named[press].space, self._values(CMYK)), _SPACES[space])

    def _read(self, mode):
        # scripts see cmyk colors through the output press
        press = _outputpress() if mode is not CMYK else None
        return self._values(mode, press if press and self._from_cmyk else None) # cheaper test first

    def _values(self, mode, press=None):
        if mode is RGB:
            key = 'rgba' if press is None else ('rgba', press)
            try:
                return self._cache[key]
            except KeyError:
                rgba = self._cache[key] = _components(self._rgb if press is None else self._read_as(self.space))
                return rgba
        elif mode is HSV:
            # unclamped, out of gamut s & b exceed 1
            r, g, b, a = self._values(RGB, press)
            hsv = colorsys.rgb_to_hsv(r, g, b) if max(r, g, b) > 0 else (0.0, 0.0, max(r, g, b))
            return hsv + (a,)
        elif mode is CMYK:
            try:
                return self._cache['cmyka']
            except KeyError:
                cmyka = self._cache['cmyka'] = _components(self._cmyk)
                return cmyka

    def copy(self):
        new = self.__class__.__new__(self.__class__)
        new._share(self)
        return new

    def _share(self, other):
        # CGColors are immutable and safe to share
        self._rgb_ = other._rgb_
        self._cmyk_ = other._cmyk_
        self._src = other._src
        self._cache = other._cache

    # setting a view starts a fresh cache
    @property
    def _rgb(self):
        # converted on demand, once per shared cache
        if self._rgb_ is None:
            cache = self._cache
            if 'rgb' not in cache:
                cache['rgb'] = _matched(self._src, _SPACES[cache['space']])
            self._rgb_ = cache['rgb']
        return self._rgb_

    @_rgb.setter
    def _rgb(self, clr):
        self._rgb_, self._cache = clr, {'space':self._cache['space']}

    @property
    def _cmyk(self):
        # derived on demand from the defining view
        if self._cmyk_ is None:
            cache = self._cache
            if 'cmyk' not in cache:
                cache['cmyk'] = _matched(self._src, _GENERIC_CMYK)
            self._cmyk_ = cache['cmyk']
        return self._cmyk_

    @_cmyk.setter
    def _cmyk(self, clr):
        self._cmyk_, self._cache = clr, {'space':self._cache['space']}

    @property
    def _from_cmyk(self):
        # defined in cmyk?
        try:
            return self._cache['from_cmyk']
        except KeyError:
            from_cmyk = self._cache['from_cmyk'] = CGColorSpaceGetModel(CGColorGetColorSpace(self._src)) == kCGColorSpaceModelCMYK
            return from_cmyk

    def _updateCmyk(self):
        self._src, self._cmyk_ = self._rgb, None

    def _updateRgb(self):
        self._src, self._rgb_ = self._cmyk, None

    def _get_hue(self):
        return self._read(HSV)[0]
    def _set_hue(self, val):
        val = self._normalize(val)
        h, s, b, a = self._read(HSV)
        self._rgb, self._cache['rgba'] = Color._cgcolor(HSV, self.space, val, s, b, a)
        self._updateCmyk()
    h = hue = property(_get_hue, _set_hue, doc="the hue of the color")

    def _get_saturation(self):
        return self._read(HSV)[1]
    def _set_saturation(self, val):
        val = self._normalize(val)
        h, s, b, a = self._read(HSV)
        self._rgb, self._cache['rgba'] = Color._cgcolor(HSV, self.space, h, val, b, a)
        self._updateCmyk()
    s = saturation = property(_get_saturation, _set_saturation, doc="the saturation of the color")

    def _get_brightness(self):
        return self._read(HSV)[2]
    def _set_brightness(self, val):
        val = self._normalize(val)
        h, s, b, a = self._read(HSV)
        self._rgb, self._cache['rgba'] = Color._cgcolor(HSV, self.space, h, s, val, a)
        self._updateCmyk()
    v = value = brightness = property(_get_brightness, _set_brightness, doc="the brightness of the color")

    def _get_hsba(self):
        return self._read(HSV)
    def _set_hsba(self, values):
        h, s, b, a = self._normalizeList(values)
        self._rgb, self._cache['rgba'] = Color._cgcolor(HSV, self.space, h, s, b, a)
        self._updateCmyk()
    hsba = property(_get_hsba, _set_hsba, doc="the hue, saturation, brightness and alpha of the color")

    def _get_red(self):
        return self._read(RGB)[0]
    def _set_red(self, val):
        val = self._normalize(val)
        r, g, b, a = self._read(RGB)
        self._rgb, self._cache['rgba'] = Color._cgcolor(RGB, self.space, val, g, b, a)
        self._updateCmyk()
    r = red = property(_get_red, _set_red, doc="the red component of the color")

    def _get_green(self):
        return self._read(RGB)[1]
    def _set_green(self, val):
        val = self._normalize(val)
        r, g, b, a = self._read(RGB)
        self._rgb, self._cache['rgba'] = Color._cgcolor(RGB, self.space, r, val, b, a)
        self._updateCmyk()
    g = green = property(_get_green, _set_green, doc="the green component of the color")

    def _get_blue(self):
        return self._read(RGB)[2]
    def _set_blue(self, val):
        val = self._normalize(val)
        r, g, b, a = self._read(RGB)
        self._rgb, self._cache['rgba'] = Color._cgcolor(RGB, self.space, r, g, val, a)
        self._updateCmyk()
    b = blue = property(_get_blue, _set_blue, doc="the blue component of the color")

    def _get_alpha(self):
        return self._read(RGB)[3]
    def _set_alpha(self, val):
        # keep a cmyk color's components
        val = _clamp(self._normalize(val))
        if self._from_cmyk:
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
        self._rgb, self._cache['rgba'] = Color._cgcolor(RGB, self.space, r, g, b, a)
        self._updateCmyk()
    rgba = property(_get_rgba, _set_rgba, doc="the red, green, blue and alpha values of the color")

    def _get_cyan(self):
        return self._values(CMYK)[0]
    def _set_cyan(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk, self._cache['cmyka'] = Color._cgcolor(CMYK, None, val, m, y, k, a)
        self._updateRgb()
    c = cyan = property(_get_cyan, _set_cyan, doc="the cyan component of the color")

    def _get_magenta(self):
        return self._values(CMYK)[1]
    def _set_magenta(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk, self._cache['cmyka'] = Color._cgcolor(CMYK, None, c, val, y, k, a)
        self._updateRgb()
    m = magenta = property(_get_magenta, _set_magenta, doc="the magenta component of the color")

    def _get_yellow(self):
        return self._values(CMYK)[2]
    def _set_yellow(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk, self._cache['cmyka'] = Color._cgcolor(CMYK, None, c, m, val, k, a)
        self._updateRgb()
    y = yellow = property(_get_yellow, _set_yellow, doc="the yellow component of the color")

    def _get_black(self):
        return self._values(CMYK)[3]
    def _set_black(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk, self._cache['cmyka'] = Color._cgcolor(CMYK, None, c, m, y, val, a)
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
        self._rgb, self._cache['rgba'] = Color._cgcolor(RGB, _ctx._colorspace, r, g, b, self.a)
        self._updateCmyk()
    hex = property(_get_hex, _set_hex, doc="the rgb hex string for the color (in the current color space)")

    def _get_hexa(self):
        return (self.hex, self.a)
    def _set_hexa(self, hexa):
        clr, alpha = hexa
        r, g, b, _ = Color._parse(clr)
        self._rgb, self._cache['rgba'] = Color._cgcolor(RGB, _ctx._colorspace, r, g, b, self._normalize(alpha))
        self._updateCmyk()
    hexa = property(_get_hexa, _set_hexa, doc="a tuple containing the color's rgb hex string and an alpha float")

    def blend(self, otherColor, factor):
        """Blend the color with otherColor with a factor; return the new color. Factor
        is a float between 0.0 and 1.0. Two cmyk colors blend in cmyk (K100 and K0 make K50)
        and give a cmyk color; otherwise the blend is made component by component in the
        current color space (whatever spaces the two colors are in) and returned in it.
        """
        other = Color(otherColor)
        if self._from_cmyk and other._from_cmyk:
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
            return s in _CSS_COLORS or re.match(r'#?[A-Fa-f0-9]{3,8}$', s)

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
            return CGColorCreate(_GENERIC_CMYK, values), values
        *values, alpha = components
        if scheme == HSV:
            h, s, v = values
            values = colorsys.hsv_to_rgb(h % 1.0, s, v)
        elif scheme == GREY:
            values = values * 3
        values = (*map(float, values), _clamp(float(alpha)))
        return CGColorCreate(_SPACES[space], values), values

    @classmethod
    def _parse(cls, clrstr):
        """Returns an r/g/b/a tuple based on a css color name or a hex string of the form:
        RRGGBBAA, RRGGBB, RGBA, or RGB (with or without a leading #)
        """
        if clrstr in _CSS_COLORS: # handle css color names
            clrstr = _CSS_COLORS[clrstr]

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
        key = tuple(matrix), _inkmode(), frame and frame.colors
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
            cmyk = frame._cmyk_space if frame is not None else None
            reps = self._image._nsImage_as(cmyk).representations()
            vectors = [r for r in reps if isinstance(r, (NSPDFImageRep, PDSVGImageRep))]
            rep = vectors[0] if vectors else max(reps, key=lambda r: r.pixelsWide() * r.pixelsHigh(), default=None)
        filling = frame is not None and snapshot is not None
        if filling and (frame.colors, frame.format) != (snapshot.colors, snapshot.format):
            from ..context import Frame
            snapshot = Frame(snapshot, frame.colors, frame.format) # in the colors of the frame it fills
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
            _copy_attrs(colors[0], self, ('_gradient', '_outputmode', '_space', '_steps', '_colors', '_center', '_angle'))
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
        self._outputmode = None
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
        c_mode = _inkmode()
        if not self._gradient or self._outputmode!=c_mode:
            # rgb in the gradient's space, else the output's
            if c_mode == RGB:
                c_space = _SPACES[self._space]
                clrs = [c._rgb_as(self._space) for c in self._colors]
            else:
                if c_mode == CMYK or (isinstance(c_mode, tuple) and not c_mode[1]):
                    c_space = _DEVICE_CMYK
                elif isinstance(c_mode, tuple):
                    c_space = Press.named[c_mode[0]].space
                else:
                    c_space = _INKS[c_mode]
                clrs = [c.cgColor for c in self._colors]
            pd_gradient = PDGradient.alloc().initWithColors_atLocations_colorSpace_(clrs, self._steps, c_space)
            self._gradient, self._outputmode = pd_gradient, c_mode
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
