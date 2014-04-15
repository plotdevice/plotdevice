# encoding: utf-8
import types
from AppKit import *
from contextlib import contextmanager, nested
from collections import namedtuple

from plotdevice import DeviceError
from .util import _copy_attr, _copy_attrs, _flatten, trim_zeroes
from .grobs.transform import Dimension
from .grobs import *
from .lib import geometry, pathmatics
from . import grobs

__all__ = ('Context', 'Canvas', 'DEFAULT_WIDTH', 'DEFAULT_HEIGHT')

# default size for Canvas and GraphicsView objects
DEFAULT_WIDTH, DEFAULT_HEIGHT = 512, 512

# named tuples for grouping state attrs
PenStyle = namedtuple('PenStyle', ['nib', 'cap', 'join', 'dash'])
TypeStyle = namedtuple('TypeStyle', ['face', 'size', 'leading', 'align'])

### NSGraphicsContext wrapper (whose methods are the business-end of the user-facing API) ###
class Context(object):
    state_vars = '_outputmode', '_colormode', '_colorrange', '_fillcolor', '_strokecolor', '_penstyle', '_effects', '_path', '_autoclosepath', '_transform', '_transformmode', '_thetamode', '_transformstack', '_typestyle', '_stylesheet', '_oldvars', '_vars'

    def __init__(self, canvas=None, ns=None):
        """Initializes the context.

        Note that we have to pass the namespace of the executing script to allow for
        ximport's _ctx-passing magic.
        """
        if canvas is None:
            canvas = Canvas()
        if ns is None:
            ns = {}
        self.canvas = canvas
        self._ns = ns
        self._imagecache = {}
        self._vars = []
        self._resetContext()
        self._statestack = []
        self.canvas._ctx = self

        # cache a list of all of the exportable attr names (for use when making namespaces)
        self.__all__ = sorted(a for a in dir(self) if not (a.startswith('_')))

    def _activate(self):
        grobs.bind(self)

    def _saveContext(self):
        cached = [_copy_attr(getattr(self, v)) for v in Context.state_vars]
        self._statestack.insert(0, cached)

    def _restoreContext(self):
        try:
            cached = self._statestack.pop(0)
        except IndexError:
            raise DeviceError, "Too many Context._restoreContext calls."

        for attr, val in zip(Context.state_vars, cached):
            setattr(self, attr, val)

    def _resetContext(self):
        """Do a thorough reset of all the state variables"""
        self._activate()

        # color state
        self._colormode = self._outputmode = RGB
        self._colorrange = 1.0
        self._fillcolor = Color() # can also be a Gradient or Pattern
        self._strokecolor = None
        self.canvas.background = Color(1.0)

        # line style
        self._penstyle = PenStyle(nib=1.0, cap=BUTT, join=MITER, dash=None)

        # bezier construction
        self._path = None
        self._autoclosepath = True
        self._autoplot = True

        # transformation state
        self._transform = Transform()
        self._transformmode = CENTER
        self._thetamode = DEGREES

        # blend, alpha, and shadow effects
        self._effects = Effect()

        # type styles
        self._stylesheet = Stylesheet()
        self._typestyle = TypeStyle(face="Helvetica", size=24, leading=1.2, align=LEFT)

        # legacy internals
        self._transformstack = [] # only used by push/pop
        self._oldvars = self._vars
        self._vars = []

    def ximport(self, libName):
        lib = __import__(libName)
        self._ns[libName] = lib
        lib._ctx = self
        return lib

    ### Setup methods ###

    def size(self, width=None, height=None, unit=None):
        if not (width is None or height is None):
            self.canvas.width = width
            self.canvas.height = height
        if unit is not None:
            self.canvas.unit = unit
        return self.canvas.size

    @property
    def WIDTH(self):
        return Dimension('width')

    @property
    def HEIGHT(self):
        return Dimension('height')

    def speed(self, speed):
        self.canvas.speed = speed

    def background(self, *args, **kwargs):
        """Set the canvas background color

        Arguments will be interpeted according to the current color-mode and range. For details:
            help(color)

        For a transparent background, call with a single arg of None

        If more than one color arg is included, a gradient will be drawn. Pass a list with the
        `steps` keyword arg to set the relative location of each color in the gradient (0-1.0).
        Setting an `angle` keyword will draw a linear gradient (otherwise it will be radial).
        Radial gradients will draw from the canvas center by default, but a relative center can
        be specified with the `center` keyword arg. If included, the center arg should be a
        2-tuple with x,y values in the range -1 to +1.

        In addition to colors, you can also call background() with an image() as its sole argument.
        In this case the image will be tiled to fill the canvas.
        """
        if len(args) > 0:
            if len(args) == 1 and args[0] is None:
                bg = None
            elif isinstance(args[0], Image):
                bg = Pattern(args[0])
                self.canvas.clear(args[0])
            elif set(Gradient.kwargs) >= set(kwargs) and len(args)>1 and all(Color.recognized(c) for c in args):
                bg = Gradient(*args, **kwargs)
            else:
                bg = Color(args)
            self.canvas.background = bg
        return self.canvas.background

    def outputmode(self, mode=None):
        if mode is not None:
            self._outputmode = mode
        return self._outputmode

    ### Drawing grobs with the current pen/stroke/fill/transform/effects ###

    def plot(self, obj=None, live=False, **kwargs):
        if obj is None:
            return self._autoplot
        elif obj in (True,False):
            return PlotContext(self, auto=obj)
        elif not isinstance(obj, Grob):
            notdrawable = 'plot() only knows how to draw Bezier, Image, or Text objects (not %s)'%type(obj)
            raise DeviceError(notdrawable)

        obj.__class__.validate(kwargs)
        grob = obj if live else obj.copy()
        for arg_key, arg_val in kwargs.items():
            setattr(grob, arg_key, _copy_attr(arg_val))
        grob.draw()
        return grob

    # def plotstyle(self, *ops):
    #     modal = [m for m in ops if m in (ON,OFF)]
    #     mode = modal[0] if modal else self._plotstyle
    #     context_mgrs = [mgr for mgr in ops if hasattr(mgr, '__enter__')]
    #     context_mgrs.append(PlotContext(self, restore=all, style=mode))
    #     return nested(*context_mgrs)

    ### Bezier Path Commands ###

    def bezier(self, x=None, y=None, **kwargs):
        """Create and plot a new bezier path."""
        origin = (x,y) if all(isinstance(c, (int,float)) for c in (x,y)) else None
        draw = kwargs.pop('draw', self._autoplot)
        draw = kwargs.pop('plot', draw)
        kwargs['draw'] = draw
        if isinstance(x, (Bezier, list, tuple)):
            # if a list of point tuples or a Bezier is the first arg, there's
            # no need to open a context (since the path is already defined). Instead
            # handle the path immediately (passing along styles and `draw` kwarg)
            kwargs.setdefault('close', False)
            return Bezier(path=x, immediate=True, **kwargs)
        else:
            # otherwise start a new path with the presumption that it will be populated
            # in a `with` block or by adding points manually. begins with a moveto
            # element if an x,y coord was provided and relies on Bezier's __enter__
            # method to update self._path if appropriate
            p = Bezier(**kwargs)
            if origin:
                p.moveto(*origin)
            return p

    @contextmanager
    def _active_path(self, kwargs):
        """Provides a target Bezier object for drawing commands within the block.
        If a bezier is currently being constructed, drawing will be appended to it.
        Otherwise a new Bezier will be created and autoplot'ed as appropriate."""
        draw = kwargs.pop('draw', self._autoplot)
        draw = kwargs.pop('plot', draw)
        Bezier.validate(kwargs)
        p=Bezier(**kwargs)
        yield p
        if self._path is not None:
            # if a bezier is being built in a `with` block, add curves to it, but
            # ignore kwargs since the parent bezier's styles apply to all lines drawn
            self._path.extend(p)
        elif draw:
            # if this is a one-off primitive, draw it depending on the kwargs & state
            p.draw()

    def moveto(self, x, y):
        """Update the current point in the active path without drawing a line to it"""
        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        self._path.moveto(x,y)

    def lineto(self, x, y, close=False):
        """Add a line from the current point in the active path to a destination point
        (and optionally close the subpath)"""
        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        self._path.lineto(x, y)
        if close:
            self._path.closepath()

    def curveto(self, x1, y1, x2, y2, x3, y3, close=False):
        """Draw a cubic bezier curve from the active path's current point to a destination
        point (x3,y3). The handles for the current and destination points will be set by
        (x1,y1) and (x2,y2) respectively.

        Calling with close=True will close the subpath after adding the curve.
        """
        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        self._path.curveto(x1, y1, x2, y2, x3, y3)
        if close:
            self._path.closepath()

    def arcto(self, x, y, cx=None, cy=None, radius=None, ccw=False, close=False):
        """Draw a circular arc from the current point in the active path to a destination point

        To draw a semicircle to the destination point use one of:
            arcto(x,y)
            arcto(x,y, ccw=True)

        To draw a parabolic arc in the triangle between the current point, an
        intermediate control point, and the destination; choose a radius small enough
        to fit in that angle and call:
            arcto(dest_x, dest_y, cp_x, cp_y, radius)

        Calling with close=True will close the subpath after adding the arc.
        """
        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        self._path.arcto(x, y, cx, cy, radius, ccw)
        if close:
            self._path.closepath()

    ### Bezier Primitives ###

    def rect(self, x, y, width, height, roundness=0.0, radius=None, **kwargs):
        """Draw a rectangle with a corner of (x,y) and size of (width, height)

        The `roundness` arg lets you control corner radii in a size-independent way.
        It can range from 0 (sharp corners) to 1.0 (maximally round) and will ensure
        rounded corners are circular.

        The `radius` arg provides less abstract control over corner-rounding. It can be
        either a single float (specifying the corner radius in canvas units) or a
        2-tuple with the radii for the x- and y-axis respectively.
        """
        if roundness > 0:
            radius = min(width,height)/2.0 * min(roundness, 1.0)
        with self._active_path(kwargs) as p:
            p.rect(x, y, width, height, radius=radius)
        return p

    def oval(self, x, y, width, height, range=None, ccw=False, close=False, **kwargs):
        """Draw an ellipse within the rectangle specified by (x,y) & (width,height)

        The `range` arg can be either a number of degrees (from 0°) or a 2-tuple
        with a start- and stop-angle. Only that subsection of the oval will be drawn.
        The `ccw` arg flags whether to interpret ranges in a counter-clockwise direction.
        If `close` is True, a chord will be drawn between the unconnected endpoints.
        """
        with self._active_path(kwargs) as p:
            p.oval(x, y, width, height, range, ccw=ccw, close=close)
        return p
    ellipse = oval

    def line(self, x1, y1, x2, y2, ccw=None, **kwargs):
        """Draw an unconnected line segment from (x1,y1) to (x2,y2)

        Ordinarily this will be a straight line (a simple MOVETO & LINETO), but if
        the `ccw` arg is set to True or False, a semicircular arc will be drawn
        between the points in the specified direction.
        """
        with self._active_path(kwargs) as p:
            p.line(x1, y1, x2, y2, ccw=ccw)
        return p

    def poly(self, x, y, radius, sides=3, **kwargs):
        """Draw a regular polygon centered at (x,y)

        The `sides` arg sets the type of polygon to draw. Regardless of the number,
        it will be oriented such that its base is horizontal.
        """
        with self._active_path(kwargs) as p:
            p.poly(x, y, radius, sides)
        return p

    def arc(self, x, y, radius, range=None, ccw=False, close=False, **kwargs):
        """Draw a full circle or partial arc centered at (x,y)

        The `range` arg can be either a number of degrees (from 0°) or a 2-tuple
        with a start- and stop-angle.
        The `ccw` arg flags whether to interpret ranges in a counter-clockwise direction.
        If `close` is true, a pie-slice will be drawn to the origin from the ends.
        """
        with self._active_path(kwargs) as p:
            p.arc(x, y, radius, range, ccw=ccw, close=close)
        return p

    def star(self, x, y, points=20, outer=100, inner=None, **kwargs):
        """Draw a star-shaped path centered at (x,y)

        The `outer` radius sets the distance of the star's points from the origin,
        while `inner` sets the radius of the notches between points. If `inner` is
        omitted, the star will be drawn with regularized angles.
        """
        with self._active_path(kwargs) as p:
            p.star(x, y, points, outer, inner)
        return p

    def arrow(self, x, y, width=100, type=NORMAL, **kwargs):
        """Draws an arrow.

        Draws an arrow pointing at position (x,y), with a default width of 100.
        There are two different types of arrows: NORMAL and (the early-oughts favorite) FORTYFIVE.
        """
        with self._active_path(kwargs) as p:
            p.arrow(x, y, width, type)
        return p

    ### ‘Classic’ Bezier API ###

    def beginpath(self, x=None, y=None):
        self._path = Bezier()
        self._pathclosed = False
        if x != None and y != None:
            self._path.moveto(x,y)

    def closepath(self):
        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        if not self._pathclosed:
            self._path.closepath()
            self._pathclosed = True

    def endpath(self, **kwargs):
        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        if self._autoclosepath:
            self.closepath()
        p = self._path

        draw = kwargs.pop('draw', self._autoplot)
        draw = kwargs.pop('plot', draw)
        if draw:
            p.draw()
        self._path = None
        self._pathclosed = False
        return p

    def drawpath(self, path, **kwargs):
        Bezier.validate(kwargs)
        if isinstance(path, (list, tuple)):
            path = Bezier(path, **kwargs)
        else: # Set the values in the current bezier path with the kwargs
            for arg_key, arg_val in kwargs.items():
                setattr(path, arg_key, _copy_attr(arg_val))
        path.draw()

    def autoclosepath(self, close=True):
        self._autoclosepath = close

    def findpath(self, points, curvature=1.0):
        return pathmatics.findpath(points, curvature=curvature)

    ### Transformation Commands ###

    def push(self):
        """Legacy command. Equivalent to: `with transform():`

        Saves the transform state to be restored by a subsequent pop()"""
        self._transformstack.insert(0, self._transform.matrix)

    def pop(self):
        """Legacy command. Equivalent to: `with transform():`

        Restores the transform to the saved state from a prior push()"""
        try:
            self._transform = Transform(self._transformstack[0])
            del self._transformstack[0]
        except IndexError, e:
            raise DeviceError, "pop: too many pops!"

    def transform(self, *args):
        """Change the transform mode or begin a `with`-statement-scoped set of transformations

        Transformation Modes

        PlotDevice determines graphic objects' screen positions using two factors:
          - the (x,y)/(w,h) point passed to rect(), text(), etc. at creation time
          - the ‘current transform’ which has accumulated as a result of prior calls
            to commands like scale() or rotate()

        By default these transformations are applied relative to the centermost point of the
        object. This is convenient since it prevents scaling and rotation from changing the
        location of the object.

        If you prefer to apply transformations relative to objects' upper-left corner, use:
            transform(CORNER)
        You can then switch back to the default scheme with:
            transform(CENTER)
        Note that changing the mode does *not* affect the transformation matrix itself, just
        the origin-point that subsequently drawn objects will use when applying it.

        Transformation Context Manager

        When used as part of a `with` statement, the transform() command will ensure the
        mode and accumulated transformations are reverted to their previous state once the
        block completes.

        As positional args, it can accept a sequence of transformation operations. It will
        apply these at the beginning of the block, then revert them on exit (as well as any
        additional transformations made within the block). For instance,
            with transform(translate(100, 100), rotate(45)):
                skew(45)           # (this will also be reset after the block exits)
                rect(0, 0, 50, 50) # drawn as a repositioned parallelogram
            rect(0, 0, 50, 50)     # drawn as a square in the top-left corner
        """

        mode = args[0] if args and args[0] in (CENTER, CORNER) else None
        if mode is not None and mode not in (CORNER, CENTER):
            raise DeviceError, "transform: mode must be CORNER or CENTER"
        elif mode:
            args = args[1:]

        xforms = [xf for xf in args if isinstance(xf, Transform)]
        if len(xforms) != len(args):
            badarg = "transform: valid arguments are reset(), rotate(), scale(), skew(), and translate()"
            raise DeviceError(badarg)

        rollback = {"_transform":self._transform.copy(),
                    "_transformmode":self._transformmode}
        for xf in reversed(xforms):
            if hasattr(xf, '_rollback'):
                rollback.update(xf._rollback)
            else:
                # if the transform was created manually, it hasn't yet made its modification
                self._transform.prepend(xf)

        if mode:
            self._transformmode = mode

        gworld = self._transform.copy()
        gworld._rollback = rollback
        return gworld

    def reset(self):
        """Discard any accumulated transformations from prior calls to translate, scale, rotate, or skew"""
        xf = self._transform.inverse
        xf._rollback = {'_transform':self._transform.copy()}
        self._transform = Transform()
        return xf

    def translate(self, x=0, y=0):
        """Shift subsequent drawing operations by (x,y)"""
        return self._transform.translate(x,y, rollback=True)

    def scale(self, x=1, y=None):
        """Scale subsequent drawing operations by x- and y-factors

        When called with one argument, the factor will be applied to the x & y axes evenly.
        """
        return self._transform.scale(x,y, rollback=True)

    def skew(self, x=0, y=0):
        """Applies a 1- or 2-axis skew distortion to subsequent drawing operations

        The `x` and `y` args are angles in the canvas's current geometry() unit
        that control the horizontal and vertical skew respectively.

        When called with only one argument, the skew will be purely horizontal.
        """
        return self._transform.skew(x,y, rollback=True)

    def rotate(self, theta=None, **kwargs):
        """Rotate subsequent drawing operations

        Positional arg:
          `theta` is an angle in the canvas's current geometry() unit (degress by default)

        Keyword args:
          the angle can be specified units other than the geometry-default by using a
          keyword argument of `degrees`, `radians`, or `percent`.
        """
        if theta is not None:
            kwargs[self._thetamode] = theta
        return self._transform.rotate(rollback=True, **kwargs)

    ### Ink Commands ###

    def color(self, *args, **kwargs):
        """Set the default mode/range for interpreting color values (or create a color object)

        Color State

        A number of plotdevice commands can take lists of numeric arguments to specify a
        color (see stroke(), fill(), background(), etc.). When called with keyword arguments
        alone, The color() command allows you to control how these numbers should be
        interpreted in subsequent color-modification commands.

        By default, color commands interpret groups of 3 or more numbers as r/g/b triplets
        (with an optional, final alpha arg). If the `mode` keyword arg is set to RGB, HSB,
        or CMYK, subsequent color commands will interpret numerical arguments according to
        that colorspace instead.

        The `range` keyword arg sets the maximum value for color channels. By default this is
        1.0, but 255 and 100 are also sensible choices.

        For instance here are three equivalent ways of setting the fill color to ‘blue’:
            color(mode=HSB)
            fill(.666, 1.0, .76)
            color(mode=RGB, range=255)
            fill(0, 0, 190)
            color(mode=CMYK, range=100)
            fill(95, 89, 0, 0)

        Color mode & range changes can be constrained to a block of code using the `with`
        statement. e.g.,
            background(.5, .5, .6) # interpteted as r/g/b (the default)
            with color(mode=CMYK): # temporarily change the mode:
                stroke(1, 0, 0, 0) # - interpteted as c/m/y/k
            fill(1, 0, 0)          # outside the block, the mode is restored to r/g/b

        Making Colors

        When called with a sequence of color-channel values, color() will return a reusable
        Color object. These can be passed to color-related commands in lieu of numeric args.
        For example:
            red = color(1, 0, 0)                   # r/g/b
            glossy_black = color(15, 15, 15, 0.25) # r/g/b/a
            background(red)
            fill(glossy_black)

        You can also prefix the numeric args with a color mode as a convenience for setting
        one-off colors in a mode different from the current colorspace:
            color(mode=HSB)
            hsb_color = color(.7, 1, .8)           # uses current mode (h/s/b)
            cmyk_color = color(CMYK, 0, .7, .9, 0) # interpreted as c/m/y/k
            still_hsb = color(1, .5, .25)          # uses current mode (h/s/b)

        Greyscale colors can be created regardless of the current mode by passing only
        one or two values (for the brightness and alpha respectively):
            fill(1, .75) # translucent white
            stroke(0)    # opaque black

        If you pass a string to a color command, it must either be a hex-string (beginning
        with a `#`) or a valid CSS color-name. The string can be followed by an optional
        alpha argument:
            background('#f00')   # blindingly red
            fill('#74e9ff', 0.4) # translucent pale blue
            stroke('chartreuse') # electric bile
        """
        # flatten any tuples in the arguments list
        args = _flatten(args)

        # if the first arg is a color mode, use that to interpret the args
        if args and args[0] in (RGB, HSB, CMYK, GREY):
            mode, args = args[0], args[1:]
            kwargs.setdefault('mode', mode)

        if not args:
            # if called without any component values update the global mode/range,
            # and return a context manager for `with color(mode=...)` usage
            if {'range', 'mode'}.intersection(kwargs):
                return PlotContext(self, **kwargs)

        # if we got at least one numerical/string arg, parse it
        return Color(*args, **kwargs)

    def colormode(self, mode=None, range=None):
        if mode is not None:
            self._colormode = mode
        if range is not None:
            self._colorrange = float(range)
        return self._colormode

    def colorrange(self, range=None):
        if range is not None:
            self._colorrange = float(range)
        return self._colorrange

    def nofill(self):
        """Set the fill color to None"""
        self._fillcolor = None

    def fill(self, *args, **kwargs):
        """Set the fill color

        Arguments will be interpeted according to the current color-mode and range. For details:
            help(color)

        If more than one color arg is included, a gradient will be drawn. Pass a list with the
        `steps` keyword arg to set the relative location of each color in the gradient (0-1.0).
        The relative locations are based on the bounding-box of the object being filled (not its
        convex hull). So for highly rounded objects, you'll need to adjust the steps to account for
        the dead-space in the corners of the bounding box.

        Including an `angle` keyword arg will draw a linear gradient (otherwise it will be radial).
        Radial gradients will draw from the object center by default, but a relative center can
        be specified with the `center` keyword arg. If included, the center arg should be a
        2-tuple with x,y values in the range -1 to +1.

        In addition to colors, you can also call fill() with an image() as its sole argument.
        In this case the image will be tiled to fit the object being filled.

        Returns:
            the current fill color as a Color (or Gradient/Pattern) object.

        Context Manager:
            fill() can be used as part of a `with` statement in which case the fill will
            be reset to its previous value once the block completes
        """
        if args:
            if args[0] is None:
                return self.nofill()

            if isinstance(args[0], Image):
                clr = Pattern(args[0])
                self.canvas.clear(args[0])
            elif set(Gradient.kwargs) >= set(kwargs) and len(args)>1 and all(Color.recognized(c) for c in args):
                clr = Gradient(*args, **kwargs)
            else:
                clr = Color(*args)
            setattr(clr, '_rollback', dict(fill=self._fillcolor))
            self._fillcolor = clr
        return self._fillcolor

    def nostroke(self):
        """Set the stroke color to None"""
        self._strokecolor = None

    def stroke(self, *args):
        """Set the stroke color

        Arguments will be interpeted according to the current color-mode and range. For details:
            help(color)

        Returns:
            the current stroke color as a Color object.

        Context Manager:
            stroke() can be used as part of a `with` statement in which case the stroke will
            be reset to its previous value once the block completes
        """
        if len(args) > 0:
            if args[0] is None:
                return self.nostroke()

            annotated = Color(*args)
            setattr(annotated, '_rollback', dict(stroke=self._strokecolor))
            self._strokecolor = annotated
        return self._strokecolor

    ### Pen Commands ###

    def pen(self, nib=None, **spec):
        """Set the width or line-style used for stroking paths

        Positional arg:
          `nib` sets the stroke width (in points)

        Keyword args:
          `cap` sets the endcap style (BUTT, ROUND, or SQUARE).
          `join` sets the linejoin style (MITER, ROUND, or BEVEL)
          `dash` is either a single number or a list of them specifying
                 on-off intervals for drawing a dashed line

        Returns:
          a context manager allowing pen changes to be constrained to the
          block of code following a `with` statement.
        """
        # stroke width can be positional or keyword
        if nib is not None:
            spec.setdefault('nib', nib)

        # validate the line-dash stepsize (if any)
        if isinstance(spec.get('dash',None), (int,float,long)):
            spec['dash'] = [spec['dash']]
        if len(spec.get('dash',[])) % 2:
            spec['dash'] += spec['dash'][-1:] # assume even spacing for omitted skip sizes

        # pull relevant kwargs into a PenStyle tuple (but pass other args as-is)
        newstyle = {k:spec.pop(k) for k in PenStyle._fields if k in spec}
        spec['pen'] = self._penstyle._replace(**newstyle)
        return PlotContext(self, **spec)

    def strokewidth(self, width=None):
        """Legacy command. Equivalent to: pen(nib=width)"""
        if width is not None:
            self._penstyle = self._penstyle._replace(nib=max(width, 0.0001))
        return self._penstyle.nib

    def capstyle(self, style=None):
        """Legacy command. Equivalent to: pen(caps=style)"""
        if style is not None:
            if style not in (BUTT, ROUND, SQUARE):
                raise DeviceError, 'Line cap style should be BUTT, ROUND or SQUARE.'
            self._penstyle = self._penstyle._replace(cap=style)
        return self._penstyle.cap

    def joinstyle(self, style=None):
        """Legacy command. Equivalent to: pen(joins=style)"""
        if style is not None:
            if style not in (MITER, ROUND, BEVEL):
                raise DeviceError, 'Line join style should be MITER, ROUND or BEVEL.'
            self._penstyle = self._penstyle._replace(join=style)
        return self._penstyle.join

    ### Compositing Effects ###

    def alpha(self, *arg):
        """Set the global alpha

        Argument:
            a value between 0 and 1.0 that controls the opacity of any objects drawn
            to the canvas.

        Returns:
            When called with no arguments, returns the current global alpha.
            When called with a value, returns a context manager.

        Context Manager:
            When called as part of a `with` statement, the new alpha value will apply
            to all drawing within the block as a `layer' effect rather than affecting
            each object individually. As a result, all objects within the block will
            be drawn with an alpha of 1.0, then the opacity will set for the accumulated
            graphics as if it were a single object.
        """
        if not arg:
            return self._effects.alpha

        a = arg[0]
        eff = Effect(alpha=a, rollback=True)
        if a==1.0:
            a = None
        self._effects.alpha = a
        return eff

    def blend(self, *arg):
        """Set the blend-mode used for overlapping `ink'

        Argument:
            `mode`: a string with the name of a valid blend mode.

        Valid Mode Names:
            normal, clear, copy, xor, multiply, screen,
            overlay, darken, lighten, difference, exclusion,
            color-dodge, color-burn, soft-light, hard-light,
            hue, saturation, color, luminosity,
            source-in, source-out, source-atop, plusdarker, pluslighter
            destination-over, destination-in, destination-out, destination-atop

        Returns:
            When called with no arguments, returns the current blend mode.
            When called with a value, returns a context manager.

        Context Manager:
            When called as part of a `with` statement, the new blend mode will apply
            to all drawing within the block as a `layer' effect rather than affecting
            each object individually. This means all drawing within the block will be
            composited using the 'normal' blend mode, then the accumulated graphics
            will be blended to the canvas as a single group.
        """
        if not arg:
            return self._effects.blend

        mode = arg[0]
        eff = Effect(blend=mode, rollback=True)
        if mode=='normal':
            mode = None
        self._effects.blend = mode
        return eff

    def noshadow(self):
        """Disable the global dropshadow"""
        return self.shadow(None)

    def shadow(self, *args, **kwargs):
        """Set a global dropshadow

        Arguments:
            `color`: a Color object, string, or tuple of component values
            `blur`: a numeric value with the blur radius
            `offset`: a single value specifying the number of units to nudge the
                      shadow (down and to the left), or a 2-tuple with x & y offsets

        To turn dropshadows off, pass None as the `color` argument or call noshadow()

        Returns:
            When called with no arguments, returns the current Shadow object (or None).
            When called with a value, returns a context manager.

        Context Manager:
            When called as part of a `with` statement, the shadow will apply to all
            drawing within the block as a `layer' effect rather than affecting
            each object individually.
        """
        if not (args or kwargs):
            return self._effects.shadow

        s = None if None in args else Shadow(*args, **kwargs)
        eff = Effect(shadow=s, rollback=True)
        self._effects.shadow = s
        return eff

    @contextmanager
    def mask(self, stencil, channel=None):
        """Sets an inverted clipping region for a block of drawing commands.

        All drawing operations within the block will be constrained by the inverted
        Bezier or Image stencil. If masking to a bezier, only drawing operations
        *outside* of the path will be visible.

        With an image mask, drawing operations will have high opacity in places where
        the mask value is *low*. The `channel` arg specifies which component of the mask
        image should be used for this calculation. If omitted it defaults to 'alpha'
        (if available) or 'black' level (if the image is opaque).

        See also: clip()
        """
        cp = self.beginclip(stencil, mask=True, channel=channel)
        self.canvas.clear(stencil)
        yield cp
        self.endclip()


    @contextmanager
    def clip(self, stencil, channel=None):
        """Sets the clipping region for a block of drawing commands.

        All drawing operations within the block will be constrained by the Bezier or
        Image stencil. If clipping to a bezier, only content *within* the bounds of
        the path will be rendered.

        With an image mask, drawing operations will have high opacity in places where
        the mask value is also high. The `channel` arg specifies which component of
        the mask image should be used for this calculation. If omitted it defaults
        to 'alpha' (if available) or 'black' level (if the image is opaque).

        See also: mask()
        """
        cp = self.beginclip(stencil, mask=False, channel=channel)
        self.canvas.clear(stencil)
        yield cp
        self.endclip()

    def beginclip(self, stencil, mask=False, channel=None):
        cp = Mask(stencil, invert=bool(mask), channel=channel)
        self.canvas.push(cp)
        return cp

    def endclip(self):
        self.canvas.pop()

    ### Typography ###

    def font(self, *args, **kwargs):
        """Set the current font to be used in subsequent calls to text()"""
        return Font(*args, **kwargs)._use()

    def fontsize(self, fontsize=None):
        if fontsize is not None:
            self._typestyle = self._typestyle._replace(size=fontsize)
        return self._typestyle.size

    def lineheight(self, lineheight=None):
        if lineheight is not None:
            self._typestyle = self._typestyle._replace(leading=lineheight)
        return self._typestyle.leading

    def align(self, align=None):
        if align is not None:
            self._typestyle = self._typestyle._replace(align=align)
        return self._typestyle.align

    def stylesheet(self, name=None, *args, **kwargs):
        """Access the context's Stylesheet (used by the text() command to format marked-up strings)

        The stylesheet() command allows for both reading and writing of the global state depending
        on the number and style of arguments received:

        stylesheet("stylename", ...)
            To set a style, pass the desired tag name as the first argument, followed by any number of
            arguments to specify the font. The argument format is identical to the font() command, e.g.:

                stylesheet('foo', family="Avenir", italic=True)

            now when you call the text command, you can use html-ish markup to use the style:

            text("<foo>This is avenir oblique</foo> This is whatever the context's default font is", 0,0)

            Ordinarily any text not contained within style tags will inherit its font from the context's
            state (whatever the most recent font() call set it to). This can be useful if you define your
            styles as modifications of that basic state rather than complete overrides of the face.

            If you'd prefer to use a fixed style for

        stylesheet("stylename", None)
           To delete a style, pass None along with the style name

        stylesheet("stylename")
            When called with a style name and no other arguments, returns a dictionary with the specification
            for the style (or None if it doesn't exist). This dictionary is only a copy, to modify the style,
            update

        stylesheet()
            With no arguments, returns the context's Stylesheet object for you to monkey with directly.
            It acts as a dictionary with all currently defined styles as its keys.

        """
        if name is None:
            return self._stylesheet
        else:
            return self._stylesheet.style(name, *args, **kwargs)

    def text(self, txt, x=0, y=0, width=None, height=None, outline=False, **kwargs):
        txt = Text(txt, x, y, width, height, **kwargs)
        if self._path is None and not outline:
            # treat as Text
            if kwargs.get('plot', kwargs.get('draw', self._autoplot)):
              txt.draw()
            return txt
        else:
            # treat as Bezier
            txt.inherit()
            with self._active_path(kwargs) as p:
                p.extend(txt.path)
            _copy_attrs(txt, p, {'fill', 'stroke', 'strokewidth'}.intersection(kwargs))
            return p

    def textpath(self, txt, x, y, width=None, height=None, **kwargs):
        txt = Text(txt, x, y, width, height, **kwargs)
        txt.inherit()
        return txt.path

    def textmetrics(self, txt, width=None, height=None, **kwargs):
        txt = Text(txt, 0, 0, width, height, **kwargs)
        txt.inherit()
        return txt.metrics

    def textwidth(self, txt, width=None, **kwargs):
        """Calculates the width of a single-line string."""
        return self.textmetrics(txt, width, **kwargs)[0]

    def textheight(self, txt, width=None, **kwargs):
        """Calculates the height of a (probably) multi-line string."""
        return self.textmetrics(txt, width, **kwargs)[1]

    ### Image commands ###

    def image(self, path, x=0, y=0, width=None, height=None, data=None, **kwargs):
        draw = kwargs.pop('draw', self._autoplot)
        draw = kwargs.pop('plot', draw)

        img = Image(path, x, y, width, height, data=data, **kwargs)
        if draw:
            img.draw()
        return img

    def imagesize(self, path, data=None):
        img = Image(path, data=data)
        return img.size

    ### Canvas proxy ###

    def save(self, fname, format=None):
        self.canvas.save(fname, format)

    def export(self, fname, fps=None, loop=None, bitrate=1.0):
        """Context manager for image/animation batch exports.

        When writing multiple images or frames of animation, the export manager keeps track of when
        the canvas needs to be cleared, when to write the graphics to file, and preventing the python
        script from exiting before the background thread has completed writing the file.

        To export an image:
            with export('output.pdf') as image:
                ... # (do some drawing)

        To export a movie:
            with export('anim.mov', fps=30, bitrate=1.8) as movie:
                for i in xrange(100):
                    with movie.frame:
                        ... # draw the next frame

        The file format is selected based on the file extension of the fname argument. If the format
        is `gif`, an image will be exported unless an `fps` or `loop` argument (of any value) is
        also provided, in which case an animated gif will be created. Otherwise all arguments aside
        from the fname are optional and default to:
            fps: 30      (relevant for both gif and mov exports)
            loop: False  (set to True to loop forever or an integer for a fixed number of repetitions)
            bitrate: 1.0 (in megabits per second)

        Note that the `loop` argument only applies to animated gifs and `bitrate` is used in the H.264
        encoding of `mov` files.

        For implementational details, inspect the format-specific exporters in the repl:
            help(export.PDF)
            help(export.Movie)
            help(export.ImageSequence)
        """
        from plotdevice.run.export import export
        return export(self, fname, fps=fps, loop=loop, bitrate=bitrate)


    ### Geometry

    def _angle(self, theta, dst_mode=RADIANS):
        """Used internally to map the current theta unit into other scales"""
        src_mode = self._thetamode
        if dst_mode==src_mode:
            return theta
        basis={DEGREES:360.0, RADIANS:2*pi, PERCENT:1.0}
        return (theta*basis[dst_mode])/basis[src_mode]

    def geometry(self, mode=None):
        """Set the mode used for angles (DEGREES, RADIANS, or PERCENT)"""
        if mode is not None:
            if mode not in (DEGREES, RADIANS, PERCENT):
                badunit = 'the geometry() mode must be DEGREES, RADIANS, or PERCENT'
                raise DeviceError(badunit)
            self._thetamode = mode
        return self._thetamode

    def measure(self, obj, width=None, height=None, **kwargs):
        """Returns a Size tuple for graphics objects, text, or file objects pointing to images"""
        if isinstance(obj, basestring):
            return Text(obj, 0, 0, width, height, **kwargs).metrics
        elif isinstance(obj, file):
            return Image(data=obj.read()).size
        elif isinstance(obj, Text):
            return obj.metrics()
        elif isinstance(obj, (Bezier, Image)):
            return obj.bounds.size
        else:
            badtype = "measure() can only handle Text, Images, Beziers, and file() objects (got %s)"%type(obj)
            raise DeviceError(badtype)

    ### Variables ###

    # def var(self, name, type, default=None, min=0, max=100, value=None):
    #     v = Variable(name, type, default, min, max, value)
    #     v = self.addvar(v)

    # def addvar(self, v):
    #     oldvar = self.findvar(v.name)
    #     if oldvar is not None:
    #         if oldvar.compliesTo(v):
    #             v.value = oldvar.value
    #     self._vars.append(v)
    #     self._ns[v.name] = v.value

    # def findvar(self, name):
    #     for v in self._oldvars:
    #         if v.name == name:
    #             return v
    #     return None


