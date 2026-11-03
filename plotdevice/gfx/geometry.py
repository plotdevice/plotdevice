# encoding: utf-8
import os
import re
import json
import warnings
import math
import operator
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import trim_zeroes, numlike
from ..lib import pathmatics

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

# the matrix of no effect
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

# rotation modes
DEGREES = "degrees"
RADIANS = "radians"
PERCENT = "percent"

# maths
pi = math.pi
tau = 2*pi

def _pivot(matrix, cx, cy, tx=0.0, ty=0.0):
    """Apply `matrix` at cx/cy, then translate by tx/ty"""
    a, b, c, d, mx, my = matrix
    return (a, b, c, d, mx + cx + tx - (a * cx + c * cy), my + cy + ty - (b * cx + d * cy))

def _hull(matrix, x0, y0, w0, h0):
    """The bounding box of a rect mapped through `matrix`"""
    a, b, c, d, tx, ty = matrix
    corners = [(cx, cy) for cx in (x0, x0 + w0) for cy in (y0, y0 + h0)]
    xs = [a * cx + c * cy + tx for cx, cy in corners]
    ys = [b * cx + d * cy + ty for cx, cy in corners]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

### tuple-like objects for grid dimensions ###

class Pair(object):
    """Base class for Point & Size objects (with basic arithmetic support)"""
    __slots__ = '_a', '_b'
    __hash__ = None

    def _arith(self, op, other, reflected=False):
        if type(other) is not self.__class__:
            other = self.__class__(other, other) if numlike(other) else self.__class__(other)
        oa, ob = other._a, other._b
        if reflected:
            return self.__class__(op(oa, self._a), op(ob, self._b))
        return self.__class__(op(self._a, oa), op(self._b, ob))

    def __iter__(self):
        # allow for assignments like: x,y = Point()
        yield self._a
        yield self._b

    def __eq__(self, other):
        try:
            return all(a==b for a,b in zip(self, other))
        except:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __abs__(self): return self.__class__(abs(self._a), abs(self._b))
    def __pos__(self): return self.__class__(self._a, self._b)
    def __neg__(self): return self.__class__(-self._a, -self._b)
    def __add__(self, other):  return self._arith(operator.add, other)
    def __radd__(self, other): return self._arith(operator.add, other, reflected=True)
    def __sub__(self, other):  return self._arith(operator.sub, other)
    def __rsub__(self, other): return self._arith(operator.sub, other, reflected=True)
    def __mul__(self, other):  return self._arith(operator.mul, other)
    def __rmul__(self, other): return self._arith(operator.mul, other, reflected=True)
    def __floordiv__(self, other): return self._arith(operator.floordiv, other)
    def __rfloordiv__(self, other): return self._arith(operator.floordiv, other, reflected=True)
    def __truediv__(self, other):  return self._arith(operator.truediv, other)
    def __rtruediv__(self, other): return self._arith(operator.truediv, other, reflected=True)

    def copy(self):
        return self.__class__(self)


