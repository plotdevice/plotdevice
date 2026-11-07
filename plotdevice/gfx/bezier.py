# encoding: utf-8
import warnings
from ..lib.cocoa import *
from math import pi, sin, cos, sqrt

from plotdevice import DeviceError
from .. import gfx
from .atoms import PenMixin, TransformMixin, ColorMixin, EffectsMixin, Grob
from .colors import Color, Gradient, Pattern
from .geometry import CENTER, DEGREES, IDENTITY, Transform, Region, Point, _pivot, _hull
from ..util import trim_zeroes, _copy_attr, _flatten, numlike
from ..lib import pathmatics
from _plotdevice import PDPath

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
    """A Bezier provides a wrapper around a CGPath."""
    stateAttrs = ('_pdpath', '_fulcrum')
    opts = ('close', 'smooth')

    def __init__(self, path=None, **kwargs):
        super(Bezier, self).__init__(**kwargs)
        self._fulcrum = None # centerpoint (set only for center-based primitives)

        # path arg might contain a list of point tuples, a bezier to copy, or a raw
        # nsbezier reference to use as the backing store. otherwise start with a
        # fresh path with no points
        if path is None:
            self._pdpath = PDPath()
        elif isinstance(path, (list,tuple)):
            if isinstance(path[0], Curve):
                self._pdpath = PDPath()
                self.extend(path)
            else:
                p = pathmatics.findpath(path, 1.0 if kwargs.get('smooth') else 0.0)
                self._pdpath = p._pdpath
        elif isinstance(path, Bezier):
            self._pdpath = PDPath(path._pdpath)
            self._fulcrum = _copy_attr(path._fulcrum)
        elif isinstance(path, NSBezierPath):
            self._pdpath = PDPath(path)
        elif isinstance(path, PDPath):
            self._pdpath = path # a native op's result, not shared with anything else
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
        # pull all state from the original object (rather than inheriting from _ctx)
        clone = Bezier.__new__(Bezier)
        clone._pdpath = PDPath(self._pdpath)
        clone._transform = self._transform.copy()
        clone._effects = self._effects.copy()
        clone._fillcolor = _copy_attr(self._fillcolor)
        clone._strokecolor = _copy_attr(self._strokecolor)
        clone._grid, clone._penstyle = self._grid, self._penstyle
        clone._fulcrum, clone._transformmode = self._fulcrum, self._transformmode
        clone._needs_closure = False
        return clone

    ### Path methods ###

    def moveto(self, x, y):
        self._pdpath.moveto(x, y)

    def lineto(self, x, y):
        self._pdpath.lineto(x, y) # with an implicit 0,0 origin if the path doesn't have a prior moveto

    def curveto(self, x1, y1, x2, y2, x3, y3):
        self._pdpath.curveto(x1, y1, x2, y2, x3, y3)

    def arcto(self, x1, y1, x2=None, y2=None, radius=None, ccw=False):
        if x2 is not None and y2 is not None:
            # arc toward the x1,y1 control point then turn toward the x2,y2 dest point. round off the
            # triangle created between the current point, the control point, and the dest point with
            # an arc of the given radius.
            #
            # Take a look at the Adding Arcs section of apple's docs for some important edge cases:
            # https://developer.apple.com/library/mac/documentation/Cocoa/Conceptual/CocoaDrawingGuide/Paths/Paths.html
            radius = 1.0 if radius is None else radius
            self._pdpath.arcto(x1, y1, x2, y2, radius)
            self._pdpath.lineto(x2, y2)
        else:
            # create a unitary semicircle...
            k = 0.5522847498 / 2.0
            p = PDPath()
            p.moveto(0, 0)
            p.curveto(0, -k, .5-k, -.5, .5, -.5)
            p.curveto(.5+k, -.5, 1, -k, 1, 0)

            # ...and transform it to match the endpoints
            sx, sy = self._pdpath.current_point()
            theta = pathmatics.angle(sx, sy, x1, y1)
            dw = pathmatics.distance(sx, sy, x1, y1)
            dh = dw*(-1.0 if ccw else 1.0)
            t = Transform()
            t.translate(sx, sy)
            t.rotate(-theta)
            t.scale(dw, dh)
            self.extend(Curve(cmd, pts) for cmd, pts in p.transformed(tuple(t.matrix)).elements()[1:]) # omit the initial moveto in the semicircle

    def closepath(self):
        self._pdpath.closepath() # if the current subpath is open and non-empty

    def _autoclose(self):
        if self._needs_closure:
            self.closepath()
            self._needs_closure = False

    ### Basic shapes (origin + size) ###

    def rect(self, x, y, width, height, radius=None):
        if radius is None:
            self._pdpath.rect(x, y, width, height)
        else:
            if numlike(radius):
                radius = (radius, radius)
            elif not isinstance(radius, (list, tuple)) or len(radius)!=2:
                badradius = 'the radius for a rect must be either a number or an (x,y) tuple'
                raise DeviceError(badradius)
            self._pdpath.rect(x, y, width, height, *radius)

    def oval(self, x, y, width, height, rng=None, ccw=False, close=False):
        # range = None:      draw a full ellipse
        # range = 180:       draws a semicircle
        # range = (90, 180): draws a quadrant in the lower left
        if rng is None:
            self._pdpath.oval(x, y, width, height)
        else:
            # convert angles from canvas units to degrees
            if numlike(rng):
                start, end = sorted([0, rng])
            else:
                start, end = rng
            if ccw:
                start, end = -start, -end
            start, end = _ctx._angle(start, DEGREES), _ctx._angle(end, DEGREES)

            p = PDPath()
            p.arc(.5, .5, .5, start, end, ccw)
            t = Transform()
            t.translate(x,y)
            t.scale(width, height)
            self._pdpath.add(p, tuple(t.matrix))
            if close:
                # optionally close the path with a chord
                self._pdpath.closepath()
            self._fulcrum = Point(x+width/2, y+width/2)
    ellipse = oval

    def line(self, x1, y1, x2, y2, ccw=None):
        if ccw in (True, False):
            self.moveto(x1,y1)
            self.arcto(x2,y2, ccw=ccw)
        else:
            self._pdpath.moveto(x1, y1)
            self._pdpath.lineto(x2, y2)

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
        angles = [2*pi * i/sides - theta for i in range(sides)]

        # walk around the circle adding points with proper scale/origin
        points = [ [radius*cos(theta)+x, radius*sin(theta)+y] for theta in angles]
        self._pdpath.moveto(*points[0])
        for pt in points[1:]:
            self._pdpath.lineto(*pt)
        self._pdpath.closepath()
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
            self._pdpath.arc(x, y, r, start, end, ccw)
        if close:
            # optionally close the path pac-man-style
            self._pdpath.lineto(x, y)
            self._pdpath.closepath()
        self._fulcrum = Point(x,y)

    def star(self, x, y, points=20, outer=100, inner=None):
        # if inner radius is unspecified, default to half-size
        if inner is None:
            inner = outer * 0.5

        self._pdpath.moveto(x, y+outer)
        for i in range(1, int(2 * points)):
          angle = i * pi / points
          radius = inner if i % 2 else outer
          self._pdpath.lineto(x+radius*sin(angle), y+radius*cos(angle))
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
            return [Curve(cmd, el) for cmd,el in self._pdpath.elements()[index]]
        else:
            # index-based access
            cmd, el = self._pdpath.elements()[index]
            return Curve(cmd, el)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __len__(self):
        return len(self._pdpath)

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
        box = self._pdpath.bounds()
        return Region() if box is None else Region(*box) # an empty path has no bounds

    @property
    def center(self):
        if self._fulcrum:
            return Point(self._fulcrum)
        else:
            (x, y), (w, h) = self.bounds
            return Point(x+w/2, y+h/2)

    def contains(self, x, y):
        return self._pdpath.contains(x, y)

    @property
    def _screen_matrix(self):
        matrix = tuple(self.transform.matrix)
        if self.transformmode == CENTER and matrix != IDENTITY:
            cx, cy = self._to_px(self.center)
            return _pivot(matrix, cx, cy)
        return matrix

    @property
    def _screen_transform(self):
        """Returns the Transform object that will be used to draw the path."""
        return Transform(self._screen_matrix)

    @property
    def cgPath(self):
        # transform the path's points from canvas- to postscript-units and return a CGPathRef
        path = self._pdpath if self._grid.dpx == 1 else self._pdpath.transformed(tuple(self._grid.to_px.matrix))
        return path.cgpath

    def _render_box(self):
        """The box its outline covers where it's drawn"""
        dpx = self._grid.dpx
        box = self._pdpath.bounds()
        if box is None:
            return (0, 0, 0, 0) # an empty path
        x, y, w, h = box
        if tuple(self.transform.matrix) == IDENTITY:
            return (x * dpx, y * dpx, w * dpx, h * dpx)
        return _hull(self._screen_matrix, x * dpx, y * dpx, w * dpx, h * dpx)

    def _draw(self):
        port = gfx._state.port
        CGContextSaveGState(port)
        try:
            # modify the context's CTM to reflect our final resting place
            if tuple(self.transform.matrix) != IDENTITY:
                self._screen_transform.concat()

            # apply blend/alpha/shadow (and any associated transparency layers)
            with self.effects.applied(self, layer=self._fillcolor is not None and bool(self._strokecolor)):
                # effects (like shadows) may shift the active context, so re-fetch
                target = gfx._state.port

                # prepare to stroke, fill, or both
                ink = None
                path = self._pdpath
                filled = isinstance(self._fillcolor, (Color, Pattern))
                lone_segment = filled and len(path) == 2 and path.elements()[1][0] == LINETO
                if filled and not lone_segment:
                    ink = kCGPathFill
                    CGContextSetFillColorWithColor(target, self._fillcolor.cgColor)
                gradient_stroke = isinstance(self._strokecolor, Gradient)
                if (self._strokecolor):
                    if not gradient_stroke:
                        ink = kCGPathStroke if ink is None else kCGPathFillStroke
                        CGContextSetStrokeColorWithColor(target, self._strokecolor.cgColor)
                    CGContextSetLineWidth(target, self.nib)
                    CGContextSetLineCap(target, _CAPSTYLE[self.cap])
                    CGContextSetLineJoin(target, _JOINSTYLE[self.join])
                    if self.dash:
                        CGContextSetLineDash(target, 0, self.dash, len(self.dash))

                # use cocoa for gradients
                if isinstance(self._fillcolor, Gradient):
                    self._fillcolor.fill(self)

                # use cg for stroke & fill
                if ink is not None:
                    CGContextBeginPath(target)
                    CGContextAddPath(target, self.cgPath)
                    CGContextDrawPath(target, ink)

                # fill the stroke's outline with its gradient
                if gradient_stroke:
                    CGContextSaveGState(target)
                    CGContextBeginPath(target)
                    CGContextAddPath(target, self.cgPath)
                    CGContextReplacePathWithStrokedPath(target)
                    outline = CGContextGetPathBoundingBox(target)
                    CGContextClip(target)
                    self._strokecolor.fill((tuple(outline.origin), tuple(outline.size)))
                    CGContextRestoreGState(target)
        finally:
            CGContextRestoreGState(port)

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
        self._pdpath = t.apply(self)._pdpath
        self._fulcrum = t.apply(self._fulcrum) if self._fulcrum else None

    def _get_x(self):
        return (self._fulcrum or self.bounds.origin).x
    def _set_x(self, new_x):
        if self._fulcrum:
            new_x -= self._fulcrum.x - self.bounds.origin.x
        self.fit(x=new_x)
    x = property(_get_x, _set_x)

    def _get_y(self):
        return (self._fulcrum or self.bounds.origin).y
    def _set_y(self, new_y):
        if self._fulcrum:
            new_y -= self._fulcrum.y - self.bounds.origin.y
        self.fit(y=new_y)
    y = property(_get_y, _set_y)

    ### Mathematics ###

    def segmentlengths(self, relative=False, n=10):
        return pathmatics.segment_lengths(self, relative=relative, n=n)

    @property
    def length(self, segmented=False, n=10):
        return pathmatics.length(self, segmented=segmented, n=n)

    def point(self, t):
        return pathmatics.point(self, t)

    def points(self, amount=100, start=0, end=1):
        return pathmatics.points(self, int(amount), start=start, end=end) # int() so we don't choke on a float

    def addpoint(self, t):
        self._pdpath = pathmatics.insert_point(self, t)._pdpath

    ### Clipping operations ###

    def intersects(self, other):
        return pathmatics.intersects(self._pdpath, other._pdpath)

    def union(self, other, flatness=0.6):
        return Bezier(pathmatics.union(self._pdpath, other._pdpath, flatness))

    def intersect(self, other, flatness=0.6):
        return Bezier(pathmatics.intersect(self._pdpath, other._pdpath, flatness))

    def difference(self, other, flatness=0.6):
        return Bezier(pathmatics.difference(self._pdpath, other._pdpath, flatness))

    def xor(self, other, flatness=0.6):
        return Bezier(pathmatics.xor(self._pdpath, other._pdpath, flatness))

    def trace(self, nib=None, join=None, cap=None):
        """Returns a new Bezier representing this path's outline as though it
        were stroked with the given weight and line style -- converting what
        would be painted as a stroke into ordinary fillable geometry.

        Any of nib/join/cap that are omitted default to the canvas's current
        pen settings (see pen()).
        """
        if nib is None:
            nib = _ctx._penstyle.nib
        if join is None:
            join = _ctx._penstyle.join
        if cap is None:
            cap = _ctx._penstyle.cap
        if join not in _JOINSTYLE:
            badstyle = 'Line join style should be MITER, ROUND or BEVEL.'
            raise DeviceError(badstyle)
        if cap not in _CAPSTYLE:
            badstyle = 'Line cap style should be BUTT, ROUND or SQUARE.'
            raise DeviceError(badstyle)
        return Bezier(pathmatics.stroke_to_fill(self._pdpath, nib, _CAPSTYLE[cap], _JOINSTYLE[join]))

    def inset(self, delta, join=None, miter=10.0):
        """Returns a new Bezier with this path's boundary shrunk (delta > 0)
        or grown (delta < 0) by delta canvas units.

        join (omitted defaults to the canvas's current pen() join) controls
        the corner style where the inset boundary bends: MITER, ROUND, or
        BEVEL.
        """
        if join is None:
            join = _ctx._penstyle.join
        if join not in _JOINSTYLE:
            badstyle = 'Line join style should be MITER, ROUND or BEVEL.'
            raise DeviceError(badstyle)
        return Bezier(pathmatics.offset(self._pdpath, -delta, _JOINSTYLE[join], miter))

    def simplify(self, epsilon=1.0):
        """Returns a new Bezier with redundant points removed -- every
        remaining point stays within epsilon canvas units of the original
        boundary."""
        return Bezier(pathmatics.simplify(self._pdpath, epsilon))

    @property
    def area(self):
        """The total filled area enclosed by this path, in canvas units squared."""
        return pathmatics.area(self._pdpath)

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
