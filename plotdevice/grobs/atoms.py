# encoding: utf-8
from AppKit import *
from Foundation import *
from Quartz import *

from plotdevice import DeviceError
from ..util import _copy_attrs, _flatten, trim_zeroes
from .colors import Color
from .transform import Transform

_ctx = None
__all__ = [
        "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT", "KEY_BACKSPACE", "KEY_TAB", "KEY_ESC",
        "Variable", "NUMBER", "TEXT", "BOOLEAN","BUTTON",
        "Grob",
        ]

# an ‘undefined’ value for state vars
INHERIT = "inherit"

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


### Graphic object inheritence hierarchy w/ mixins to merge local and context state ###

class Grob(object):
    """A GRaphic OBject is the base class for all drawing primitives."""

    def __init__(self, **kwargs):
        attr_tuples = [getattr(cls,'stateAttrs',tuple()) for cls in self.__class__.__mro__]
        self.stateAttrs = sum(attr_tuples, tuple())

    def draw(self):
        """Adds the grob to the canvas. This will result in a _draw later on, when the
        scene graph is rendered. References to the grob are still ‘live’ meaning additional
        modifications of its transform, color, penstyle, etc. can be applied before the
        canvas renders."""
        self.inherit()
        _ctx.canvas.append(self)

    def copy(self):
        """Returns a deep copy of this grob."""
        raise NotImplementedError, "Copy is not implemented on this Grob class."

    def inherit(self):
        """Fills in unspecified attributes with the graphics context's state"""
        attrs_to_copy = [a for a in self.stateAttrs if getattr(self, a, INHERIT) is INHERIT]
        _copy_attrs(_ctx, self, attrs_to_copy)

    @classmethod
    def validate(self, kwargs):
        """Sanity check a potential set of constructor kwargs"""
        remaining = [arg for arg in kwargs.keys() if arg not in self.kwargs]
        if remaining:
            unknown = "Unknown argument(s) '%s'" % ", ".join(remaining)
            raise DeviceError(unknown)

class EffectsMixin(Grob):
    """Mixin class for transparency layer support.
    Adds the alpha, blend, and shadow attributes to the class."""
    stateAttrs = ('_effects',)

    def __init__(self, **kwargs):
        from .effects import Effect
        super(EffectsMixin, self).__init__(**kwargs)
        self._effects = INHERIT # effects from the context
        self._solo_fx = {}      # effect overrides from inline kwargs
        for eff, val in {k:kwargs[k] for k in kwargs if k in Effect.kwargs}.items():
            setattr(self, eff, val)

    @property
    def effects(self):
        """An Effect object merging inherited alpha/blend/shadow with local overrides"""
        from .effects import Effect
        merged = Effect() if self._effects==INHERIT else self._effects
        merged._fx.update(self._solo_fx)
        return merged

    def _get_alpha(self):
        return self._solo_fx.get('alpha', _ctx._effects.alpha)
    def _set_alpha(self, a):
        from .effects import Effect
        self._solo_fx['alpha'] = Effect._validate('alpha',a)
    alpha = property(_get_alpha, _set_alpha)

    def _get_blend(self):
        return self._solo_fx.get('blend', _ctx._effects.blend)
    def _set_blend(self, mode):
        from .effects import Effect
        self._solo_fx['blend'] = Effect._validate('blend', mode)
    blend = property(_get_blend, _set_blend)

    def _get_shadow(self):
        return self._solo_fx.get('shadow', _ctx._effects.shadow)
    def _set_shadow(self, spec):
        from .effects import Effect
        self._solo_fx['shadow'] = Effect._validate('shadow', spec)
    shadow = property(_get_shadow, _set_shadow)

class ColorMixin(Grob):
    """Mixin class for color support.
    Adds the _fillcolor and _strokecolor attributes to the class."""
    stateAttrs = ('_fillcolor', '_strokecolor')

    def __init__(self, **kwargs):
        super(ColorMixin, self).__init__(**kwargs)
        try:
            self._fillcolor = Color(kwargs['fill'])
        except KeyError:
            self._fillcolor = INHERIT
        try:
            self._strokecolor = Color(kwargs['stroke'])
        except KeyError:
            self._strokecolor = INHERIT

    def _get_fill(self):
        return _ctx._fillcolor if self._fillcolor is INHERIT else self._fillcolor
    def _set_fill(self, *args):
        self._fillcolor = Color(*args)
    fill = property(_get_fill, _set_fill)

    def _get_stroke(self):
        return _ctx._strokecolor if self._strokecolor is INHERIT else self._strokecolor
    def _set_stroke(self, *args):
        self._strokecolor = Color(*args)
    stroke = property(_get_stroke, _set_stroke)

