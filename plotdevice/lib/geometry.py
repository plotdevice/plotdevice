# Geometric functionality

from math import degrees, atan2
from math import sqrt, pow
from math import radians, sin, cos

try:
    # Faster C versions.
    import cGeometry as geo
    isqrt = inverse_sqrt = geo.fast_inverse_sqrt
    angle = geo.angle
    distance = geo.distance
    coordinates = geo.coordinates
except ImportError:
    def inverse_sqrt(x):
        return 1.0 / sqrt(x)

    isqrt = inverse_sqrt

    def angle(x0, y0, x1, y1):
        a = degrees( atan2(y1-y0, x1-x0) )
        return a

    def distance(x0, y0, x1, y1):
        return sqrt(pow(x1-x0, 2) + pow(y1-y0, 2))

    def coordinates(x0, y0, distance, angle):
        x1 = x0 + cos(radians(angle)) * distance
        y1 = y0 + sin(radians(angle)) * distance
        return x1, y1

def reflect(x0, y0, x1, y1, d=1.0, a=180):
    d *= distance(x0, y0, x1, y1)
    a += angle(x0, y0, x1, y1)
    x, y = coordinates(x0, y0, d, a)
    return x, y

