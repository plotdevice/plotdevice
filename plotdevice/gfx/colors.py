# encoding: utf-8
import os
import re
import json
import zlib
from glob import glob
import colorsys
import warnings
from array import array
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import _copy_attr, _copy_attrs, _flatten, trim_zeroes, rsrc_path, numlike
from . import _inkmode, _outputpress
_ctx = None
__all__ = ("RGB", "HSV", "HSB", "CMYK", "GREY", "P3", "SRGB",
           "GRACOL", "GRACOL_UNCOATED", "SWOP", "FOGRA39", "FOGRA47",
           "Color", "Pattern", "Gradient",)

# color/output modes
RGB = "rgb"
HSV = HSB = "hsv"
CMYK = "cmyk"
GREY = "greyscale"

P3 = "p3"
SRGB = "srgb"

GRACOL = "gracol"
GRACOL_UNCOATED = "gracol_uncoated"
SWOP = "swop"
FOGRA39 = "fogra39"
FOGRA47 = "fogra47"
_PRESSES = {GRACOL: 'GRACoL2013_CRPC6.icc', GRACOL_UNCOATED: 'GRACoL2013UNC_CRPC3.icc', SWOP: 'SWOP2013C3_CRPC5.icc',
            FOGRA39: 'ISOcoated_v2_bas.icc', FOGRA47: 'PSO_Uncoated_ISO12647_bas.icc'}

_PRESS_CONDITIONS = {GRACOL: ('CGATS21-2-CRPC6', 'Universal Premium Coated (GRACoL 2013, CGATS21-2 CRPC6)'),
                     GRACOL_UNCOATED: ('CGATS21-2-CRPC3', 'Universal Premium Uncoated (GRACoL 2013, CGATS21-2 CRPC3)'),
                     SWOP: ('CGATS21-2-CRPC5', 'Universal Publication Coated (SWOP 2013, CGATS21-2 CRPC5)'),
                     FOGRA39: ('FOGRA39', 'Offset, gloss or matt coated paper (ISO 12647-2:2004, FOGRA39)'),
                     FOGRA47: ('FOGRA47', 'Offset, uncoated white paper (ISO 12647-2:2004, FOGRA47)')}

_PRESS_LABELS = {GRACOL: 'GRACoL 2013 Coated (CRPC6)', GRACOL_UNCOATED: 'GRACoL 2013 Uncoated (CRPC3)', SWOP: 'SWOP 2013 (CRPC5)',
                 FOGRA39: 'ISO Coated v2 (FOGRA39)', FOGRA47: 'PSO Uncoated (FOGRA47)'}

_PROFILE_FOLDERS = ['/Library/ColorSync/Profiles', '/Library/ColorSync/Profiles/Profiles', '/Library/ColorSync/Profiles/Recommended',
                    '~/Library/ColorSync/Profiles', '/Library/Application Support/Adobe/Color/Profiles',
                    '/Library/Application Support/Adobe/Color/Profiles/Recommended']
_CANON_PROFILES = '/Library/Printers/Canon/BJPrinter/Resources/ICCProfiles'
_PROFILE_HEADERS = {} # path -> (mtime, (class, data space, description)), see _profile_header
_PROFILE_LISTS = {}   # function -> (the folders' & PPDs' mtimes, the list), see _profile_sources

_PRESS_SPACES = {}
_PRESS_NS_SPACES = {}
_PRESS_INTENTS = {} # (each press's output intent, see _output_intent)
_PRESS_TRANSFORMS = {} # (each press's ColorSync transform from p3, see Color._press_values)

_SPACES = {P3: CGColorSpaceCreateWithName(kCGColorSpaceExtendedDisplayP3),
           SRGB: CGColorSpaceCreateWithName(kCGColorSpaceExtendedSRGB)}
_SPACE_NAMES = {kCGColorSpaceExtendedDisplayP3:P3, kCGColorSpaceDisplayP3:P3,
                kCGColorSpaceExtendedSRGB:SRGB, kCGColorSpaceSRGB:SRGB}