class Point(Pair):
    """Represents a 2D location with `x` and `y` properties"""
    __slots__ = ()

    def __init__(self, *vals, **kwargs):
        plain = len(vals) == 2 and type(vals[0]) in (int, float) and type(vals[1]) in (int, float)
        if plain:
            # fast path for plain numbers & copies
            self._a, self._b = float(vals[0]), float(vals[1])
        elif len(vals) == 1 and type(vals[0]) is Point:
            self._a, self._b = vals[0]._a, vals[0]._b
        elif len(vals) == 2:
            self.x, self.y = vals
        elif vals:
            try:
                self.x, self.y = vals[0]
            except:
                baddims = 'Point requires a single coordinate pair'
                raise DeviceError(baddims)
        elif not kwargs:
            self._a = self._b = 0.0
        else:
            # kwargs will only be used if there are no positional args
            self.x = kwargs.get('x', 0)
            self.y = kwargs.get('y', 0)

    @trim_zeroes
    def __repr__(self):
        return "Point(%.3f, %.3f)" % (self.x, self.y)

    # lib.pathmatics methods (accept either x,y pairs or Point args)

    def angle(self, x=0, y=0):
        if isinstance(x, Point):
            x, y = iter(x)
        theta = pathmatics.angle(self.x, self.y, x, y)
        basis={DEGREES:360.0, RADIANS:2*pi, PERCENT:1.0}
        return (theta*basis[_ctx._thetamode])/basis[DEGREES]

    def distance(self, x=0, y=0):
        if isinstance(x, Point):
            x, y = iter(x)
        return pathmatics.distance(self.x, self.y, x, y)

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
        return Point(pathmatics.reflect(self.x, self.y, x, y, d, a))

    def coordinates(self, distance, angle):
        angle = _ctx._angle(angle, DEGREES)
        return Point(pathmatics.coordinates(self.x, self.y, distance, angle))

    def _get_x(self):
        return self._a
    def _set_x(self, x):
        if not numlike(x):
            raise DeviceError('Point: x coordinate must be int or float (not %r)'%type(x))
        self._a = float(x)
    x = property(_get_x, _set_x)

    def _get_y(self):
        return self._b
    def _set_y(self, y):
        if not numlike(y):
            raise DeviceError('Point: y coordinate must be int or float (not %r)'%type(y))
        self._b = float(y)
    y = property(_get_y, _set_y)


class Size(Pair):
    """Represents a 2D area with `width` and `height` properties"""
    __slots__ = ()

    def __init__(self, *vals, **kwargs):
        # fast path for plain numbers & copies
        plain = len(vals) == 2 and (vals[0] is None or type(vals[0]) in (int, float)) and \
                (vals[1] is None or type(vals[1]) in (int, float))
        if plain:
            w, h = vals
            self._a, self._b = (float(w) if w else w), (float(h) if h else h)
        elif len(vals) == 1 and type(vals[0]) is Size:
            self._a, self._b = vals[0]._a, vals[0]._b
        elif len(vals) == 2:
            self.w, self.h = vals
        elif vals:
            try:
                self.w, self.h = vals[0]
            except:
                baddims = 'Size requires a single coordinate pair'
                raise DeviceError(baddims)
        elif not kwargs:
            self._a = self._b = 0
        else:
            # kwargs will only be used if there are no positional args
            kwargs = {k[0]:v for k,v in kwargs.items()}
            self.w = kwargs.get('w', 0)
            self.h = kwargs.get('h', 0)

    @trim_zeroes
    def __repr__(self):
        return "Size(%.3f, %.3f)" % (self.w, self.h)

    def _get_w(self):
        return self._a
    def _set_w(self, w):
        if not numlike(w) and w is not None:
            raise DeviceError('Size: width must be an int or float (not %r)'%type(w))
        elif w:
            w = float(w)
        self._a = w
    w = width = property(_get_w, _set_w)

    def _get_h(self):
        return self._b
    def _set_h(self, h):
        if not numlike(h) and h is not None:
            raise DeviceError('Size: height must be an int or float (not %r)'%type(h))
        elif h:
            h = float(h)
        self._b = h
    h = height = property(_get_h, _set_h)


