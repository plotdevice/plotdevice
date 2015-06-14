# encoding: utf-8
from AppKit import *
from Foundation import *
from Quartz import *
from collections import namedtuple, defaultdict

from plotdevice import DeviceError
from ..lib.foundry import fontspec
from ..util import _copy_attrs, _copy_attr, _flatten, trim_zeroes, numlike
from .colors import Color
from .geometry import Transform, Dimension, Region, Pair
from .effects import Effect

_ctx = None
__all__ = [
        "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT", "KEY_BACKSPACE", "KEY_TAB", "KEY_ESC",
        "Variable", "NUMBER", "TEXT", "BOOLEAN","BUTTON",
        "Grob",
        ]

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


### Graphic object inheritance hierarchy w/ mixins to merge local and context state ###

class Bequest(type):
    """Metaclass for grobs that walks through the inheritance hierarchy building up three tuples:

        _inherit: attrs to copy from the _ctx when creating a new grob
        _state:   attrs to copy from instance to instance when making a copy
        _opts:    valid keyword arguments (for setting inline styles)

    The tuples are added as class variables and can be accessed as attributes on any
    instance of Bezier, Image, or Text.
    """

    def __init__(cls, name, bases, dct):
        super(Bequest, cls).__init__(name, bases, dct)
        if not (name=='Grob' or name.endswith('Mixin')):
            info = defaultdict(set)
            for typ in (cls,)+bases:
                info['_inherit'].update(getattr(typ,'ctxAttrs',[]))
                info['_state'].update(getattr(typ,'stateAttrs',[]))
                info['_opts'].update(getattr(typ,'opts',[]))
            info['_state'].update(info['_inherit'])
            for attr, val in info.items():
                setattr(cls, attr, val)

class Grob(object):
    """A GRaphic OBject is the base class for all drawing primitives."""
    __metaclass__ = Bequest
    ctxAttrs = ('_grid',)

    def __init__(self, **kwargs):
        self.inherit() # copy over every _ctx attribute we're interested in

    def draw(self):
        """Adds the grob to the canvas. This will result in a _draw later on, when the
        scene graph is rendered. References to the grob are still ‘live’ meaning additional
        modifications of its transform, color, penstyle, etc. can be applied before the
        canvas renders."""
        _ctx.canvas.append(self)

    def copy(self):
        """Returns a deep copy of this grob."""
        return self.__class__(self)

    def inherit(self, src=None):
        """Fills in attributes drawn from the _ctx (at init time) or another grob (to make a copy)."""
        if src is None:
            src, attrs = _ctx, self._inherit
        else:
            attrs = set(src._state).intersection(self._state)
        _copy_attrs(src, self, attrs)

    def update(self, mapping=None, **kwargs):
        """Assign new values to one or more properties

        Either call with keyword arguments of the same name as the object properties you
        wish to change, or with a dictionary of property names and values as the sole
        positional argument.
        """
        if isinstance(mapping, dict):
            kwargs = mapping
        for attr, val in kwargs.items():
            setattr(self, attr, val)

    @classmethod
    def validate(cls, kwargs):
        """Sanity check a potential set of constructor kwargs"""
        known = getattr(cls, '_opts', cls.opts)
        remaining = [arg for arg in kwargs.keys() if arg not in known]
        if remaining:
            unknown = "Unknown %s argument%s '%s'" % (cls.__name__, '' if len(remaining)==1 else 's', ", ".join(remaining))
            raise DeviceError(unknown)

    def _to_px(self, unit):
        """Convert from canvas units to postscript points"""
        if numlike(unit) or isinstance(unit, Pair):
            return unit * self._grid.dpx
        return self._grid.to_px.apply(unit)

    def _from_px(self, px):
        """Convert from postscript points to canvas units"""
        if numlike(px) or isinstance(px, Pair):
            return px / self._grid.dpx
        return self._grid.from_px.apply(px)


