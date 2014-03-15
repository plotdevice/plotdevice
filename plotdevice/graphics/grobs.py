# encoding: utf-8
import os
import re
import json
import warnings
import math
from operator import itemgetter
from collections import OrderedDict as odict
from random import choice, shuffle
from AppKit import *
from Foundation import *

from plotdevice import DeviceError
from plotdevice.util import _copy_attr, _copy_attrs, _flatten
from plotdevice.lib import polymagic, geometry

_ctx = None
__all__ = [
        "DEFAULT_WIDTH", "DEFAULT_HEIGHT",
        "inch", "cm", "mm", "pi", "tau",
        "RGB", "HSB", "CMYK", "GREY",
        "CENTER", "CORNER",
        "DEGREES", "RADIANS", "PERCENT",
        "MOVETO", "LINETO", "CURVETO", "CLOSE",
        "MITER", "ROUND", "BEVEL", "BUTT", "SQUARE",
        "NORMAL","FORTYFIVE",
        "NUMBER", "TEXT", "BOOLEAN","BUTTON",
        "Point", "Size", "Region",
        "Grob", "Transform", "DeviceError",
        "ClippingPath", # "Rect", "Oval",
        "BezierPath", "Bezier", "PathElement", "Curve",
        "Color", "Image",
        "Variable",
        ]
DEFAULT_WIDTH, DEFAULT_HEIGHT = 512, 512

# scale factors
inch = 72
cm = 28.3465
mm = 2.8346
pi = math.pi
tau = 2*pi

# color/output modes
RGB = "rgb"
HSB = "hsb"
CMYK = "cmyk"
GREY = "grey"

# transform modes
CENTER = "center"
CORNER = "corner"

# rotation modes
DEGREES = "degrees"
RADIANS = "radians"
PERCENT = "percent"

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

# var datatypes
NUMBER = 1
TEXT = 2
BOOLEAN = 3
BUTTON = 4

# ui events
KEY_UP = 126
KEY_DOWN = 125
KEY_LEFT = 123
KEY_RIGHT = 124
KEY_BACKSPACE = 51
KEY_TAB = 48
KEY_ESC = 53

_STATE_NAMES = {
    '_outputmode':    'outputmode',
    '_colorrange':    'colorrange',
    '_fillcolor':     'fill',
    '_strokecolor':   'stroke',
    '_strokewidth':   'strokewidth',
    '_capstyle':      'capstyle',
    '_joinstyle':     'joinstyle',
    '_transform':     'transform',
    '_transformmode': 'transformmode',
    '_fontname':      'font',
    '_fontsize':      'fontsize',
    '_align':         'align',
    '_lineheight':    'lineheight',
}

_CSS_COLORS = json.load(file('%s/colors.json'%os.path.dirname(__file__)))

def _save():
    NSGraphicsContext.currentContext().saveGraphicsState()

def _restore():
    NSGraphicsContext.currentContext().restoreGraphicsState()

def trim_zeroes(func):
    # a handy decorator for tidying up numbers in repr strings
    return lambda slf: re.sub(r'\.?0+(?=[,\)])', '', func(slf))

class Point(object):

    def __init__(self, *args):
        if len(args) == 2:
            self.x, self.y = args
        elif len(args) == 1:
            self.x, self.y = args[0]
        elif len(args) == 0:
            self.x = self.y = 0.0
        else:
            badcoords = "Bad initial coordinates for Point object"
            raise DeviceError(badcoords)

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
        return geometry.angle(self.x, self.y, x, y)

    def distance(self, x=0, y=0):
        if isinstance(x, Point):
            x, y = x.__iter__()
        return geometry.distance(self.x, self.y, x, y)

    def reflect(self, x=0, y=0, d=1.0, a=180):
        if isinstance(x, Point):
            d, a = y, d
            x, y = x.__iter__()
        return geometry.reflect(self.x, self.y, x, y, d, a)

    def coordinates(self, distance, angle):
        return geometry.coordinates(self.x, self.y, distance, angle)

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