class Region(object):
    """Represents a rectangular region combining a Point and a Size (as `origin` and `size`)

    Syntax:
        Region(x, y, w, h)
        Region(x, y, Size)
        Region(Point, x, y)
        Region(Point, Size)
    """
    __slots__ = ('_origin', '_size')
    opts = ('x','y','w','h','width','height')

    def __init__(self, *args, **kwargs):
        # fast paths for the usual forms
        count = 0 if kwargs else len(args)
        if count == 1 and type(args[0]) is Region:
            self._origin, self._size = Point(args[0]._origin), Size(args[0]._size)
            return
        if count == 1 and isinstance(args[0], NSRect):
            (x, y), (w, h) = args[0]
            self._origin, self._size = Point(x, y), Size(w, h)
            return
        if 2 <= count <= 4 and type(args[0]) in (int, float) and type(args[1]) in (int, float):
            # a None dim needs both dims given
            w, h = (args[2:] + (0, 0))[:2]
            plain_w = type(w) in (int, float) or (w is None and count == 4)
            plain_h = type(h) in (int, float) or (h is None and count == 4)
            if plain_w and plain_h:
                self._origin, self._size = Point(args[0], args[1]), Size(w, h)
                return
        if count == 2 and type(args[0]) in (tuple, Point) and type(args[1]) in (tuple, Size):
            origin, size = args
            plain_origin = type(origin) is Point or (len(origin) == 2 and all(type(v) in (int, float) for v in origin))
            plain_size = type(size) is Size or (len(size) == 2 and all(v is None or type(v) in (int, float) for v in size))
            if plain_origin and plain_size:
                self._origin, self._size = Point(*origin), Size(*size)
                return

        self._origin = Point()
        self._size = Size()

        # process the positional args
        self._parse(args)

        # allow kwargs to override
        for k,v in kwargs.items():
            if k not in Region.opts:
                badarg = 'Valid args for Region are %s (not %r)' % ("/".join(Region.opts), k)
                raise DeviceError(badarg)
            setattr(self, k[0], v)

    def _parse(self, coords):
        """Look for a Point and Size (or at least a Point and width-val) in an arg array

        Any valid coordinates found in the `coords` will be merged into the object's current
        measurements. If invalid syntax was used, raises a DeviceError"""

        # return immediately if there's nothing to do or everything's prepared
        if coords:
            if isinstance(coords[0], (Region, NSRect)):
                self.origin, self.size = coords[0]
                return

            # plain x/y or x/y/w numbers can only match one pattern
            plain_numbers = len(coords) in (2, 3) and all(type(c) in (int, float) for c in coords)
            if plain_numbers and len(coords) == 2:
                self.origin = parse_coords(coords, [Point])
                return
            if plain_numbers and len(coords) == 3:
                self.origin, self.width = parse_coords(coords, [Point,float])
                return

            # try to unpack a full rect or at least an origin from the args
            try:
                self.origin, self.size = parse_coords(coords, [Point,Size])
            except Exception as e_orig:
                try:
                    self.origin, self.width = parse_coords(coords, [Point,float])
                except:
                    try:
                        self.origin = parse_coords(coords, [Point])
                    except:
                        raise e_orig

    @trim_zeroes
    def __repr__(self):
        vals = [getattr(self, attr) for attr in ('x','y','w','h')]
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

    def __hash__(self):
        return hash(tuple(getattr(self, attr) for attr in ('x','y','w','h')))

    def union(self, *args):
        """Return a new Region which fully encloses the existing Region and the arguments"""
        # empty regions are left out, as in NSUnionRect
        other = Region(*args)
        (x0, y0), (w0, h0) = self._origin, self._size
        (x1, y1), (w1, h1) = other._origin, other._size
        empty, other_empty = w0 <= 0 or h0 <= 0, w1 <= 0 or h1 <= 0
        if empty and other_empty:
            return Region(0.0, 0.0, 0.0, 0.0)
        if empty or other_empty:
            return Region(self if other_empty else other)
        left, top = min(x0, x1), min(y0, y1)
        return Region(left, top, max(x0 + w0, x1 + w1) - left, max(y0 + h0, y1 + h1) - top)

    def intersect(self, *args):
        """Return a new Region with the in-common portion of this Region and the arguments"""
        # matches NSIntersectionRect
        other = Region(*args)
        (x0, y0), (w0, h0) = self._origin, self._size
        (x1, y1), (w1, h1) = other._origin, other._size
        left, top = max(x0, x1), max(y0, y1)
        right, bottom = min(x0 + w0, x1 + w1), min(y0 + h0, y1 + h1)
        overlap = w0 > 0 and h0 > 0 and w1 > 0 and h1 > 0 and right > left and bottom > top
        if not overlap:
            return Region(0.0, 0.0, 0.0, 0.0)
        return Region(left, top, right - left, bottom - top)

    def shift(self, dx, dy=None):
        """Return a new Region whose origin is shifted by dx/dy or a Point object"""
        try: dx, dy = dx # accept an x/y tuple as 1st arg
        except: dy = dx if dy is None else dy # also accept a single float and copy it
        return Region(NSOffsetRect(self, dx, dy))

    def inset(self, dx, dy=None):
        """Return a new Region whose edges are moved `inward' by dx/dy or a Point/Size object"""
        try: dx, dy = dx # accept an x/y tuple as 1st arg
        except: dy = dx if dy is None else dy # also accept a single float and copy it
        return Region(NSInsetRect(self, dx, dy))

    def copy(self):
        return Region(self)

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

    def _get_left(self):
        return self._origin.x
    def _set_left(self, left):
        self._origin.x = left
        self._size.w += self._origin.x - left
    l = left = property(_get_left, _set_left)

    def _get_y(self):
        return self._origin.y
    def _set_y(self, y):
        self._origin.y = y
    y = property(_get_y, _set_y)

    def _get_top(self):
        return self._origin.y
    def _set_top(self, top):
        self._origin.y = top
        self._size.h += self._origin.y - top
    t = top = property(_get_top, _set_top)

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

    def _get_right(self):
        return self._origin.x + self._size.w
    def _set_right(self, right):
        self._size.w = right - self._origin.x
    r = right = property(_get_right, _set_right)

    def _get_h(self):
        return self._size.h
    def _set_h(self, h):
        self._size.h = h
    h = height = property(_get_h, _set_h)

    def _get_bottom(self):
        return self._origin.y + self._size.h
    def _set_bottom(self, bottom):
        self._size.h = bottom - self._origin.y
    b = bottom = property(_get_bottom, _set_bottom)