class EffectsMixin(Grob):
    """Mixin class for transparency layer support.
    Adds the alpha, blend, and shadow properties to the class."""
    ctxAttrs = ('_effects',)
    opts = ('alpha','blend','shadow')

    def __init__(self, **kwargs):
        super(EffectsMixin, self).__init__(**kwargs)
        for attr in EffectsMixin.opts:
            if attr in kwargs:
                setattr(self, attr, kwargs[attr])

    @property
    def effects(self):
        """An Effect object merging inherited alpha/blend/shadow with local overrides"""
        return self._effects

    def _get_alpha(self):
        return self._effects.alpha
    def _set_alpha(self, a):
        self._effects.alpha = a
    alpha = property(_get_alpha, _set_alpha)

    def _get_blend(self):
        return self._effects.blend
    def _set_blend(self, mode):
        self._effects.blend = mode
    blend = property(_get_blend, _set_blend)

    def _get_shadow(self):
        return self._effects.shadow
    def _set_shadow(self, spec):
        self._effects.shadow = spec
    shadow = property(_get_shadow, _set_shadow)

class FrameMixin(Grob):
    """Mixin class for dimensions.
    Adds x, y, width, & height properties to the class."""
    stateAttrs = ('_frame',)
    opts = ('x','y','w','h','width','height')

    def __init__(self, **kwargs):
        super(FrameMixin, self).__init__(**kwargs)

        x, y = kwargs.get('x',0), kwargs.get('y',0)
        h = kwargs.get('h',kwargs.get('height',None))
        w = kwargs.get('w',kwargs.get('width',None))
        if isinstance(w, basestring):
            w = None # ignore width if it's passing a font style
        self._frame = Region(x,y,w,h)

    @property
    def frame(self):
        return Region(self._frame)

    def _get_x(self):
        return self._frame.x
    def _set_x(self, x):
        self._frame.x = x
    x = property(_get_x, _set_x)

    def _get_y(self):
        return self._frame.y
    def _set_y(self, y):
        self._frame.y = y
    y = property(_get_y, _set_y)

    def _get_width(self):
        return self._frame.width
    def _set_width(self, w):
        changed = self._frame.width != w
        self._frame.width = w
        if changed:
            self._resized()
    w = width = property(_get_width, _set_width)

    def _get_height(self):
        return self._frame.height
    def _set_height(self, h):
        changed = self._frame.height != h
        self._frame.height = h
        if changed:
            self._resized()
    h = height = property(_get_height, _set_height)

    def _resized(self):
        pass # overridden by Text & TextBlock

class ColorMixin(Grob):
    """Mixin class for color support.
    Adds the fill & stroke properties to the class."""
    ctxAttrs = ('_fillcolor', '_strokecolor')
    opts = ('fill','stroke',)

    def __init__(self, **kwargs):
        super(ColorMixin, self).__init__(**kwargs)
        for attr in ColorMixin.opts:
            if attr in kwargs:
                setattr(self, attr, kwargs[attr])

    def _get_fill(self):
        return self._fillcolor
    def _set_fill(self, *args):
        self._fillcolor = None if args[0] is None else Color(*args)
    fill = property(_get_fill, _set_fill)

    def _get_stroke(self):
        return self._strokecolor
    def _set_stroke(self, *args):
        self._strokecolor = None if args[0] is None else Color(*args)
    stroke = property(_get_stroke, _set_stroke)

class TransformMixin(Grob):
    """Mixin class for transformation support.
    Adds the _transform and _transformmode attributes to the class."""
    ctxAttrs = ('_transform', '_transformmode',)

    def __init__(self, **kwargs):
        super(TransformMixin, self).__init__(**kwargs)

    def _get_transformmode(self):
        return self._transformmode
    def _set_transformmode(self, mode):
        if style not in (CENTER, CORNER):
            badmode = 'Transform mode should be CENTER or CORNER.'
            raise DeviceError(badmode)
        self._transformmode = mode
    transformmode = property(_get_transformmode, _set_transformmode)

    def _get_transform(self):
        return self._transform
    def _set_transform(self, transform):
        self._transform = Transform(transform)
    transform = property(_get_transform, _set_transform)

    def translate(self, x=0, y=0):
        self._transform.translate(x,y)
        return self

    def rotate(self, arg=None, **opts):
        self._transform.rotate(arg, **opts)
        return self

    def scale(self, x=1, y=None):
        self._transform.scale(x,y)
        return self

    def skew(self, x=0, y=0):
        self._transform.skew(x,y)
        return self

    def reset(self):
        self._transform = Transform()
        return self