_GENERIC_CMYK = CGColorSpaceCreateWithName(kCGColorSpaceGenericCMYK)
_DEVICE_CMYK = CGColorSpaceCreateDeviceCMYK()

_INKS = {SRGB: CGColorSpaceCreateWithName(kCGColorSpaceSRGB)}

_FORMAT_COLORS = dict(png=('rgb',), heic=('rgb',), mov=(P3, SRGB), gif=(SRGB,), eps=(SRGB, CMYK),
                      pdf=('rgb', CMYK), tiff=('rgb', CMYK), jpg=('rgb', CMYK))
_FORMAT_DEFAULTS = dict(gif=SRGB, eps=SRGB)

_NAMES = dict(mode={RGB:RGB, HSV:HSV, 'hsb':HSV, CMYK:CMYK, GREY:GREY},
              space={P3:P3, SRGB:SRGB})

_CSS_COLORS = json.load(open(rsrc_path('colors.json')))

def _named(kind, val):
    if val is None:
        return None
    names = _NAMES[kind]
    key = val.lower() if isinstance(val, str) else val
    if key not in names:
        unknown = 'Unknown color %s %r (should be one of: %s)' % (kind, val, ', '.join(sorted(set(names.values()))))
        raise DeviceError(unknown)
    return names[key]

def _output_colors(val, format):
    format = 'jpg' if format == 'jpeg' else format
    if val is None:
        return _FORMAT_DEFAULTS.get(format, P3)
    if not isinstance(val, str):
        notpalette = 'colors= is the color space, press or profile to export in: P3, SRGB, CMYK, a press like GRACOL, or an .icc file (not %r)' % (val,)
        if numlike(val):
            notpalette += "; it isn't a gif's palette size"
        raise DeviceError(notpalette)
    key = val.lower().replace('-', '_')
    if key in (P3, SRGB, CMYK):
        kind = key
    elif key in _PRESSES:
        kind = 'press'
        if key not in _PRESS_SPACES:
            _PRESS_SPACES[key] = CGColorSpaceCreateWithICCData(_press_profile(key))
    else:
        key = os.path.abspath(os.path.expanduser(val))
        try:
            icc = open(key, 'rb').read()
        except OSError:
            unknown = 'colors= should be P3, SRGB, CMYK, a press (GRACOL, GRACOL_UNCOATED, SWOP, FOGRA39 or FOGRA47), or the path to an .icc profile (%r is none of them)' % val
            raise DeviceError(unknown)
        model = icc[16:20] if icc[36:40] == b'acsp' else None
        space = CGColorSpaceCreateWithICCData(icc) if model in (b'RGB ', b'CMYK') else None
        if space is None:
            notrgb = 'colors= needs an RGB or CMYK .icc profile (%s is neither)' % val
            raise DeviceError(notrgb)
        if model == b'CMYK':
            _PRESS_SPACES.setdefault(key, space)
            kind = 'press'
        else:
            _INKS.setdefault(key, space)
            kind = 'rgb'
    allowed = _FORMAT_COLORS[format]
    fits = kind in allowed or (kind in (P3, SRGB) and 'rgb' in allowed) or (kind == 'press' and CMYK in allowed)
    if not fits:
        options = ', '.join('an RGB .icc profile' if opt == 'rgb' else opt.upper() for opt in allowed)
        if 'rgb' in allowed:
            options = 'P3, SRGB, ' + options
        if CMYK in allowed:
            options += ', a press'
        cantfit = "%s %s file can't be exported with colors=%r (it takes %s)" % ('An' if format == 'eps' else 'A', format.upper(), val, options)
        raise DeviceError(cantfit)
    return key

def _output_mode(colors):
    return CMYK if colors == CMYK or colors in _PRESS_SPACES else RGB