### argument destructuring madness (a.k.a. wouldn't multimethods be nice...) ###

def _abort(stream, objs, types, orig):
    needed = [t.__name__ for t in types]
    got = [o.__class__.__name__ for o in objs] + [arg.__class__.__name__ for arg in stream]
    invalid = 'Invalid coordinates (looking for %r, found %r in %r)' % (needed, got, orig)
    raise DeviceError(invalid)

def parse_coords(coords, types):
    """Unpacks (and validates) *args tuples representing sets of geometric or numeric types

    The `types` arg should be a list of classes to be `found' in the coords list. Currently,
    Point, Size, and float are supported. The elements of the coords list will be grouped
    and coerced into the specified types. If the coords list can't be pattern-matched
    precisely into the given sequence of types, an exception is raised.
    """

    # fast path for exactly enough plain numbers
    needed = sum(1 if cls is float else 2 for cls in types)
    if len(coords) == needed and all(type(c) in (int, float) for c in coords):
        objs, at = [], 0
        for cls in types:
            if cls is float:
                objs.append(float(coords[at]))
                at += 1
            else:
                objs.append(cls(coords[at], coords[at + 1]))
                at += 2
        return objs[0] if len(types) == 1 else objs

    # make a mutable copy we can traverse and an output list to shift into
    stream = list(coords)
    objs = []

    # splice in a Point + Size for any Regions passed in the args
    for i in range(len(stream)-1,-1,-1):
        if isinstance(stream[i], Region):
            stream[i:i+1] = [stream[i].origin, stream[i].size]

    for cls in types:
        # crash on insufficient args
        if not stream:
            _abort(stream, objs, types, coords)

        # unpack the next 1 or 2 args into a Point/Size/float (or die trying)
        try:
            if cls is not float and numlike(stream[0]) or stream[0] is None:
                obj = cls(stream[0], stream[1])
                del stream[:2]
            else:
                obj = cls(stream[0])
                del stream[0]
        except:
            _abort(stream, objs, types, coords)

        objs.append(obj)

    # crash on extraneous args
    if stream:
        _abort(stream, objs, types, coords)

    # exclude the container list if only one arg is returned
    if len(types) == 1:
        return objs[0]
    return objs


