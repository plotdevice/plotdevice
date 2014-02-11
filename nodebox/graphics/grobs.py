import os
import re
import json
import warnings
from random import choice, shuffle
from AppKit import *
from Foundation import *

from nodebox.util import _copy_attr, _copy_attrs

try:
    import cPolymagic
except ImportError, e:
    warnings.warn('Could not load cPolymagic: %s' % e)

__all__ = [
        "DEFAULT_WIDTH", "DEFAULT_HEIGHT",
        "inch", "cm", "mm",
        "RGB", "HSB", "CMYK",
        "CENTER", "CORNER",
        "MOVETO", "LINETO", "CURVETO", "CLOSE",
        "MITER", "ROUND", "BEVEL", "BUTT", "SQUARE",
        "LEFT", "RIGHT", "CENTER", "JUSTIFY",
        "NORMAL","FORTYFIVE",
        "NUMBER", "TEXT", "BOOLEAN","BUTTON",
        "NodeBoxError",
        "Point", "Grob", "BezierPath", "PathElement", "ClippingPath", "Rect", "Oval", "Color", "Transform", "Image", "Text",
        "Variable",
        ]

DEFAULT_WIDTH, DEFAULT_HEIGHT = 500, 500

inch = 72
cm = 28.3465
mm = 2.8346

RGB = "rgb"
HSB = "hsb"
CMYK = "cmyk"

CENTER = "center"
CORNER = "corner"

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

LEFT = NSLeftTextAlignment
RIGHT = NSRightTextAlignment
CENTER = NSCenterTextAlignment
JUSTIFY = NSJustifiedTextAlignment

NORMAL = "normal"
FORTYFIVE = "fortyfive"

NUMBER = 1
TEXT = 2
BOOLEAN = 3
BUTTON = 4

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

_CSS_COLORS = json.load(file('%s/colors/names.json'%os.path.dirname(__file__)))

def _save():
    NSGraphicsContext.currentContext().saveGraphicsState()

def _restore():
    NSGraphicsContext.currentContext().restoreGraphicsState()

class NodeBoxError(Exception): pass

class Point(object):

    def __init__(self, *args):
        if len(args) == 2:
            self.x, self.y = args
        elif len(args) == 1:
            self.x, self.y = args[0]
        elif len(args) == 0:
            self.x = self.y = 0.0
        else:
            raise NodeBoxError, "Wrong initializer for Point object"

    def __repr__(self):
        return "Point(x=%.3f, y=%.3f)" % (self.x, self.y)
        
    def __eq__(self, other):
        if other is None: return False
        return self.x == other.x and self.y == other.y
        
    def __ne__(self, other):
        return not self.__eq__(other)

class Grob(object):
    """A GRaphic OBject is the base class for all DrawingPrimitives."""

    def __init__(self, ctx):
        """Initializes this object with the current context."""
        self._ctx = ctx

    def draw(self):
        """Appends the grob to the canvas.
           This will result in a draw later on, when the scene graph is rendered."""
        self._ctx.canvas.append(self)
        
    def copy(self):
        """Returns a deep copy of this grob."""
        raise NotImplementedError, "Copy is not implemented on this Grob class."
        
    def inheritFromContext(self, ignore=()):
        attrs_to_copy = list(self.__class__.stateAttributes)
        [attrs_to_copy.remove(k) for k, v in _STATE_NAMES.items() if v in ignore]
        _copy_attrs(self._ctx, self, attrs_to_copy)
        
    def checkKwargs(self, kwargs):
        remaining = [arg for arg in kwargs.keys() if arg not in self.kwargs]
        if remaining:
            raise NodeBoxError, "Unknown argument(s) '%s'" % ", ".join(remaining)
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
            self._fillcolor = Color(self._ctx, kwargs['fill'])
        except KeyError:
            self._fillcolor = Color(self._ctx)
        try:
            self._strokecolor = Color(self._ctx, kwargs['stroke'])
        except KeyError:
            self._strokecolor = None
        self._strokewidth = kwargs.get('strokewidth', 1.0)
        
    def _get_fill(self):
        return self._fillcolor
    def _set_fill(self, *args):
        self._fillcolor = Color(self._ctx, *args)
    fill = property(_get_fill, _set_fill)
    
    def _get_stroke(self):
        return self._strokecolor
    def _set_stroke(self, *args):
        self._strokecolor = Color(self._ctx, *args)
    stroke = property(_get_stroke, _set_stroke)
    
    def _get_strokewidth(self):
        return self._strokewidth
    def _set_strokewidth(self, strokewidth):
        self._strokewidth = max(strokewidth, 0.0001)
    strokewidth = property(_get_strokewidth, _set_strokewidth)

