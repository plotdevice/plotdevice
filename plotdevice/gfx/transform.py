# encoding: utf-8
import os
import re
import json
import warnings
import math
from operator import neg
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import trim_zeroes, numlike
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

class Pair(object):
    """Base class for Point & Size objects (with basic arithmetic support)"""
    def __init__(self, *vals, **kwargs):
        attrs = self._coords
        kwargs = {k[0]:v for k,v in kwargs.items()}

        if len(vals) == 2:
            # handle Point(x, y) or Size(w, h)
            for attr, val in zip(attrs, vals):
                setattr(self, attr, val)
        elif len(vals) == 1 and isinstance(vals[0], Pair):
            # handle things like Point(Point())
            for attr, val in zip(attrs, vals[0]):
                setattr(self, attr, val)
        elif len(vals) == 1 and hasattr(vals[0], '__getitem__'):
            # handle Point(NSPoint()) and the like
            for attr, val in zip(attrs, vals[0]):
                setattr(self, attr, val)
        elif vals:
            baddims = '%s requires a single coordinate pair' % self.__class__.__name__
            raise DeviceError(baddims)
        else:
            # kwargs will only be used if there are no positional args
            for attr in attrs:
                setattr(self, attr, kwargs.get(attr, 0.0))

    @trim_zeroes
    def __repr__(self):
        dims = ["%s=%.3f"%(attr,d) if numlike(d) else repr(d) for attr, d in zip(self._coords, self)]
        return self.__class__.__name__ + "(%s, %s)" % tuple(dims)

    def __iter__(self):
        # allow for assignments like: x,y = Point()
        return iter([getattr(self, attr) for attr in self._coords])

    def __eq__(self, other):
        if other is None: return False
        return all(a==b for a,b in zip(self, other))
    def __ne__(self, other):
        return not self.__eq__(other)

    def __abs__(self):
        return self.__class__(map(abs, self))
    def __pos__(self):
        return self.__class__(self)
    def __neg__(self):
        return self.__class__(map(neg, self))

    def __add__(self, other):
        other = self.__class__(other)
        return self.__class__(map(sum, zip(self, other)))
    def __radd__(self, other):
        return self.__add__(other)
    def __sub__(self, other):
        other = self.__class__(other)
        return self.__class__(map(sum, zip(self, -other)))
    def __rsub__(self, other):
        other = self.__class__(other)
        return self.__class__(map(sum, zip(other, -self)))

    def copy(self):
        return self.__class__(self)


class Point(Pair):
    """Represents a 2D location with `x` and `y` properties"""
    _coords = ('x','y')

    def __init__(self, *args, **kwargs):
        super(Point, self).__init__(*args, **kwargs)

    # lib.geometry methods (accept either x,y pairs or Point args)

    def angle(self, x=0, y=0):
        if isinstance(x, Point):
            x, y = iter(x)
        theta = geometry.angle(self.x, self.y, x, y)
        basis={DEGREES:360.0, RADIANS:2*pi, PERCENT:1.0}
        return (theta*basis[_ctx._thetamode])/basis[DEGREES]

    def distance(self, x=0, y=0):
        if isinstance(x, Point):
            x, y = iter(x)
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

    def _get_x(self):
        return self._x
    def _set_x(self, x):
        if not numlike(x):
            raise DeviceError('Point: x coordinate must be int or float (not %r)'%type(x))
        self._x = float(x)
    x = property(_get_x, _set_x)

    def _get_y(self):
        return self._y
    def _set_y(self, y):
        if not numlike(y):
            raise DeviceError('Point: y coordinate must be int or float (not %r)'%type(y))
        self._y = float(y)
    y = property(_get_y, _set_y)


class Size(Pair):
    """Represents a 2D area with `width` and `height` properties"""
    _coords = ('w','h')

    def __init__(self, *args, **kwargs):
        super(Size, self).__init__(*args, **kwargs)

    def _get_w(self):
        return self._w
    def _set_w(self, w):
        if not numlike(w) and w is not None:
            raise DeviceError('Size: width must be an int or float (not %r)'%type(w))
        elif w:
            w = float(w)
        self._w = w
    w = width = property(_get_w, _set_w)

    def _get_h(self):
        return self._h
    def _set_h(self, h):
        if not numlike(h) and h is not None:
            raise DeviceError('Size: height must be an int or float (not %r)'%type(h))
        elif h:
            h = float(h)
        self._h = h
    h = height = property(_get_h, _set_h)