### Unit-conversions for canvas measurements ###

class MagicNumber(object):
    # be a well-behaved pseudo-number (based on the float in self.value)
    def __int__(self): return int(self.value)
    def __float__(self): return float(self.value)
    def __index__(self): return int(self.value)
    def __eq__(self, n): return n == self.value
    def __hash__(self): return hash(self.value)
    def __lt__(self, n): return self.value < n
    def __gt__(self, n): return self.value > n
    def __le__(self, n): return self.value <= n
    def __ge__(self, n): return self.value >= n

    def __abs__(self): return abs(self.value)
    def __pos__(self): return +self.value
    def __neg__(self): return -self.value
    def __trunc__(self): return math.trunc(self.value)
    def __round__(self, ndigits=None): return round(self.value, ndigits)
    def __format__(self, spec): return format(self.value, spec)

    def __add__(self, n): return self.value + n
    def __sub__(self, n): return self.value - n
    def __mul__(self, n): return self.value * n
    def __truediv__(self, n): return self.value/n
    def __floordiv__(self, n): return self.value // n
    def __mod__(self, n): return self.value % n
    def __pow__(self, n): return self.value ** n

    def __radd__(self, n): return n + self.value
    def __rsub__(self, n): return n - self.value
    def __rmul__(self, n): return n * self.value
    def __rtruediv__(self, n): return n / self.value
    def __rfloordiv__(self, n): return n // self.value
    def __rmod__(self, n): return n % self.value
    def __rpow__(self, n): return n ** self.value

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
    _dpx = {"px":1.0, "inch":72.0, "pica":12.0, "cm":72/2.54, "mm":72/25.4}

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        if self.basis==_ctx._grid.dpx:
            return '<one %s>' % self.name
        return '<one %s (%0.3f canvas units)>'%(self.name, self.value)

    @property
    def value(self):
        """Size of this unit in terms of the current canvas unit"""
        return self.basis/_ctx._grid.dpx

    @property
    def basis(self):
        """Size of this unit of measure in Postscript points"""
        return Unit._dpx[self.name]

# create a module-level variable for each of the standard units
globals().update({u:Unit(u) for u in Unit._dpx})


### NSAffineTransform wrapper used for positioning Grobs in a Context ###

class Transform(object):

    def __init__(self, transform=None):
        if transform is None:
            transform = NSAffineTransform.transform()
        elif isinstance(transform, Transform):
            transform = nscopy(transform._nsAffineTransform)
        elif isinstance(transform, NSAffineTransform):
            transform = nscopy(transform)
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
        if isinstance(x, (Pair, list, tuple)):
            x, y = x
        xf = Transform()
        xf._nsAffineTransform.translateXBy_yBy_(x, y)
        if opt.get('rollback'):
            xf._rollback = {"_transform":self.copy()}
        self.prepend(xf)
        return xf

    def scale(self, x=1, y=None, **opt):
        if isinstance(x, (Pair, list, tuple)):
            x, y = x
        elif y is None:
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
        from .bezier import Bezier, PDPath
        if isinstance(obj, (Bezier, NSBezierPath, PDPath)):
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
        from .bezier import Bezier, PDPath
        if isinstance(path, NSBezierPath):
            return self._nsAffineTransform.transformBezierPath_(path)
        elif isinstance(path, PDPath):
            return path.transformed(tuple(self.matrix))

        if isinstance(path, Bezier):
            path = path.copy()
        else:
            wrongtype = "Can only transform Beziers"
            raise DeviceError(wrongtype)
        path._pdpath = path._pdpath.transformed(tuple(self.matrix))
        return path

    def transformBezierPath(self, path):
        return self.transformBezier(path)

    @property
    def transform(self):
        warnings.warn("The 'transform' attribute is deprecated. Please use _nsAffineTransform instead.", FutureWarning, stacklevel=2)
        return self._nsAffineTransform
