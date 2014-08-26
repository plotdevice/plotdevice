# encoding: utf-8
import os, re, types
from contextlib import contextmanager, nested
from collections import namedtuple
from os.path import exists, expanduser

from .lib.cocoa import *
from .util import _copy_attr, _copy_attrs, _flatten, trim_zeroes
from .lib import geometry, pathmatics
from .gfx.transform import Dimension
from .gfx import *
from . import gfx, lib, util, Halted, DeviceError

__all__ = ('Context', 'Canvas')

# default size for Canvas and GraphicsView objects
DEFAULT_WIDTH, DEFAULT_HEIGHT = 512, 512

# named tuples for grouping state attrs
PenStyle = namedtuple('PenStyle', ['nib', 'cap', 'join', 'dash'])
TypeStyle = namedtuple('TypeStyle', ['face', 'size', 'leading', 'align'])

### NSGraphicsContext wrapper (whose methods are the business-end of the user-facing API) ###
class Context(object):
    _state_vars = '_outputmode', '_colormode', '_colorrange', '_fillcolor', '_strokecolor', '_penstyle', '_effects', '_path', '_autoclosepath', '_transform', '_transformmode', '_thetamode', '_transformstack', '_typestyle', '_stylesheet', '_oldvars', '_vars'

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
        self.canvas._ctx = self

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
        self._typestyle = TypeStyle(face="Helvetica", size=24, leading=1.2, align=LEFT)

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
        self.clear(all)

    def _restoreContext(self):
        try:
            cached = self._statestack.pop(0)
        except IndexError:
            raise DeviceError, "Too many Context._restoreContext calls."

        for attr, val in zip(Context._state_vars, cached):
            setattr(self, attr, val)

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
            self.canvas.unit = unit
        return self.canvas.size

    @property
    def WIDTH(self):
        return Dimension('width')

    @property
    def HEIGHT(self):
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
        draw = kwargs.pop('draw', self._autoplot)
        draw = kwargs.pop('plot', draw)
        kwargs['draw'] = draw

        if isinstance(x, (list, tuple)):
            # if the first arg is an iterable of point tuples, there's no need to open a context
            # since the path is already fully-specified. Instead handle the path immediately
            # (passing along styles and `draw` kwarg)
            return Bezier(path=x, immediate=True, **kwargs)
        elif isinstance(x, Bezier):
            # when called with an existing Bezier object, only pass the underlying NSBezierPath.
            # otherwise the constructor would make an identical copy of it rather than inheriting
            # from the current graphics state.
            return Bezier(path=x._nsBezierPath, immediate=True, **kwargs)
        else:
            # otherwise start a new path with the presumption that it will be populated
            # in a `with` block or by adding points manually. begins with a moveto
            # element if an x,y coord was provided and relies on Bezier's __enter__
            # method to update self._path if appropriate
            p = Bezier(**kwargs)
            origin = (x,y) if all(isinstance(c, (int,float)) for c in (x,y)) else None
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
            xf = p._screen_transform
            self._path.extend(xf.apply(p))
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

    def arcto(self, x1, y1, x2=None, y2=None, radius=None, ccw=False, close=False):
        """Draw a circular arc from the current point in the active path to a destination point

        To draw a semicircle to the destination point use one of:
            arcto(x,y)
            arcto(x,y, ccw=True)

        To draw a parabolic arc in the triangle between the current point, an
        intermediate control point, and the destination; choose a radius small enough
        to fit in that angle and call:
            arcto(mid_x, mid_y, dest_x, dest_y, radius)

        Calling with close=True will close the subpath after adding the arc.
        """
        if self._path is None:
            raise DeviceError, "No active path. Use bezier() or beginpath() first."
        self._path.arcto(x1, y1, x2, y2, radius, ccw)
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

    def poly(self, x, y, radius, sides=4, points=None, **kwargs):
        """Draw a regular polygon centered at (x,y)

        The `sides` arg sets the type of polygon to draw. Regardless of the number,
        it will be oriented such that its base is horizontal.

        If a `points` keyword argument is passed instead of a `sides` argument,
        a regularized star polygon will be drawn at the given coordinates & radius,
        """
        with self._active_path(kwargs) as p:
            p.poly(x, y, radius, sides, points)
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

    def transform(self, mode=None):
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

        Transformation Context Manager

        When used as part of a `with` statement, the transform() command will ensure the
        mode and transformations applied during the indented code-block are reverted to their
        previous state once the block completes.
        """

        if mode not in (CORNER, CENTER, None):
            badmode = "transform: mode must be CORNER or CENTER"
            raise DeviceError(badmode)
        rollback = {"_transform":self._transform.copy(),
                    "_transformmode":self._transformmode}
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

    def font(self, *args, **kwargs):
        """Set the current font to be used in subsequent calls to text()"""
        return Font(*args, **kwargs)._use()

    def fonts(self, like=None, western=True):
        """Returns a list of all fonts installed on the system (with filtering capabilities)

        If `like` is a string, only fonts whose names contain those characters will be returned.

        If `western` is True (the default), fonts with non-western character sets will be omitted.
        If False, only non-western fonts will be returned.
        """
        return gfx.typography.families(like, western)

    def fontsize(self, fontsize=None):
        """Legacy command. Equivalent to: font(size=fontsize)"""
        if fontsize is not None:
            self._typestyle = self._typestyle._replace(size=fontsize)
        return self._typestyle.size

    def lineheight(self, lineheight=None):
        """Legacy command. Equivalent to: font(leading=lineheight)"""
        if lineheight is not None:
            self._typestyle = self._typestyle._replace(leading=lineheight)
        return self._typestyle.leading

    def align(self, align=None):
        """Set the text alignment (to LEFT, RIGHT, or CENTER)

        Alignment only applies to text() calls that include a column `width` parameter"""
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

    def text(self, txt, *args, **kwargs):
        """Draw a single line (or a block) of text

        Arguments:
          - `txt` is a unicode string. If it begins and ends with an xml tag, the string will
            be parsed and styles from the stylesheet() applied to it. Otherwise the text will
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
        """
        outline = kwargs.pop('outline', False)
        path_args = {k:v for k,v in kwargs.items() if k in Bezier._opts}
        text_args = {k:v for k,v in kwargs.items() if k in Text._opts}

        txt = Text(txt, *args, **text_args)
        if outline:
            with self._active_path(path_args) as p:
                p.extend(txt.path)
            return p
        else:
            if kwargs.get('draw', kwargs.get('plot', self._autoplot)):
              txt.draw()
            return txt

    def textpath(self, txt, x, y, **kwargs):
        """Format a string with the current font() settings and return it as a Bezier

        textpath() accepts the same arguments as text() and is a shorthand for
        text(txt, outline=True, plot=False).
        """
        text_args = {k:v for k,v in kwargs.items() if k in Text._opts}
        return Text(txt, x, y, **text_args).path

    def textmetrics(self, txt, width=None, height=None, style=None, **kwargs):
        """Legacy command. Equivalent to: measure(txt, width, height)"""
        txt = Text(txt, 0, 0, width, height, style, **kwargs)
        # txt.inherit()
        return txt.metrics

    def textwidth(self, txt, width=None, **kwargs):
        """Calculates the width of a single-line string."""
        return self.textmetrics(txt, width, **kwargs)[0]

    def textheight(self, txt, width=None, **kwargs):
        """Calculates the height of a (probably) multi-line string."""
        return self.textmetrics(txt, width, **kwargs)[1]

    ### Image commands ###

    def image(self, *args, **kwargs):
        """Draw a bitmap or vector image

        Arguments:
          - `path` is the path to an image file (relative to the script's directory)
          - `x` & `y` position the image on the canvas
          - `width` and `height` are optional and define maximum sizes for the image.
            If provided, the image will be scaled to fit the bounds while preserving
            its aspect ratio.

        Keyword Args:
          - `blend`, `alpha`, and `shadow` will be inherited from the context but can
            be overridden via the corresponding keyword arguments.
        """
        draw = kwargs.pop('draw', self._autoplot)
        draw = kwargs.pop('plot', draw)

        img = Image(*args, **kwargs)
        if draw:
            img.draw()
        return img

    def imagesize(self, path, data=None):
        """Legacy command. Equivalent to: measure(file(path))"""
        img = Image(path, data=data)
        return img.size

    ### draw, erase, and save-to-file ###

    def plot(self, obj=None, live=False, inherit=False, **kwargs):
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
        grob = obj if live else obj.copy()

        # optionally reflect the *current* graphics state rather than the state
        # that was inherited when the grob was originally created
        if inherit:
            grob.inherit()

        # for any valid kwargs, assign the value to the attr of the same name
        grob.__class__.validate(kwargs)
        for arg_key, arg_val in kwargs.items():
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
            eslf.canvas.clear(*grobs)

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

    def measure(self, obj, width=None, height=None, **kwargs):
        """Returns a Size tuple for graphics objects, strings, or file objects

        When called with a string, the size will reflect the current font() settings
        and will layout the text using the optional `width` and `height` arguments.

        If `obj` if a file() object, PlotDevice will treat it as an image file and
        return its pixel dimensions.
        """
        if isinstance(obj, basestring):
            txt = Text(obj, 0, 0, width, height, **kwargs)
            return txt.metrics
        elif isinstance(obj, Text):
            return obj.metrics
        elif isinstance(obj, file):
            return Image(obj.name).size
        elif isinstance(obj, (Bezier, Image)):
            return obj.bounds.size
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
        if self.unit.basis != 1.0:
            # it might be wiser to have this factor into ctx.transform so it doesn't end up
            # scaling stroke widths...
            t = Transform()
            t.scale(self.unit.basis)
            t.concat()
        for grob in self._grobs:
            grob._draw()
        # import cProfile
        # cProfile.runctx('[grob._draw() for grob in self._grobs*10]', globals(), {"self":self}, sort='cumulative')

    @property
    def _nsImage(self):
        return self.rasterize()

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

