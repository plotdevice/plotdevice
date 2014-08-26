# encoding: utf-8
import os
import re
import json
import warnings
import math
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import trim_zeroes
from ..lib import geometry

_ctx = None
__all__ = [
        "DEGREES", "RADIANS", "PERCENT",
        "px", "inch", "pica", "cm", "mm", "pi", "tau",
        "Point", "Size", "Region",
        "Transform", "CENTER", "CORNER",
        ]

# transform modes
CENTER = "center"
CORNER = "corner"

# rotation modes
DEGREES = "degrees"
RADIANS = "radians"
PERCENT = "percent"

# maths
pi = math.pi
tau = 2*pi

### tuple-like objects for grid dimensions ###

class Point(object):
    def __init__(self, *args, **kwargs):
        if len(args) == 2:
            self.x, self.y = args
        else:
            try:
                self.x, self.y = args[0]
            except:
                self.x = kwargs.get('x', 0.0)
                self.y = kwargs.get('y', 0.0)

    @trim_zeroes
    def __repr__(self):
        return "Point(x=%.3f, y=%.3f)" % (self.x, self.y)

    def __eq__(self, other):
        if other is None: return False
        return self.x == other.x and self.y == other.y

    def __ne__(self, other):
        return not self.__eq__(other)

    def __iter__(self):
        # allow for assignments like: x,y = Point()
        return iter([self.x, self.y])

    # lib.geometry methods (accept either x,y pairs or Point args)

    def angle(self, x=0, y=0):
        if isinstance(x, Point):
            x, y = x.__iter__()
        theta = geometry.angle(self.x, self.y, x, y)
        basis={DEGREES:360.0, RADIANS:2*pi, PERCENT:1.0}
        return (theta*basis[_ctx._thetamode])/basis[DEGREES]


    def distance(self, x=0, y=0):
        if isinstance(x, Point):
            x, y = x.__iter__()
        return geometry.distance(self.x, self.y, x, y)

    def reflect(self, *args, **kwargs):
        d = kwargs.get('d', 1.0)
        a = kwargs.get('a', 180)
        if isinstance(args[0], Point):
            (x,y), opts = args[0], args[1:]
        else:
            (x,y), opts = args[:2], args[2:]
        if opts:
            d=opts[0]
        if opts[1:]:
            a=opts[1]
        return Point(geometry.reflect(self.x, self.y, x, y, d, a))

    def coordinates(self, distance, angle):
        angle = _ctx._angle(angle, DEGREES)
        return Point(geometry.coordinates(self.x, self.y, distance, angle))

class Size(tuple):
    def __new__(cls, width, height):
        this = tuple.__new__(cls, (width, height))
        for attr in ('w','width'): setattr(this, attr, width)
        for attr in ('h','height'): setattr(this, attr, height)
        return this

    @trim_zeroes
    def __repr__(self):
        return 'Size(width=%.3f, height=%.3f)'%self

class Region(tuple):
    # Bug?: maybe this actually needs to be mutable...
    def __new__(cls, x=0, y=0, w=0, h=0, **kwargs):
        if isinstance(x, NSRect):
            return Region(*x)

        try: # accept a pair of 2-tuples as origin/size
            (x,y), (width,height) = x,y
        except TypeError:
            # accept both w/h and width/height spellings
            width = kwargs.get('width', w)
            height = kwargs.get('height', h)
        this = tuple.__new__(cls, [(x,y), (width, height)])
        for nm in ('x','y','width','height'):
            if nm[1:]: setattr(this, nm[0], locals()[nm])
            setattr(this, nm, locals()[nm])
        this.origin = Point(x,y)
        this.size = Size(width, height)
        return this

    @trim_zeroes
    def __repr__(self):
        return 'Region(x=%.3f, y=%.3f, w=%.3f, h=%.3f)'%(self[0]+self[1])


### NSAffineTransform wrapper used for positioning Grobs in a Context ###

