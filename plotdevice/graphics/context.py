import types
from AppKit import *
from contextlib import contextmanager, nested

from .typography import *
from .bezier import *
from .grobs import *
from .colors import *
from .transform import *
from .image import Image
from .effects import Effect, Shadow, Mask
from . import grobs

from ..util.foundry import sanitized, font_encoding, family_names, family_name, family_members
from ..util import _copy_attr, _copy_attrs, _flatten
from ..lib import geometry

### NSGraphicsContext wrapper (whose methods are the business-end of the user-facing API) ###

class Context(object):
    state_vars = '_outputmode', '_colormode', '_colorrange', '_fillcolor', '_strokecolor', '_strokewidth', '_effects', '_capstyle', '_joinstyle', '_dashstyle', '_path', '_autoclosepath', '_transform', '_transformmode', '_rotationmode', '_transformstack', '_fontname', '_fontsize', '_lineheight', '_align', '_noImagesHint', '_oldvars', '_vars'

    def __init__(self, canvas=None, ns=None):
        """Initializes the context.

        Note that we have to pass the namespace of the executing script,
        to keep the WIDTH and HEIGHT properties updated (and to allow for
        ximport's _ctx-passing magic).
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
        self.__all__ = sorted(a for a in dir(self) if not (a.startswith('_') or a.endswith('_')))

    def _activate(self):
        from . import activate
        activate(self)

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
        self._plotstyle = LIVE
        self._capstyle = BUTT
        self._joinstyle = MITER
        self._dashstyle = None
        self._strokewidth = 1.0
        self._autoclosepath = True

        # transformation state
        self._transform = Transform()
        self._transformmode = CENTER
        self._rotationmode = DEGREES

        # blend, alpha, and shadow effects
        self._effects = Effect()

        # type styles
        self._stylesheet = Stylesheet()
        self._fontname = "Helvetica"
        self._fontsize = 24
        self._lineheight = 1.2
        self._align = LEFT

        # legacy internals
        self._transformstack = [] # only used by push/pop
        self._oldvars = self._vars
        self._vars = []
        self._path = None
        self._noImagesHint = False

    def ximport(self, libName):
        lib = __import__(libName)
        self._ns[libName] = lib
        lib._ctx = self
        return lib

    ### Setup methods ###

    def size(self, width, height):
        self.canvas.width = width
        self.canvas.height = height
        self._ns["WIDTH"] = width
        self._ns["HEIGHT"] = height

    def _get_width(self):
        return self.canvas.width

    WIDTH = property(_get_width)

    def _get_height(self):
        return self.canvas.height

    HEIGHT = property(_get_height)

    def speed(self, speed):
        self.canvas.speed = speed

    def background(self, *args):
        if len(args) > 0:
            if len(args) == 1 and args[0] is None:
                self.canvas.background = None
            else:
                self.canvas.background = Color(args)
        return self.canvas.background

    def outputmode(self, mode=None):
        if mode is not None:
            self._outputmode = mode
        return self._outputmode

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

    ### Primitives ###

    def rect(self, x, y, width, height, radius=None, roundness=0.0, draw=True, **kwargs):
        Bezier.validate(kwargs)
        if roundness > 0:
            # support the pre-10.5 roundrect behavior via the roundness arg
            curve = min(width*roundness, height*roundness)
            p = Bezier(**kwargs)
            p.moveto(x, y+curve)
            p.curveto(x, y, x, y, x+curve, y)
            p.lineto(x+width-curve, y)
            p.curveto(x+width, y, x+width, y, x+width, y+curve)
            p.lineto(x+width, y+height-curve)
            p.curveto(x+width, y+height, x+width, y+height, x+width-curve, y+height)
            p.lineto(x+curve, y+height)
            p.curveto(x, y+height, x, y+height, x, y+height-curve)
            p.closepath()
        else:
            # otherwise let the nsbezier use its built-in support for rect radii
            p = Bezier(**kwargs)
            p.rect(x, y, width, height, radius=radius)

        if draw:
            p.draw()
        return p

    def oval(self, x, y, width, height, range=None, ccw=False, close=False, draw=True, **kwargs):
        Bezier.validate(kwargs)
        path = Bezier(**kwargs)
        path.oval(x, y, width, height, range, ccw=ccw, close=close)

        if draw:
          path.draw()
        return path

    ellipse = oval

    def line(self, x1, y1, x2, y2, arc=0, draw=True, **kwargs):
        if self._path is None:
            Bezier.validate(kwargs)
            p = Bezier(**kwargs)
            p.line(x1, y1, x2, y2, arc=arc)
            if draw:
              p.draw()
        else:
            # if a bezier is being built in a `with` block, add line segments to it, but
            # ignore kwargs since the bezier object's styles apply to all lines drawn
            p = self._path
            p.line(x1, y1, x2, y2)
        return p

    def poly(self, x, y, radius, sides=3, draw=True, **kwargs):
        Bezier.validate(kwargs)
        p = Bezier(**kwargs)
        p.poly(x, y, radius, sides)
        if draw:
          p.draw()
        return p

    def arc(self, x, y, radius, range=None, ccw=False, close=False, draw=True, **kwargs):
        Bezier.validate(kwargs)
        p = Bezier(**kwargs)
        p.arc(x, y, radius, range, ccw=ccw, close=close)
        if draw:
          p.draw()
        return p

    def star(self, startx, starty, points=20, outer=100, inner=None, draw=True, **kwargs):
        Bezier.validate(kwargs)
        p = Bezier(**kwargs)
        p.star(startx, starty, points, outer, inner)
        if draw:
          p.draw()
        return p

    def arrow(self, x, y, width=100, type=NORMAL, draw=True, **kwargs):
        """Draws an arrow.

        Draws an arrow pointing at position (x,y), with a default width of 100.
        There are two different types of arrows: NORMAL and (the early-oughts favorite) FORTYFIVE.
        """

        Bezier.validate(kwargs)
        p = Bezier(**kwargs)
        p.arrow(x, y, width, type)
        if draw:
          p.draw()
        return p


    ### Path Commands ###

    def bezier(self, x=None, y=None, **kwargs):
        origin = (x,y) if all(isinstance(c, (int,float)) for c in (x,y)) else None
        kwargs.setdefault('draw', True)
        if isinstance(x, (Bezier, list, tuple)):
            # if a list of point tuples or a Bezier is the first arg, there's
            # no need to open a context (since the path is already defined). Instead
            # handle the path immediately (passing along styles and `draw` kwarg)
            kwargs.setdefault('close', False)
            return Bezier(path=x, immediate=True, **kwargs)
        else:
            # otherwise start a new path with the presumption that it will be populated
            # in a `with` block or by adding points manually. begins with a moveto
            # element if an x,y coord was provided
            p = Bezier(**kwargs)
            if origin:
                p.moveto(*origin)
            return p

    def moveto(self, x, y):
        if self._path is None:
            raise DeviceError, "No current path. Use bezier() or beginpath() first."
        self._path.moveto(x,y)

    def lineto(self, x, y, close=False):
        if self._path is None:
            raise DeviceError, "No current path. Use bezier() or beginpath() first."
        self._path.lineto(x, y)
        if close:
            self._path.closepath()

    def curveto(self, x1, y1, x2, y2, x3, y3, close=False):
        if self._path is None:
            raise DeviceError, "No current path. Use bezier() or beginpath() first."
        self._path.curveto(x1, y1, x2, y2, x3, y3)
        if close:
            self._path.closepath()

    def arcto(self, x, y, radius=1.0, close=False):
        if self._path is None:
            raise DeviceError, "No current path. Use bezier() or beginpath() first."
        self._path.arcto(x, y, radius)
        if close:
            self._path.closepath()

    def beginpath(self, x=None, y=None):
        self._path = Bezier()
        self._pathclosed = False
        if x != None and y != None:
            self._path.moveto(x,y)

    def closepath(self):
        if self._path is None:
            raise DeviceError, "No current path. Use bezier() or beginpath() first."
        if not self._pathclosed:
            self._path.closepath()
            self._pathclosed = True

    def endpath(self, draw=True):
        if self._path is None:
            raise DeviceError, "No current path. Use bezier() or beginpath() first."
        if self._autoclosepath:
            self.closepath()
        p = self._path
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
        import bezier
        path = bezier.findpath(points, curvature=curvature)
        return path

    ### Transformation Commands ###

    def push(self):
        self._transformstack.insert(0, self._transform.matrix)

    def pop(self):
        try:
            self._transform = Transform(self._transformstack[0])
            del self._transformstack[0]
        except IndexError, e:
            raise DeviceError, "pop: too many pops!"

    def transform(self, *args):
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
                    "_transformmode":self._transformmode,
                    "_rotationmode":self._rotationmode}
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
        xf = self._transform.inverse
        xf._rollback = {'_transform':self._transform.copy(), '_rotationmode':self._rotationmode}
        self._transform = Transform()
        self._rotationmode = DEGREES
        return xf

    def translate(self, x=0, y=0):
        return self._transform.translate(x,y, rollback=True)

    def scale(self, x=1, y=None):
        return self._transform.scale(x,y, rollback=True)

    def skew(self, x=0, y=0):
        return self._transform.skew(x,y, rollback=True)

    def rotate(self, arg=None, **kwargs):
        # with no args, return the current mode
        if arg is None and not kwargs:
            return self._rotationmode

        # when setting the mode, update the context then return the prior mode
        if arg in (DEGREES, RADIANS, PERCENT):
            xf = Transform()
            xf._rollback = {'_rotationmode':self._rotationmode}
            self._rotationmode = arg
            return xf

        # check the kwargs for unit-specific settings
        units = {k:v for k,v in kwargs.items() if k in ['degrees', 'radians', 'percent']}
        if len(units) > 1:
            badunits = 'rotate: specify one rotation at a time (got %s)' % " & ".join(units.keys())
            raise DeviceError(badunits)

        # if nothing in the kwargs, use the current mode and take the quantity from the first arg
        if not units:
            units[self._rotationmode] = arg or 0

        # add rotation to the graphics state
        degrees = units.get('degrees', 0)
        radians = units.get('radians', 0)
        if 'percent' in units:
            degrees, radians = 0, tau*units['percent']
        return self._transform.rotate(-degrees,-radians, rollback=True)

    ### Color Commands ###

    def pen(self, nib=None, **spec): # spec: caps, joins, dash
        if nib is not None:
            spec.setdefault('nib', nib)
        return PlotContext(self, **spec)

    def color(self, *args, **kwargs):
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
        return self.fill(None)

    def fill(self, *args, **kwargs):
        if args and isinstance(args[0], Image):
            p = Pattern(args[0])
            self._fillcolor = p
        elif set(Gradient.kwargs) >= set(kwargs) and len(args)>1 and all(Color.recognized(c) for c in args):
            g = Gradient(*args, **kwargs)
            setattr(g, '_rollback', dict(fill=self._fillcolor))
            self._fillcolor = g
        elif len(args) > 0:
            annotated = Color(*args)
            setattr(annotated, '_rollback', dict(fill=self._fillcolor))
            self._fillcolor = annotated
        return self._fillcolor

    def nostroke(self):
        return self.stroke(None)

    def stroke(self, *args):
        if len(args) > 0:
            annotated = Color(*args)
            setattr(annotated, '_rollback', dict(stroke=self._strokecolor))
            self._strokecolor = annotated
        return self._strokecolor

    def strokewidth(self, width=None):
        if width is not None:
            self._strokewidth = max(width, 0.0001)
        return self._strokewidth

    def capstyle(self, style=None):
        if style is not None:
            if style not in (BUTT, ROUND, SQUARE):
                raise DeviceError, 'Line cap style should be BUTT, ROUND or SQUARE.'
            self._capstyle = style
        return self._capstyle

    def joinstyle(self, style=None):
        if style is not None:
            if style not in (MITER, ROUND, BEVEL):
                raise DeviceError, 'Line join style should be MITER, ROUND or BEVEL.'
            self._joinstyle = style
        return self._joinstyle

    ### Compositing Effects ###

    @contextmanager
    def layer(self, *fx):
        # fx is a list of alpha(), blend(), or shadow() calls
        for eff in fx:
            if hasattr(eff, '_rollback'):
                rollback = eff._rollback
                break
        else:
            nop = "`with layer(...)` accepts alpha(), blend(), or shadow() calls as arguments"
        context_mgrs = [mgr for mgr in fx if hasattr(mgr, '__enter__')]

        self.canvas.push(Effect(self._effects))
        self._effects = Effect()
        yield
        self.canvas.pop()
        self._effects = rollback

    def alpha(self, a=-1):
        if a is not -1:
            if a==1.0:
                a = None
            self._effects = Effect(self._effects, alpha=a)
            return self._effects
        return self._effects.alpha or 1.0

    def blend(self, mode=-1):
        if mode is not -1:
            if mode=='normal':
                mode = None
            self._effects = Effect(self._effects, blend=mode)
            return self._effects
        return self._effects.blend or 'normal'

    def shadow(self, *args, **kwargs):
        if args and None in args:
            self._effects = Effect(self._effects, shadow=None)
        else:
            s = Shadow(*args, **kwargs)
            self._effects = Effect(self._effects, shadow=s)
        return self._effects

    @contextmanager
    def clip(self, path, mask=False, channel=None):
        """Sets the clipping region for a block of code.

        All drawing operations within the block will be constrained by the clipping
        path. By default, only content within the bounds of the path will be rendered.
        If the `mask` argument is True, this relationship is inverted and only content
        that lies *outside* of the clipping path will be drawn.
        """
        cp = self.beginclip(path, mask=mask, channel=channel)
        self.canvas.clear(path)
        yield cp
        self.endclip()

    def beginclip(self, path, mask=False, channel=None):
        cp = Mask(path, invert=bool(mask), channel=channel)
        self.canvas.push(cp)
        return cp

    def endclip(self):
        self.canvas.pop()

    ### Drawing grobs with the current pen/stroke/fill ###

    def plot(self, obj, copy=False, **kwargs):
        if not isinstance(obj, Grob):
            notdrawable = 'plot() only knows how to draw Bezier, Image, or Text objects (not %s)'%type(obj)
            raise DeviceError(notdrawable)
        obj.__class__.validate(kwargs)
        grob = obj.copy() if copy else obj
        for arg_key, arg_val in kwargs.items():
            setattr(grob, arg_key, _copy_attr(arg_val))
        grob.draw()

    def plotstyle(self, *ops):
        modal = [m for m in ops if m in (COPY,LIVE,OFF)]
        mode = modal[0] if modal else self._plotstyle
        context_mgrs = [mgr for mgr in ops if hasattr(mgr, '__enter__')]
        context_mgrs.append(PlotContext(self, restore=all, style=mode))
        return nested(*context_mgrs)

    ### Font Commands ###

    def font(self, *args, **kwargs):
        """Set the current font to be used in subsequent calls to text()"""
        return Font(*args, **kwargs)._use()

    def fontsize(self, fontsize=None):
        if fontsize is not None:
            self._fontsize = fontsize
        return self._fontsize

    def fonts(self, like=None, western=True):
        """Returns a list of all fonts installed on the system (with filtering capabilities)

        If `like` is a string, only fonts whose names contain those characters will be returned.

        If `western` is True (the default), fonts with non-western character sets will be omitted.
        If False, only non-western fonts will be returned.
        """
        all_fams = family_names()
        if like:
            all_fams = [name for name in all_fams if sanitized(like) in sanitized(name)]

        representatives = {fam:family_members(fam, names=True)[0] for fam in all_fams}
        in_region = {fam:font_encoding(fnt)=="MacOSRoman" for fam,fnt in representatives.items()}
        if not western:
            in_region = {fam:not macroman for fam,macroman in in_region.items()}

        return [Family(fam) for fam in all_fams if in_region[fam]]

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

    def lineheight(self, lineheight=None):
        if lineheight is not None:
            self._lineheight = max(lineheight, 0.01)
        return self._lineheight

    def align(self, align=None):
        if align is not None:
            self._align = align
        return self._align

    def text(self, txt, x, y, width=None, height=None, outline=False, draw=True, **kwargs):
        txt = Text(txt, x, y, width, height, **kwargs)

        if outline:
            txt.inherit()
            path = txt.path
            _copy_attrs(txt, path, {'fill', 'stroke', 'strokewidth'}.intersection(kwargs))
            if draw:
                path.draw()
            return path
        else:
          if draw:
            txt.draw()
          return txt

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

    def image(self, path, x=0, y=0, width=None, height=None, data=None, draw=True, **kwargs):
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

    @property
    def geo(self):
        return geometry

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

class PlotContext(object):
    """Performs the setup/cleanup for a `with pen()/stroke()/fill()/color(mode,range)` block"""
    _statevars = dict(nib='_strokewidth', cap='_capstyle', join='_joinstyle', dash='_dashstyle',
                      mode='_colormode', range='_colorrange', stroke='_strokecolor', fill='_fillcolor',
                      style='_plotstyle')

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
        super(_PDFRenderView, self).initWithFrame_( ((0, 0), (canvas.width, canvas.height)) )
        self.canvas = canvas
        return self

    def drawRect_(self, rect):
        self.canvas.draw()

    def isOpaque(self):
        return False

    def isFlipped(self):
        return True

class Canvas(Grob):

    def __init__(self, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
        self.width = width
        self.height = height
        self.speed = None
        self.mousedown = False
        self.clear()

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

    def _get_size(self):
        return self.width, self.height
    size = property(_get_size)

    def append(self, el):
        self._container.append(el)

    def __iter__(self):
        for grob in self._grobs:
            yield grob

    def __len__(self):
        return len(self._grobs)

    def __getitem__(self, index):
        return self._grobs[index]

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
            self.background.set()
            NSRectFillUsingOperation(((0,0), (self.width, self.height)), NSCompositeSourceOver)
        # import cProfile
        # cProfile.runctx('[grob._draw() for grob in self._grobs]', globals(), {"self":self}, sort='cumulative')
        for grob in self._grobs:
            grob._draw()

    def rasterize(self, zoom=1.0):
        """Return an NSImage with the canvas dimensions scaled to the specified zoom level"""
        img = NSImage.alloc().initWithSize_((self.width*zoom, self.height*zoom))
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
