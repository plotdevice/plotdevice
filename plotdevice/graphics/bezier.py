# encoding: utf-8
import warnings
from AppKit import *
from Foundation import *

from plotdevice import DeviceError
from .grobs import TransformMixin, ColorMixin, Color, Transform, Grob
from .grobs import CENTER, INHERIT, Region, Size, Point, _save, _restore
from ..util import trim_zeroes, _copy_attr, _copy_attrs, _flatten
from ..lib import pathmatics

_ctx = None
__all__ = ("Bezier", "Curve", "Mask",                   # new names
           "BezierPath", "PathElement", "ClippingPath", # compat. aliases
           "MOVETO", "LINETO", "CURVETO", "CLOSE",
           "MITER", "ROUND", "BEVEL", "BUTT", "SQUARE",
           "NORMAL","FORTYFIVE",
)

# path commands
MOVETO = NSMoveToBezierPathElement
LINETO = NSLineToBezierPathElement
CURVETO = NSCurveToBezierPathElement
CLOSE = NSClosePathBezierPathElement

# linejoin styles and nstypes
MITER = "miter"
ROUND = "round"
BEVEL = "bevel"
_JOINSTYLE=dict(
    miter = NSMiterLineJoinStyle,
    round = NSRoundLineJoinStyle,
    bevel = NSBevelLineJoinStyle,
)

# endcap styles and nstypes
BUTT = "butt"
ROUND = "round"
SQUARE = "square"
_CAPSTYLE=dict(
    butt = NSButtLineCapStyle,
    round = NSRoundLineCapStyle,
    square = NSSquareLineCapStyle,
)

# arrow styles
NORMAL = "normal"
FORTYFIVE = "fortyfive"

class PenMixin(Grob):
    stateAttributes = ('_strokewidth', '_capstyle', '_joinstyle', '_dashstyle')

    """Mixin class for linestyle support.
    Adds the _capstyle, _joinstyle, _dashstyle, and _strokewidth attributes to the class."""

    def __init__(self, **kwargs):
        super(PenMixin, self).__init__(**kwargs)
        self.strokewidth = kwargs.get('nib', kwargs.get('strokewidth', INHERIT))
        self.capstyle = kwargs.get('cap', kwargs.get('capstyle', INHERIT))
        self.joinstyle = kwargs.get('join', kwargs.get('joinstyle', INHERIT))
        self.dashstyle = kwargs.get('dash', kwargs.get('dashstyle', INHERIT))

    def _get_strokewidth(self):
        return _ctx._strokewidth if self._strokewidth is INHERIT else self._strokewidth
    def _set_strokewidth(self, strokewidth):
        self._strokewidth = max(strokewidth, 0.0001)
    nib = strokewidth = property(_get_strokewidth, _set_strokewidth)

    def _get_capstyle(self):
        return _ctx._capstyle if self._capstyle is INHERIT else self._capstyle
    def _set_capstyle(self, style):
        from bezier import BUTT, ROUND, SQUARE
        if style not in (INHERIT, BUTT, ROUND, SQUARE):
            badstyle = 'Line cap style should be BUTT, ROUND or SQUARE.'
            raise DeviceError(badstyle)
        self._capstyle = style
    cap = capstyle = property(_get_capstyle, _set_capstyle)

    def _get_joinstyle(self):
        return _ctx._joinstyle if self._joinstyle is INHERIT else self._joinstyle
    def _set_joinstyle(self, style):
        from bezier import MITER, ROUND, BEVEL
        if style not in (INHERIT, MITER, ROUND, BEVEL):
            badstyle = 'Line join style should be MITER, ROUND or BEVEL.'
            raise DeviceError(badstyle)
        self._joinstyle = style
    join = joinstyle = property(_get_joinstyle, _set_joinstyle)

    def _get_dashstyle(self):
        return _ctx._dashstyle if self._dashstyle is INHERIT else self._dashstyle
    def _set_dashstyle(self, *segments):
        if None in segments or INHERIT in segments:
            self._dashstyle = segments[0]
        else:
            steps = map(int, _flatten(segments))
            if len(steps)%2:
                steps += steps[-1:] # assume even spacing for omitted skip sizes
            self._dashstyle = steps
    dash = dashstyle = property(_get_dashstyle, _set_dashstyle)