class Transform(object):

    def __init__(self, transform=None):
        if transform is None:
            transform = NSAffineTransform.transform()
        elif isinstance(transform, Transform):
            transform = transform._nsAffineTransform.copy()
        elif isinstance(transform, NSAffineTransform):
            transform = transform.copy()
        elif isinstance(transform, (list, tuple, NSAffineTransformStruct)):
            struct = tuple(transform)
            transform = NSAffineTransform.transform()
            transform.setTransformStruct_(struct)
        else:
            wrongtype = "Don't know how to handle transform %s." % transform
            raise DeviceError(wrongtype)
        self._nsAffineTransform = transform

    def __enter__(self):
        # Transform objects get _rollback attrs when they're derived from the graphics
        # context's current transform via a state-mutation command. In these cases
        # the global state has already been changed before the context manager was
        # invoked, so don't re-apply it again here.
        if not hasattr(self, '_rollback'):
            _ctx._transform.prepend(self)

    def __exit__(self, type, value, tb):
        # once we've been through a block the _rollback (if any) can be discarded
        if hasattr(self, '_rollback'):
            # _rollback is a dict containing _transform and/or _transformmode.
            # in these cases do a direct overwrite then bail out rather than
            # applying the inverse transform
            for attr, priorval in self._rollback.items():
                setattr(_ctx, attr, priorval)
            del self._rollback
            return
        else:
            # invert our changes to restore the context's transform
            _ctx._transform.prepend(self.inverse)

    @trim_zeroes
    def __repr__(self):
        return "%s([%.3f, %.3f, %.3f, %.3f, %.3f, %.3f])" % ((self.__class__.__name__,)
                 + tuple(self))

    def __iter__(self):
        for value in self._nsAffineTransform.transformStruct():
            yield value

    def copy(self):
        return self.__class__(self)

    def _get_matrix(self):
        return self._nsAffineTransform.transformStruct()
    def _set_matrix(self, value):
        self._nsAffineTransform.setTransformStruct_(value)
    matrix = property(_get_matrix, _set_matrix)

    @property
    def inverse(self):
        inv = self.copy()
        inv._nsAffineTransform.invert()
        return inv

    def rotate(self, arg=None, **opt):
        """Prepend a rotation transform to the receiver

        The angle should be specified through a keyword argument defining its range. e.g.,
            t.rotate(degrees=180)
            t.rotate(radians=pi)
            t.rotate(percent=0.5)

        If called with a positional arg, the angle will be interpreted as degrees unless a
        prior call to geometry() changed the units.
        """

        # check the kwargs for unit-specific settings
        units = {k:v for k,v in opt.items() if k in ['degrees', 'radians', 'percent']}
        if len(units) > 1:
            badunits = 'rotate: specify one rotation at a time (got %s)' % " & ".join(units.keys())
            raise DeviceError(badunits)

        # if nothing in the kwargs, use the current mode and take the quantity from the first arg
        if not units:
            units[_ctx._thetamode] = arg or 0

        # add rotation to the graphics state
        degrees = units.get('degrees', 0)
        radians = units.get('radians', 0)
        if 'percent' in units:
            degrees, radians = 0, tau*units['percent']

        xf = Transform()
        if degrees:
            xf._nsAffineTransform.rotateByDegrees_(-degrees)
        else:
            xf._nsAffineTransform.rotateByRadians_(-radians)
        if opt.get('rollback'):
            xf._rollback = {"_transform":self.copy()}
        self.prepend(xf)
        return xf

    def translate(self, x=0, y=0, **opt):
        xf = Transform()
        xf._nsAffineTransform.translateXBy_yBy_(x, y)
        if opt.get('rollback'):
            xf._rollback = {"_transform":self.copy()}
        self.prepend(xf)
        return xf

    def scale(self, x=1, y=None, **opt):
        if y is None:
            y = x
        xf = Transform()
        xf._nsAffineTransform.scaleXBy_yBy_(x, y)
        if opt.get('rollback'):
            xf._rollback = {"_transform":self.copy()}
        self.prepend(xf)
        return xf

    def skew(self, x=0, y=0, **opt):
        x,y = map(_ctx._angle, [x,y]) # convert from canvas units to radians
        xf = Transform()
        xf.matrix = (1, math.tan(y), -math.tan(x), 1, 0, 0)
        if opt.get('rollback'):
            xf._rollback = {"_transform":self.copy()}
        self.prepend(xf)
        return xf

    def set(self):
        self._nsAffineTransform.set()

    def concat(self):
        self._nsAffineTransform.concat()

    def append(self, other):
        if isinstance(other, Transform):
            other = other._nsAffineTransform
        self._nsAffineTransform.appendTransform_(other)

    def prepend(self, other):
        if isinstance(other, Transform):
            other = other._nsAffineTransform
        self._nsAffineTransform.prependTransform_(other)

    def apply(self, point_or_path):
        from .bezier import Bezier
        if isinstance(point_or_path, Bezier):
            return self.transformBezier(point_or_path)
        elif isinstance(point_or_path, Point):
            return self.transformPoint(point_or_path)
        else:
            wrongtype = "Can only transform Beziers or Points"
            raise DeviceError(wrongtype)

    def transformPoint(self, point):
        return Point(self._nsAffineTransform.transformPoint_((point.x,point.y)))

    def transformBezier(self, path):
        from .bezier import Bezier
        if isinstance(path, Bezier):
            path = path.copy()
        else:
            wrongtype = "Can only transform Beziers"
            raise DeviceError(wrongtype)
        path._nsBezierPath = self._nsAffineTransform.transformBezierPath_(path._nsBezierPath)
        return path

    def transformBezierPath(self, path):
        return self.transformBezier(path)

    @property
    def transform(self):
        warnings.warn("The 'transform' attribute is deprecated. Please use _nsAffineTransform instead.", DeprecationWarning, stacklevel=2)
        return self._nsAffineTransform