def _press_ns_space(press):
    if press not in _PRESS_NS_SPACES:
        _PRESS_NS_SPACES[press] = NSColorSpace.alloc().initWithCGColorSpace_(_PRESS_SPACES[press])
    return _PRESS_NS_SPACES[press]

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
    try:
        mtime = os.path.getmtime(path)
        if _PROFILE_HEADERS.get(path, (None,))[0] == mtime:
            return _PROFILE_HEADERS[path][1]
        with open(path, 'rb') as f:
            head = f.read(132)
            if len(head) < 132 or head[36:40] != b'acsp':
                header = None
            else:
                count = min(int.from_bytes(head[128:132], 'big'), 256)
                table = f.read(12 * count)
                icc = bytearray(head + table)
                for at in range(0, len(table), 12):
                    if table[at:at + 4] == b'desc':
                        offset, size = int.from_bytes(table[at + 4:at + 8], 'big'), int.from_bytes(table[at + 8:at + 12], 'big')
                        f.seek(offset)
                        icc = bytes(icc) + b'\0' * (offset - len(icc)) + f.read(min(size, 4096))
                desc = _icc_text(bytes(icc), b'desc') or os.path.splitext(os.path.basename(path))[0]
                header = (head[12:16], head[16:20], desc.strip())
    except OSError:
        return None
    _PROFILE_HEADERS[path] = (mtime, header)
    return header

def _profile_sources():
    paths = [os.path.expanduser(folder) for folder in _PROFILE_FOLDERS] + ['/etc/cups/ppd'] + glob('/etc/cups/ppd/*.ppd')
    return tuple(os.path.getmtime(path) if os.path.exists(path) else None for path in paths)

def _installed_presses():
    sources = _profile_sources()
    if _PROFILE_LISTS.get('presses', (None,))[0] == sources:
        return _PROFILE_LISTS['presses'][1]
    found = {}
    for folder in _PROFILE_FOLDERS:
        folder = os.path.expanduser(folder)
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            path = os.path.join(folder, name)
            header = _profile_header(path) if os.path.splitext(name)[1].lower() in ('.icc', '.icm') else None
            if header and header[:2] == (b'prtr', b'CMYK'):
                found.setdefault(header[2], path)
    presses = sorted(found.items(), key=lambda item: item[0].lower())
    _PROFILE_LISTS['presses'] = (sources, presses)
    return presses

def _printer_profiles():
    sources = _profile_sources()
    if _PROFILE_LISTS.get('printers', (None,))[0] == sources:
        return _PROFILE_LISTS['printers'][1]
    found, seen = [], set()
    for ppd in sorted(glob(os.path.join('/etc/cups/ppd', '*.ppd'))):
        printer = os.path.splitext(os.path.basename(ppd))[0].replace('_', ' ')
        try:
            text = open(ppd, encoding='latin-1').read()
        except OSError:
            continue
        paths = re.findall(r'^\*cupsICCProfile [^:]*:\s*"([^"]+)"', text, re.M)
        if '*cupsICCQualifier2: CNIJProfileID' in text:
            paths += [os.path.join(_CANON_PROFILES, name) for name in re.findall(r'^\*CNIJProfileID \d+/([^:]+):', text, re.M)]
        for path in paths:
            header = None if path.startswith('/System/Library/') else _profile_header(path)
            if header and header[0] == b'prtr' and (printer, path) not in seen:
                seen.add((printer, path))
                found.append((printer, header[2], path))
    for folder in _PROFILE_FOLDERS:
        folder = os.path.expanduser(folder)
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            path = os.path.join(folder, name)
            header = _profile_header(path) if os.path.splitext(name)[1].lower() in ('.icc', '.icm') else None
            if header and header[:2] == (b'prtr', b'RGB ') and not any(path == p for _, _, p in found):
                found.append((None, header[2], path))
    _PROFILE_LISTS['printers'] = (sources, found)
    return found

def _output_intent(press):
    if press not in _PRESS_INTENTS:
        if press in _PRESS_CONDITIONS:
            identifier, condition = _PRESS_CONDITIONS[press]
            registry = 'http://www.color.org'
            profile = open(rsrc_path('press/%s.zlib' % _PRESSES[press]), 'rb').read()
        else:
            icc = _press_profile(press)
            targ = (_icc_text(icc, b'targ') or '').strip()
            named = targ and '\n' not in targ and len(targ) < 64 # (rather than the characterization data itself)
            identifier, registry = (targ, 'http://www.color.org') if named else ('Custom', '')
            condition = _icc_text(icc, b'desc') or os.path.basename(press)
            profile = zlib.compress(icc, 1) # (level 6 is only ~1% smaller, at twice the time)
        _PRESS_INTENTS[press] = dict(identifier=identifier, condition=condition, registry=registry, profile=profile)
    return _PRESS_INTENTS[press]

