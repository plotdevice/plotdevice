# encoding: utf-8
import os, re, types
from contextlib import contextmanager
from collections import namedtuple
from os.path import exists, expanduser
from objc import super

from .lib.cocoa import *
from .lib import pathmatics
from .util import _copy_attr, _copy_attrs, _flatten, trim_zeroes, numlike, autorelease
from .gfx.geometry import Dimension, parse_coords
from .gfx.typography import Layout
from .gfx import *
from . import gfx, lib, util, Halted, DeviceError

__all__ = ('Context', 'Canvas')

# default size for Canvas and GraphicsView objects
DEFAULT_WIDTH, DEFAULT_HEIGHT = 512, 512

# named tuples for grouping state attrs
PenStyle = namedtuple('PenStyle', ['nib', 'cap', 'join', 'dash'])
GridUnits = namedtuple('GridUnits', ['unit', 'dpx', 'to_px', 'from_px'])

### NSGraphicsContext wrapper (whose methods are the business-end of the user-facing API) ###
class Context(object):
    _state_vars = '_outputmode', '_colormode', '_colorrange', '_fillcolor', '_strokecolor', '_penstyle', '_font', '_effects', '_path', '_autoclosepath', '_grid', '_transform', '_transformmode', '_thetamode', '_transformstack', '_oldvars', '_vars'

    def __init__(self, canvas=None, ns=None):
        """Initializes the context.

        Note that we have to pass the namespace of the executing script to allow for
        ximport's _ctx-passing magic.
        """
        self.canvas = Canvas() if canvas is None else canvas
        self._ns = {} if ns is None else ns
        self._imagecache = {}
        self._statestack = []
        self._vars = []

        self._resetContext()     # initialize default graphics state
        self._resetEnvironment() # initialize namespace & canvas

    def _activate(self):
        """Pass a reference to this context to all the gfx objects and libs that have
        registered themselves as needing _ctx access."""
        gfx.bind(self)
        lib.bind(self)

    def _resetEnvironment(self):
        """Set the namespace and canvas to factory defaults (preparing for a new run)"""

        # clean out the namespace. include just the plotdevice commands/types
        self._ns.clear()
        self._ns.update( (a,getattr(util,a)) for a in util.__all__  )
        self._ns.update( (a,getattr(gfx,a)) for a in gfx.__all__  )
        self._ns.update( (a,getattr(self,a)) for a in dir(self) if not a.startswith('_') )
        self._ns["_ctx"] = self

        # clear the canvas and reset the dims/background
        self.canvas.reset()
        self.canvas.background = Color(1.0)
        self.canvas.speed = None
        self.canvas.unit = px

        # keep track of non-px canvas units
        self._grid = GridUnits(px, 1, Transform(), Transform())

        # default output colorspace
        self._outputmode = RGB

    def _resetContext(self):
        """Do a thorough reset of all the state variables"""
        self._activate()

        # color state
        self._colormode = RGB
        self._colorrange = 1.0
        self._fillcolor = Color() # can also be a Gradient or Pattern
        self._strokecolor = None

        # line style
        self._penstyle = PenStyle(nib=1.0, cap=BUTT, join=MITER, dash=None)

        # transformation state
        self._transform = Transform()
        self._transformmode = CENTER
        self._thetamode = DEGREES

        # compositing effects (blend, alpha, and shadow)
        self._effects = Effect()

        # type styles
        self._stylesheet = Stylesheet()
        self._font = Font(None)

        # bezier construction internals
        self._path = None
        self._autoclosepath = True
        self._autoplot = True

        # legacy internals
        self._transformstack = [] # only used by push/pop
        self._oldvars = self._vars
        self._vars = []

    def _saveContext(self):
        cached = [_copy_attr(getattr(self, v)) for v in Context._state_vars]
        self._statestack.insert(0, cached)
        self.clear()

    def _restoreContext(self):
        try:
            cached = self._statestack.pop(0)
        except IndexError:
            raise DeviceError, "Too many Context._restoreContext calls."

        for attr, val in zip(Context._state_vars, cached):
            setattr(self, attr, val)
        self.canvas.unit = self._grid.unit

    def ximport(self, libName):
        lib = __import__(libName)
        self._ns[libName] = lib
        lib._ctx = self
        return lib

    ### Setup methods ###

    def size(self, width=None, height=None, unit=None):
        """Set the dimensions of the canvas

        The canvas defaults to 512x512 pixels, but this can be changed by calling
        size() as the first drawing-related command in your script. In addition to
        the `width` and `height` args, you can provide an optional `unit`. Use one
        of the constants: px, pica, inch, cm, or mm.

        Setting the canvas unit affects all subsequent drawing commands too. For
        instance, the following will create a 1" x 1" square in the top-left corner
        of a standard letter-sized page:
            size(8.5, 11, inch)
            rect(0,0,1,1)
        """
        if not (width is None or height is None):
            self.canvas.width = width
            self.canvas.height = height
        if unit is not None:
            dpx = unit.basis
            self._grid = GridUnits(unit, dpx, Transform().scale(dpx), Transform().scale(1/dpx))
            self.canvas.unit = unit
        return self.canvas.size

    @property
    def WIDTH(self):
        """The current canvas width (read-only)"""
        return Dimension('width')

    @property
    def HEIGHT(self):
        """The current canvas height (read-only)"""
        return Dimension('height')

    def speed(self, fps):
        """Set the target frame-rate for an animation

        Calling speed() signals to PlotDevice that your script is an animation containing a
        `draw()` method (and optionally, `setup()` and `stop()` methods to be called at the
        beginning and end of the run respectively). Your draw method will be called repeatedly
        until hitting command-period.

        If you set the speed to 0 your draw method will be called only once and the animation
        will terminate.
        """
        if fps<0:
            timetraveler = "Sorry, can't animate at %r fps" % fps
            raise DeviceError(timetraveler)
        self.canvas.speed = fps

    def halt(self):
        """Cleanly terminates an animation when called from your draw() function"""
        raise Halted()

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
            elif isinstance(args[0],basestring) and (args[0].startswith('http') or exists(expanduser(args[0]))):
                bg = Pattern(args[0])
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

    ### Bezier Path Commands ###

    def bezier(self, x=None, y=None, **kwargs):
        """Create and plot a new bezier path."""
        draw = self._should_plot(kwargs)
        try: # accept a Point as the first arg
            x, y = parse_coords([x], [Point])
        except:
            pass

        Bezier.validate(kwargs)
        if isinstance(x, (list, tuple, Bezier)):
            # if the first arg is an iterable of point tuples or an existing Bezier, apply
            # the `close` kwarg immediately since the path is already fully-specified
            pth = Bezier(path=x, **kwargs)
            pth._autoclose()
        else:
            # otherwise start a new path with the presumption that it will be populated
            # in a `with` block or by adding points manually. begins with a moveto
            # element if an x,y coord was provided and relies on Bezier's __enter__
            # method to update self._path if appropriate
            pth = Bezier(**kwargs)
            if numlike(x) and numlike(y):
                pth.moveto(x,y)
        if draw:
            pth.draw()
        return pth

    @contextmanager
    def _active_path(self, kwargs):
        """Provides a target Bezier object for drawing commands within the block.
        If a bezier is currently being constructed, drawing will be appended to it.
        Otherwise a new Bezier will be created and autoplot'ed as appropriate."""
        draw = self._should_plot(kwargs)

        Bezier.validate(kwargs)
        p=Bezier(**kwargs)
        yield p
        if self._path is not None:
            # if a bezier is being built in a `with` block, add curves to it, but
            # ignore kwargs since the parent bezier's styles apply to all lines drawn
            xf = p._screen_transform
            self._path.extend(xf.apply(p))
        elif draw:
            # if this is a one-off primitive, draw it depending on the kwargs & state
            p.draw()

    def moveto(self, *coords):
        """Update the current point in the active path without drawing a line to it

        Syntax:
            moveto(x, y)
            moveto(Point)
        """
        (x,y) = parse_coords(coords, [Point])
        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        self._path.moveto(x,y)

    def lineto(self, *coords, **kwargs):
        """Add a line from the current point in the active path to a destination point
        (and optionally close the subpath)

        Syntax:
            lineto(x, y, close=False)
            lineto(Point, close=False)
        """
        close = kwargs.pop('close', False)
        (x,y) = parse_coords(coords, [Point])
        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        self._path.lineto(x, y)
        if close:
            self._path.closepath()

    def curveto(self, *coords, **kwargs):
        """Draw a cubic bezier curve from the active path's current point to a destination
        point (x3,y3). The handles for the current and destination points will be set by
        (x1,y1) and (x2,y2) respectively.

        Syntax:
            curveto(x1, y1, x2, y2, x3, y3, close=False)
            curveto(Point, Point, Point, close=False)

        Calling with close=True will close the subpath after adding the curve.
        """
        close = kwargs.pop('close', False)
        (x1,y1), (x2,y2), (x3,y3) = parse_coords(coords, [Point,Point,Point])

        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        self._path.curveto(x1, y1, x2, y2, x3, y3)
        if close:
            self._path.closepath()

    def arcto(self, *coords, **kwargs):
        """Draw a circular arc from the current point in the active path to a destination point

        Syntax:
            arcto(x1, y1, ccw=False, close=False)
            arcto(Point, ...)
            arcto(x1, y1, x2, y2, radius=None, close=False)
            arcto(Point, Point, ...)

        To draw a semicircle to the destination point use one of:
            arcto(x,y)
            arcto(x,y, ccw=True)

        To draw a parabolic arc in the triangle between the current point, an
        intermediate control point, and the destination; choose a radius small enough
        to fit in that angle and call:
            arcto(mid_x, mid_y, dest_x, dest_y, radius)

        Calling with close=True will close the subpath after adding the arc.
        """
        ccw = kwargs.pop('ccw', False)
        close = kwargs.pop('close', False)
        radius = kwargs.pop('radius', None)
        x2 = y2 = None
        try:
            (x1,y1), (x2,y2), radius = parse_coords(coords, [Point,Point,float])
        except:
            try:
                (x1,y1), (x2,y2) = parse_coords(coords, [Point,Point])
            except:
                (x1,y1) = parse_coords(coords, [Point])

        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        self._path.arcto(x1, y1, x2, y2, radius, ccw)
        if close:
            self._path.closepath()

    ### Bezier Primitives ###

    def rect(self, *coords, **kwargs):
        """Draw a rectangle with a corner of (x,y) and size of (width, height)

        Syntax:
            rect(x, y, width, height, roundness=0.0, radius=None, plot=True, **kwargs):
            rect(Point, Size, ...)
            rect(Region, ...)

        The `roundness` arg lets you control corner radii in a size-independent way.
        It can range from 0 (sharp corners) to 1.0 (maximally round) and will ensure
        rounded corners are circular.

        The `radius` arg provides less abstract control over corner-rounding. It can be
        either a single float (specifying the corner radius in canvas units) or a
        2-tuple with the radii for the x- and y-axis respectively.
        """
        try:
            (x,y), (w,h), roundness = parse_coords(coords, [Point,Size,float])
        except:
            (x,y), (w,h) = parse_coords(coords, [Point,Size])
            roundness = 0
        roundness = kwargs.pop('roundness', roundness)
        radius = kwargs.pop('radius', None)
        if roundness > 0:
            radius = min(w,h)/2.0 * min(roundness, 1.0)

        with self._active_path(kwargs) as p:
            p.rect(x, y, w, h, radius=radius)
        return p

    def oval(self, *coords, **kwargs):
        """Draw an ellipse within the rectangle specified by (x,y) & (width,height)

        Syntax:
            oval(x, y, width, height, range=None, ccw=False, close=False, plot=True, **kwargs):
            oval(Point, Size, ...)
            oval(Region, ...)

        The `range` arg can be either a number of degrees (from 0°) or a 2-tuple
        with a start- and stop-angle. Only that subsection of the oval will be drawn.
        The `ccw` arg flags whether to interpret ranges in a counter-clockwise direction.
        If `close` is True, a chord will be drawn between the unconnected endpoints.
        """
        rng = kwargs.pop('range', None)
        ccw = kwargs.pop('ccw', False)
        close = kwargs.pop('close', False)
        (x,y), (w,h) = parse_coords(coords, [Point,Size])

        with self._active_path(kwargs) as p:
            p.oval(x, y, w, h, rng, ccw, close)
        return p
    ellipse = oval

    def line(self, *coords, **kwargs):
        """Draw an unconnected line segment from (x1,y1) to (x2,y2)

        Syntax:
            line(x1, y1, x2, y2, ccw=None, plot=True, **kwargs)
            line(Point, Point, ...)
            line(x1, y1, dx=0, dy=0, ccw=None, plot=True, **kwargs)
            line(Point, dx=0, dy=0, ...)

        Ordinarily this will be a straight line (a simple MOVETO & LINETO), but if
        the `ccw` arg is set to True or False, a semicircular arc will be drawn
        between the points in the specified direction.
        """
        dx, dy = kwargs.pop('dx',None), kwargs.pop('dy', None)
        if any(map(numlike, [dx, dy])):
            start = parse_coords(coords, [Point])
            end = start + (dx or 0, dy or 0)
            (x1,y1), (x2,y2) = start, end
        else:
            (x1,y1), (x2,y2) = parse_coords(coords, [Point,Point])
        ccw = kwargs.pop('ccw', None)

        with self._active_path(kwargs) as p:
            p.line(x1, y1, x2, y2, ccw)
        return p

    def poly(self, *coords, **kwargs):
        """Draw a regular polygon centered at (x,y)

        Syntax:
            poly(x, y, radius, sides=4, points=None, plot=True, **kwargs)
            poly(Point, radius, ...)

        The `sides` arg sets the type of polygon to draw. Regardless of the number,
        it will be oriented such that its base is horizontal.

        If a `points` keyword argument is passed instead of a `sides` argument,
        a regularized star polygon will be drawn at the given coordinates & radius,
        """
        sides = kwargs.pop('sides', 4)
        points = kwargs.pop('points', None)
        if 'radius' in kwargs:
            coords = coords + (kwargs.pop('radius'),)
        (x,y), radius = parse_coords(coords, [Point,float])

        with self._active_path(kwargs) as p:
            p.poly(x, y, radius, sides, points)
        return p

    def arc(self, *coords, **kwargs):
        """Draw a full circle or partial arc centered at (x,y)

        Syntax:
            arc(x, y, radius, range=None, ccw=False, close=False, plot=True, **kwargs)
            arc(Point, radius, ...)

        The `range` arg can be either a number of degrees (from 0°) or a 2-tuple
        with a start- and stop-angle.
        The `ccw` arg flags whether to interpret ranges in a counter-clockwise direction.
        If `close` is true, a pie-slice will be drawn to the origin from the ends.
        """
        rng = kwargs.pop('range', None)
        ccw = kwargs.pop('ccw', False)
        close = kwargs.pop('close', False)
        if 'radius' in kwargs:
            coords = coords + (kwargs.pop('radius'),)
        (x,y), radius = parse_coords(coords, [Point,float])

        with self._active_path(kwargs) as p:
            p.arc(x, y, radius, rng, ccw, close)
        return p

    def star(self, x, y, points=20, outer=100, inner=None, **kwargs):
        """Draw a star-shaped path centered at (x,y)

        The `outer` radius sets the distance of the star's points from the origin,
        while `inner` sets the radius of the notches between points. If `inner` is
        omitted, it will be set to half the outer radius.
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

        draw = self._should_plot(kwargs)
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

    def transform(self, mode=None, matrix=None):
        """Change the transform mode or begin a `with`-statement-scoped set of transformations

        Transformation Modes

        PlotDevice determines graphic objects' final screen positions using two factors:
          - the (x,y)/(w,h) point passed to rect(), text(), etc. at creation time
          - the ‘current transform’ which has accumulated as a result of prior calls
            to commands like scale() or rotate()

        By default these transformations are applied relative to the centermost point of the
        object (based on its x/y/w/h). This is convenient since it prevents scaling and rotation
        from changing the location of the object.

        If you prefer to apply transformations relative to the canvas's upper-left corner, use:
            transform(CORNER)
        You can then switch back to the default scheme with:
            transform(CENTER)
        Note that changing the mode does *not* affect the transformation matrix itself, just
        the origin-point that subsequently drawn objects will use when applying it.

        Transformation Matrices

        In addition to changing the mode, the transform() command also allows you to
        overwrite the underlying transformation matrix with a new set of values. Pass a
        6-element list or tuple of the form [m11, m21, m12, m22, tX, tY] as the `matrix`
        argument to update the current transform. Note that you can omit the `mode` arg
        when setting a new matrix if you don't want the transformation origin to change.

        See Apple's docs for all the math-y details:
            http://tinyurl.com/cocoa-drawing-guide-transforms

        Transformation Context Manager

        When used as part of a `with` statement, the transform() command will ensure the
        mode and transformations applied during the indented code-block are reverted to their
        previous state once the block completes.
        """
        if matrix is None and isinstance(mode, (list, tuple, NSAffineTransformStruct)):
            mode, matrix = None, mode

        if mode not in (CORNER, CENTER, None):
            badmode = "transform: mode must be CORNER or CENTER"
            raise DeviceError(badmode)

        rollback = {"_transformmode":self._transformmode,
                    "_transform":self._transform.copy()}

        if mode:
            self._transformmode = mode

        if matrix:
            self._transform = Transform(matrix)

        xf = self._transform.copy()
        xf._rollback = rollback
        return xf

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
        (with an optional, final alpha arg). If the `mode` keyword arg is set to RGB, HSV,
        or CMYK, subsequent color commands will interpret numerical arguments according to
        that colorspace instead.

        The `range` keyword arg sets the maximum value for color channels. By default this is
        1.0, but 255 and 100 are also sensible choices.

        For instance here are three equivalent ways of setting the fill color to ‘blue’:
            color(mode=HSV)
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
            color(mode=HSV)
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
        if args and args[0] in (RGB, HSV, CMYK, GREY):
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
        """Legacy command. Equivalent to: color(mode=...)"""
        if mode is not None:
            self._colormode = mode
        if range is not None:
            self._colorrange = float(range)
        return self._colormode

    def colorrange(self, range=None):
        """Legacy command. Equivalent to: color(range=...)"""
        if range is not None:
            self._colorrange = float(range)
        return self._colorrange

    def nofill(self):
        """Set the fill color to None"""
        clr = Color(None)
        setattr(clr, '_rollback', dict(fill=self._fillcolor))
        self._fillcolor = None
        return clr

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
            elif isinstance(args[0],basestring) and (args[0].startswith('http') or exists(expanduser(args[0]))):
                clr = Pattern(args[0])
            elif set(Gradient.kwargs) >= set(kwargs) and len(args)>1 and all(Color.recognized(c) for c in args):
                clr = Gradient(*args, **kwargs)
            else:
                clr = Color(*args)
            setattr(clr, '_rollback', dict(fill=self._fillcolor))
            self._fillcolor = clr
        return self._fillcolor

    def nostroke(self):
        """Set the stroke color to None"""
        clr = Color(None)
        setattr(clr, '_rollback', dict(fill=self._strokecolor))
        self._strokecolor = None
        return clr

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
        if numlike(nib):
            spec.setdefault('nib', nib)
        elif nib is not None:
            badnib = "the pen's nib size must be a number (not %r)" % type(nib)
            raise DeviceError(badnib)

        # validate the line-dash stepsize (if any)
        if numlike(spec.get('dash',None)):
            spec['dash'] = [spec['dash']]
        if len(spec.get('dash') or []) % 2:
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
                      shadow (down and to the right), or a 2-tuple with x & y offsets

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
        """Legacy command. Equivalent to: `with clip():`"""
        cp = Stencil(stencil, invert=bool(mask), channel=channel)
        self.canvas.push(cp)
        return cp

    def endclip(self):
        """Legacy command. Equivalent to: `with clip():`"""
        self.canvas.pop()

    ### Typography ###

    def fonts(self, like=None, encoding='western'):
        """Returns a list of all fonts installed on the system (with filtering capabilities)

        If `like` is a string, only fonts whose names contain those characters will be returned.

        If `encoding` is "western" (the default), fonts with non-western character sets will
        be omitted. Setting it to another writing system like "korean" or "cyrillic".
        """
        return Family.find(like, encoding)

    def font(self, *args, **kwargs):
        """Set the typeface & character-style to be used in subsequent calls to text()

        All font() arguments are optional and any un-specified values will be inherited
        from the canvas's current font. Calling font() with no arguments simply returns
        the current Font object (which exposes metrics, layout-settings, and more).

        Positional Args:
          `family` is a case insensitive font family name
          `weight` is the name of the desired weight (`regular` by default)
          `size` is a number with the point-size for the font

        Character-style Keyword Args:
          `width` is the name of a condensed- or extended-style font width
          `variant` selects between fonts with names like "display", "subhead", etc.
          `tracking` is the amount of letter-spacing to add (1000 = 1em)
          `italic` is a boolean specifying whether to use a slanted face

        OpenType Keyword Args (set flags if supported by current typeface):
          `sc` small-capitals (0, 1, -1, or all)
          `ss` numbered stylistic sets (1-20 or a tuple of sets to enable)
          `lig` ligatures (0, 1, or all)
          `osf` old-style-figures (0 or 1)
          `tab` tabular numerals (0 or 1)
          `vpos` superscript/subscript (-1, 0, 1, or ord)
          `frac` automatic fractions (0 or 1)

        Returns:
          a Font object with a number of inspectable attributes

        Context Manager
            font() can be used as part of a `with` statement in which case the character
            style will be reset to its previous value once the block completes
        """
        Font.validate(kwargs)
        if args or kwargs:
            newfont = Font(*args, **kwargs)
            newfont._rollback = self._font
            self._font = newfont
        return self._font

    def layout(self, **kwargs):
        """Set the paragraph-style to be used in subsequent calls to text()

        All keyword arguments are optional and any unspecified values will remain
        unchanged. Calling layout() without any arguments returns the current
        layout settings.

        Line-layout Args:
          `align` the text-alignment (LEFT, RIGHT, CENTER, or JUSTIFY)
          `hyphenate` how hyphen-happy to be when breaking lines. Set to 0 or False to only
                      wrap lines on whitespace, or to 1.0 to add as many hyphens as possible
                      (the best values usually lie in the 0.9-1 range).

        Vertical-spacing Args:
          `leading` the baseline-to-baseline distance (measured in em's)
          `spacing` the amount of extra space to add above and below paragraphs. Pass a
                    single number to set the top margin or a list of two to set the
                    top and bottom respectively (in em's).

        Horizontal-spacing Args:
          `indent` the indentation distance for the first lines of paragraphs (in em's)
          `margin` the amount of space on the sides of the text block to leave empty. Pass
                   a single number to set the left margin, or a pair to set the left
                   and right respectively. Margins measurements should be in *canvas units*.
                   N.B. unpredictable things will happen if you set margins that are larger
                   than the `width` of the Text object.

        Returns:
          a Layout object with attributes corresponding to each of the keyword arguments

        Context Manager
            layout() can be used as part of a `with` statement in which case the paragraph
            style will be reset to its previous value once the block completes
        """
        Layout.validate(kwargs)
        if kwargs:
            newfont = Font(**kwargs)
            layout = Layout(newfont)
            layout._rollback = self._font
            self._font = newfont
        else:
            layout = Layout(self._font)
        return layout

    def fontsize(self, fontsize=None):
        """Legacy command. Equivalent to: font(size=fontsize)"""
        if fontsize is not None:
            self.font(size=fontsize)
        return self._font.size

    def lineheight(self, lineheight=None):
        """Legacy command. Equivalent to: layout(leading=lineheight)"""
        if lineheight is not None:
            self.layout(leading=lineheight)
        return self._font.leading

    def align(self, align=None):
        """Set the text alignment (to LEFT, RIGHT, CENTER, or JUSTIFY)"""
        if align is not None:
            self.layout(align=align)
        return self._font.align

    def stylesheet(self, name=None, *args, **kwargs):
        """Access the context's Stylesheet (used by the text() command to format marked-up strings)

        The stylesheet() command allows for both reading and writing of the global state depending
        on the number and style of arguments received:

        stylesheet("stylename", ...)
            To set a style, pass the desired tag name as the first argument, followed by any number of
            arguments to specify the font. The argument format is identical to the font() command, e.g.:

                stylesheet('foo', family="Avenir", italic=True)
                stylesheet('em', italic=False)

            now when you call the text command, you can use html-ish markup to use the style:

                text("<foo>This is avenir oblique <em>and this is upright</em></foo>", 0,0)

            Note that the string you pass to text() must be enclosed in a top-level 'root'
            element in order for it to be treated as markup.

        stylesheet("stylename", None)
           To delete a style, pass None along with the style name

        stylesheet("stylename")
            When called with a style name and no other arguments, returns a dictionary with the
            specification for the style (or None if it doesn't exist).

        stylesheet()
            With no arguments, returns the context's Stylesheet object for you to monkey with directly.
            It acts as a dictionary with all currently defined styles as its keys.
        """
        if name is None:
            return self._stylesheet
        else:
            return self._stylesheet.style(name, *args, **kwargs)

    def text(self, *args, **kwargs):
        """Draw a single line (or a block) of text

        Usage:
          text(str, x, y, width=None, height=None, **kwargs)
          text(x, y, width=None, height=None, str="", **kwargs) # equivalent to first usage
          text(x, y, width=None, height=None, xml="", **kwargs) # parses xml before rendering
          text(x, y, width=None, height=None, src="", **kwargs) # reads from file path or url

        Arguments:
          - `str` is a unicode string or utf-8 encoded bytestring. The text will
            be drawn using the current font() and fill().
          - `x` & `y` set the position. Note that the `y` value corresponds to the the text's
            baseline rather than the top of its bounding box.
          - `width` optionally sets the column width. Text will be line-wrapped using the
            current align() setting. If width is omitted, the text will be drawn as a single line.
          - `height` optionally sets the maximum height of a text column. Only the parts of
            the string that fit within the width & height will be drawn.

        Keyword Args:
          - `outline` converts the text to a set of Bezier paths before drawing. This allows
            you to use the canvas's current stroke() and pen() settings as well as fill() color
          - If `style` is a string corresponding to a rule defined in the stylesheet(), the text
            will be drawn in that style. The argument can also be set to False to disable
            XML parsing of the string.
          - `plot` can be set to False to prevent the command from immediately drawing to the
            canvas. You can pass the return value to the plot() command to draw it later on.

        Styling Args:
          - you can pass any of the standard font() args as keyword commands:
              family, size, leading, weight, variant, italic, heavier, lighter
          - the `fill` argument can override the color inherited from the graphics state

        Returns:
          A Text object whose x, y, width, and height can be manipulated through its attribtues.
          In addition, you can call its .append() method to add more text to the end of the run.
        """
        outline = kwargs.pop('outline', False)
        draw = self._should_plot(kwargs)
        text_args = {k:v for k,v in kwargs.items() if k in Text._opts}
        path_args = {k:v for k,v in kwargs.items() if k in Bezier._opts}
        path_args['draw'] = draw

        # make sure we didn't get any invalid kwargs
        if outline:
            rest = [k for k in kwargs if k not in Bezier._opts.union(Text._opts)]
        else:
            rest = [k for k in kwargs if k not in Text._opts]
        if rest:
            unknown = 'Invalid Text argument%s: %s'%('' if len(rest)==1 else 's', ", ".join(rest))
            raise DeviceError(unknown)

        # draw the text (either as a bezier or as type)
        txt = Text(*args, **text_args)
        if outline:
            with self._active_path(path_args) as p:
                p.extend(txt.path)
            return p
        else:
            if draw:
              txt.draw()
            return txt

    def textpath(self, txt, x, y, **kwargs):
        """Format a string with the current font() settings and return it as a Bezier

        textpath() accepts the same arguments as text() and is a shorthand for
        text(txt, outline=True, plot=False).
        """
        text_args = {k:v for k,v in kwargs.items() if k in Text._opts}
        return Text(txt, x, y, **text_args).path

    def textmetrics(self, txt, width=None, height=None, **kwargs):
        """Legacy command. Equivalent to: measure(txt, width, height)"""
        txt = Text(txt, 0, 0, width, height, **kwargs)
        return txt.metrics

    def textwidth(self, txt, width=None, **kwargs):
        """Legacy command. Equivalent to: measure(txt, width).width"""
        return self.textmetrics(txt, width, **kwargs).width

    def textheight(self, txt, width=None, **kwargs):
        """Legacy command. Equivalent to: measure(txt, width).height"""
        return self.textmetrics(txt, width, **kwargs).height

    def paginate(self, *args, **kwargs):
        """Return a generator which yields Text objects (as many as needed to fully lay out the string)

        Usage:
          paginate(str, x, y, width, height, **kwargs)
          paginate(x, y, width, height, str="", **kwargs) # equivalent to first usage
          paginate(x, y, width, height, xml="", **kwargs) # parses xml before rendering
          paginate(x, y, width, height, src="", **kwargs) # reads from file path or url
          paginate(Text, folio=1, verso=None) # works with existing Text objects too

        The paginate() command accepts the same arguments as text(), but rather than
        drawing to the canvas it returns the resulting Text objects for your script
        to plot() manually. Note that you must define both a width and a height for
        pagination to be meaningful. In addition to the standard set of text() arguments,
        paginate() accepts some optional keyword arguments to control the counters and
        odd/even layout (see below).

        The objects returned are standard Text objects with two additional `counter'
        attributes attached to them:
          txt.folio - the "page number" of the object (typically counting from one)
          txt.pg - the index of the object in the series (counting from zero)

        Additional Keyword Args:
          - `folio` sets the "page number" of the first page in the sequence – accessible
             through its corresponding .folio attribute. Defaults to 1 if omitted.
          - `verso` is a 2-tuple with x/y coordinates for "even" pages in the sequence.
             If omitted, all pages in the sequence will use the same x/y position as
             defined in the positional arguments.
        """
        folio = kwargs.pop('folio', 1)
        verso = kwargs.pop('verso', None)

        # create the sequence of Text objects
        page = Text(*args, **kwargs)
        dims = page.width, page.height
        pg = 0
        while page:
            page.pg = pg
            page.folio = folio
            page.width, page.height = dims
            if pg%2 and verso:
                page.x, page.y = verso
            yield page
            pg += 1
            folio += 1
            page = page.overleaf()

    ### Image commands ###

    def image(self, *args, **kwargs):
        """Draw a bitmap or vector image

        Syntax:
            image(src, x, y, width=None, height=None, **kwargs)
            image(x, y, src='path-or-url', ...)
            image(Point, src="", ...)
            image(Point, Size, src="", ...)
            image(Region, src="", ...)

        Arguments:
          - `src` is a url or the path to an image file (relative to the script's directory)
          - `x` & `y` position the image on the canvas
          - `width` and `height` are optional and define maximum sizes for the image.
            If provided, the image will be scaled to fit the bounds while preserving
            its aspect ratio.

        Keyword Args:
          - `blend`, `alpha`, and `shadow` will be inherited from the context but can
            be overridden via the corresponding keyword arguments.
        """
        draw = self._should_plot(kwargs)
        img = Image(*args, **kwargs)
        if draw:
            img.draw()
        return img

    def imagesize(self, path, data=None):
        """Legacy command. Equivalent to: measure(file(path))"""
        img = Image(path, data=data)
        return img.size

    ### draw, erase, and save-to-file ###

    def _should_plot(self, opts):
        """Extracts the `plot` and/or `draw` args from a kwargs dict and returns a
        boolean signaling whether to immediately draw the grob based on the input.

        Note that as a side effect it removes the keys from the dict (which many
        constructors count on before passing what remains to validate())
        """
        return opts.pop('plot', opts.pop('draw', self._autoplot))

    def plot(self, obj=None, *coords, **kwargs):
        """Add a new copy of a graphics object to the canvas

        Arguments:
          Accepts an object to be drawn followed (optionally) by x & y arguments
          specifying a location. If coordinates are omitted, the object will be
          drawn without modifying its original position:
              box = poly(10,10, 5, plot=False) # create a sqaure w/o drawing it
              plot(box)      # draw a square centered at (10,10)
              plot(box, 0,0) # draw another square at (0,0)

          When called with True or False, sets whether the primitive commands
          draw to the canvas by default or just return a reference.

        Keyword args:
          If `live` is set to True, the command will add the graphics object to
          the canvas directly (rather than drawing a copy of it). As a result,
          your variable reference to the object will remain `connected', allowing
          you to modify its properties even though it's already on the canvas.

          You may also include any keyword args that are approriate for the kind of
          object being drawn and its values will be updated before it is rendered.
          Valid keywords correspond to the attributes provided by the object in
          question (fill, stroke, width, height, etc.):
              dot = arc(0,0, 4, plot=False)
              plot(dot, 10,10, fill='red')        # a bright red dot
              plot(dot, 15,10, fill=0, alpha=0.2) # a pale black dot

        Context Manager:
          plot() can be used as part of a `with` statement to control whether
          primitive commands like rect() and image() draw to the screen by default.
          For instance, calling `with plot(False)` will inhibit drawing even if
          the primitive command is called without a `plot=False` keyword argument:
              r = rect(100,100, 20,20, plot=False) # not drawn
              with plot(False):
                  s = rect(0,0, 20,20) # not drawn either
        """
        if obj is None:
            return self._autoplot
        elif obj in (True,False):
            return PlotContext(self, auto=obj)
        elif not isinstance(obj, Grob):
            notdrawable = 'plot() only knows how to draw Bezier, Image, or Text objects (not %s)'%type(obj)
            raise DeviceError(notdrawable)

        # by default, plot a copy of the grob and return a reference to that new copy.
        # if live=True, the obj itself will be added to the canvas and the caller can
        # make additional modifications on that instance
        grob = obj if kwargs.get('live') else obj.copy()

        # if there are any positional args following the grob, assign a new x/y (and possibly w/h)
        if coords:
            try:
                (grob.x, grob.y), (grob.width, grob.height) = parse_coords(coords, [Point,Size])
            except:
                try:
                    (grob.x, grob.y), grob.width = parse_coords(coords, [Point,float])
                except:
                    grob.x, grob.y = parse_coords(coords, [Point])

        # for any valid kwargs, assign the value to the attr of the same name
        grob.__class__.validate(kwargs)
        for arg_key, arg_val in kwargs.items():
            if not hasattr(grob, arg_key):
                badattr = "Unknown property '%s' for object of class %r"%(arg_key, grob.__class__.__name__)
                raise DeviceError(badattr)
            setattr(grob, arg_key, _copy_attr(arg_val))

        grob.draw() # add to canvas
        return grob # return the newly-drawn copy (or `live` grob reference)

    def clear(self, *grobs):
        """Erase the canvas (or remove specific objects already added to it)

        - with no arguments, `clear()` will remove all objects from the canvas
        - calling `clear(all)` will erase the canvas and also reset the drawing
          state (colors, transform, compositing effects, etc.) to default values
        - passing references to a previously-drawn object will remove just those
          objects. For instance the following will result in only the triangle
          being drawn:
              r = rect(0,0,1,1) # add a rectangle
              t = poly(0,0,1,3) # add a triangle
              c = oval(0,0,2,2) # add a circle
              clear(r, c)       # remove the rectangle & circle
        """
        if all in grobs:
            self.canvas.clear()
            self._resetContext()
        else:
            self.canvas.clear(*grobs)

    def export(self, fname, fps=None, loop=None, bitrate=1.0, cmyk=False):
        """Write single images or manage batch exports for animations.

        To write the canvas's current contents to a file, simply call export("~/somefile.png")
        after your drawing commands have executed. When writing files that support non-RGB colors
        (e.g., PDFs or TIFFs), the `cmyk` argument lets you optionally specify CMYK output.

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
        """

        # determine the format by normalizing the file extension
        format = fname.lower().rsplit('.',1)[1]
        if format not in ('pdf','eps','png','jpg','gif','tiff', 'mov'):
            badform = 'Unknown export format "%s"'%format
            raise DeviceError(badform)

        # build up opts based on type of output file (anim vs static)
        opts = {"cmyk":cmyk}
        if format=='mov' or (format=='gif' and fps or loop is not None):
            opts.update(fps=fps or 30, # set a default for .mov exports
                        loop={True:-1, False:0, None:0}.get(loop, loop), # convert bool args to int
                        bitrate=bitrate)

        return ImageWriter(fname, format, **opts)

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

    def measure(self, obj=None, width=None, height=None, **kwargs):
        """Returns a Size tuple for graphics objects, strings, or file objects

        When called with a string, the size will reflect the current font() settings
        and will layout the text using the optional `width` and `height` arguments.

        If `obj` if a file() object, PlotDevice will treat it as an image file and
        return its pixel dimensions.
        """
        if isinstance(obj, basestring):
            obj = Text(obj, 0, 0, width, height, **kwargs)

        if hasattr(obj, 'metrics'):
            return obj.metrics
        elif kwargs.get('image'):
            return Image(kwargs['image'], width=width, height=height).size
        elif isinstance(obj, (Bezier, Image)):
            return obj.bounds.size
        elif isinstance(obj, Canvas):
            return obj.size
        else:
            badtype = "measure() can only handle Text, Images, Beziers, and file() objects (got %s)"%type(obj)
            raise DeviceError(badtype)

    ### Variables ###

    def var(self, name, type, default=None, min=0, max=100, value=None):
        v = Variable(name, type, default, min, max, value)
        v = self.addvar(v)

    def addvar(self, v):
        oldvar = self.findvar(v.name)
        if oldvar is not None:
            if oldvar.compliesTo(v):
                v.value = oldvar.value
        self._vars.append(v)
        self._ns[v.name] = v.value

    def findvar(self, name):
        for v in self._oldvars:
            if v.name == name:
                return v
        return None


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

class Canvas(object):

    def __init__(self, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, unit=px):
        self.unit = unit
        self.width = width
        self.height = height
        self.speed = None
        self.mousedown = False
        self.clear() # set up the container & stack

    @trim_zeroes
    def __repr__(self):
        return 'Canvas(%0.3f, %0.3f, %s)'%(self.width, self.height, self.unit.name)

    def reset(self):
        """Reset dimensions & animation state then clear"""
        self.__init__()

    def clear(self, *grobs):
        """Erase the canvas entirely (or remove specified grobs)"""
        if not grobs:
            self._grobs = self._container = []
            self._stack = [self._container]
        else:
            for grob in grobs:
                self._drop(grob, self._grobs)

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

    def push(self, containerFrob):
        # when Frobs like Stencils or Effects are added, they become their own container
        # that applies to all grobs drawn until the frob is popped off the stack
        self._stack.insert(0, containerFrob)
        self._container.append(containerFrob)
        self._container = containerFrob

    def pop(self):
        try:
            del self._stack[0]
            self._container = self._stack[0]
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

        with autorelease():
            for grob in self._grobs:
                grob._draw()
        # import cProfile
        # cProfile.runctx('[grob._draw() for grob in self._grobs*10]', globals(), {"self":self}, sort='cumulative')

    @property
    def _nsImage(self):
        return self.rasterize()

    def _cg_image(self, zoom=1.0):
        """Return a CGImage with the canvas dimensions scaled to the specified zoom level"""
        from Quartz import CGBitmapContextCreate, CGBitmapContextCreateImage, CGColorSpaceCreateDeviceRGB, CGContextClearRect
        from Quartz import CGSizeMake, CGRectMake
        from Quartz import kCGImageAlphaPremultipliedFirst, kCGBitmapByteOrder32Host, kCGImageAlphaNoneSkipFirst
        w,h = self.pagesize
        # size = Size(int(w*zoom), int(h*zoom))
        size = Size(*[int(dim*zoom) for dim in self.pagesize])
        bitmapBytesPerRow   = (size.width * 4);
        bitmapByteCount     = (bitmapBytesPerRow * size.height);
        bitmapContext = CGBitmapContextCreate(None,
                                              size.width, size.height, 8, bitmapBytesPerRow,
                                              CGColorSpaceCreateDeviceRGB(),
                                              kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Host)

        ns_ctx = NSGraphicsContext.graphicsContextWithGraphicsPort_flipped_(bitmapContext, True)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.setCurrentContext_(ns_ctx)
        trans = NSAffineTransform.transform()
        trans.translateXBy_yBy_(0, size.height)
        trans.scaleXBy_yBy_(zoom,-zoom)
        trans.concat()
        self.draw()
        NSGraphicsContext.restoreGraphicsState()

        return CGBitmapContextCreateImage(bitmapContext)

    def _bitmap_image(self, zoom=1.0):
        w,h = self.pagesize
        img_rect = Region(0,0, int(w*zoom), int(h*zoom))

        from Cocoa import NSBitmapImageRep, NSDeviceRGBColorSpace, NSAlphaFirstBitmapFormat

        offscreen = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bitmapFormat_bytesPerRow_bitsPerPixel_(
          None, img_rect.w, img_rect.h, 8, 4, True, False, NSDeviceRGBColorSpace, NSAlphaFirstBitmapFormat, 0, 0
        )

        ns_ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(offscreen)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.setCurrentContext_(ns_ctx)
        trans = NSAffineTransform.transform()
        trans.scaleBy_(zoom)
        trans.concat()
        self.draw()
        NSGraphicsContext.restoreGraphicsState()

        img = NSImage.alloc().initWithSize_(img_rect.size)
        img.addRepresentation_(offscreen)
        return img

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
                props = {NSImageCompressionFactor:1.0} if format in ('jpg','jpeg') else None
                return rep.representationUsingType_properties_(imgType, props)
            else:
                return data

    def save(self, fname, format=None):
        """Write the current graphics objects to an image file"""
        if format is None:
            format = fname.rsplit('.',1)[-1].lower()
        data = self._getImageData(format)
        fname = NSString.stringByExpandingTildeInPath(fname)
        data.writeToFile_atomically_(fname, False)