class PlotContext(object):
    """Performs the setup/cleanup for a `with pen()/stroke()/fill()/color(mode,range)` block"""
    _statevars = dict(pen='_penstyle', stroke='_strokecolor', fill='_fillcolor',
                      mode='_colormode', range='_colorrange', auto='_autoplot')

    def __init__(self, ctx, restore=None, **spec):
        # start with the current context state as a baseline
        prior = {k:getattr(ctx, v) for k,v in self._statevars.items() if k in spec or restore==all}
        snapshots = {k:v._rollback for k,v in spec.items() if hasattr(v, '_rollback')}
        prior.update(snapshots)

        for param, val in spec.items():
            # make sure fill & stroke are Color objects (or None)
            if param in ('stroke','fill'):
                if val is None: continue
                val = Color(val)
                spec[param] = val
            setattr(ctx, self._statevars[param], val)

        # keep the dictionary of prior state around for restoration at the end of the block
        self._rollback = prior
        self._spec = spec
        self._ctx = ctx

    def __enter__(self):
        return dict(self._spec)

    def __exit__(self, type, value, tb):
        for param, val in self._rollback.items():
            setattr(self._ctx, self._statevars[param], val)

    def __repr__(self):
        spec = ", ".join('%s=%r'%(k,v) for k,v in self._spec.items())
        return 'PlotContext(%s)'%spec