class Bezier(TransformMixin, ColorMixin, PenMixin, Grob):
    """A Bezier provides a wrapper around NSBezierPath."""
    kwargs = ('fill', 'stroke', 'strokewidth', 'capstyle', 'joinstyle', 'nib', 'cap', 'join')

    def __init__(self, path=None, immediate=False, **kwargs):
        super(Bezier, self).__init__(**kwargs)
        self._segment_cache = None
        self._finished = False

        # path arg might contain a list of point tuples, a bezier to copy, or a raw
        # nsbezier reference to use as the backing store. otherwise start with a
        # fresh path with no points
        if path is None:
            self._nsBezierPath = NSBezierPath.bezierPath()
        elif isinstance(path, (list,tuple)):
            self._nsBezierPath = NSBezierPath.bezierPath()
            self.extend(path)
        elif isinstance(path, Bezier):
            self._nsBezierPath = path._nsBezierPath.copy()
            _copy_attrs(path, self, self.stateAttributes)
        elif isinstance(path, NSBezierPath):
            self._nsBezierPath = path
        else:
            badpath = "Don't know what to do with %s." % path
            raise DeviceError(badpath)

        # use any plotstyle settings in kwargs (the rest will be inherited)
        for attr, val in kwargs.items():
            if attr in Bezier.kwargs:
                setattr(self, attr, _copy_attr(val))
        self._overrides = {k:_copy_attr(v) for k,v in kwargs.items() if k in Bezier.kwargs}
        self._autoclose = kwargs.get('close', _ctx._autoclosepath)
        self._autodraw = kwargs.get('draw', False)

        # finish the path (and potentially draw it) immediately if flagged to do so.
        # in practice, `immediate` is only passed when invoked by the `bezier()` command
        # with a preexisting point-set or bezier `path` argument.
        if immediate and kwargs.get('draw',True):
            self._autofinish()

    def __enter__(self):
        if self._finished:
            reentrant = "Bezier already complete. Only use `with bezier()` when defining a path using moveto, lineto, etc."
            raise DeviceError(reentrant)
        elif _ctx._path is not None:
            recursive = "Already defining a bezier path. Don't nest `with bezier()` blocks"
            raise DeviceError(recursive)
        _ctx._saveContext()
        _ctx._path = self
        return self

    def __exit__(self, type, value, tb):
        self._autofinish()
        _ctx._path = None
        _ctx._restoreContext()

    def _autofinish(self):
        if self._autoclose:
            self.closepath()
        if self._autodraw:
            self.draw()
        self._finished = True

    @property
    def path(self):
        warnings.warn("The 'path' attribute is deprecated. Please use _nsBezierPath instead.", DeprecationWarning, stacklevel=2)
        return self._nsBezierPath

    def copy(self):
        return self.__class__(self)

    ### Path methods ###

    def moveto(self, x, y):
        self._segment_cache = None
        self._nsBezierPath.moveToPoint_( (x, y) )

    def lineto(self, x, y):
        self._segment_cache = None
        if self._nsBezierPath.elementCount()==0:
            # use an implicit 0,0 origin if path doesn't have a prior moveto
            self._nsBezierPath.moveToPoint_( (0, 0) )
        self._nsBezierPath.lineToPoint_( (x, y) )

    def curveto(self, x1, y1, x2, y2, x3, y3):
        self._segment_cache = None
        self._nsBezierPath.curveToPoint_controlPoint1_controlPoint2_( (x3, y3), (x1, y1), (x2, y2) )

    def closepath(self):
        self._segment_cache = None
        self._nsBezierPath.closePath()

    def _get_bounds(self):
        try:
            return Region(*self._nsBezierPath.bounds())
        except:
            # Path is empty -- no bounds
            return Region()
    bounds = property(_get_bounds)

    def contains(self, x, y):
        return self._nsBezierPath.containsPoint_((x,y))

    ### Basic shapes ###

    def rect(self, x, y, width, height, radius=None):
        self._segment_cache = None
        if radius is None:
            self._nsBezierPath.appendBezierPathWithRect_( ((x, y), (width, height)) )
        else:
            if isinstance(radius, (int,float,long)):
                radius = (radius, radius)
            elif not isinstance(radius, (list, tuple)) or len(radius)!=2:
                badradius = 'the radius for a rect must be either a number or an (x,y) tuple'
                raise DeviceError(badradius)
            self._nsBezierPath.appendBezierPathWithRoundedRect_xRadius_yRadius_( ((x,y), (width,height)), *radius)

    def oval(self, x, y, width, height):
        self._segment_cache = None
        self._nsBezierPath.appendBezierPathWithOvalInRect_( ((x, y), (width, height)) )

    ellipse = oval

    def line(self, x1, y1, x2, y2):
        self._segment_cache = None
        self._nsBezierPath.moveToPoint_( (x1, y1) )
        self._nsBezierPath.lineToPoint_( (x2, y2) )

    ### List methods ###

    def __getitem__(self, index):
        cmd, el = self._nsBezierPath.elementAtIndex_associatedPoints_(index)
        return Curve(cmd, el)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __len__(self):
        return self._nsBezierPath.elementCount()

    def extend(self, pathElements):
        self._segment_cache = None
        for el in pathElements:
            if isinstance(el, (list, tuple)):
                x, y = el
                if len(self) == 0:
                    cmd = MOVETO
                else:
                    cmd = LINETO
                self.append(Curve(cmd, ((x, y),)))
            elif isinstance(el, Curve):
                self.append(el)
            else:
                wrongtype = "Don't know how to handle %s" % el
                raise DeviceError(wrongtype)

    def append(self, el):
        self._segment_cache = None
        if el.cmd == MOVETO:
            self.moveto(el.x, el.y)
        elif el.cmd == LINETO:
            self.lineto(el.x, el.y)
        elif el.cmd == CURVETO:
            self.curveto(el.ctrl1.x, el.ctrl1.y, el.ctrl2.x, el.ctrl2.y, el.x, el.y)
        elif el.cmd == CLOSE:
            self.closepath()

    @property
    def contours(self):
        return pathmatics.contours(self)

    ### Drawing methods ###

    @property
    def transform(self):
        trans = self._transform.copy()
        if (self._transformmode == CENTER):
            (x, y), (w, h) = self.bounds
            deltax = x+w/2
            deltay = y+h/2
            t = Transform()
            t.translate(-deltax,-deltay)
            trans.prepend(t)
            t = Transform()
            t.translate(deltax,deltay)
            trans.append(t)
        return trans

    def _draw(self):
        _save()
        self.transform.concat()
        if (self._fillcolor):
            self._fillcolor.set()
            self._nsBezierPath.fill()
        if (self._strokecolor):
            self._strokecolor.set()
            self._nsBezierPath.setLineWidth_(self._strokewidth)
            self._nsBezierPath.setLineCapStyle_(_CAPSTYLE[self._capstyle])
            self._nsBezierPath.setLineJoinStyle_(_JOINSTYLE[self._joinstyle])
            if self._dashstyle:
                self._nsBezierPath.setLineDash_count_phase_(self._dashstyle, len(self._dashstyle), 0)
            self._nsBezierPath.stroke()
        _restore()

    ### Geometry ###

    def fit(self, x=None, y=None, width=None, height=None, stretch=False):

        """Fits this path to the specified bounds.

        All parameters are optional; if no parameters are specified, nothing will happen.
        Specifying a parameter will constrain its value:

        - x: The path will be positioned at the specified x value
        - y: The path will be positioned at the specified y value
        - width: The path will be of the specified width
        - height: The path will be of the specified height
        - stretch: If both width and height are defined, either stretch the path or
                   keep the aspect ratio.
        """

        (px, py), (pw, ph) = self.bounds
        t = Transform()
        if x is not None and y is None:
            t.translate(x, py)
        elif x is None and y is not None:
            t.translate(px, y)
        elif x is not None and y is not None:
            t.translate(x, y)
        else:
            t.translate(px, py)
        if width is not None and height is None:
            t.scale(width / pw)
        elif width is None and height is not None:
            t.scale(height / ph)
        elif width is not None and height is not None:
            if stretch:
                t.scale(width /pw, height / ph)
            else:
                t.scale(min(width /pw, height / ph))
        t.translate(-px, -py)
        self._nsBezierPath = t.transformBezierPath(self)._nsBezierPath

    ### Mathematics ###

    def segmentlengths(self, relative=False, n=10):
        if relative: # Use the opportunity to store the segment cache.
            if self._segment_cache is None:
                self._segment_cache = pathmatics.segment_lengths(self, relative=True, n=n)
            return self._segment_cache
        else:
            return pathmatics.segment_lengths(self, relative=False, n=n)

    @property
    def length(self, segmented=False, n=10):
        return pathmatics.length(self, segmented=segmented, n=n)

    def point(self, t):
        return pathmatics.point(self, t)

    def points(self, amount=100):
        if len(self) == 0:
            empty = "The given path is empty"
            raise DeviceError(empty)

        # The delta value is divided by amount - 1, because we also want the last point (t=1.0)
        # If I wouldn't use amount - 1, I fall one point short of the end.
        # E.g. if amount = 4, I want point at t 0.0, 0.33, 0.66 and 1.0,
        # if amount = 2, I want point at t 0.0 and t 1.0
        try:
            delta = 1.0/(amount-1)
        except ZeroDivisionError:
            delta = 1.0

        for i in xrange(amount):
            yield pathmatics.point(delta*i)

    def addpoint(self, t):
        self._nsBezierPath = pathmatics.insert_point(self, t)._nsBezierPath
        self._segment_cache = None

    ### Clipping operations ###

    def intersects(self, other):
        return pathmatics.intersects(self._nsBezierPath, other._nsBezierPath)

    def union(self, other, flatness=0.6):
        return Bezier(pathmatics.union(self._nsBezierPath, other._nsBezierPath, flatness))

    def intersect(self, other, flatness=0.6):
        return Bezier(pathmatics.intersect(self._nsBezierPath, other._nsBezierPath, flatness))

    def difference(self, other, flatness=0.6):
        return Bezier(pathmatics.difference(self._nsBezierPath, other._nsBezierPath, flatness))

    def xor(self, other, flatness=0.6):
        return Bezier(pathmatics.xor(self._nsBezierPath, other._nsBezierPath, flatness))