def _press_profile(press):
    if press in _PRESSES:
        return zlib.decompress(open(rsrc_path('press/%s.zlib' % _PRESSES[press]), 'rb').read())
    return open(press, 'rb').read()

def _output_space(colors):
    if colors == CMYK:
        return None
    if colors in _PRESS_SPACES:
        return _PRESS_SPACES[colors]
    return CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3) if colors == P3 else _INKS[colors]

def _clamp(v):
    return min(max(v, 0.0), 1.0)

def _components(cg):
    return CGColorGetComponents(cg).as_tuple(CGColorGetNumberOfComponents(cg))

def _matched(cg, space):
    return CGColorCreateCopyByMatchingToColorSpace(space, kCGRenderingIntentDefault, cg, None)

def _hexstring(r, g, b):
    s = "".join('%02x'%round(255*_clamp(c)) for c in (r,g,b))
    if all([len(set(pair))==1 for pair in zip(s[::2], s[1::2])]):
        s = "".join(s[::2])
    return "#"+s

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

        converting = kwargs.get('space') is not None
        space = _named('space', kwargs.get('space')) or _ctx._colorspace

        # use the specified range for int values, or leave it as None to use the default 0-1 scale
        rng = kwargs.get('range')

        params = len(args)
        cmyk, values = False, None # whether it's a cmyk color, and its components if they're known
        if params == 1 and args[0] is None:                 # None -> transparent
            clr, values = Color._cgcolor(GREY, space, 0, 0)
        elif params == 1 and isinstance(args[0], Color):    # Color object
            self._share(args[0])
            if converting and self.space != space:
                if self._from_cmyk:
                    self._cmyk = self._cmyk_src
                    self._cache['space'], self._rgb_ = space, None # (converted on demand, see _rgb)
                else:
                    self._rgb = _matched(self._rgb, _SPACES[space])
                    self._cache['space'] = space
                    self._updateCmyk()
            return
        elif params == 1 and isinstance(args[0], Pattern):  # Pattern object
            pattern = args[0]._nsColor
            self._rgb_ = self._cmyk_ = self._cmyk_src = pattern.CGColor()
            self._cache = {('ns', mode):pattern for mode in (RGB, CMYK)}
            self._cache['pattern'] = pattern # (the nsColor for any ink)
            self._cache['space'] = space
            return
        elif params == 1 and isinstance(args[0], Gradient): # Gradient (use first shade)
            self._share(args[0]._colors[0])
            return
        elif params == 1 and isinstance(args[0], (NSColor, CGColorRef)): # NSColor or CGColor object
            clr = args[0].CGColor() if isinstance(args[0], NSColor) else args[0]
            own = _SPACE_NAMES.get(CGColorSpaceCopyName(CGColorGetColorSpace(clr)))
            if own is not None:
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

        self._cache = {'space':space}
        if cmyk:
            self._rgb_, self._cmyk_src = None, clr
            self._cmyk = clr
            if values is not None:
                self._cache['cmyka'] = values
        else:
            self._rgb = clr
            self._cmyk_src, self._cmyk_ = clr, None # converted on demand (see _cmyk)
            if values is not None:
                self._cache['rgba'] = values

    @trim_zeroes
    def __repr__(self):
        r, g, b, a = self._values(RGB)
        args = [repr(_hexstring(r, g, b))]
        if a != 1.0:
            args.append(repr(a))
        if self.space != _ctx._colorspace:
            args.append('space=%s' % self.space.upper())
        return '%s(%s)'%(self.__class__.__name__, ', '.join(args))

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
        self.nsColor.set()

    # fill() and stroke() both cache the previous canvas state by creating a _rollback attr.
    # act as a context manager if there's a fill/stroke state to revert to at the end of the block.
    def __enter__(self):
        if not hasattr(self, '_rollback'):
            badcontext = 'the with-statement can only be used with fill() and stroke(), not arbitrary colors'
            raise DeviceError(badcontext)
        param = next(iter(self._rollback))
        statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
        if getattr(_ctx, statevar) is not self._installed:
            self._rollback = {param:getattr(_ctx, statevar)}
            setattr(_ctx, statevar, self._installed)
        return self

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
            setattr(_ctx, statevar, val)

    @property
    def space(self):
        return self._cache['space']

    @property
    def nsColor(self):
        mode = _inkmode()
        try:
            return self._cache['ns', mode]
        except KeyError:
            if mode == RGB:
                ns = NSColor.colorWithCGColor_(self._rgb_as(P3))
            elif mode == CMYK:
                ns = NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_(*self._values(CMYK))
            elif self._cache.get('pattern'):
                ns = self._cache['pattern']
            elif isinstance(mode, tuple):
                press, in_space = mode
                if in_space:
                    ns = NSColor.colorWithColorSpace_components_count_(_press_ns_space(press), self._press_values(press), 5)
                else:
                    ns = NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_(*self._press_values(press))
            else:
                ns = NSColor.colorWithCGColor_(_matched(self._rgb, _INKS[mode]))
            self._cache['ns', mode] = ns
            return ns

    @property
    def _src(self):
        return self._cmyk_src

    @property
    def cgColor(self):
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
                cg = CGColorCreate(_PRESS_SPACES[press] if in_space else _DEVICE_CMYK, self._press_values(press))
            else:
                cg = _matched(self._rgb, _INKS[mode])
            self._cache['cg', mode] = cg
            return cg

    def _press_values(self, press):
        key = 'press', press
        if key not in self._cache:
            if self._from_cmyk:
                self._cache[key] = self._values(CMYK)
            else:
                if press not in _PRESS_TRANSFORMS:
                    icc = CGColorSpaceCopyICCData(_PRESS_SPACES[press])
                    profile, _ = ColorSyncProfileCreate(icc, None) # (profile, error)
                    steps = [{kColorSyncProfile: ColorSyncProfileCreateWithName(kColorSyncDisplayP3Profile),
                              kColorSyncRenderingIntent: kColorSyncRenderingIntentRelative,
                              kColorSyncTransformTag: kColorSyncTransformDeviceToPCS},
                             {kColorSyncProfile: profile, kColorSyncRenderingIntent: kColorSyncRenderingIntentRelative,
                              kColorSyncTransformTag: kColorSyncTransformPCSToDevice, kColorSyncBlackPointCompensation: True}]
                    _PRESS_TRANSFORMS[press] = ColorSyncTransformCreate(steps, {kColorSyncBlackPointCompensation: True})
                r, g, b, alpha = _components(self._rgb_as(P3))
                rgb = array('H', (round(_clamp(v) * 65535) for v in (r, g, b)))
                _, cmyk = ColorSyncTransformConvert(_PRESS_TRANSFORMS[press], 1, 1, array('H', [0] * 4), kColorSync16BitInteger,
                                                    kColorSyncAlphaNone, 8, rgb, kColorSync16BitInteger, kColorSyncAlphaNone, 6, None)
                inks = tuple(0.0 if v < .001 else 1.0 if v > .999 else v for v in (c / 65535 for c in cmyk))
                self._cache[key] = inks + (alpha,)
        return self._cache[key]

    def _rgb_as(self, space):
        return self._rgb if self.space == space else _matched(self._rgb, _SPACES[space])

    def _read_as(self, space):
        press = _outputpress()
        if press is None or not self._from_cmyk: # (in that order: _outputpress is the cheaper)
            return self._rgb_as(space)
        return _matched(CGColorCreate(_PRESS_SPACES[press], self._values(CMYK)), _SPACES[space])

    def _read(self, mode):
        press = _outputpress() if mode is not CMYK else None
        return self._values(mode, press if press and self._from_cmyk else None) # (the press first: see _read_as)

    def _values(self, mode, press=None):
        if mode is RGB:
            key = 'rgba' if press is None else ('rgba', press)
            try:
                return self._cache[key]
            except KeyError:
                rgba = self._cache[key] = _components(self._rgb if press is None else self._read_as(self.space))
                return rgba
        elif mode is HSV:
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
        self._rgb_ = other._rgb_
        self._cmyk_ = other._cmyk_
        self._cmyk_src = other._cmyk_src
        self._cache = other._cache

    @property
    def _rgb(self):
        if self._rgb_ is None:
            cache = self._cache
            if 'rgb' not in cache:
                cache['rgb'] = _matched(self._cmyk_src, _SPACES[cache['space']])
            self._rgb_ = cache['rgb']
        return self._rgb_

    @_rgb.setter
    def _rgb(self, clr):
        self._rgb_, self._cache = clr, {'space':self._cache['space']}

    @property
    def _cmyk(self):
        if self._cmyk_ is None:
            cache = self._cache
            if 'cmyk' not in cache:
                cache['cmyk'] = _matched(self._cmyk_src, _GENERIC_CMYK)
            self._cmyk_ = cache['cmyk']
        return self._cmyk_

    @_cmyk.setter
    def _cmyk(self, clr):
        self._cmyk_, self._cache = clr, {'space':self._cache['space']}

    @property
    def _from_cmyk(self):
        try:
            return self._cache['from_cmyk']
        except KeyError:
            from_cmyk = self._cache['from_cmyk'] = CGColorSpaceGetModel(CGColorGetColorSpace(self._cmyk_src)) == kCGColorSpaceModelCMYK
            return from_cmyk

    def _updateCmyk(self):
        self._cmyk_src, self._cmyk_ = self._rgb, None

    def _updateRgb(self):
        self._cmyk_src, self._rgb_ = self._cmyk, None

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
        val = _clamp(self._normalize(val))
        if self._from_cmyk:
            self._cmyk = CGColorCreateCopyWithAlpha(self._cmyk_src, val)
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

    def _get_hex(self):
        r, g, b, a = _components(self._read_as(_ctx._colorspace))
        return _hexstring(r, g, b)
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

