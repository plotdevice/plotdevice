# encoding: utf-8
import os
import zlib
import struct
from array import array
from collections import namedtuple
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import rsrc_path, numlike

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

# bundled presses
GRACOL = "gracol"
GRACOL_UNCOATED = "gracol_uncoated"
SWOP = "swop"
FOGRA39 = "fogra39"
FOGRA47 = "fogra47"

class Profile(object):
    named = {} # key -> Profile, as colors= names it

    # system profiles, searched after the installed ones
    SYSTEM = '/System/Library/ColorSync/Profiles'

    # ICC profile search path
    FOLDERS = ['~/Library/ColorSync/Profiles', '/Library/ColorSync/Profiles', '/Library/ColorSync/Profiles/Profiles',
               '/Library/ColorSync/Profiles/Recommended', '/Library/Application Support/Adobe/Color/Profiles',
               '/Library/Application Support/Adobe/Color/Profiles/Recommended', SYSTEM]

    # default video spaces
    SYSTEM_VIDEO = {os.path.join(SYSTEM, 'ITU-709.icc'): 'Rec. 709',
                    os.path.join(SYSTEM, 'ITU-2020.icc'): 'Rec. 2020'}

    # system rgb spaces offered beside P3 and sRGB
    SYSTEM_RGB = {os.path.join(SYSTEM, 'AdobeRGB1998.icc'): 'Adobe RGB (1998)',
                  os.path.join(SYSTEM, 'ROMM RGB.icc'): 'ROMM RGB (ProPhoto)',
                  **SYSTEM_VIDEO}

    scanned = {} # folder mtimes -> (presses, names)

    def __init__(self, key, mode, space):
        self.key = key
        self.mode = mode
        self.space = space # the file's space, or None for Generic CMYK

    @classmethod
    def find(cls, val):
        """The profile a colors= string names: a built-in space, a press, or an ICC profile's path or name"""
        key = val.lower().replace('-', '_')
        if key in (P3, SRGB, CMYK):
            return cls.named[key]
        if key in Press.BUNDLED:
            if key not in cls.named:
                cls.named[key] = Press(key)
            return cls.named[key]

        # a path, else an installed profile's name
        rec709, rec2020 = cls.SYSTEM_VIDEO
        path = {REC709: rec709, REC2020: rec2020}.get(key, val) # rec709 & rec2020 point to the system's .icc profiles
        key = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(key):
            key = cls.scan()[1].get(val.lower(), key)
        try:
            icc = open(key, 'rb').read()
        except OSError:
            searched = ', '.join(cls.FOLDERS)
            unknown = "%r isn't a built-in color space or ICC profile filename (searched in: %s)" % (val, searched)
            raise DeviceError(unknown)
        model = icc[16:20] if icc[36:40] == b'acsp' else None
        space = CGColorSpaceCreateWithICCData(icc) if model in (b'RGB ', b'CMYK') else None
        if space is None:
            notrgb = "%r isn't an RGB or CMYK ICC profile" % val
            raise DeviceError(notrgb)
        generic = os.path.join(cls.SYSTEM, 'Generic CMYK Profile.icc')
        if model == b'CMYK' and os.path.exists(generic) and icc == open(generic, 'rb').read():
            # generic cmyk means unlabeled CMYK
            return cls.named[CMYK]
        if model == b'CMYK':
            return cls.named.setdefault(key, Press(key, space))
        return cls.named.setdefault(key, Profile(key, RGB, space))

    @classmethod
    def installed(cls, mode):
        """The profiles the menus offer for `mode` beside the built-in spaces, as (label, key) pairs"""
        if mode == RGB:
            return [(label, path) for path, label in cls.SYSTEM_RGB.items() if os.path.exists(path)]
        return [(label, press) for press, label in Press.LABELS.items()] + cls.scan()[0]

    @staticmethod
    def header(path):
        """A profile's class, data space, & description, or None"""
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
                desc = Profile.tag_text(bytes(icc), b'desc') or os.path.splitext(os.path.basename(path))[0]
                return (head[12:16], head[16:20], desc.strip())
        except OSError:
            return None

    @classmethod
    def scan(cls):
        """The installed presses as (description, path) pairs, and profiles by lowercased name"""
        folders = [os.path.expanduser(folder) for folder in cls.FOLDERS]
        sources = tuple(os.path.getmtime(path) if os.path.exists(path) else None for path in folders)
        lists = cls.scanned.get(sources)
        if lists is None:
            found, names = {}, {}
            for folder in folders:
                for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                    stem, ext = os.path.splitext(name)
                    if ext.lower() not in ('.icc', '.icm'):
                        continue
                    path = os.path.join(folder, name)
                    real = os.path.realpath(path) # Adobe links into ColorSync's
                    if os.path.isfile(real):
                        names.setdefault(name.lower(), real)
                        names.setdefault(stem.lower(), real)
                    header = cls.header(path) if folder != cls.SYSTEM else None
                    if header and header[:2] == (b'prtr', b'CMYK'):
                        found.setdefault(header[2], path)
            lists = (sorted(found.items(), key=lambda item: item[0].lower()), names)
            cls.scanned.clear()
            cls.scanned[sources] = lists
        return lists

    @staticmethod
    def tag_text(icc, sig):
        """The text of an ICC profile's `sig` tag, or None"""
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