class PenMixin(Grob):
    """Mixin class for linestyle support.
    Adds the nib, cap, join, and dash attributes to the class."""
    ctxAttrs = ('_penstyle', )
    opts = ('nib','cap','join','dash','strokewidth','capstyle','joinstyle','dashstyle',)

    def __init__(self, **kwargs):
        super(PenMixin, self).__init__(**kwargs)
        for attr, val in kwargs.items():
            if attr in PenMixin.opts:
                setattr(self, attr, val)

    def _get_strokewidth(self):
        return self._penstyle.nib
    def _set_strokewidth(self, strokewidth):
        self._penstyle = self._penstyle._replace(nib=max(strokewidth, 0.0001))
    nib = strokewidth = property(_get_strokewidth, _set_strokewidth)

    def _get_capstyle(self):
        return self._penstyle.cap
    def _set_capstyle(self, style):
        from bezier import BUTT, ROUND, SQUARE
        if style not in (BUTT, ROUND, SQUARE):
            badstyle = 'Line cap style should be BUTT, ROUND or SQUARE.'
            raise DeviceError(badstyle)
        self._penstyle = self._penstyle._replace(cap=style)
    cap = capstyle = property(_get_capstyle, _set_capstyle)

    def _get_joinstyle(self):
        return self._penstyle.join
    def _set_joinstyle(self, style):
        from bezier import MITER, ROUND, BEVEL
        if style not in (MITER, ROUND, BEVEL):
            badstyle = 'Line join style should be MITER, ROUND or BEVEL.'
            raise DeviceError(badstyle)
        self._penstyle = self._penstyle._replace(join=style)
    join = joinstyle = property(_get_joinstyle, _set_joinstyle)

    def _get_dashstyle(self):
        return self._penstyle.dash
    def _set_dashstyle(self, *segments):
        if None in segments:
            steps = None
        else:
            steps = map(int, _flatten(segments))
            if len(steps)%2:
                steps += steps[-1:] # assume even spacing for omitted skip sizes
        self._penstyle = self._penstyle._replace(dash=steps)
    dash = dashstyle = property(_get_dashstyle, _set_dashstyle)

class StyleMixin(Grob):
    """Mixin class for text-styling support.
    Adds the stylesheet, fill, and font attributes to the class."""
    ctxAttrs = ('_font', '_stylesheet', '_fillcolor')
    layoutOpts = ('leading','spacing','margin','indent','align','hyphenate','lineheight')
    fontOpts = ('face','family','size','weight','width','variant','italic','tracking','fontname','fontsize','font')
    aatOpts = ('lig','sc','osf','tab','vpos','frac', 'ss')
    opts = fontOpts + layoutOpts + aatOpts + ('style', 'fill')

    def __init__(self, **kwargs):
        super(StyleMixin, self).__init__(**kwargs)

        # ignore `width` if it's a column-width rather than typeface width
        if not isinstance(kwargs.get('width', ''), basestring):
            kwargs = dict(kwargs)
            del kwargs['width']

        self._update_style(**kwargs)

    def _parse_style(self, *args, **opts):
        fontopts = {k:v for k,v in opts.items() if k in StyleMixin.opts}
        fontargs = opts.get('font', args)
        if not isinstance(fontargs, (list,tuple)):
            fontargs = [fontargs]

        spec = self.stylesheet._styles.get( opts.get('style'), {} )
        spec.update(fontspec(*fontargs, **fontopts))
        if 'fill' in opts:
            spec['fill'] = Color(opts['fill'])
        return spec

    def _update_style(self, *args, **kwargs):
        # combine inherited ctx state and kwargs to create a baseline style
        spec = self._font._spec                         # start with the current font
        spec.update(fill=self._fillcolor)               # use the ctx's current fill by default
        spec.update(self._parse_style(*args, **kwargs)) # merge in any modifications from the text() call

        # update the font & fill references to reflect kwarg styling (if any)
        self._font = self._font.__class__(**spec)
        self._fillcolor = spec.get('fill', self._fillcolor)

    def font(self, *args, **kwargs):
        from .typography import Font
        if args or kwargs:
            Font.validate(kwargs)
            self._update_style(*args, **kwargs)
        return self._font

    def layout(self, **kwargs):
        from .typography import Layout
        if kwargs:
            Layout.validate(kwargs)
            self._update_style(**kwargs)
        return Layout(self._font)

    @property
    def stylesheet(self):
        return self._stylesheet

    @property
    def fill(self):
        return self._fillcolor

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
        if hasattr(self, 'min'):
            return "Variable(name=%s, type=%s, default=%s, min=%s, max=%s, value=%s)" % (self.name, self.type, self.default, self.min, self.max, self.value)

        return "Variable(name=%s, type=%s, default=%s, value=%s)" % (self.name, self.type, self.default, self.value)