class TransformMixin(Grob):
    """Mixin class for transformation support.
    Adds the _transform and _transformmode attributes to the class."""
    stateAttrs = ('_transform', '_transformmode')

    def __init__(self, **kwargs):
        super(TransformMixin, self).__init__(**kwargs)
        self._reset()

    def _reset(self):
        self._transform = INHERIT
        self._transformmode = INHERIT

    def _get_transform(self):
        if self._transform==INHERIT:
            self._transform = Transform(_ctx._transform)
        return self._transform
    def _set_transform(self, transform):
        self._transform = Transform(transform)
    transform = property(_get_transform, _set_transform)

    def _get_transformmode(self):
        return self._transformmode if self._transformmode!=INHERIT else _ctx._transformmode
    def _set_transformmode(self, mode):
        self._transformmode = mode
    transformmode = property(_get_transformmode, _set_transformmode)

    def translate(self, x, y):
        self.transform.translate(x, y)
        return self

    def reset(self):
        self._transform = Transform()
        return self

    def rotate(self, arg=None, **opts):
        self.transform.rotate(arg, **opts)
        return self

    def translate(self, x=0, y=0):
        self.transform.translate(x,y)
        return self

    def scale(self, x=1, y=None):
        self.transform.scale(x,y)
        return self

    def skew(self, x=0, y=0):
        self.transform.skew(x,y)
        return self

class PenMixin(Grob):
    """Mixin class for linestyle support.
    Adds the _capstyle, _joinstyle, _dashstyle, and _strokewidth attributes to the class."""
    stateAttrs = ('_penstyle', )

    def __init__(self, **kwargs):
        super(PenMixin, self).__init__(**kwargs)
        self._penstyle = INHERIT
        self._override = {}

        aliases = dict(nib='strokewidth', cap='capstyle', join='joinstyle', dash='dashstyle')
        for attr, alias in aliases.items():
            setattr(self, attr, kwargs.get(attr, kwargs.get(alias, INHERIT)))

        # self.nib = kwargs.get('nib', kwargs.get('strokewidth', INHERIT))
        # self.cap = kwargs.get('cap', kwargs.get('capstyle', INHERIT))
        # self.join = kwargs.get('join', kwargs.get('joinstyle', INHERIT))
        # self.dash = kwargs.get('dash', kwargs.get('dashstyle', INHERIT))

    def _get_strokewidth(self):
        baseline = _ctx if self._penstyle is INHERIT else self
        return self._override.get('nib', baseline._penstyle.nib)
    def _set_strokewidth(self, strokewidth):
        if strokewidth is INHERIT:
            self._override.pop('nib', None)
        else:
            self._override['nib'] = max(strokewidth, 0.0001)
    nib = strokewidth = property(_get_strokewidth, _set_strokewidth)

    def _get_capstyle(self):
        baseline = _ctx if self._penstyle is INHERIT else self
        return self._override.get('cap', baseline._penstyle.cap)
    def _set_capstyle(self, style):
        from bezier import BUTT, ROUND, SQUARE
        if style is INHERIT:
            self._override.pop('cap', None)
        elif style not in (BUTT, ROUND, SQUARE):
            badstyle = 'Line cap style should be BUTT, ROUND or SQUARE.'
            raise DeviceError(badstyle)
        else:
            self._override['cap'] = style
    cap = capstyle = property(_get_capstyle, _set_capstyle)

    def _get_joinstyle(self):
        baseline = _ctx if self._penstyle is INHERIT else self
        return self._override.get('join', baseline._penstyle.join)
    def _set_joinstyle(self, style):
        from bezier import MITER, ROUND, BEVEL
        if style is INHERIT:
            self._override.pop('join', None)
        elif style not in (MITER, ROUND, BEVEL):
            badstyle = 'Line join style should be MITER, ROUND or BEVEL.'
            raise DeviceError(badstyle)
        else:
            self._override['join'] = style
    join = joinstyle = property(_get_joinstyle, _set_joinstyle)

    def _get_dashstyle(self):
        baseline = _ctx if self._penstyle is INHERIT else self
        return self._override.get('dash', baseline._penstyle.dash)
    def _set_dashstyle(self, *segments):
        if INHERIT in segments:
            self._override.pop('dash', None)
        elif None in segments:
            self._override['dash'] = None
        else:
            steps = map(int, _flatten(segments))
            if len(steps)%2:
                steps += steps[-1:] # assume even spacing for omitted skip sizes
            self._override['dash'] = steps
    dash = dashstyle = property(_get_dashstyle, _set_dashstyle)

class StyleMixin(Grob):
    """Mixin class for transparency layer support.
    Adds the alpha, blend, and shadow attributes to the class."""
    stateAttrs = ('_stylesheet', '_typestyle', '_fillcolor',)

    def __init__(self, **kwargs):
        from .typography import Stylesheet
        super(StyleMixin, self).__init__(**kwargs)
        self._stylesheet = INHERIT # global stylesheet
        self._typestyle = INHERIT  # ctx font style
        self._fillcolor = INHERIT  # ctx fill color
        if 'fill' in kwargs:
            self._fillcolor = Color(kwargs['fill']) # override color
        self._override = Stylesheet._spec(**kwargs) # inline style params

    @property
    def stylesheet(self):
        """An Effect object merging inherited alpha/blend/shadow with local overrides"""
        if self._stylesheet==INHERIT:
            merged = _ctx._stylesheet.copy()
        else:
            merged = self._stylesheet.copy()
        merged._baseline = self._typestyle._asdict()
        merged._baseline['color'] = self.fill
        merged._override = self._override
        return merged

    def _get_fill(self):
        return _ctx._fillcolor if self._fillcolor is INHERIT else self._fillcolor
    def _set_fill(self, *args):
        self._fillcolor = Color(*args)
    fill = property(_get_fill, _set_fill)

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