class BezierPath(Bezier):
    pass # NodeBox compat...

class Curve(object):

    def __init__(self, cmd=None, pts=None):
        self.cmd = cmd
        if cmd == MOVETO:
            assert len(pts) == 1
            self.x, self.y = pts[0]
            self.ctrl1 = Point(pts[0])
            self.ctrl2 = Point(pts[0])
        elif cmd == LINETO:
            assert len(pts) == 1
            self.x, self.y = pts[0]
            self.ctrl1 = Point(pts[0])
            self.ctrl2 = Point(pts[0])
        elif cmd == CURVETO:
            assert len(pts) == 3
            self.ctrl1 = Point(pts[0])
            self.ctrl2 = Point(pts[1])
            self.x, self.y = pts[2]
        elif cmd == CLOSE:
            assert pts is None or len(pts) == 0
            self.x = self.y = 0.0
            self.ctrl1 = Point(0.0, 0.0)
            self.ctrl2 = Point(0.0, 0.0)
        else:
            self.x = self.y = 0.0
            self.ctrl1 = Point()
            self.ctrl2 = Point()

    @trim_zeroes
    def __repr__(self):
        if self.cmd == MOVETO:
            return "Curve(MOVETO, ((%.3f, %.3f),))" % (self.x, self.y)
        elif self.cmd == LINETO:
            return "Curve(LINETO, ((%.3f, %.3f),))" % (self.x, self.y)
        elif self.cmd == CURVETO:
            return "Curve(CURVETO, ((%.3f, %.3f), (%.3f, %s), (%.3f, %.3f))" % \
                (self.ctrl1.x, self.ctrl1.y, self.ctrl2.x, self.ctrl2.y, self.x, self.y)
        elif self.cmd == CLOSE:
            return "Curve(CLOSE)"

    def __eq__(self, other):
        if other is None: return False
        if self.cmd != other.cmd: return False
        return self.x == other.x and self.y == other.y \
            and self.ctrl1 == other.ctrl1 and self.ctrl2 == other.ctrl2

    def __ne__(self, other):
        return not self.__eq__(other)

class PathElement(Curve):
    pass # NodeBox compat...

class Mask(Grob):

    def __init__(self, path):
        self.path = path
        self._grobs = []

    def append(self, grob):
        self._grobs.append(grob)

    def _draw(self):
        _save()
        cp = self.path.transform.transformBezierPath(self.path)
        cp._nsBezierPath.addClip()
        for grob in self._grobs:
            grob._draw()
        _restore()

class ClippingPath(Mask):
    pass # NodeBox compat...