### canvas scale-factors ###

class MagicNumber(object):
    # be a well-behaved pseudo-number (based on the float in self.value)
    def __int__(self): return int(self.value)
    def __long__(self): return long(self.value)
    def __float__(self): return float(self.value)
    def __cmp__(self, n): return cmp(self.value, n)

    def __abs__(self): return abs(self.value)
    def __pos__(self): return +self.value
    def __neg__(self): return -self.value
    def __invert__(self): return ~self.value
    def __trunc__(self): return math.trunc(self.value)

    def __add__(self, n): return self.value + n
    def __sub__(self, n): return self.value - n
    def __mul__(self, n): return self.value * n
    def __div__(self, n): return self.value/n
    def __floordiv__(self, n): return self.value // n
    def __mod__(self, n): return self.value % n
    def __pow__(self, n): return self.value ** n
    def __lshift__(self, n): return self.value << n
    def __rshift__(self, n): return self.value >> n

    def __radd__(self, n): return n + self.value
    def __rsub__(self, n): return n - self.value
    def __rmul__(self, n): return n * self.value
    def __rdiv__(self, n): return n / self.value
    def __rfloordiv__(self, n): return n // self.value
    def __rmod__(self, n): return n % self.value
    def __rpow__(self, n): return n ** self.value
    def __rlshift__(self, n): return n << self.value
    def __rrshift__(self, n): return n >> self.value

# the WIDTH and HEIGHT globals are Dimension objects
class Dimension(MagicNumber):
    """A persistent reference to the current canvas's size"""
    def __init__(self, dim):
        self._dim = dim # "width" or "height"

    def __repr__(self):
        return repr(self.value)

    @property
    def value(self):
        return float(getattr(_ctx.canvas, self._dim))

# the px, inch, pica, cm, & mm globals are Unit objects
class Unit(MagicNumber):
    """A standard unit of measurement."""
    _dpx = {"px":1.0, "inch":72.0, "pica":12.0, "cm":28.3465, "mm":2.8346}

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        if self==_ctx.canvas.unit:
            return '<one %s>' % self.name
        return '<one %s (%0.3f canvas units)>'%(self.name, self.value)

    @property
    def value(self):
        """Size of this unit in terms of the current canvas unit"""
        return self.basis/_ctx.canvas.unit.basis

    @property
    def basis(self):
        """Size of this unit of measure in Postscript points"""
        return Unit._dpx[self.name]

# create a module-level variable for each of the standard units
globals().update({u:Unit(u) for u in Unit._dpx})