class Pattern(object):
    def __init__(self, img):
        if isinstance(img, Pattern):
            self._nsColor = img._nsColor
        else:
            from .image import Image
            img = Image(img) if isinstance(img, str) else img
            self._nsColor = NSColor.colorWithPatternImage_(img._nsImage)

    # fill() and stroke() both cache the previous canvas state by creating a _rollback attr.
    # act as a context manager if there's a fill/stroke state to revert to at the end of the block.
    def __enter__(self):
        if not hasattr(self, '_rollback'):
            badcontext = 'the with-statement can only be used with fill() and stroke(), not arbitrary colors'
            raise DeviceError(badcontext)
        param = next(iter(self._rollback))
        statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
        if getattr(_ctx, statevar) is not self._installed:
            self._rollback = {param:getattr(_ctx, statevar)}
            setattr(_ctx, statevar, self._installed)
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
            _copy_attrs(colors[0], self, ('_gradient', '_outputmode', '_space', '_steps', '_colors', '_center', '_angle'))
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
    def nsGradient(self):
        c_mode = _inkmode()
        if not self._gradient or self._outputmode!=c_mode:
            if c_mode == RGB:
                c_space = NSColorSpace.alloc().initWithCGColorSpace_(_SPACES[self._space])
                ns_clrs = [NSColor.colorWithCGColor_(c._rgb_as(self._space)) for c in self._colors]
            else:
                if c_mode == CMYK or (isinstance(c_mode, tuple) and not c_mode[1]):
                    c_space = NSColorSpace.deviceCMYKColorSpace()
                elif isinstance(c_mode, tuple):
                    c_space = _press_ns_space(c_mode[0])
                else:
                    c_space = NSColorSpace.alloc().initWithCGColorSpace_(_INKS[c_mode])
                ns_clrs = [c.nsColor for c in self._colors]
            ns_gradient = NSGradient.alloc().initWithColors_atLocations_colorSpace_(ns_clrs, self._steps, c_space)
            self._gradient, self._outputmode = ns_gradient, c_mode
        return self._gradient

    @property
    def brightness(self):
        return max(clr.brightness for clr in self._colors)

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