class BezierPath(Grob, TransformMixin, ColorMixin):
    """A BezierPath provides a wrapper around NSBezierPath."""
    
    stateAttributes = ('_fillcolor', '_strokecolor', '_strokewidth', '_capstyle', '_joinstyle', '_transform', '_transformmode')
    kwargs = ('fill', 'stroke', 'strokewidth', 'capstyle', 'joinstyle')


    def __init__(self, ctx, path=None, immediate=False, **kwargs):
        super(BezierPath, self).__init__(ctx)
        TransformMixin.__init__(self)
        ColorMixin.__init__(self, **kwargs)
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
        elif isinstance(path, BezierPath):
            self._nsBezierPath = path._nsBezierPath.copy()
            _copy_attrs(path, self, self.stateAttributes)
        elif isinstance(path, NSBezierPath):
            self._nsBezierPath = path
        else:
            raise NodeBoxError, "Don't know what to do with %s." % path

        # use any drawstyle settings in kwargs (the rest will be inherited)
        self.capstyle = kwargs.get('capstyle', self._ctx._capstyle)
        self.joinstyle = kwargs.get('joinstyle', self._ctx._joinstyle)
        self._overrides = {k:_copy_attr(v) for k,v in kwargs.items() if k in BezierPath.kwargs}
        self._autoclose = kwargs.get('close', self._ctx._autoclosepath)
        self._autodraw = kwargs.get('draw', False)
        
        # finish the path (and potentially draw it) immediately if flagged to do so.
        # in practice, `immediate` is only passed when invoked by the `bezier()` command
        # with a preexisting point-set or bezier `path` argument.
        if immediate:
            self._autofinish()

    def __enter__(self):
        if self._finished:
            raise NodeBoxError, "Bezier already complete. Only use `with bezier()` when defining a path using moveto, lineto, etc."
        elif self._ctx._path is not None:
            raise NodeBoxError, "Already defining a bezier path. Don't nest `with bezier()` blocks"
        self._ctx._saveContext()
        self._ctx._path = self
        return self

    def __exit__(self, type, value, tb):
        self._autofinish()
        self._ctx._path = None
        self._ctx._restoreContext()

    def _autofinish(self):
        if self._autoclose:
            self.closepath()
        if self._autodraw:
            self.inheritFromContext(self._overrides.keys())
            for attr, val in self._overrides.items():
                setattr(self, attr, val)
            self.draw()
        self._finished = True

    def _get_path(self):
        warnings.warn("The 'path' attribute is deprecated. Please use _nsBezierPath instead.", DeprecationWarning, stacklevel=2)
        return self._nsBezierPath
    path = property(_get_path)

    def copy(self):
        return self.__class__(self._ctx, self)
    
    ### Cap and Join style ###
    
    def _get_capstyle(self):
        return self._capstyle
    def _set_capstyle(self, style):
        if style not in (BUTT, ROUND, SQUARE):
            raise NodeBoxError, 'Line cap style should be BUTT, ROUND or SQUARE.'
        self._capstyle = style
    capstyle = property(_get_capstyle, _set_capstyle)

    def _get_joinstyle(self):
        return self._joinstyle
    def _set_joinstyle(self, style):
        if style not in (MITER, ROUND, BEVEL):
            raise NodeBoxError, 'Line join style should be MITER, ROUND or BEVEL.'
        self._joinstyle = style
    joinstyle = property(_get_joinstyle, _set_joinstyle)

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
        
    def setlinewidth(self, width):
        self.linewidth = width

    def _get_bounds(self):
        try:
            return self._nsBezierPath.bounds()
        except:
            # Path is empty -- no bounds
            return (0,0) , (0,0)

    bounds = property(_get_bounds)

    def contains(self, x, y):
        return self._nsBezierPath.containsPoint_((x,y))

    ### Basic shapes ###
    
    def rect(self, x, y, width, height):
        self._segment_cache = None
        self._nsBezierPath.appendBezierPathWithRect_( ((x, y), (width, height)) )
        
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
        return PathElement(cmd, el)

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
                self.append(PathElement(cmd, ((x, y),)))
            elif isinstance(el, PathElement):
                self.append(el)
            else:
                raise NodeBoxError, "Don't know how to handle %s" % el

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
            
    def _get_contours(self):
        from nodebox.graphics import bezier
        return bezier.contours(self)
    contours = property(_get_contours)

    ### Drawing methods ###

    def _get_transform(self):
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
    transform = property(_get_transform)

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

    def _get_length(self, segmented=False, n=10):
        import bezier
        return bezier.length(self, segmented=segmented, n=n)
    length = property(_get_length)
        
    def point(self, t):
        import bezier
        return bezier.point(self, t)
        
    def points(self, amount=100):
        import bezier
        if len(self) == 0:
            raise NodeBoxError, "The given path is empty"

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
        return cPolymagic.intersects(self._nsBezierPath, other._nsBezierPath)
        
    def union(self, other, flatness=0.6):
        return BezierPath(self._ctx, cPolymagic.union(self._nsBezierPath, other._nsBezierPath, flatness))
    
    def intersect(self, other, flatness=0.6):
        return BezierPath(self._ctx, cPolymagic.intersect(self._nsBezierPath, other._nsBezierPath, flatness))

    def difference(self, other, flatness=0.6):
        return BezierPath(self._ctx, cPolymagic.difference(self._nsBezierPath, other._nsBezierPath, flatness))

    def xor(self, other, flatness=0.6):
        return BezierPath(self._ctx, cPolymagic.xor(self._nsBezierPath, other._nsBezierPath, flatness))