class Press(Profile):
    # bundled presses' zlib'd profiles
    BUNDLED = {GRACOL: 'GRACoL2013_CRPC6.icc', GRACOL_UNCOATED: 'GRACoL2013UNC_CRPC3.icc', SWOP: 'SWOP2013C3_CRPC5.icc',
               FOGRA39: 'ISOcoated_v2_bas.icc', FOGRA47: 'PSO_Uncoated_ISO12647_bas.icc'}

    # PDF/X output conditions from color.org's registry
    CONDITIONS = {GRACOL: ('CGATS21-2-CRPC6', 'Universal Premium Coated (GRACoL 2013, CGATS21-2 CRPC6)'),
                  GRACOL_UNCOATED: ('CGATS21-2-CRPC3', 'Universal Premium Uncoated (GRACoL 2013, CGATS21-2 CRPC3)'),
                  SWOP: ('CGATS21-2-CRPC5', 'Universal Publication Coated (SWOP 2013, CGATS21-2 CRPC5)'),
                  FOGRA39: ('FOGRA39', 'Offset, gloss or matt coated paper (ISO 12647-2:2004, FOGRA39)'),
                  FOGRA47: ('FOGRA47', 'Offset, uncoated white paper (ISO 12647-2:2004, FOGRA47)')}

    # the menus' names for the bundled presses
    LABELS = {GRACOL: 'GRACoL 2013 Coated (CRPC6)', GRACOL_UNCOATED: 'GRACoL 2013 Uncoated (CRPC3)', SWOP: 'SWOP 2013 (CRPC5)',
              FOGRA39: 'ISO Coated v2 (FOGRA39)', FOGRA47: 'PSO Uncoated (FOGRA47)'}

    def __init__(self, key, space=None):
        self.key = key # read by the icc property
        self._icc = self._intent = self._transform = None
        super().__init__(key, CMYK, space if space is not None else CGColorSpaceCreateWithICCData(self.icc))

    @property
    def icc(self):
        """The press's ICC profile bytes"""
        if self._icc is None:
            if self.key in self.BUNDLED:
                self._icc = zlib.decompress(open(rsrc_path('press/%s.zlib' % self.BUNDLED[self.key]), 'rb').read())
            else:
                self._icc = open(self.key, 'rb').read()
        return self._icc

    @property
    def intent(self):
        """The press's PDF/X output intent"""
        if self._intent is None:
            if self.key in self.CONDITIONS:
                identifier, condition = self.CONDITIONS[self.key]
                registry = 'http://www.color.org'
                profile = open(rsrc_path('press/%s.zlib' % self.BUNDLED[self.key]), 'rb').read()
            else:
                # the condition its targ tag names, else Custom
                targ = (self.tag_text(self.icc, b'targ') or '').strip()
                named = targ and '\n' not in targ and len(targ) < 64 # not the data itself
                identifier, registry = (targ, 'http://www.color.org') if named else ('Custom', '')
                condition = self.tag_text(self.icc, b'desc') or os.path.basename(self.key)
                profile = zlib.compress(self.icc, 1)
            self._intent = dict(identifier=identifier, condition=condition, registry=registry, profile=profile)
        return self._intent

    def convert(self, rgb):
        """The inks this press prints for P3 `rgb` components"""

        def transformed(transform, values, count):
            # apply the color `transform` to a pixel's `values` and return `count` float components
            depth, alpha = kColorSync32BitFloat, kColorSyncAlphaNone
            _, out = ColorSyncTransformConvert(
              transform, 1, 1,
              array('f', [0] * count), depth, alpha, 4 * count,
              array('f', values), depth, alpha, 4 * len(values), None
            )
            return out

        if self._transform is None:
            # use colorsync's transforms from p3 into the press and back
            profile, _ = ColorSyncProfileCreate(self.icc, None) # (profile, error)
            p3 = ColorSyncProfileCreateWithName(kColorSyncDisplayP3Profile)
            step = lambda prof, tag: {kColorSyncProfile: prof,
                                      kColorSyncRenderingIntent: kColorSyncRenderingIntentRelative,
                                      kColorSyncTransformTag: tag}
            self._transform = ColorSyncTransformCreate([step(p3, kColorSyncTransformDeviceToPCS), step(profile, kColorSyncTransformPCSToDevice)], None)
            back = ColorSyncTransformCreate([step(profile, kColorSyncTransformDeviceToPCS), step(p3, kColorSyncTransformPCSToDevice)], None)

            # the luminance of the press's black
            black = transformed(back, transformed(self._transform, (0, 0, 0), 4), 3)
            self._black = _apply(_TO_XYZ, [_decode(v) for v in black])[1]

        # black point compensation in linear p3, since ColorSync's lightens and shifts neutrals toward violet
        lin = (self._black + (1 - self._black) * _decode(min(max(v, 0.0), 1.0)) for v in rgb)
        cmyk = transformed(self._transform, [v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in lin], 4)
        return tuple(0.0 if v < .001 else 1.0 if v > .999 else v for v in cmyk)