class Region(object):
    """Represents a rectangular region combining a Point and a Size (as `origin` and `size`)"""
    def __init__(self, *args, **kwargs):
        self._origin = Point()
        self._size = Size()

        if len(args) == 4: # (x, y, w, h)
            for k,v in zip('xywh', args):
                setattr(self, k, v)
        elif len(args)==3:
            try: # (x, y, (w,h))
                for k,v in zip(['x','y','size'], args):
                    setattr(self, k, v)
            except: # ((x,y), w, h)
                for k,v in zip(['origin','w','h'], args):
                    setattr(self, k, v)
        elif len(args)==2: # ((x,y), (w,h)) or (Point, Size)
            self.origin, self.size = args
        elif len(args)==1 and len(args[0])==4: # ([x,y,w,h]):
            for k,v in zip('xywh', args[0]):
                setattr(self, k, v)
        elif len(args)==1: # (Region)
            self.origin, self.size = args[0]
        elif args:
            badbox = 'Region requires a single Point and Size pair'
            raise DeviceError(badbox)
        else: # (**dict)
            self.w = kwargs.get('width', kwargs.get('w', 0))
            self.h = kwargs.get('height', kwargs.get('h', 0))
            self.x = kwargs.get('x', 0.0)
            self.y = kwargs.get('y', 0.0)

    @trim_zeroes
    def __repr__(self):
        vals = [getattr(self, attr) for attr in 'x','y','w','h']
        dims = ["%.3f"%d if numlike(d) else repr(d) for d in vals]
        return 'Region(x=%s, y=%s, w=%s, h=%s)' % tuple(dims)

    def __eq__(self, other):
        if other is None: return False
        other = Region(other)
        return self.origin==other.origin and self.size==other.size

    def __ne__(self, other):
        return not self.__eq__(other)

    def __iter__(self):
        # allow for assignments like: (x,y), (w,h) = Region()
        return iter([self.origin, self.size])

    def union(self, *args):
        """Return a new Region which fully encloses the existing Region and the arguments"""
        other = Region(*args)
        return Region(NSUnionRect(self, other))

    def intersect(self, *args):
        """Return a new Region with the in-common portion of this Region and the arguments"""
        other = Region(*args)
        return Region(NSIntersectionRect(self, other))

    def offset(self, dx, dy=None):
        """Return a new Region whose origin is shifted by dx/dy or a Point object"""
        try: dx, dy = dx # accept an x/y tuple as 1st arg
        except: dy = dx if dy is None else dy # also accept a single float and copy it
        return Region(NSOffsetRect(self, dx, dy))

    def inset(self, dx, dy=None):
        """Return a new Region whose edges are moved `inward' by dx/dy or a Point/Size object"""
        try: dx, dy = dx # accept an x/y tuple as 1st arg
        except: dy = dx if dy is None else dy # also accept a single float and copy it
        return Region(NSInsetRect(self, dx, dy))

    def _get_origin(self):
        return self._origin
    def _set_origin(self, pt):
        self._origin = Point(pt)
    origin = property(_get_origin, _set_origin)

    def _get_x(self):
        return self._origin.x
    def _set_x(self, x):
        self._origin.x = x
    x = property(_get_x, _set_x)

    def _get_y(self):
        return self._origin.y
    def _set_y(self, y):
        self._origin.y = y
    y = property(_get_y, _set_y)

    def _get_size(self):
        return self._size
    def _set_size(self, dims):
        self._size = Size(dims)
    size = property(_get_size, _set_size)

    def _get_w(self):
        return self._size.w
    def _set_w(self, w):
        self._size.w = w
    w = width = property(_get_w, _set_w)

    def _get_h(self):
        return self._size.h
    def _set_h(self, h):
        self._size.h = h
    h = height = property(_get_h, _set_h)


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

    def apply(self, obj):
        from .bezier import Bezier
        if isinstance(obj, (Bezier, NSBezierPath)):
            return self.transformBezier(obj)
        elif isinstance(obj, (Point, NSPoint)):
            return self.transformPoint(obj)
        elif isinstance(obj, (Size, NSSize)):
            return self.transformSize(obj)
        elif isinstance(obj, (Region, NSRect)):
            return self.transformRegion(obj)
        else:
            wrongtype = "Can only transform Beziers, Points, Sizes, and Regions"
            raise DeviceError(wrongtype)

    def transformPoint(self, point):
        return Point(self._nsAffineTransform.transformPoint_(tuple(point)))

    def transformSize(self, size):
        return Size(self._nsAffineTransform.transformSize_(tuple(size)))

    def transformRegion(self, rect):
        origin = self.transformPoint(rect.origin)
        size = self.transformSize(rect.size)
        return Region(origin, size)

    def transformBezier(self, path):
        if isinstance(path, NSBezierPath):
            return self._nsAffineTransform.transformBezierPath_(path)

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
    _dpx = {"px":1.0, "inch":72.0, "pica":12.0, "cm":72/2.54, "mm":72/.254}

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

