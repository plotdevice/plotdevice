import types
from AppKit import *
from contextlib import contextmanager, nested

from .typography import *
from .bezier import *
from .grobs import *
from . import grobs, typography, bezier

from ..util.foundry import sanitized, font_encoding, family_names, family_name, family_members
from ..util import _copy_attr, _copy_attrs, _flatten, foundry
from ..lib import geometry

class Context(object):
    KEY_UP = grobs.KEY_UP
    KEY_DOWN = grobs.KEY_DOWN
    KEY_LEFT = grobs.KEY_LEFT
    KEY_RIGHT = grobs.KEY_RIGHT
    KEY_BACKSPACE = grobs.KEY_BACKSPACE
    KEY_TAB = grobs.KEY_TAB
    KEY_ESC = grobs.KEY_ESC
    state_vars = '_outputmode', '_colormode', '_colorrange', '_fillcolor', '_strokecolor', '_strokewidth', '_capstyle', '_joinstyle', '_path', '_autoclosepath', '_transform', '_transformmode', '_rotationmode', '_transformstack', '_fontname', '_fontsize', '_lineheight', '_align', '_noImagesHint', '_oldvars', '_vars'

    def __init__(self, canvas=None, ns=None):
        """Initializes the context.

        Note that we have to give the namespace of the executing script,
        which is a hack to keep the WIDTH and HEIGHT properties updated.
        Python's getattr only looks up property values once: at assign time."""
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
        grobs._ctx = typography._ctx = bezier._ctx = self

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
        self._outputmode = RGB
        self._colormode = RGB
        self._colorrange = 1.0
        self._fillcolor = Color()
        self._strokecolor = None
        self._strokewidth = 1.0
        self._capstyle = BUTT
        self._joinstyle = MITER
        self._dashstyle = None
        self._path = None
        self._autoclosepath = True
        self._transform = Transform()
        self._transformmode = CENTER
        self._rotationmode = DEGREES
        self._transformstack = []
        self._fontname = "Helvetica"
        self._fontsize = 24
        self._lineheight = 1.2
        self._align = LEFT
        self._noImagesHint = False
        self._oldvars = self._vars
        self._vars = []
        self._stylesheet = Stylesheet()
        self.canvas.background = Color(1.0)

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

    ### Primitives ###

    def rect(self, x, y, width, height, radius=None, roundness=0.0, draw=True, **kwargs):
        Bezier.checkKwargs(kwargs)
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
        p.inheritFromContext(kwargs.keys())

        if draw:
            p.draw()
        return p

    def oval(self, x, y, width, height, draw=True, **kwargs):
        Bezier.checkKwargs(kwargs)
        path = Bezier(**kwargs)
        path.oval(x, y, width, height)
        path.inheritFromContext(kwargs.keys())

        if draw:
          path.draw()
        return path

    ellipse = oval

    def line(self, x1, y1, x2, y2, draw=True, **kwargs):
        if self._path is None:
            Bezier.checkKwargs(kwargs)
            p = Bezier(**kwargs)
            p.line(x1, y1, x2, y2)
            p.inheritFromContext(kwargs.keys())
            if draw:
              p.draw()
        else:
            # if a bezier is being built in a `with` block, add line segments to it, but
            # ignore kwargs since the bezier object's styles apply to all lines drawn
            p = self._path
            p.line(x1, y1, x2, y2)
        return p

    def star(self, startx, starty, points=20, outer=100, inner=50, draw=True, **kwargs):
        Bezier.checkKwargs(kwargs)
        from math import sin, cos, pi

        p = Bezier(**kwargs)
        p.moveto(startx, starty + outer)

        for i in range(1, int(2 * points)):
          angle = i * pi / points
          x = sin(angle)
          y = cos(angle)
          if i % 2:
              radius = inner
          else:
              radius = outer
          x = startx + radius * x
          y = starty + radius * y
          p.lineto(x,y)

        p.closepath()
        p.inheritFromContext(kwargs.keys())
        if draw:
          p.draw()
        return p

    def arrow(self, x, y, width=100, type=NORMAL, draw=True, **kwargs):

        """Draws an arrow.

        Draws an arrow at position x, y, with a default width of 100.
        There are two different types of arrows: NORMAL and trendy FORTYFIVE degrees arrows.
        When draw=False then the arrow's path is not ended, similar to endpath(draw=False)."""

        Bezier.checkKwargs(kwargs)
        if type==NORMAL:
          return self._arrow(x, y, width, draw, **kwargs)
        elif type==FORTYFIVE:
          return self._arrow45(x, y, width, draw, **kwargs)
        else:
          raise DeviceError("arrow: available types for arrow() are NORMAL and FORTYFIVE\n")

    def _arrow(self, x, y, width, draw, **kwargs):

        head = width * .4
        tail = width * .2

        p = Bezier(**kwargs)
        p.moveto(x, y)
        p.lineto(x-head, y+head)
        p.lineto(x-head, y+tail)
        p.lineto(x-width, y+tail)
        p.lineto(x-width, y-tail)
        p.lineto(x-head, y-tail)
        p.lineto(x-head, y-head)
        p.lineto(x, y)
        p.closepath()
        p.inheritFromContext(kwargs.keys())
        if draw:
          p.draw()
        return p

    def _arrow45(self, x, y, width, draw, **kwargs):

        head = .3
        tail = 1 + head

        p = Bezier(**kwargs)
        p.moveto(x, y)
        p.lineto(x, y+width*(1-head))
        p.lineto(x-width*head, y+width)
        p.lineto(x-width*head, y+width*tail*.4)
        p.lineto(x-width*tail*.6, y+width)
        p.lineto(x-width, y+width*tail*.6)
        p.lineto(x-width*tail*.4, y+width*head)
        p.lineto(x-width, y+width*head)
        p.lineto(x-width*(1-head), y)
        p.lineto(x, y)
        p.inheritFromContext(kwargs.keys())
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

    def beginpath(self, x=None, y=None):
        self._path = Bezier()
        self._pathclosed = False
        if x != None and y != None:
            self._path.moveto(x,y)

    def moveto(self, x, y):
        if self._path is None:
            raise DeviceError, "No current path. Use bezier() or beginpath() first."
        self._path.moveto(x,y)

    def lineto(self, x, y):
        if self._path is None:
            raise DeviceError, "No current path. Use bezier() or beginpath() first."
        self._path.lineto(x, y)

    def curveto(self, x1, y1, x2, y2, x3, y3):
        if self._path is None:
            raise DeviceError, "No current path. Use bezier() or beginpath() first."
        self._path.curveto(x1, y1, x2, y2, x3, y3)

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
        p.inheritFromContext()
        if draw:
            p.draw()
        self._path = None
        self._pathclosed = False
        return p

    def drawpath(self, path, **kwargs):
        Bezier.checkKwargs(kwargs)
        if isinstance(path, (list, tuple)):
            path = Bezier(path, **kwargs)
        else: # Set the values in the current bezier path with the kwargs
            for arg_key, arg_val in kwargs.items():
                setattr(path, arg_key, _copy_attr(arg_val))
        path.inheritFromContext(kwargs.keys())
        path.draw()

    def autoclosepath(self, close=True):
        self._autoclosepath = close

    def findpath(self, points, curvature=1.0):
        import bezier
        path = bezier.findpath(points, curvature=curvature)
        path._ctx = self
        path.inheritFromContext()
        return path

    ### Clipping Commands ###

    @contextmanager
    def clip(self, path):
        cp = self.beginclip(path)
        yield cp
        self.endclip()

    def beginclip(self, path):
        cp = ClippingPath(path)
        self.canvas.push(cp)
        return cp

    def endclip(self):
        self.canvas.pop()

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

    def plotstyle(self, *ops):
        context_mgrs = [mgr for mgr in ops if hasattr(mgr, '__enter__')]
        context_mgrs.append(InkContext(restore=all))
        return nested(*context_mgrs)

    def pen(self, nib=None, **spec): # spec: caps, joins, dash
        if nib is not None:
            spec.setdefault('nib', nib)
        return InkContext(**spec)

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
                return InkContext(**kwargs)

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

    def fill(self, *args):
        if len(args) > 0:
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
        txt.inheritFromContext(kwargs.keys())

        if outline:
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
        txt.inheritFromContext(kwargs.keys())
        return txt.path

    def textmetrics(self, txt, width=None, height=None, **kwargs):
        txt = Text(txt, 0, 0, width, height, **kwargs)
        txt.inheritFromContext(kwargs.keys())
        return txt.metrics

    def textwidth(self, txt, width=None, **kwargs):
        """Calculates the width of a single-line string."""
        return self.textmetrics(txt, width, **kwargs)[0]

    def textheight(self, txt, width=None, **kwargs):
        """Calculates the height of a (probably) multi-line string."""
        return self.textmetrics(txt, width, **kwargs)[1]

    ### Image commands ###

    def image(self, path, x, y, width=None, height=None, alpha=1.0, data=None, draw=True, **kwargs):
        img = Image(path, x, y, width, height, alpha, data=data, **kwargs)
        img.inheritFromContext(kwargs.keys())
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

    def plot(self, obj, copy=False, **kwargs):
        if not isinstance(obj, Grob):
            notdrawable = 'plot() only knows how to draw Bezier, Image, or Text objects (not %s)'%type(obj)
            raise DeviceError(notdrawable)
        obj.__class__.checkKwargs(kwargs)
        grob = obj.copy() if copy else obj
        for arg_key, arg_val in kwargs.items():
            setattr(grob, arg_key, _copy_attr(arg_val))
        grob.inheritFromContext(kwargs.keys())
        grob.draw()

    def measure(self, obj, width=None, height=None, **kwargs):
        """Returns a Size tuple for graphics objects, text, or file objects pointing to images"""
        if isinstance(obj, basestring):
            return Text(obj, 0, 0, width, height, **kwargs).metrics
        elif isinstance(obj, file):
            return Image(data=obj.read()).size
        elif isinstance(obj, Text):
            return obj.metrics()
        elif isinstance(obj, Image):
            return obj.getSize()
        elif isinstance(obj, Bezier):
            return obj.bounds.size
        else:
            badtype = "measure() can only handle Text, Images, Beziers, and file() objects (got %s)"%type(obj)
            raise DeviceError(badtype)


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

    def clear(self):
        self._grobs = self._container = []
        self._grobstack = [self._grobs]

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