class Grob(object):
    """A GRaphic OBject is the base class for all DrawingPrimitives."""

    def draw(self):
        """Appends the grob to the canvas.
           This will result in a _draw later on, when the scene graph is rendered."""
        _ctx.canvas.append(self)

    def copy(self):
        """Returns a deep copy of this grob."""
        raise NotImplementedError, "Copy is not implemented on this Grob class."

    def inheritFromContext(self, ignore=()):
        attrs_to_skip = [k for k, v in _STATE_NAMES.items() if v in ignore]
        attrs_to_copy = set(self.__class__.stateAttributes).difference(attrs_to_skip)
        _copy_attrs(_ctx, self, attrs_to_copy)

    def checkKwargs(self, kwargs):
        remaining = [arg for arg in kwargs.keys() if arg not in self.kwargs]
        if remaining:
            unknown = "Unknown argument(s) '%s'" % ", ".join(remaining)
            raise DeviceError(unknown)
    checkKwargs = classmethod(checkKwargs)

class TransformMixin(object):

    """Mixin class for transformation support.
    Adds the _transform and _transformmode attributes to the class."""

    def __init__(self):
        self._reset()

    def _reset(self):
        self._transform = Transform()
        self._transformmode = CENTER

    def _get_transform(self):
        return self._transform
    def _set_transform(self, transform):
        self._transform = Transform(transform)
    transform = property(_get_transform, _set_transform)

    def _get_transformmode(self):
        return self._transformmode
    def _set_transformmode(self, mode):
        self._transformmode = mode
    transformmode = property(_get_transformmode, _set_transformmode)

    def translate(self, x, y):
        self._transform.translate(x, y)

    def reset(self):
        self._transform = Transform()

    def rotate(self, degrees=0, radians=0):
        self._transform.rotate(-degrees,-radians)

    def translate(self, x=0, y=0):
        self._transform.translate(x,y)

    def scale(self, x=1, y=None):
        self._transform.scale(x,y)

    def skew(self, x=0, y=0):
        self._transform.skew(x,y)

class ColorMixin(object):

    """Mixin class for color support.
    Adds the _fillcolor, _strokecolor and _strokewidth attributes to the class."""

    def __init__(self, **kwargs):
        try:
            self._fillcolor = Color(kwargs['fill'])
        except KeyError:
            self._fillcolor = Color()
        try:
            self._strokecolor = Color(kwargs['stroke'])
        except KeyError:
            self._strokecolor = None

    def _get_fill(self):
        return self._fillcolor
    def _set_fill(self, *args):
        self._fillcolor = Color(*args)
    fill = property(_get_fill, _set_fill)

    def _get_stroke(self):
        return self._strokecolor
    def _set_stroke(self, *args):
        self._strokecolor = Color(*args)
    stroke = property(_get_stroke, _set_stroke)

class PenMixin(object):

    """Mixin class for linestyle support.
    Adds the _capstyle, _joinstyle, _dashstyle, and _strokewidth attributes to the class."""

    def __init__(self, **kwargs):
        self.strokewidth = kwargs.get('nib', kwargs.get('strokewidth', _ctx._strokewidth))
        self.capstyle = kwargs.get('cap', kwargs.get('capstyle', _ctx._capstyle))
        self.joinstyle = kwargs.get('join', kwargs.get('joinstyle', _ctx._joinstyle))
        self.dashstyle = kwargs.get('dash', kwargs.get('dashstyle', _ctx._dashstyle))

    def _get_strokewidth(self):
        return self._strokewidth
    def _set_strokewidth(self, strokewidth):
        self._strokewidth = max(strokewidth, 0.0001)
    nib = strokewidth = property(_get_strokewidth, _set_strokewidth)

    def _get_capstyle(self):
        return self._capstyle
    def _set_capstyle(self, style):
        if style not in (BUTT, ROUND, SQUARE):
            badstyle = 'Line cap style should be BUTT, ROUND or SQUARE.'
            raise DeviceError(badstyle)
        self._capstyle = style
    cap = capstyle = property(_get_capstyle, _set_capstyle)

    def _get_joinstyle(self):
        return self._joinstyle
    def _set_joinstyle(self, style):
        if style not in (MITER, ROUND, BEVEL):
            badstyle = 'Line join style should be MITER, ROUND or BEVEL.'
            raise DeviceError(badstyle)
        self._joinstyle = style
    join = joinstyle = property(_get_joinstyle, _set_joinstyle)

    def _get_dashstyle(self):
        return self._dashstyle
    def _set_dashstyle(self, *segments):
        if None in segments:
            self._dashstyle = None
        else:
            steps = map(int, _flatten(segments))
            if len(steps)%2:
                steps += steps[-1:] # assume even spacing for omitted skip sizes
            self._dashstyle = steps
    dash = dashstyle = property(_get_dashstyle, _set_dashstyle)