class PathElement(object):

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

    def __repr__(self):
        if self.cmd == MOVETO:
            return "PathElement(MOVETO, ((%.3f, %.3f),))" % (self.x, self.y)
        elif self.cmd == LINETO:
            return "PathElement(LINETO, ((%.3f, %.3f),))" % (self.x, self.y)
        elif self.cmd == CURVETO:
            return "PathElement(CURVETO, ((%.3f, %.3f), (%.3f, %s), (%.3f, %.3f))" % \
                (self.ctrl1.x, self.ctrl1.y, self.ctrl2.x, self.ctrl2.y, self.x, self.y)
        elif self.cmd == CLOSE:
            return "PathElement(CLOSE)"
            
    def __eq__(self, other):
        if other is None: return False
        if self.cmd != other.cmd: return False
        return self.x == other.x and self.y == other.y \
            and self.ctrl1 == other.ctrl1 and self.ctrl2 == other.ctrl2
        
    def __ne__(self, other):
        return not self.__eq__(other)

class ClippingPath(Grob):

    def __init__(self, ctx, path):
        self._ctx = ctx
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

class Rect(BezierPath):

    def __init__(self, ctx, x, y, width, height, **kwargs):
        warnings.warn("Rect is deprecated. Use BezierPath's rect method.", DeprecationWarning, stacklevel=2)
        r = (x,y), (width,height)
        super(Rect, self).__init__(ctx, NSBezierPath.bezierPathWithRect_(r), **kwargs)

    def copy(self):
        raise NotImplementedError, "Please don't use Rect anymore"

class Oval(BezierPath):

    def __init__(self, ctx, x, y, width, height, **kwargs):
        warnings.warn("Oval is deprecated. Use BezierPath's oval method.", DeprecationWarning, stacklevel=2)
        r = (x,y), (width,height)
        super(Oval, self).__init__(ctx, NSBezierPath.bezierPathWithOvalInRect_(r), **kwargs)

    def copy(self):
        raise NotImplementedError, "Please don't use Oval anymore"

