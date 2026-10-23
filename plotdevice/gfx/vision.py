# encoding: utf-8
import struct
from ..lib.cocoa import *

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

_P3_TO_XYZ = ((0.4865709, 0.2656677, 0.1982173), (0.2289746, 0.6917385, 0.0792869), (0.0, 0.0451134, 1.0439444))
_XYZ_TO_SRGB = ((3.2404542, -1.5371385, -0.4985314), (-0.9692660, 1.8760108, 0.0415560), (0.0556434, -0.2040259, 1.0572252))

_GRID = 33     # lookup table points per channel
_VISION = {}   # deficiency -> CGColorSpace, made the first time it's proofed


def _mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))

def _apply(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))

def _inverse(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return ((( e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det),
            (( f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det),
            (( d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det))

def _decode(v):
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

_TO_SRGB = _mul(_XYZ_TO_SRGB, _P3_TO_XYZ)
_FROM_SRGB = _inverse(_TO_SRGB)

def _tag(icc, sig):
    count = struct.unpack('>I', icc[128:132])[0]
    for at in range(132, 132 + 12 * count, 12):
        if icc[at:at + 4] == sig:
            offset, size = struct.unpack('>II', icc[at + 4:at + 12])
            return icc[offset:offset + size]
    return None

def _profile(deficiency):
    p3 = bytes(CGColorSpaceCopyICCData(CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3)))
    fixed = lambda b: struct.unpack('>i', b)[0] / 65536.0
    colorants = [[fixed(_tag(p3, sig)[8 + 4 * i:12 + 4 * i]) for i in range(3)] for sig in (b'rXYZ', b'gXYZ', b'bXYZ')]
    to_xyz = tuple(tuple(colorants[j][i] for j in range(3)) for i in range(3)) # (columns: r, g & b's XYZ)

    steps = [_decode(i / (_GRID - 1)) for i in range(_GRID)]
    clut = bytearray()
    for r in steps:
        for g in steps:
            for b in steps:
                xyz = _apply(to_xyz, _simulate(deficiency, (r, g, b)))
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
    if deficiency not in _VISION:
        _VISION[deficiency] = CGColorSpaceCreateWithICCData(_profile(deficiency))
    return _VISION[deficiency]