# the built-in spaces
Profile.named.update({P3: Profile(P3, RGB, CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3)),
                      SRGB: Profile(SRGB, RGB, CGColorSpaceCreateWithName(kCGColorSpaceSRGB)),
                      CMYK: Profile(CMYK, CMYK, None)})

# what a render's colors resolve to, and whether a press's numbers keep its space
Ink = namedtuple('Ink', ['profile', 'tagged'])

class Output(namedtuple('Output', ['profile', 'format'])):
    __slots__ = ()

    # the colors= each format takes, and its default
    FORMATS = dict(png=('rgb',), heic=('rgb',), mov=(P3, SRGB, *Profile.SYSTEM_VIDEO), gif=(SRGB,), eps=(SRGB, CMYK),
                   pdf=('rgb', CMYK), tiff=('rgb', CMYK), jpg=('rgb', CMYK))
    DEFAULTS = dict(gif=SRGB, eps=SRGB)

    @classmethod
    def parse(cls, val, format):
        """The output an export in `format` is written in for colors=`val`"""
        name = 'jpg' if format == 'jpeg' else format
        if val is None:
            return cls(Profile.named[cls.DEFAULTS.get(name, P3)], format)
        if not isinstance(val, str):
            notpalette = "colors=%r isn't a built-in color space or ICC profile filename" % (val,)
            if numlike(val):
                notpalette += " (it isn't a gif's palette size)"
            raise DeviceError(notpalette)
        profile = Profile.find(val)
        key = profile.key
        if key in (P3, SRGB, CMYK):
            kind = key
        elif isinstance(profile, Press):
            kind = 'press'
        else:
            kind = 'rgb'
        allowed = cls.FORMATS[name]
        listed = kind in allowed or key in allowed
        rgb_fits = kind in (P3, SRGB) and 'rgb' in allowed
        press_fits = kind == 'press' and CMYK in allowed
        if not (listed or rgb_fits or press_fits):
            rec709, rec2020 = Profile.SYSTEM_VIDEO
            names = {'rgb': 'an RGB ICC profile', rec709: 'REC709', rec2020: 'REC2020'}
            options = ', '.join(names.get(opt, opt.upper()) for opt in allowed)
            if 'rgb' in allowed:
                options = 'P3, SRGB, ' + options
            if CMYK in allowed:
                options += ', GRACOL, GRACOL_UNCOATED, SWOP, FOGRA39, FOGRA47, a CMYK ICC profile'
            cantfit = "%s %s file can't be exported with colors=%r (it takes %s)" % ('An' if name == 'eps' else 'A', name.upper(), val, options)
            raise DeviceError(cantfit)
        return cls(profile, format)

    @classmethod
    def working(cls, mode):
        """The output a script or a window draws in for `mode`, with no file"""
        return cls(Profile.named[CMYK if mode == CMYK else P3], None)

    @property
    def mode(self):
        """The RGB or CMYK mode colors are drawn in"""
        return self.profile.mode

    @property
    def press(self):
        """The press colors convert into, or None"""
        return self.profile if isinstance(self.profile, Press) else None

    @property
    def cmyk_space(self):
        """What CMYK bitmaps are tagged with to keep their numbers, or None outside a CMYK export"""
        if self.mode != CMYK or self.format is None:
            return None
        return self.press.space if self.ink.tagged else CGColorSpaceCreateDeviceCMYK()

    @property
    def surface_space(self):
        """The space a window-displayable surface is tagged with, or None for P3"""
        rgb_profile = self.mode == RGB and self.profile.key != P3
        return self.profile.space if rgb_profile else None

    @property
    def ink(self):
        """What colors resolve to: CMYK bitmaps keep a press's numbers in its space"""
        return Ink(self.profile, self.press is not None and self.format in ('tiff', 'jpg', 'jpeg'))