class Bezier(Grob, TransformMixin, ColorMixin, PenMixin):
    """A Bezier provides a wrapper around NSBezierPath."""

    stateAttributes = ('_fillcolor', '_strokecolor', '_strokewidth', '_capstyle', '_joinstyle', '_transform', '_transformmode')
    kwargs = ('fill', 'stroke', 'strokewidth', 'capstyle', 'joinstyle', 'nib', 'cap', 'join')

    def __init__(self, path=None, immediate=False, **kwargs):
        TransformMixin.__init__(self)
        ColorMixin.__init__(self, **kwargs)
        PenMixin.__init__(self, **kwargs)
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
        self._overrides = {k:_copy_attr(v) for k,v in kwargs.items() if k in Bezier.kwargs}
        self._autoclose = kwargs.get('close', _ctx._autoclosepath)
        self._autodraw = kwargs.get('draw', False)

        # finish the path (and potentially draw it) immediately if flagged to do so.
        # in practice, `immediate` is only passed when invoked by the `bezier()` command
        # with a preexisting point-set or bezier `path` argument.
        if immediate:
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
            self.inheritFromContext(self._overrides.keys())
            for attr, val in self._overrides.items():
                setattr(self, attr, val)
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
        from plotdevice.graphics import bezier
        return bezier.contours(self)

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
        import bezier
        if relative: # Use the opportunity to store the segment cache.
            if self._segment_cache is None:
                self._segment_cache = bezier.segment_lengths(self, relative=True, n=n)
            return self._segment_cache
        else:
            return bezier.segment_lengths(self, relative=False, n=n)

    @property
    def length(self, segmented=False, n=10):
        import bezier
        return bezier.length(self, segmented=segmented, n=n)

    def point(self, t):
        import bezier
        return bezier.point(self, t)

    def points(self, amount=100):
        import bezier
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
            yield self.point(delta*i)

    def addpoint(self, t):
        import bezier
        self._nsBezierPath = bezier.insert_point(self, t)._nsBezierPath
        self._segment_cache = None

    ### Clipping operations ###

    def intersects(self, other):
        return polymagic.intersects(self._nsBezierPath, other._nsBezierPath)

    def union(self, other, flatness=0.6):
        return Bezier(polymagic.union(self._nsBezierPath, other._nsBezierPath, flatness))

    def intersect(self, other, flatness=0.6):
        return Bezier(polymagic.intersect(self._nsBezierPath, other._nsBezierPath, flatness))

    def difference(self, other, flatness=0.6):
        return Bezier(polymagic.difference(self._nsBezierPath, other._nsBezierPath, flatness))

    def xor(self, other, flatness=0.6):
        return Bezier(polymagic.xor(self._nsBezierPath, other._nsBezierPath, flatness))

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

class ClippingPath(Grob):

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

