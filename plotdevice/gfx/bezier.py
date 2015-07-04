# encoding: utf-8
import warnings
from ..lib.cocoa import *
from math import pi, sin, cos, sqrt

from plotdevice import DeviceError
from . import _cg_context
from .atoms import PenMixin, TransformMixin, ColorMixin, EffectsMixin, Grob
from .colors import Color, Gradient, Pattern
from .geometry import CENTER, DEGREES, Transform, Region, Point
from ..util import trim_zeroes, _copy_attr, _copy_attrs, _flatten, numlike
from ..lib import pathmatics

_ctx = None
__all__ = ("Bezier", "Curve", "BezierPath", "PathElement",
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
_JOINSTYLE={MITER:kCGLineJoinMiter, ROUND:kCGLineJoinRound, BEVEL:kCGLineJoinBevel}

# endcap styles and nstypes
BUTT = "butt"
ROUND = "round"
SQUARE = "square"
_CAPSTYLE={BUTT:kCGLineCapButt, ROUND:kCGLineCapRound, SQUARE:kCGLineCapSquare}

# arrow styles
NORMAL = "normal"
FORTYFIVE = "fortyfive"

class Bezier(EffectsMixin, TransformMixin, ColorMixin, PenMixin, Grob):
    """A Bezier provides a wrapper around NSBezierPath."""
    stateAttrs = ('_nsBezierPath', '_fulcrum')
    opts = ('close', 'smooth')

    def __init__(self, path=None, **kwargs):
        super(Bezier, self).__init__(**kwargs)
        self._segment_cache = {} # used by pathmatics
        self._fulcrum = None # centerpoint (set only for center-based primitives)

        # path arg might contain a list of point tuples, a bezier to copy, or a raw
        # nsbezier reference to use as the backing store. otherwise start with a
        # fresh path with no points
        if path is None:
            self._nsBezierPath = NSBezierPath.bezierPath()
        elif isinstance(path, (list,tuple)):
            if isinstance(path[0], Curve):
                self._nsBezierPath = NSBezierPath.bezierPath()
                self.extend(path)
            else:
                p = pathmatics.findpath(path, 1.0 if kwargs.get('smooth') else 0.0)
                self._nsBezierPath = p._nsBezierPath
        elif isinstance(path, Bezier):
            _copy_attrs(path, self, Bezier.stateAttrs)
        elif isinstance(path, NSBezierPath):
            self._nsBezierPath = path.copy()
        else:
            badpath = "Don't know what to do with %s." % path
            raise DeviceError(badpath)

        # decide what needs to be done at the end of the `with` context
        self._needs_closure = kwargs.get('close', False)

    def __enter__(self):
        self._rollback = {attr:getattr(_ctx,attr) for attr in ['_path','_transform','_transformmode']}
        _ctx._path = self
        _ctx._transform = Transform()
        return self

    def __exit__(self, type, value, tb):
        self._autoclose()
        for attr, val in self._rollback.items():
            setattr(_ctx, attr, val)

    def copy(self):
        clone = Bezier()
        clone.inherit(self)
        return clone

    ### Path methods ###

    def moveto(self, x, y):
        self._nsBezierPath.moveToPoint_( (x, y) )

    def lineto(self, x, y):
        if self._nsBezierPath.elementCount()==0:
            # use an implicit 0,0 origin if path doesn't have a prior moveto
            self._nsBezierPath.moveToPoint_( (0, 0) )
        self._nsBezierPath.lineToPoint_( (x, y) )

    def curveto(self, x1, y1, x2, y2, x3, y3):
        self._nsBezierPath.curveToPoint_controlPoint1_controlPoint2_( (x3, y3), (x1, y1), (x2, y2) )

    def arcto(self, x1, y1, x2=None, y2=None, radius=None, ccw=False):
        if x2 is not None and y2 is not None:
            # arc toward the x1,y1 control point then turn toward the x2,y2 dest point. round off the
            # triangle created between the current point, the control point, and the dest point with
            # an arc of the given radius.
            #
            # Take a look at the Adding Arcs section of apple's docs for some important edge cases:
            # https://developer.apple.com/library/mac/documentation/Cocoa/Conceptual/CocoaDrawingGuide/Paths/Paths.html
            radius = 1.0 if radius is None else radius
            self._nsBezierPath.appendBezierPathWithArcFromPoint_toPoint_radius_( (x1,y1), (x2,y2), radius)
            self._nsBezierPath.lineToPoint_( (x2,y2) )
        else:
            # create a unitary semicircle...
            k = 0.5522847498 / 2.0
            p = NSBezierPath.bezierPath()
            p.moveToPoint_((0,0))
            p.curveToPoint_controlPoint1_controlPoint2_((.5,-.5), (0,-k), (.5-k,-.5))
            p.curveToPoint_controlPoint1_controlPoint2_((1,0), (.5+k,-.5), (1,-k))

            # ...and transform it to match the endpoints
            src = self._nsBezierPath.currentPoint()
            theta = pathmatics.angle(src.x, src.y, x1, y1)
            dw = pathmatics.distance(src.x, src.y, x1, y1)
            dh = dw*(-1.0 if ccw else 1.0)
            t = Transform()
            t.translate(src.x,src.y)
            t.rotate(-theta)
            t.scale(dw, dh)
            p.transformUsingAffineTransform_(t._nsAffineTransform)
            self.extend(Bezier(p)[1:]) # omit the initial moveto in the semicircle

    def closepath(self):
        self._nsBezierPath.closePath()

    def _autoclose(self):
        if self._needs_closure:
            self.closepath()
            self._needs_closure = False

    ### Basic shapes (origin + size) ###

    def rect(self, x, y, width, height, radius=None):
        if radius is None:
            self._nsBezierPath.appendBezierPathWithRect_( ((x, y), (width, height)) )
        else:
            if numlike(radius):
                radius = (radius, radius)
            elif not isinstance(radius, (list, tuple)) or len(radius)!=2:
                badradius = 'the radius for a rect must be either a number or an (x,y) tuple'
                raise DeviceError(badradius)
            self._nsBezierPath.appendBezierPathWithRoundedRect_xRadius_yRadius_( ((x,y), (width,height)), *radius)

    def oval(self, x, y, width, height, rng=None, ccw=False, close=False):
        # range = None:      draw a full ellipse
        # range = 180:       draws a semicircle
        # range = (90, 180): draws a quadrant in the lower left
        if rng is None:
            self._nsBezierPath.appendBezierPathWithOvalInRect_( ((x, y), (width, height)) )
        else:
            # convert angles from canvas units to degrees
            if numlike(rng):
                start, end = sorted([0, rng])
            else:
                start, end = rng
            if ccw:
                start, end = -start, -end
            start, end = _ctx._angle(start, DEGREES), _ctx._angle(end, DEGREES)

            p = NSBezierPath.bezierPath()
            p.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_((.5,.5), .5, start, end, ccw)
            t = Transform()
            t.translate(x,y)
            t.scale(width, height)
            p.transformUsingAffineTransform_(t._nsAffineTransform)
            self._nsBezierPath.appendBezierPath_(p)
            if close:
                # optionally close the path with a chord
                self._nsBezierPath.closePath()
            self._fulcrum = Point(x+width/2, y+width/2)
    ellipse = oval

    def line(self, x1, y1, x2, y2, ccw=None):
        if ccw in (True, False):
            self.moveto(x1,y1)
            self.arcto(x2,y2, ccw=ccw)
        else:
            self._nsBezierPath.moveToPoint_( (x1, y1) )
            self._nsBezierPath.lineToPoint_( (x2, y2) )

    ### Radial shapes (center + radius) ###

    def poly(self, x, y, radius, sides=4, points=None):
        # if `points` is defined, draw a regularized star, otherwise draw
        # a regular polygon with the given number of `sides`.
        if points and points>4:
            inner = radius * cos(pi*2/points)/cos(pi/points)
            return self.star(x, y, points, inner, radius)
        elif points is not None:
            # for 3-4 `points`, treat stars like a sided n-gon
            sides = points

        # special-case radius interpretation for squares
        if sides == 4:
            # draw with sides of 2*r (this seems less surprising than drawing a
            # square *inside* a circle at the given radius and winding up with
            # sides that are weird fractions of the radius)
            radius *= sqrt(2.0)
        elif sides < 3:
            badpoly = 'polygons must have at least 3 points'
            raise DeviceError(badpoly)

        # rotate the origin slightly so the polygon sits on an edge
        theta = pi/2 + (0 if sides%2 else 1*pi/sides)
        angles = [2*pi * i/sides - theta for i in xrange(sides)]

        # walk around the circle adding points with proper scale/origin
        points = [ [radius*cos(theta)+x, radius*sin(theta)+y] for theta in angles]
        self._nsBezierPath.moveToPoint_(points[0])
        for pt in points[1:]:
            self._nsBezierPath.lineToPoint_(pt)
        self._nsBezierPath.closePath()
        self._fulcrum = Point(x,y)

    def arc(self, x, y, r, rng=None, ccw=False, close=False):
        if not rng:
            self.oval(x-r, y-r, 2*r, 2*r)
        else:
            # convert angles from canvas units to degrees
            if numlike(rng):
                start, end = sorted([0, rng])
            else:
                start, end = rng
            if ccw:
                start, end = -start, -end
            start, end = _ctx._angle(start, DEGREES), _ctx._angle(end, DEGREES)

            # note that we're negating the ccw arg because the path is being drawn in flipped coords
            self._nsBezierPath.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_((x,y), r, start, end, ccw)
        if close:
            # optionally close the path pac-man-style
            self._nsBezierPath.lineToPoint_( (x,y) )
            self._nsBezierPath.closePath()
        self._fulcrum = Point(x,y)

    def star(self, x, y, points=20, outer=100, inner=None):
        # if inner radius is unspecified, default to half-size
        if inner is None:
            inner = outer * 0.5

        self._nsBezierPath.moveToPoint_( (x, y+outer) )
        for i in range(1, int(2 * points)):
          angle = i * pi / points
          radius = inner if i % 2 else outer
          pt = (x+radius*sin(angle), y+radius*cos(angle))
          self._nsBezierPath.lineToPoint_(pt)
        self.closepath()
        self._fulcrum = Point(x,y)

    def arrow(self, x, y, width=100, type=NORMAL):
        if type not in (NORMAL, FORTYFIVE):
            badtype = "available types for arrow() are NORMAL and FORTYFIVE"
            raise DeviceError(badtype)

        if type==NORMAL:
            head = width * .4
            tail = width * .2
            self.moveto(x, y)
            self.lineto(x-head, y+head)
            self.lineto(x-head, y+tail)
            self.lineto(x-width, y+tail)
            self.lineto(x-width, y-tail)
            self.lineto(x-head, y-tail)
            self.lineto(x-head, y-head)
            self.lineto(x, y)
            self.closepath()
        elif type==FORTYFIVE:
            head = .3
            tail = 1 + head
            self.moveto(x, y)
            self.lineto(x, y+width*(1-head))
            self.lineto(x-width*head, y+width)
            self.lineto(x-width*head, y+width*tail*.4)
            self.lineto(x-width*tail*.6, y+width)
            self.lineto(x-width, y+width*tail*.6)
            self.lineto(x-width*tail*.4, y+width*head)
            self.lineto(x-width, y+width*head)
            self.lineto(x-width*(1-head), y)
            self.lineto(x, y)
        self._fulcrum = Point(x,y)

    ### List methods ###

    def __getitem__(self, index):
        if isinstance(index, slice):
            # slice-based access
            pts = [self._nsBezierPath.elementAtIndex_associatedPoints_(i) for i in xrange(*index.indices(len(self)))]
            return [Curve(cmd, el) for cmd,el in pts]
        else:
            # index-based access
            cmd, el = self._nsBezierPath.elementAtIndex_associatedPoints_(index)
            return Curve(cmd, el)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __len__(self):
        return self._nsBezierPath.elementCount()

    def extend(self, pathElements):
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
        if el.cmd == MOVETO:
            self.moveto(el.x, el.y)
        elif el.cmd == LINETO:
            self.lineto(el.x, el.y)
        elif el.cmd == CURVETO:
            c1, c2 = el.ctrl1, el.ctrl2
            self.curveto(c1.x, c1.y, c2.x, c2.y, el.x, el.y)
        elif el.cmd == CLOSE:
            self.closepath()
        self._fulcrum = None

    @property
    def contours(self):
        return pathmatics.contours(self)

    ### Drawing methods ###

    @property
    def bounds(self):
        try:
            return Region(self._nsBezierPath.bounds())
        except:
            # Path is empty -- no bounds
            return Region()

    @property
    def center(self):
        if self._fulcrum:
            return Point(self._fulcrum)
        else:
            (x, y), (w, h) = self.bounds
            return Point(x+w/2, y+h/2)

    def contains(self, x, y):
        return self._nsBezierPath.containsPoint_((x,y))

    @property
    def _screen_transform(self):
        """Returns the Transform object that will be used to draw the path."""

        nudge = Transform()
        if (self.transformmode == CENTER):
            # if center-based, sandwich transform with a scoot out/in to the origin
            dx, dy = self._to_px(self.center)
            nudge.translate(dx, dy)

        xf = Transform()
        xf.prepend(nudge)
        xf.prepend(self.transform)
        xf.prepend(nudge.inverse)
        return xf

    @property
    def cgPath(self):
        # transform the path's points from canvas- to postscript-units and return a CGPathRef
        return pathmatics.convert_path(self._to_px(self._nsBezierPath))

    def _draw(self):
        with _cg_context() as port:
            # modify the context's CTM to reflect our final resting place
            self._screen_transform.concat()

            # apply blend/alpha/shadow (and any associated transparency layers)
            with self.effects.applied():
                # prepare to stroke, fill, or both
                ink = None
                if isinstance(self._fillcolor, Color):
                    ink = kCGPathFill
                    CGContextSetFillColorWithColor(port, self._fillcolor.cgColor)
                if (self._strokecolor):
                    ink = kCGPathStroke if ink is None else kCGPathFillStroke
                    CGContextSetStrokeColorWithColor(port, self._strokecolor.cgColor)
                    CGContextSetLineWidth(port, self.nib)
                    CGContextSetLineCap(port, _CAPSTYLE[self.cap])
                    CGContextSetLineJoin(port, _JOINSTYLE[self.join])
                    if self.dash:
                        CGContextSetLineDash(port, 0, self.dash, len(self.dash))

                # use cocoa for patterns/gradients
                if isinstance(self._fillcolor, (Gradient, Pattern)):
                    self._fillcolor.fill(self)

                # use cg for stroke & fill
                if ink is not None:
                    CGContextBeginPath(port)
                    CGContextAddPath(port, self.cgPath)
                    CGContextDrawPath(port, ink)

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
        self._nsBezierPath = t.apply(self)._nsBezierPath
        self._fulcrum = t.apply(self._fulcrum) if self._fulcrum else None
        self._segment_cache = {}

    def _get_x(self):
        return getattr(self._fulcrum or self.bounds.origin.x, 'x')
    def _set_x(self, new_x):
        if self._fulcrum:
            new_x -= self._fulcrum.x - self.bounds.origin.x
        self.fit(x=new_x)
    x = property(_get_x, _set_x)

    def _get_y(self):
        return getattr(self._fulcrum or self.bounds.origin.x, 'y')
    def _set_y(self, new_y):
        if self._fulcrum:
            new_y -= self._fulcrum.y - self.bounds.origin.y
        self.fit(y=new_y)
    y = property(_get_y, _set_y)

    ### Mathematics ###

    def segmentlengths(self, relative=False, n=10):
        if relative: # Use the opportunity to store the segment cache.
            key = (len(self), self.bounds)
            if key not in self._segment_cache:
                self._segment_cache = {key:pathmatics.segment_lengths(self, relative=True, n=n)}
            return self._segment_cache[key]
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

        count = int(amount) # make sure we don't choke on a float
        delta = 1.0/max(1, count-1) # div by count-1 so the last point is at t=1.0
        for i in xrange(count):
            yield pathmatics.point(self, delta*i)

    def addpoint(self, t):
        self._nsBezierPath = pathmatics.insert_point(self, t)._nsBezierPath

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

    def angle(self, x=0, y=0):
        return Point(self.x, self.y).angle(x, y)

    def distance(self, x=0, y=0):
        return Point(self.x, self.y).distance(x, y)

    def reflect(self, *args, **kwargs):
        return Point(self.x, self.y).reflect(*args, **kwargs)

    def coordinates(self, distance, angle):
        return Point(self.x, self.y).coordinates(distance, angle)

# NodeBox compat...
BezierPath = Bezier
PathElement = Curve