class Proof(namedtuple('Proof', ['output', 'vision'])):
    __slots__ = ()

    @classmethod
    def named(cls, kind, value):
        """The proof a View > Proof Colors item names: a press, an rgb profile, or a color vision deficiency"""
        if kind == 'vision':
            return cls(None, _vision_space(value))
        return cls(Output.parse(value, 'tiff' if kind == 'press' else 'png'), None)

    @property
    def space(self):
        """The space a proofed render is drawn in before it's shown, or None to draw as usual"""
        if self.vision is not None:
            return CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3)
        return self.output.profile.space

# color spaces that simulate color vision deficiencies
# Viénot 1999, Brettel 1997, & Machado 2009 (see daltonlens.org/opensource-cvd-simulation)
_BRETTEL_TRITAN = ((1.01277, 0.13548, -0.14826, -0.01243, 0.86812, 0.14431, 0.07589, 0.80500, 0.11911),
                   (0.93678, 0.18979, -0.12657, 0.06154, 0.81526, 0.12320, -0.37562, 1.12767, 0.24796),
                   (0.03901, -0.02788, -0.01113))
_SIMULATIONS = {
    'protanopia': ((0.11238, 0.88762, 0.00000, 0.11238, 0.88762, -0.00000, 0.00401, -0.00401, 1.00000), None, None, 1.0),
    'deuteranopia': ((0.29275, 0.70725, 0.00000, 0.29275, 0.70725, -0.00000, -0.02234, 0.02234, 1.00000), None, None, 1.0),
    'tritanopia': _BRETTEL_TRITAN + (1.0,),
    'protanomaly': ((0.385450, 0.769005, -0.154455, 0.100526, 0.829802, 0.069673, -0.007442, -0.022190, 1.029632), None, None, 1.0),
    'deuteranomaly': ((0.498864, 0.674741, -0.173604, 0.205199, 0.754872, 0.039929, -0.011131, 0.030969, 0.980162), None, None, 1.0),
    'tritanomaly': _BRETTEL_TRITAN + (0.6,),
}