class Color(object):

    def __init__(self, *args, **kwargs):

        # flatten any tuples in the arguments list
        args = _flatten(args)

        # if the first arg is a color mode, use that to interpret the args
        if args and args[0] in (RGB, HSB, CMYK, GREY):
            mode, args = args[0], args[1:]
        else:
            mode=kwargs.get('mode')

        if mode not in (RGB, HSB, CMYK, GREY):
            # if no mode was specified, interpret the components in the context's current mode
            mode = _ctx._colormode

        # use the specified range for int values, or leave it as None to use the default 0-1 scale
        rng = kwargs.get('range')

        params = len(args)
        if params == 1 and args[0] is None:                # None -> transparent
            clr = Color._nscolor(GREY, 0, 0)
        elif params == 1 and isinstance(args[0], Color):   # Color object
            is_rgb = _ctx._outputmode == RGB
            clr = args[0]._rgb if is_rgb else args[0]._cmyk
        elif params == 1 and isinstance(args[0], NSColor): # NSColor object
            clr = args[0]
        elif params>=1 and isinstance(args[0], basestring):
            r, g, b, a = Color._parse(args[0])             # Hex string or named color
            if args[1:]:
                a = args[1]
            clr = Color._nscolor(RGB, r, g, b, a)
        elif 1<=params<=2:                                 # Greyscale (+ alpha)
            gscale = self._normalizeList(args, rng)
            if params<2:
                gscale += (1,)
            clr = Color._nscolor(GREY, *gscale)
        elif 3<=params<=4 and mode in (RGB, HSB):          # RGB(a) & HSB(a)
            rgba_hsba = self._normalizeList(args, rng)
            if params<4:
                rgba_hsba += (1,)
            clr = Color._nscolor(mode, *rgba_hsba)
        elif 4<=params<=5 and mode==CMYK:                  # CMYK(a)
            cmyka = self._normalizeList(args, rng)
            if params<5:
                cmyka += (1,)
            clr = Color._nscolor(CMYK, *cmyka)
        else:                                              # default is the new black
            clr = Color._nscolor(GREY, 0, 1)

        self._cmyk = clr.colorUsingColorSpaceName_(NSDeviceCMYKColorSpace)
        self._rgb = clr.colorUsingColorSpaceName_(NSDeviceRGBColorSpace)

    @trim_zeroes
    def __repr__(self):
        args = repr(self.hexa) if self.a!=1.0 else '(%r)'%self.hex
        return '%s%s'%(self.__class__.__name__, args)

    def set(self):
        self.nsColor.set()

    # fill() and stroke() both cache the previous canvas state by creating a _rollback attr.
    # act as a context manager if there's a fill/stroke state to revert to at the end of the block.
    def __enter__(self):
        if not hasattr(self, '_rollback'):
            badcontext = 'the with-statement can only be used with fill() and stroke(), not arbitrary colors'
            raise DeviceError(badcontext)
        return self

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            statevar = {"fill":"_fillcolor", "stroke":"_strokecolor"}[param]
            setattr(_ctx, statevar, val)

    @property
    def nsColor(self):
        if _ctx._outputmode == RGB:
            return self._rgb
        else:
            return self._cmyk

    def _values(self, mode):
        outargs = [None] * 4
        if mode is RGB:
            return self._rgb.getRed_green_blue_alpha_(*outargs)
        elif mode is HSB:
            return self._rgb.getHue_saturation_brightness_alpha_(*outargs)
        elif mode is CMYK:
            return (self._cmyk.cyanComponent(), self._cmyk.magentaComponent(),
                    self._cmyk.yellowComponent(), self._cmyk.blackComponent(),
                    self._cmyk.alphaComponent())

    def copy(self):
        new = self.__class__()
        new._rgb = self._rgb.copy()
        new._updateCmyk()
        return new

    def _updateCmyk(self):
        self._cmyk = self._rgb.colorUsingColorSpaceName_(NSDeviceCMYKColorSpace)

    def _updateRgb(self):
        self._rgb = self._cmyk.colorUsingColorSpaceName_(NSDeviceRGBColorSpace)

    def _get_hue(self):
        return self._rgb.hueComponent()
    def _set_hue(self, val):
        val = self._normalize(val)
        h, s, b, a = self._values(HSB)
        self._rgb = Color._nscolor(HSB, val, s, b, a)
        self._updateCmyk()
    h = hue = property(_get_hue, _set_hue, doc="the hue of the color")

    def _get_saturation(self):
        return self._rgb.saturationComponent()
    def _set_saturation(self, val):
        val = self._normalize(val)
        h, s, b, a = self._values(HSB)
        self._rgb = Color._nscolor(HSB, h, val, b, a)
        self._updateCmyk()
    s = saturation = property(_get_saturation, _set_saturation, doc="the saturation of the color")

    def _get_brightness(self):
        return self._rgb.brightnessComponent()
    def _set_brightness(self, val):
        val = self._normalize(val)
        h, s, b, a = self._values(HSB)
        self._rgb = Color._nscolor(HSB, h, s, val, a)
        self._updateCmyk()
    v = brightness = property(_get_brightness, _set_brightness, doc="the brightness of the color")

    def _get_hsba(self):
        return self._values(HSB)
    def _set_hsba(self, values):
        h, s, b, a = self._normalizeList(values)
        self._rgb = Color._nscolor(HSB, h, s, b, a)
        self._updateCmyk()
    hsba = property(_get_hsba, _set_hsba, doc="the hue, saturation, brightness and alpha of the color")

    def _get_red(self):
        return self._rgb.redComponent()
    def _set_red(self, val):
        val = self._normalize(val)
        r, g, b, a = self._values(RGB)
        self._rgb = Color._nscolor(RGB, val, g, b, a)
        self._updateCmyk()
    r = red = property(_get_red, _set_red, doc="the red component of the color")

    def _get_green(self):
        return self._rgb.greenComponent()
    def _set_green(self, val):
        val = self._normalize(val)
        r, g, b, a = self._values(RGB)
        self._rgb = Color._nscolor(RGB, r, val, b, a)
        self._updateCmyk()
    g = green = property(_get_green, _set_green, doc="the green component of the color")

    def _get_blue(self):
        return self._rgb.blueComponent()
    def _set_blue(self, val):
        val = self._normalize(val)
        r, g, b, a = self._values(RGB)
        self._rgb = Color._nscolor(RGB, r, g, val, a)
        self._updateCmyk()
    b = blue = property(_get_blue, _set_blue, doc="the blue component of the color")

    def _get_alpha(self):
        return self._rgb.alphaComponent()
    def _set_alpha(self, val):
        val = self._normalize(val)
        r, g, b, a = self._values(RGB)
        self._rgb = Color._nscolor(RGB, r, g, b, val)
        self._updateCmyk()
    a = alpha = property(_get_alpha, _set_alpha, doc="the alpha component of the color")

    def _get_rgba(self):
        return self._values(RGB)
    def _set_rgba(self, values):
        r, g, b, a = self._normalizeList(values)
        self._rgb = Color._nscolor(RGB, r, g, b, a)
        self._updateCmyk()
    rgba = property(_get_rgba, _set_rgba, doc="the red, green, blue and alpha values of the color")

    def _get_cyan(self):
        return self._cmyk.cyanComponent()
    def _set_cyan(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = Color._nscolor(CMYK, val, m, y, k, a)
        self._updateRgb()
    c = cyan = property(_get_cyan, _set_cyan, doc="the cyan component of the color")

    def _get_magenta(self):
        return self._cmyk.magentaComponent()
    def _set_magenta(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = Color._nscolor(CMYK, c, val, y, k, a)
        self._updateRgb()
    m = magenta = property(_get_magenta, _set_magenta, doc="the magenta component of the color")

    def _get_yellow(self):
        return self._cmyk.yellowComponent()
    def _set_yellow(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = Color._nscolor(CMYK, c, m, val, k, a)
        self._updateRgb()
    y = yellow = property(_get_yellow, _set_yellow, doc="the yellow component of the color")

    def _get_black(self):
        return self._cmyk.blackComponent()
    def _set_black(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = Color._nscolor(CMYK, c, m, y, val, a)
        self._updateRgb()
    k = black = property(_get_black, _set_black, doc="the black component of the color")

    def _get_cmyka(self):
        return (self._cmyk.cyanComponent(), self._cmyk.magentaComponent(), self._cmyk.yellowComponent(), self._cmyk.blackComponent(), self._cmyk.alphaComponent())
    cmyka = property(_get_cmyka, doc="a tuple containing the CMYKA values for this color")

    def _get_hex(self):
        r, g, b, a = self._values(RGB)
        s = "".join('%02x'%int(255*c) for c in (r,g,b))
        if all([len(set(pair))==1 for pair in zip(s[::2], s[1::2])]):
            s = "".join(s[::2])
        return "#"+s
    def _set_hex(self, val):
        r, g, b, a = Color._parse(clr)
        self._rgb = Color._nscolor(RGB, r, g, b, a)
        self._updateCmyk()
    hex = property(_get_hex, _set_hex, doc="the rgb hex string for the color")

    def _get_hexa(self):
        return (self.hex, self.a)
    def _set_hexa(self, clr, alpha):
        a = self._normalize(alpha)
        r, g, b, _ = Color._parse(clr)
        self._rgb = Color._nscolor(RGB, r, g, b, a)
        self._updateCmyk()
    hexa = property(_get_hexa, _set_hexa, doc="a tuple containing the color's rgb hex string and an alpha float")

    def blend(self, otherColor, factor):
        """Blend the color with otherColor with a factor; return the new color. Factor
        is a float between 0.0 and 1.0.
        """
        if hasattr(otherColor, "color"):
            otherColor = otherColor._rgb
        return self.__class__(color=self._rgb.blendedColorWithFraction_ofColor_(
                factor, otherColor))

    def _normalize(self, v, rng=None):
        """Bring the color into the 0-1 scale for the current colorrange"""
        r = float(_ctx._colorrange if rng is None else rng)
        return v if r==1.0 else v/r

    def _normalizeList(self, lst, rng=None):
        """Bring the color into the 0-1 scale for the current colorrange"""
        r = float(_ctx._colorrange if rng is None else rng)
        if r == 1.0: return lst
        return [v / r for v in lst]

    @classmethod
    def _nscolor(cls, scheme, *components):
        factory = {RGB: NSColor.colorWithDeviceRed_green_blue_alpha_,
                   HSB: NSColor.colorWithDeviceHue_saturation_brightness_alpha_,
                   CMYK: NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_,
                   GREY: NSColor.colorWithDeviceWhite_alpha_}
        return factory[scheme](*components)

    @classmethod
    def _parse(cls, clrstr):
        """Returns an r/g/b/a tuple based on a css color name or a hex string of the form:
        RRGGBBAA, RRGGBB, RGBA, or RGB (with or without a leading #)
        """
        if clrstr in _CSS_COLORS: # handle css color names
            clrstr = _CSS_COLORS[clrstr]

        if re.search(r'#?[0-9a-f]{3,8}', clrstr): # rgb & rgba hex strings
            hexclr = clrstr.lstrip('#')
            if len(hexclr) in (3,4):
                hexclr = "".join(map("".join, zip(hexclr,hexclr)))
            if len(hexclr) not in (6,8):
                invalid = "Don't know how to interpret hex color '#%s'." % hexclr
                raise DeviceError(invalid)
            r, g, b = [int(n, 16)/255.0 for n in (hexclr[0:2], hexclr[2:4], hexclr[4:6])]
            a = 1.0 if len(hexclr)!=8 else int(hexclr[6:], 16)/255.0
        else:
            invalid = "Color strings must be 3/6/8-character hex codes or valid css-names"
            raise DeviceError(invalid)
        return r, g, b, a


color = Color # hmmmmm... is this here for good or ill?


class InkContext(object):
    """Performs the setup/cleanup for a `with pen()/stroke()/fill()/color(mode,range)` block"""
    _statevars = dict(nib='_strokewidth', cap='_capstyle', join='_joinstyle', dash='_dashstyle',
                      mode='_colormode', range='_colorrange', stroke='_strokecolor', fill='_fillcolor')

    def __init__(self, restore=None, **spec):
        # start with the current context state as a baseline
        prior = {k:getattr(_ctx, v) for k,v in self._statevars.items() if k in spec or restore==all}
        snapshots = {k:v._rollback for k,v in spec.items() if hasattr(v, '_rollback')}
        prior.update(snapshots)

        for param, val in spec.items():
            # make sure fill & stroke are Color objects (or None)
            if param in ('stroke','fill'):
                if val is None: continue
                val = Color(val)
                spec[param] = val
            setattr(_ctx, self._statevars[param], val)

        # keep the dictionary of prior state around for restoration at the end of the block
        self._rollback = prior
        self._spec = spec

    def __enter__(self):
        return dict(self._spec)

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            setattr(_ctx, self._statevars[param], val)

    def __repr__(self):
        spec = ", ".join('%s=%r'%(k,v) for k,v in self._spec.items())
        return 'InkContext(%s)'%spec


class TransformContext(object):
    """Performs the setup/cleanup for a `with transform()` block (and changes the mode)"""
    _xforms = ['reset','rotate','translate','scale','skew']

    def __init__(self, mode=None, rotation=None, *xforms):
        # work backwards from the current state and apply inverses of any transformation
        # calls that occurred in the arguments
        self._rollback = _ctx._transform.copy()
        for xf in reversed(xforms):
            self._rollback.prepend(xf.inverse)

        # remember the old center/corner setting and rotation units, then apply the new ones
        self._oldmode = _ctx._transformmode
        self._oldrotation = rotation or _ctx._rotationmode
        self._mode = mode or self._oldmode
        _ctx._transformmode = self._mode

    def __enter__(self):
        return _ctx._transform

    def __exit__(self, type, value, tb):
        _ctx._transform = self._rollback
        _ctx._transformmode = self._oldmode

    def __eq__(self, other):
        return self._mode == other

    def __repr__(self):
        return {CENTER:'CENTER', CORNER:'CORNER'}.get(self._mode)

    @property
    def mode(self):
        return _ctx._transformmode

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
        # Transform objects get _rollback attrs when they're derived from an existing
        # xform (in particular the graphics context's current transform). In that case
        # the global state has already been changed before the context manager was
        # invoked, so use the cached state this one time. On any subsequent with-
        # statement invocations take a snapshot of the current global state
        if not hasattr(self, '_rollback'):
            self._rollback = Transform(_ctx._transform)

    def __exit__(self, type, value, tb):
        # restore the context's transform and discard the snapshot
        _ctx._transform = self._rollback
        del self._rollback

    def __repr__(self):
        return "<%s [%.3f %.3f %.3f %.3f %.3f %.3f]>" % ((self.__class__.__name__,)
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

    def rotate(self, degrees=0, radians=0):
        xf = NSAffineTransform.transform()
        if degrees:
            xf.rotateByDegrees_(degrees)
        else:
            xf.rotateByRadians_(radians)
        self.prepend(xf)
        return Transform(xf)

    def translate(self, x=0, y=0):
        xf = Transform()
        xf._nsAffineTransform.translateXBy_yBy_(x, y)
        xf._rollback = self.copy()
        self.prepend(xf)
        return xf

    def scale(self, x=1, y=None):
        if y is None:
            y = x
        xf = Transform()
        xf._nsAffineTransform.scaleXBy_yBy_(x, y)
        xf._rollback = self.copy()
        self.prepend(xf)
        return xf

    def skew(self, x=0, y=0):
        x,y = map(lambda n: n*pi/180, [x,y])
        xf = Transform()
        xf.matrix = (1, math.tan(y), -math.tan(x), 1, 0, 0)
        xf._rollback = self.copy()
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
        if isinstance(path, Bezier):
            path = Bezier(path)
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

class Image(Grob, TransformMixin):

    stateAttributes = ('_transform', '_transformmode')
    kwargs = ()

    def __init__(self, path=None, x=0, y=0, width=None, height=None, alpha=1.0, image=None, data=None):
        """
        Parameters:
         - path: A path to a certain image on the local filesystem.
         - x: Horizontal position.
         - y: Vertical position.
         - width: Maximum width. Images get scaled according to this factor.
         - height: Maximum height. Images get scaled according to this factor.
              If a width and height are both given, the smallest
              of the two is chosen.
         - alpha: transparency factor
         - image: optionally, an Image or NSImage object.
         - data: a stream of bytes of image data.
        """
        TransformMixin.__init__(self)
        if data is not None:
            if not isinstance(data, NSData):
                data = NSData.dataWithBytes_length_(data, len(data))
            self._nsImage = NSImage.alloc().initWithData_(data)
            if self._nsImage is None:
                unreadable = "can't read image %r" % path
                raise DeviceError(unreadable)
            self._nsImage.setFlipped_(True)
            self._nsImage.setCacheMode_(NSImageCacheNever)
        elif image is not None:
            if isinstance(image, NSImage):
                self._nsImage = image
                self._nsImage.setFlipped_(True)
            else:
                wrongtype = "Don't know what to do with %s." % image
                raise DeviceError(wrongtype)
        elif path is not None:
            if not os.path.exists(path):
                notfound = 'Image "%s" not found.' % path
                raise DeviceError(notfound)
            curtime = os.path.getmtime(path)
            try:
                image, lasttime = _ctx._imagecache[path]
                if lasttime != curtime:
                    image = None
            except KeyError:
                pass
            if image is None:
                image = NSImage.alloc().initWithContentsOfFile_(path)
                if image is None:
                    invalid = "Can't read image %r" % path
                    raise DeviceError(invalid)
                image.setFlipped_(True)
                image.setCacheMode_(NSImageCacheNever)
                _ctx._imagecache[path] = (image, curtime)
            self._nsImage = image
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.alpha = alpha
        self.debugImage = False

    @property
    def image(self):
        warnings.warn("The 'image' attribute is deprecated. Please use _nsImage instead.", DeprecationWarning, stacklevel=2)
        return self._nsImage

    def copy(self):
        new = self.__class__()
        _copy_attrs(self, new, ('image', 'x', 'y', 'width', 'height', '_transform', '_transformmode', 'alpha', 'debugImage'))
        return new

    def getSize(self):
        return Size(*self._nsImage.size())

    size = property(getSize)

    def _draw(self):
        """Draw an image on the given coordinates."""

        srcW, srcH = self._nsImage.size()
        srcRect = ((0, 0), (srcW, srcH))

        # Width or height given
        if self.width is not None or self.height is not None:
            if self.width is not None and self.height is not None:
                factor = min(self.width / srcW, self.height / srcH)
            elif self.width is not None:
                factor = self.width / srcW
            elif self.height is not None:
                factor = self.height / srcH
            _save()

            # Center-mode transforms: translate to image center
            if self._transformmode == CENTER:
                # This is the hardest case: center-mode transformations with given width or height.
                # Order is very important in this code.

                # Set the position first, before any of the scaling or transformations are done.
                # Context transformations might change the translation, and we don't want that.
                t = Transform()
                t.translate(self.x, self.y)
                t.concat()

                # Set new width and height factors. Note that no scaling is done yet: they're just here
                # to set the new center of the image according to the scaling factors.
                srcW = srcW * factor
                srcH = srcH * factor

                # Move image to newly calculated center.
                dX = srcW / 2
                dY = srcH / 2
                t = Transform()
                t.translate(dX, dY)
                t.concat()

                # Do current transformation.
                self._transform.concat()

                # Move back to the previous position.
                t = Transform()
                t.translate(-dX, -dY)
                t.concat()

                # Finally, scale the image according to the factors.
                t = Transform()
                t.scale(factor)
                t.concat()
            else:
                # Do current transformation
                self._transform.concat()
                # Scale according to width or height factor
                t = Transform()
                t.translate(self.x, self.y) # Here we add the positioning of the image.
                t.scale(factor)
                t.concat()

            # A debugImage draws a black rectangle instead of an image.
            if self.debugImage:
                Color().set()
                pt = Bezier()
                pt.rect(0, 0, srcW / factor, srcH / factor)
                pt.fill()
            else:
                self._nsImage.drawAtPoint_fromRect_operation_fraction_((0, 0), srcRect, NSCompositeSourceOver, self.alpha)
            _restore()
        # No width or height given
        else:
            _save()
            x,y = self.x, self.y
            # Center-mode transforms: translate to image center
            if self._transformmode == CENTER:
                deltaX = srcW / 2
                deltaY = srcH / 2
                t = Transform()
                t.translate(x+deltaX, y+deltaY)
                t.concat()
                x = -deltaX
                y = -deltaY
            # Do current transformation
            self._transform.concat()
            # A debugImage draws a black rectangle instead of an image.
            if self.debugImage:
                Color().set()
                pt = Bezier()
                pt.rect(x, y, srcW, srcH)
                pt.fill()
            else:
                # The following code avoids a nasty bug in Cocoa/PyObjC.
                # Apparently, EPS files are put on a different position when drawn with a certain position.
                # However, this only happens when the alpha value is set to 1.0: set it to something lower
                # and the positioning is the same as a bitmap file.
                # I could of course make every EPS image have an alpha value of 0.9999, but this solution
                # is better: always use zero coordinates for drawAtPoint and use a transform to set the
                # final position.
                t = Transform()
                t.translate(x,y)
                t.concat()
                self._nsImage.drawAtPoint_fromRect_operation_fraction_((0,0), srcRect, NSCompositeSourceOver, self.alpha)
            _restore()


class Variable(object):
    def __init__(self, name, type, default=None, min=0, max=100, value=None):
        self.name = name
        self.type = type or NUMBER
        if self.type == NUMBER:
            if default is None:
                self.default = 50
            else:
                self.default = default
            self.min = min
            self.max = max
        elif self.type == TEXT:
            if default is None:
                self.default = "hello"
            else:
                self.default = default
        elif self.type == BOOLEAN:
            if default is None:
                self.default = True
            else:
                self.default = default
        elif self.type == BUTTON:
            self.default = self.name
        self.value = value or self.default

    def sanitize(self, val):
        """Given a Variable and a value, cleans it out"""
        if self.type == NUMBER:
            try:
                return float(val)
            except ValueError:
                return 0.0
        elif self.type == TEXT:
            return unicode(str(val), "utf_8", "replace")
            try:
                return unicode(str(val), "utf_8", "replace")
            except:
                return ""
        elif self.type == BOOLEAN:
            if unicode(val).lower() in ("true", "1", "yes"):
                return True
            else:
                return False

    def compliesTo(self, v):
        """Return whether I am compatible with the given var:
             - Type should be the same
             - My value should be inside the given vars' min/max range.
        """
        if self.type == v.type:
            if self.type == NUMBER:
                if self.value < self.min or self.value > self.max:
                    return False
            return True
        return False

    @trim_zeroes
    def __repr__(self):
        return "Variable(name=%s, type=%s, default=%s, min=%s, max=%s, value=%s)" % (self.name, self.type, self.default, self.min, self.max, self.value)


def _test():
    import doctest, cocoa
    return doctest.testmod(cocoa)

if __name__=='__main__':
    _test()