class Color(object):

    def __init__(self, ctx, *args):
        self._ctx = ctx
        params = len(args)

        # Decompose the arguments into tuples. 
        if params == 1 and isinstance(args[0], tuple):
            args = args[0]
            params = len(args)

        if params == 1 and args[0] is None:
            clr = NSColor.colorWithDeviceWhite_alpha_(0.0, 0.0)
        elif params == 1 and isinstance(args[0], Color):
            if self._ctx._outputmode == RGB:
                clr = args[0]._rgb
            else:
                clr = args[0]._cmyk
        elif params == 1 and isinstance(args[0], NSColor):
            clr = args[0]
        elif params>=1 and isinstance(args[0], (str, unicode)):
            if re.search(r'#?[0-9a-f]{3,8}', args[0]): # rgb & rgba hex strings
                hexclr = args[0].lstrip('#')
                if len(hexclr) in (3,4):
                    hexclr = "".join(map("".join, zip(hexclr,hexclr)))
                if len(hexclr) not in (6,8):
                    raise NodeBoxError, "Don't know how to interpret hex color '#%s'." % hexclr
                r, g, b = [int(n, 16)/255.0 for n in (hexclr[0:2], hexclr[2:4], hexclr[4:6])]
                a = args[1] if params==2 else 1.0
                if len(hexclr)==8:
                    a = int(hexclr[6:], 16)/255.0                
            elif args[0] in _CSS_COLORS: # handle css color names
                try:
                    r, g, b, a = _CSS_COLORS[args[0]]
                except ValueError:
                    r, g, b = _CSS_COLORS[args[0]]
                    a = args[1] if params==2 else 1.0
            else:
                raise NodeBoxError, "Color strings must be 3/6/8-character hex codes or valid css-names"
            clr = NSColor.colorWithDeviceRed_green_blue_alpha_(r, g, b, a)
        elif params == 1: # Gray, no alpha
            g, = self._normalizeList(args)
            clr = NSColor.colorWithDeviceWhite_alpha_(g, 1)
        elif params == 2: # Gray and alpha
            g, a = self._normalizeList(args)
            clr = NSColor.colorWithDeviceWhite_alpha_(g, a)
        elif params == 3 and self._ctx._colormode == RGB: # RGB, no alpha
            r,g,b = self._normalizeList(args)
            clr = NSColor.colorWithDeviceRed_green_blue_alpha_(r, g, b, 1)
        elif params == 3 and self._ctx._colormode == HSB: # HSB, no alpha
            h, s, b = self._normalizeList(args)
            clr = NSColor.colorWithDeviceHue_saturation_brightness_alpha_(h, s, b, 1)
        elif params == 4 and self._ctx._colormode == RGB: # RGB and alpha
            r,g,b, a = self._normalizeList(args)
            clr = NSColor.colorWithDeviceRed_green_blue_alpha_(r, g, b, a)
        elif params == 4 and self._ctx._colormode == HSB: # HSB and alpha
            h, s, b, a = self._normalizeList(args)
            clr = NSColor.colorWithDeviceHue_saturation_brightness_alpha_(h, s, b, a)
        elif params == 4 and self._ctx._colormode == CMYK: # CMYK, no alpha
            c, m, y, k  = self._normalizeList(args)
            clr = NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_(c, m, y, k, 1)
        elif params == 5 and self._ctx._colormode == CMYK: # CMYK and alpha
            c, m, y, k, a  = self._normalizeList(args)
            clr = NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_(c, m, y, k, a)
        else:
            clr = NSColor.colorWithDeviceWhite_alpha_(0, 1)

        self._cmyk = clr.colorUsingColorSpaceName_(NSDeviceCMYKColorSpace)
        self._rgb = clr.colorUsingColorSpaceName_(NSDeviceRGBColorSpace)

    def __repr__(self):
        return "%s(%.3f, %.3f, %.3f, %.3f)" % (self.__class__.__name__, self.red,
                self.green, self.blue, self.alpha)

    def set(self):
        self.nsColor.set()
    
    def _get_nsColor(self):
        if self._ctx._outputmode == RGB:
            return self._rgb
        else:
            return self._cmyk
    nsColor = property(_get_nsColor)
        

    def copy(self):
        new = self.__class__(self._ctx)
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
        h, s, b, a = self._rgb.getHue_saturation_brightness_alpha_(None, None, None, None)
        self._rgb = NSColor.colorWithDeviceHue_saturation_brightness_alpha_(val, s, b, a)
        self._updateCmyk()
    h = hue = property(_get_hue, _set_hue, doc="the hue of the color")

    def _get_saturation(self):
        return self._rgb.saturationComponent()
    def _set_saturation(self, val):
        val = self._normalize(val)
        h, s, b, a = self._rgb.getHue_saturation_brightness_alpha_(None, None, None, None)
        self._rgb = NSColor.colorWithDeviceHue_saturation_brightness_alpha_(h, val, b, a)
        self._updateCmyk()
    s = saturation = property(_get_saturation, _set_saturation, doc="the saturation of the color")

    def _get_brightness(self):
        return self._rgb.brightnessComponent()
    def _set_brightness(self, val):
        val = self._normalize(val)
        h, s, b, a = self._rgb.getHue_saturation_brightness_alpha_(None, None, None, None)
        self._rgb = NSColor.colorWithDeviceHue_saturation_brightness_alpha_(h, s, val, a)
        self._updateCmyk()
    v = brightness = property(_get_brightness, _set_brightness, doc="the brightness of the color")

    def _get_hsba(self):
        return self._rgb.getHue_saturation_brightness_alpha_(None, None, None, None)
    def _set_hsba(self, values):
        val = self._normalize(val)
        h, s, b, a = values
        self._rgb = NSColor.colorWithDeviceHue_saturation_brightness_alpha_(h, s, b, a)
        self._updateCmyk()
    hsba = property(_get_hsba, _set_hsba, doc="the hue, saturation, brightness and alpha of the color")

    def _get_red(self):
        return self._rgb.redComponent()
    def _set_red(self, val):
        val = self._normalize(val)
        r, g, b, a = self._rgb.getRed_green_blue_alpha_(None, None, None, None)
        self._rgb = NSColor.colorWithDeviceRed_green_blue_alpha_(val, g, b, a)
        self._updateCmyk()
    r = red = property(_get_red, _set_red, doc="the red component of the color")

    def _get_green(self):
        return self._rgb.greenComponent()
    def _set_green(self, val):
        val = self._normalize(val)
        r, g, b, a = self._rgb.getRed_green_blue_alpha_(None, None, None, None)
        self._rgb = NSColor.colorWithDeviceRed_green_blue_alpha_(r, val, b, a)
        self._updateCmyk()
    g = green = property(_get_green, _set_green, doc="the green component of the color")

    def _get_blue(self):
        return self._rgb.blueComponent()
    def _set_blue(self, val):
        val = self._normalize(val)
        r, g, b, a = self._rgb.getRed_green_blue_alpha_(None, None, None, None)
        self._rgb = NSColor.colorWithDeviceRed_green_blue_alpha_(r, g, val, a)
        self._updateCmyk()
    b = blue = property(_get_blue, _set_blue, doc="the blue component of the color")

    def _get_alpha(self):
        return self._rgb.alphaComponent()
    def _set_alpha(self, val):
        val = self._normalize(val)
        r, g, b, a = self._rgb.getRed_green_blue_alpha_(None, None, None, None)
        self._rgb = NSColor.colorWithDeviceRed_green_blue_alpha_(r, g, b, val)
        self._updateCmyk()
    a = alpha = property(_get_alpha, _set_alpha, doc="the alpha component of the color")

    def _get_rgba(self):
        return self._rgb.getRed_green_blue_alpha_(None, None, None, None)
    def _set_rgba(self, val):
        val = self._normalizeList(val)
        r, g, b, a = val
        self._rgb = NSColor.colorWithDeviceRed_green_blue_alpha_(r, g, b, a)
        self._updateCmyk()
    rgba = property(_get_rgba, _set_rgba, doc="the red, green, blue and alpha values of the color")

    def _get_cyan(self):
        return self._cmyk.cyanComponent()
    def _set_cyan(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_(val, m, y, k, a)
        self._updateRgb()
    c = cyan = property(_get_cyan, _set_cyan, doc="the cyan component of the color")

    def _get_magenta(self):
        return self._cmyk.magentaComponent()
    def _set_magenta(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_(c, val, y, k, a)
        self._updateRgb()
    m = magenta = property(_get_magenta, _set_magenta, doc="the magenta component of the color")

    def _get_yellow(self):
        return self._cmyk.yellowComponent()
    def _set_yellow(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_(c, m, val, k, a)
        self._updateRgb()
    y = yellow = property(_get_yellow, _set_yellow, doc="the yellow component of the color")

    def _get_black(self):
        return self._cmyk.blackComponent()
    def _set_black(self, val):
        val = self._normalize(val)
        c, m, y, k, a = self.cmyka
        self._cmyk = NSColor.colorWithDeviceCyan_magenta_yellow_black_alpha_(c, m, y, val, a)
        self._updateRgb()
    k = black = property(_get_black, _set_black, doc="the black component of the color")

    def _get_cmyka(self):
        return (self._cmyk.cyanComponent(), self._cmyk.magentaComponent(), self._cmyk.yellowComponent(), self._cmyk.blackComponent(), self._cmyk.alphaComponent())
    cmyka = property(_get_cmyka, doc="a tuple containing the CMYKA values for this color")

    def blend(self, otherColor, factor):
        """Blend the color with otherColor with a factor; return the new color. Factor
        is a float between 0.0 and 1.0.
        """
        if hasattr(otherColor, "color"):
            otherColor = otherColor._rgb
        return self.__class__(color=self._rgb.blendedColorWithFraction_ofColor_(
                factor, otherColor))

    def _normalize(self, v):
        """Bring the color into the 0-1 scale for the current colorrange"""
        if self._ctx._colorrange == 1.0: return v
        return v / self._ctx._colorrange

    def _normalizeList(self, lst):
        """Bring the color into the 0-1 scale for the current colorrange"""
        r = self._ctx._colorrange
        if r == 1.0: return lst
        return [v / r for v in lst]

color = Color

class TransformContext(object):
    """Performs the setup/cleanup for a `with transform()` block (and changes the mode)"""
    _xforms = ['reset','rotate','translate','scale','skew']

    def __init__(self, ctx, mode=None, *xforms):
        self._oldmode = ctx._transformmode
        self._oldtransform = ctx._transform.matrix
        self._mode = mode or self._oldmode
        self._ctx = ctx

        # walk through the transformations in the args and apply them
        ctx._transformmode = self._mode
        for xf in [xforms[i:i+2] for i,t in enumerate(xforms) if callable(t)]:
            cmd, arg = xf[0], [a for a in xf[1:] if not callable(a)]
            if arg and isinstance(arg[0], tuple):
                arg = arg[0]
            if cmd.__name__ not in self._xforms:
                raise NodeBoxError, "Unknown transformation method: %s." % cmd.__name__
            cmd(*arg)

    def __enter__(self):
        return self._ctx._transform

    def __exit__(self, type, value, tb):
        self._ctx._transform = Transform(self._oldtransform)
        self._ctx._transformmode = self._oldmode

    def __eq__(self, other):
        return self._mode == other

    def __repr__(self):
        return {CENTER:'CENTER', CORNER:'CORNER'}.get(self._mode)

    @property
    def mode(self):
        return self._ctx._transformmode

class Transform(object):

    def __init__(self, transform=None):
        if transform is None:
            transform = NSAffineTransform.transform()
        elif isinstance(transform, Transform):
            matrix = transform._nsAffineTransform.transformStruct()
            transform = NSAffineTransform.transform()
            transform.setTransformStruct_(matrix)
        elif isinstance(transform, (list, tuple, NSAffineTransformStruct)):
            matrix = tuple(transform)
            transform = NSAffineTransform.transform()
            transform.setTransformStruct_(matrix)
        elif isinstance(transform, NSAffineTransform):
            pass
        else:
            raise NodeBoxError, "Don't know how to handle transform %s." % transform
        self._nsAffineTransform = transform
        
    def _get_transform(self):
        warnings.warn("The 'transform' attribute is deprecated. Please use _nsAffineTransform instead.", DeprecationWarning, stacklevel=2)
        return self._nsAffineTransform
    transform = property(_get_transform)
    
    def set(self):
        self._nsAffineTransform.set()

    def concat(self):
        self._nsAffineTransform.concat()

    def copy(self):
        return self.__class__(self._nsAffineTransform.copy())

    def __repr__(self):
        return "<%s [%.3f %.3f %.3f %.3f %.3f %.3f]>" % ((self.__class__.__name__,)
                 + tuple(self))

    def __iter__(self):
        for value in self._nsAffineTransform.transformStruct():
            yield value

    def _get_matrix(self):
        return self._nsAffineTransform.transformStruct()
    def _set_matrix(self, value):
        self._nsAffineTransform.setTransformStruct_(value)
    matrix = property(_get_matrix, _set_matrix)

    def rotate(self, degrees=0, radians=0):
        if degrees:
            self._nsAffineTransform.rotateByDegrees_(degrees)
        else:
            self._nsAffineTransform.rotateByRadians_(radians)

    def translate(self, x=0, y=0):
        self._nsAffineTransform.translateXBy_yBy_(x, y)

    def scale(self, x=1, y=None):
        if y is None:
            y = x
        self._nsAffineTransform.scaleXBy_yBy_(x, y)

    def skew(self, x=0, y=0):
        import math
        x = math.pi * x / 180
        y = math.pi * y / 180
        t = Transform()
        t.matrix = 1, math.tan(y), -math.tan(x), 1, 0, 0
        self.prepend(t)

    def invert(self):
        self._nsAffineTransform.invert()

    def append(self, other):
        if isinstance(other, Transform):
            other = other._nsAffineTransform
        self._nsAffineTransform.appendTransform_(other)

    def prepend(self, other):
        if isinstance(other, Transform):
            other = other._nsAffineTransform
        self._nsAffineTransform.prependTransform_(other)

    def apply(self, point_or_path):
        if isinstance(point_or_path, BezierPath):
            return self.transformBezierPath(point_or_path)
        elif isinstance(point_or_path, Point):
            return self.transformPoint(point_or_path)
        else:
            raise NodeBoxError, "Can only transform BezierPaths or Points"

    def transformPoint(self, point):
        return Point(self._nsAffineTransform.transformPoint_((point.x,point.y)))

    def transformBezierPath(self, path):
        if isinstance(path, BezierPath):
            path = BezierPath(path._ctx, path)
        else:
            raise NodeBoxError, "Can only transform BezierPaths"
        path._nsBezierPath = self._nsAffineTransform.transformBezierPath_(path._nsBezierPath)
        return path

class Image(Grob, TransformMixin):

    stateAttributes = ('_transform', '_transformmode')
    kwargs = ()

    def __init__(self, ctx, path=None, x=0, y=0, width=None, height=None, alpha=1.0, image=None, data=None):
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
        super(Image, self).__init__(ctx)
        TransformMixin.__init__(self)
        if data is not None:
            if not isinstance(data, NSData):
                data = NSData.dataWithBytes_length_(data, len(data))
            self._nsImage = NSImage.alloc().initWithData_(data)
            if self._nsImage is None:
                raise NodeBoxError, "can't read image %r" % path
            self._nsImage.setFlipped_(True)
            self._nsImage.setCacheMode_(NSImageCacheNever)
        elif image is not None:
            if isinstance(image, NSImage):
                self._nsImage = image
                self._nsImage.setFlipped_(True)
            else:
                raise NodeBoxError, "Don't know what to do with %s." % image
        elif path is not None:
            if not os.path.exists(path):
                raise NodeBoxError, 'Image "%s" not found.' % path
            curtime = os.path.getmtime(path)
            try:
                image, lasttime = self._ctx._imagecache[path]
                if lasttime != curtime:
                    image = None
            except KeyError:
                pass
            if image is None:
                image = NSImage.alloc().initWithContentsOfFile_(path)
                if image is None:
                    raise NodeBoxError, "Can't read image %r" % path
                image.setFlipped_(True)
                image.setCacheMode_(NSImageCacheNever)
                self._ctx._imagecache[path] = (image, curtime)
            self._nsImage = image
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.alpha = alpha
        self.debugImage = False

    def _get_image(self):
        warnings.warn("The 'image' attribute is deprecated. Please use _nsImage instead.", DeprecationWarning, stacklevel=2)
        return self._nsImage
    image = property(_get_image)

    def copy(self):
        new = self.__class__(self._ctx)
        _copy_attrs(self, new, ('image', 'x', 'y', 'width', 'height', '_transform', '_transformmode', 'alpha', 'debugImage'))
        return new

    def getSize(self):
        return self._nsImage.size()

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
                Color(self._ctx).set()
                pt = BezierPath()
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
                Color(self._ctx).set()
                pt = BezierPath()
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

class Text(Grob, TransformMixin, ColorMixin):

    stateAttributes = ('_transform', '_transformmode', '_fillcolor', '_fontname', '_fontsize', '_align', '_lineheight')
    kwargs = ('fill', 'font', 'fontsize', 'align', 'lineheight')

    __dummy_color = NSColor.blackColor()
    
    def __init__(self, ctx, text, x=0, y=0, width=None, height=None, **kwargs):
        super(Text, self).__init__(ctx)
        TransformMixin.__init__(self)
        ColorMixin.__init__(self, **kwargs)
        self.text = unicode(text)
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self._fontname = kwargs.get('font', "Helvetica")
        self._fontsize = kwargs.get('fontsize', 24)
        self._lineheight = max(kwargs.get('lineheight', 1.2), 0.01)
        self._align = kwargs.get('align', NSLeftTextAlignment)

    def copy(self):
        new = self.__class__(self._ctx, self.text)
        _copy_attrs(self, new,
            ('x', 'y', 'width', 'height', '_transform', '_transformmode', 
            '_fillcolor', '_fontname', '_fontsize', '_align', '_lineheight'))
        return new
        
    def font_exists(cls, fontname):
        # Check if the font exists.
        f = NSFont.fontWithName_size_(fontname, 12)
        return f is not None
    font_exists = classmethod(font_exists)

    def _get_font(self):
        return NSFont.fontWithName_size_(self._fontname, self._fontsize)
    font = property(_get_font)

    def _getLayoutManagerTextContainerTextStorage(self, clr=__dummy_color):
        paraStyle = NSMutableParagraphStyle.alloc().init()
        paraStyle.setAlignment_(self._align)
        paraStyle.setLineBreakMode_(NSLineBreakByWordWrapping)
        paraStyle.setLineHeightMultiple_(self._lineheight)

        dict = {NSParagraphStyleAttributeName:paraStyle,
                NSForegroundColorAttributeName:clr,
                NSFontAttributeName:self.font}

        textStorage = NSTextStorage.alloc().initWithString_attributes_(self.text, dict)
        try:
            textStorage.setFont_(self.font)
        except ValueError:
            raise NodeBoxError("Text.draw(): font '%s' not available.\n" % self._fontname)
            return

        layoutManager = NSLayoutManager.alloc().init()
        textContainer = NSTextContainer.alloc().init()
        if self.width != None:
            textContainer.setContainerSize_((self.width,1000000))
            textContainer.setWidthTracksTextView_(False)
            textContainer.setHeightTracksTextView_(False)
        layoutManager.addTextContainer_(textContainer)
        textStorage.addLayoutManager_(layoutManager)
        return layoutManager, textContainer, textStorage

    def _draw(self):
        if self._fillcolor is None: return
        layoutManager, textContainer, textStorage = self._getLayoutManagerTextContainerTextStorage(self._fillcolor.nsColor)
        x,y = self.x, self.y
        glyphRange = layoutManager.glyphRangeForTextContainer_(textContainer)
        (dx, dy), (w, h) = layoutManager.boundingRectForGlyphRange_inTextContainer_(glyphRange, textContainer)
        preferredWidth, preferredHeight = textContainer.containerSize()
        if self.width is not None:
            if self._align == RIGHT:
                x += preferredWidth - w
            elif self._align == CENTER:
                x += preferredWidth/2 - w/2

        _save()
        # Center-mode transforms: translate to image center
        if self._transformmode == CENTER:
            deltaX = w / 2
            deltaY = h / 2
            t = Transform()
            t.translate(x+deltaX, y-self.font.defaultLineHeightForFont()+deltaY)
            t.concat()
            self._transform.concat()
            layoutManager.drawGlyphsForGlyphRange_atPoint_(glyphRange, (-deltaX-dx,-deltaY-dy))
        else:
            self._transform.concat()
            layoutManager.drawGlyphsForGlyphRange_atPoint_(glyphRange, (x-dx,y-dy-self.font.defaultLineHeightForFont()))
        _restore()
        return (w, h)

    def _get_metrics(self):
        layoutManager, textContainer, textStorage = self._getLayoutManagerTextContainerTextStorage()
        glyphRange = layoutManager.glyphRangeForTextContainer_(textContainer)
        (dx, dy), (w, h) = layoutManager.boundingRectForGlyphRange_inTextContainer_(glyphRange, textContainer)
        return w,h
    metrics = property(_get_metrics)

    def _get_path(self):
        layoutManager, textContainer, textStorage = self._getLayoutManagerTextContainerTextStorage()
        x, y = self.x, self.y
        glyphRange = layoutManager.glyphRangeForTextContainer_(textContainer)
        (dx, dy), (w, h) = layoutManager.boundingRectForGlyphRange_inTextContainer_(glyphRange, textContainer)
        preferredWidth, preferredHeight = textContainer.containerSize()
        if self.width is not None:
           if self._align == RIGHT:
               x += preferredWidth - w
           elif self._align == CENTER:
               x += preferredWidth/2 - w/2
        length = layoutManager.numberOfGlyphs()
        path = NSBezierPath.bezierPath()
        for glyphIndex in range(length):
            lineFragmentRect = layoutManager.lineFragmentRectForGlyphAtIndex_effectiveRange_(glyphIndex, None)
            # HACK: PyObjc 2.0 and 2.2 are subtly different:
            #  - 2.0 (bundled with OS X 10.5) returns one argument: the rectangle.
            #  - 2.2 (bundled with OS X 10.6) returns two arguments: the rectangle and the range.
            # So we check if we got one or two arguments back (in a tuple) and unpack them.
            if isinstance(lineFragmentRect, tuple):
                lineFragmentRect = lineFragmentRect[0]
            layoutPoint = layoutManager.locationForGlyphAtIndex_(glyphIndex)
            # Here layoutLocation is the location (in container coordinates) where the glyph was laid out. 
            finalPoint = [lineFragmentRect[0][0],lineFragmentRect[0][1]]
            finalPoint[0] += layoutPoint[0] - dx
            finalPoint[1] += layoutPoint[1] - dy
            g = layoutManager.glyphAtIndex_(glyphIndex)
            if g == 0: continue
            path.moveToPoint_((finalPoint[0], -finalPoint[1]))
            path.appendBezierPathWithGlyph_inFont_(g, self.font)
            path.closePath()
        path = BezierPath(self._ctx, path)
        trans = Transform()
        trans.translate(x,y-self.font.defaultLineHeightForFont())
        trans.scale(1.0,-1.0)
        path = trans.transformBezierPath(path)
        path.inheritFromContext()
        return path
    path = property(_get_path)
    
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

    def __repr__(self):
        return "Variable(name=%s, type=%s, default=%s, min=%s, max=%s, value=%s)" % (self.name, self.type, self.default, self.min, self.max, self.value)


def _test():
    import doctest, cocoa
    return doctest.testmod(cocoa)

if __name__=='__main__':
    _test()