# linear P3 <-> linear sRGB
_TO_SRGB = ((1.22474504332068, -0.2249043124736699, 7.250784997414605e-08),
            (-0.04205780743371995, 1.0420809603180001, -5.531688000021129e-08),
            (-0.01964228962508, -0.07865489259129002, 1.0985372304589898))
_FROM_SRGB = ((0.8225929891205486, 0.1775339096877781, -4.535470049199205e-08),
              (0.03319939601171828, 0.966783512371125, 4.6491124104576245e-08),
              (0.017085360552979614, 0.07239574917612229, 0.9103014217807303))

# linear P3 -> D50 XYZ
_TO_XYZ = ((0.5151214599609375, 0.2919769287109375, 0.1571044921875),
           (0.2411956787109375, 0.6922454833984375, 0.0665740966796875),
           (-0.0010528564453125, 0.0418853759765625, 0.7840728759765625))

_GRID = 33     # lookup table points per channel
_VISION = {}   # deficiency -> CGColorSpace


def _apply(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))

def _decode(v):
    # inverse sRGB curve, which P3 shares
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

def _simulate(deficiency, p3):
    first, second, normal, severity = _SIMULATIONS[deficiency]
    rgb = _apply(_TO_SRGB, p3)
    matrix = first
    if normal and sum(n * c for n, c in zip(normal, rgb)) < 0:
        matrix = second
    simulated = _apply((matrix[0:3], matrix[3:6], matrix[6:9]), rgb)
    simulated = [s * severity + c * (1 - severity) for s, c in zip(simulated, rgb)]
    return _apply(_FROM_SRGB, simulated)

def _profile(deficiency):
    steps = [_decode(i / (_GRID - 1)) for i in range(_GRID)]
    clut = bytearray()
    for r in steps:
        for g in steps:
            for b in steps:
                xyz = _apply(_TO_XYZ, _simulate(deficiency, (r, g, b)))
                clut += struct.pack('>3H', *[min(max(int(round(v * 32768)), 0), 65535) for v in xyz])

    s15 = lambda v: struct.pack('>i', int(round(v * 65536)))
    name = ('%s simulation (Display P3)' % deficiency.capitalize()).encode('ascii') + b'\0'
    tags = [(b'desc', b'desc' + bytes(4) + struct.pack('>I', len(name)) + name + bytes(8) + bytes(3) + bytes(67)),
            (b'cprt', b'text' + bytes(4) + b'No copyright, use freely\0'),
            (b'wtpt', b'XYZ ' + bytes(4) + s15(0.9642) + s15(1.0) + s15(0.8249)),
            (b'A2B0', b'mft2' + bytes(4) + bytes([3, 3, _GRID, 0]) + b''.join(s15(v) for v in (1, 0, 0, 0, 1, 0, 0, 0, 1))
                      + struct.pack('>HH', 2, 2) + struct.pack('>6H', 0, 65535, 0, 65535, 0, 65535) + bytes(clut)
                      + struct.pack('>6H', 0, 65535, 0, 65535, 0, 65535))]
    table, data = b'', b''
    offset = 128 + 4 + 12 * len(tags)
    for sig, body in tags:
        body += bytes(-len(body) % 4)
        table += sig + struct.pack('>II', offset + len(data), len(body))
        data += body
    size = offset + len(data)
    header = (struct.pack('>I4sI4s4s4s', size, bytes(4), 0x02100000, b'scnr', b'RGB ', b'XYZ ') + struct.pack('>6H', 2026, 1, 1, 0, 0, 0)
              + b'acspAPPL' + bytes(24) + s15(0.9642) + s15(1.0) + s15(0.8249) + bytes(48))
    return header + struct.pack('>I', len(tags)) + table + data

def _vision_space(deficiency):
    """The color space that shows P3 as `deficiency` sees it"""
    if deficiency not in _VISION:
        _VISION[deficiency] = CGColorSpaceCreateWithICCData(_profile(deficiency))
    return _VISION[deficiency]