### containers ###

class _PDFRenderView(NSView):

    # This view was created to provide PDF data.
    # Strangely enough, the only way to get PDF data from Cocoa is by asking
    # dataWithPDFInsideRect_ from a NSView. So, we create one just to get to
    # the PDF data.

    def initWithCanvas_(self, canvas):
        super(_PDFRenderView, self).initWithFrame_( ((0, 0), canvas.pagesize) )
        self.canvas = canvas
        return self

    def drawRect_(self, rect):
        self.canvas.draw()

    def isOpaque(self):
        return False

    def isFlipped(self):
        return True

class Canvas(Grob):

    def __init__(self, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, unit=px):
        self.unit = unit
        self.width = width
        self.height = height
        self.speed = None
        self.mousedown = False
        self.clear()

    @trim_zeroes
    def __repr__(self):
        return 'Canvas(%0.3f, %0.3f, %s)'%(self.width, self.height, self.unit.name)

    def clear(self, grob=None):
        if grob:
            self._drop(grob, self._grobs)
        else:
            self._grobs = self._container = []
            self._grobstack = [self._grobs]

    def _drop(self, grob, container):
        if grob in container:
            container.remove(grob)
        for frob in [f for f in container if hasattr(f, 'contents')]:
            self._drop(grob, frob.contents)

    @property
    def size(self):
        """The canvas's size in terms of its default unit"""
        return Size(self.width, self.height)

    @property
    def pagesize(self):
        """The canvas's size in Postscript points"""
        dpx = self.unit.basis
        return Size(self.width*dpx, self.height*dpx)

    def _get_unit(self):
        return self._unit
    def _set_unit(self, u):
        if u not in (px, inch, pica, cm, mm):
            nonstandard = 'Canvas units must be one of: px, inch, pica, cm, or mm (not %r)'%u
            raise DeviceError(nonstandard)
        self._unit = u
    unit = property(_get_unit, _set_unit)

    def __iter__(self):
        for grob in self._grobs:
            yield grob

    def __len__(self):
        return len(self._grobs)

    def __getitem__(self, index):
        return self._grobs[index]

    def append(self, el):
        # when beziers, images, and text are added, they're placed in the current
        # tail of the container stack (see push/pop)
        self._container.append(el)

    def push(self, containerGrob):
        # when things like Masks are added, they become their own container that
        # applies to all grobs drawn until the effect is popped off the stack
        self._grobstack.insert(0, containerGrob)
        self._container.append(containerGrob)
        self._container = containerGrob

    def pop(self):
        try:
            del self._grobstack[0]
            self._container = self._grobstack[0]
        except IndexError, e:
            raise DeviceError, "pop: too many canvas pops!"

    def draw(self):
        if self.background is not None:
            rect = ((0,0), self.pagesize)
            if isinstance(self.background, Gradient):
                self.background.fill(rect)
            else:
                self.background.set()
                NSRectFillUsingOperation(rect, NSCompositeSourceOver)
        if self.unit.basis != 1.0:
            # it might be wiser to have this factor into ctx.transform so it doesn't end up
            # scaling stroke widths...
            t = Transform()
            t.scale(self.unit.basis)
            t.concat()
        for grob in self._grobs:
            grob._draw()

    def rasterize(self, zoom=1.0):
        """Return an NSImage with the canvas dimensions scaled to the specified zoom level"""
        w,h = self.pagesize
        img = NSImage.alloc().initWithSize_((w*zoom, h*zoom))
        img.setFlipped_(True)
        img.lockFocus()
        trans = NSAffineTransform.transform()
        trans.scaleBy_(zoom)
        trans.concat()
        self.draw()
        img.unlockFocus()
        return img

    def _getImageData(self, format):
        if format == 'pdf':
            view = _PDFRenderView.alloc().initWithCanvas_(self)
            return view.dataWithPDFInsideRect_(view.bounds())
        elif format == 'eps':
            view = _PDFRenderView.alloc().initWithCanvas_(self)
            return view.dataWithEPSInsideRect_(view.bounds())
        else:
            imgTypes = {"gif":  NSGIFFileType,
                        "jpg":  NSJPEGFileType,
                        "jpeg": NSJPEGFileType,
                        "png":  NSPNGFileType,
                        "tiff": NSTIFFFileType}
            if format not in imgTypes:
                badformat = "Filename should end in .pdf, .eps, .tiff, .gif, .jpg or .png"
                raise DeviceError(badformat)
            data = self.rasterize().TIFFRepresentation()
            if format != 'tiff':
                imgType = imgTypes[format]
                rep = NSBitmapImageRep.imageRepWithData_(data)
                return rep.representationUsingType_properties_(imgType, None)
            else:
                return data

    def save(self, fname, format=None):
        """Write the current graphics objects to an image file"""
        if format is None:
            format = fname.rsplit('.',1)[-1].lower()
        data = self._getImageData(format)
        fname = NSString.stringByExpandingTildeInPath(fname)
        data.writeToFile_atomically_(fname, False)

