# encoding: utf-8
"""Color spaces that simulate color vision deficiencies"""
import struct
from ..lib.cocoa import *

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
