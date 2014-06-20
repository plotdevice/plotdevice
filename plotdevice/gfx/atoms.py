# encoding: utf-8
from AppKit import *
from Foundation import *
from Quartz import *

from plotdevice import DeviceError
from ..util import _copy_attrs, _copy_attr, _flatten, trim_zeroes
from .colors import Color
from .transform import Transform

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

class Grob(object):
    """A GRaphic OBject is the base class for all drawing primitives."""
    stateAttrs = ('_preserve',)

    def __init__(self, **kwargs):
        # _inherit:  tuple of attrs to copy from the _ctx
        # _state:    tuple of attrs to copy when cloning a grob
        # _preserve: set of grob property names with overridden values
        self._inherit, self._state = _merge_state(self)
        self._preserve = set()
        self.inherit()

    def draw(self):
        """Adds the grob to the canvas. This will result in a _draw later on, when the
        scene graph is rendered. References to the grob are still ‘live’ meaning additional
        modifications of its transform, color, penstyle, etc. can be applied before the
        canvas renders."""
        _ctx.canvas.append(self)

    def copy(self):
        """Returns a deep copy of this grob."""
        raise NotImplementedError, "Copy is not implemented on this Grob class."

    def inherit(self):
        """Fills in unspecified attributes with the graphics context's state"""
        preserve = {attr:getattr(self, attr) for attr in self._preserve}
        _copy_attrs(_ctx, self, self._inherit)
        for attr, val in preserve.items():
            setattr(self, attr, val)

    @classmethod
    def validate(self, kwargs):
        """Sanity check a potential set of constructor kwargs"""
        remaining = [arg for arg in kwargs.keys() if arg not in self.kwargs]
        if remaining:
            unknown = "Unknown argument(s) '%s'" % ", ".join(remaining)
            raise DeviceError(unknown)

# memoize walking the class hierarchy for inheritance information
def _merge_state(obj, types={}):
    """Returns a 2-tuple with inherited- and state-var names"""
    t = type(obj)
    if t not in types:
        ctx, state = set(), set()
        for cls in obj.__class__.__mro__:
            ctx.update(getattr(cls,'ctxAttrs',[]))
            state.update(getattr(cls,'stateAttrs',[]))
        state.update(ctx)
        types[t] = (tuple(sorted(ctx)), tuple(sorted(state)))
    return types[t]


class EffectsMixin(Grob):
    """Mixin class for transparency layer support.
    Adds the alpha, blend, and shadow attributes to the class."""
    ctxAttrs = ('_effects',)

    def __init__(self, **kwargs):
        from .effects import Effect
        super(EffectsMixin, self).__init__(**kwargs)
        for eff in [k for k in kwargs.keys() if k in Effect.kwargs]:
            setattr(self, eff, kwargs[eff])

    @property
    def effects(self):
        """An Effect object merging inherited alpha/blend/shadow with local overrides"""
        return self._effects

    def _get_alpha(self):
        return self._effects.alpha
    def _set_alpha(self, a):
        self._effects.alpha = a
        self._preserve.add('alpha')
    alpha = property(_get_alpha, _set_alpha)

    def _get_blend(self):
        return self._effects.blend
    def _set_blend(self, mode):
        self._effects.blend = mode
        self._preserve.add('blend')
    blend = property(_get_blend, _set_blend)

    def _get_shadow(self):
        return self._effects.shadow
    def _set_shadow(self, spec):
        self._effects.shadow = spec
        self._preserve.add('shadow')
    shadow = property(_get_shadow, _set_shadow)

class ColorMixin(Grob):
    """Mixin class for color support.
    Adds the _fillcolor and _strokecolor attributes to the class."""
    ctxAttrs = ('_fillcolor', '_strokecolor')

    def __init__(self, **kwargs):
        super(ColorMixin, self).__init__(**kwargs)
        for ink in 'fill', 'stroke':
            if ink in kwargs:
                setattr(self, '_%scolor'%ink, Color(kwargs[ink]))

    def _get_fill(self):
        return self._fillcolor
    def _set_fill(self, *args):
        self._fillcolor = None if args[0] is None else Color(*args)
        self._preserve.add('fill')
    fill = property(_get_fill, _set_fill)

    def _get_stroke(self):
        return self._strokecolor
    def _set_stroke(self, *args):
        self._strokecolor = None if args[0] is None else Color(*args)
        self._preserve.add('stroke')
    stroke = property(_get_stroke, _set_stroke)

class TransformMixin(Grob):
    """Mixin class for transformation support.
    Adds the _transform and _transformmode attributes to the class."""
    ctxAttrs = ('_transform', '_transformmode')
    stateAttrs = ('_localTransform',)

    def __init__(self, **kwargs):
        super(TransformMixin, self).__init__(**kwargs)
        self._localTransform = Transform()

    # CENTER or CORNER
    def _get_transformmode(self):
        return self._transformmode
    def _set_transformmode(self, mode):
        if style not in (BUTT, ROUND, SQUARE):
            badmode = 'Transform mode should be CENTER or CORNER.'
            raise DeviceError(badmode)
        self._transformmode = mode
    transformmode = property(_get_transformmode, _set_transformmode)

    # the inherited `canvas transform'
    def _get_transform(self):
        # .transform returns a merger of the ctm and local transforms (if any)
        xf = Transform(self._transform)
        xf.prepend(self._localTransform)
        return xf
    def _set_transform(self, transform):
        # setting .transform assigns to the slot for the ctm and sets
        # the local transform to identity
        self._preserve.add('_transform') # flag that we've modified the ctm
        self._transform = Transform(transform)
        self._localTransform = Transform()
    transform = property(_get_transform, _set_transform)

    # object-specific transform matrix (set by obj.rotate(), obj.translate(), etc.).
    # will always be applied *after* the inherited `canvas transform'
    def _get_localTransformform(self):
        self._preserve.add('localTransform') # flag that we've modified the local matrix
        # (not that we have yet, but dereferencing is the first step in that...)
        return self._localTransform
    def _set_localTransformform(self, transform):
        self._localTransform = Transform(transform)
    localTransform = property(_get_localTransformform, _set_localTransformform)

    def translate(self, x, y):
        self.localTransform.translate(x, y)
        return self

    def rotate(self, arg=None, **opts):
        self.localTransform.rotate(arg, **opts)
        return self

    def translate(self, x=0, y=0):
        self.localTransform.translate(x,y)
        return self

    def scale(self, x=1, y=None):
        self.localTransform.scale(x,y)
        return self

    def skew(self, x=0, y=0):
        self.localTransform.skew(x,y)
        return self

    def reset(self):
        # clear out the inherited transform rather than our localTransform
        # the property setter will set *both* matrices to Identity so it's a
        # true reset (rather than wiping out *just* the local transformations).
        self.transform = Transform()
        return self


class PenMixin(Grob):
    """Mixin class for linestyle support.
    Adds the _capstyle, _joinstyle, _dashstyle, and _strokewidth attributes to the class."""
    ctxAttrs = ('_penstyle', )

    def __init__(self, **kwargs):
        super(PenMixin, self).__init__(**kwargs)
        aliases = dict(nib='strokewidth', cap='capstyle', join='joinstyle', dash='dashstyle')
        for attr, alias in aliases.items():
            try:
                setattr(self, attr, kwargs.get(attr, kwargs[alias]))
            except KeyError:
                pass

    def _get_strokewidth(self):
        return self._penstyle.nib
    def _set_strokewidth(self, strokewidth):
        self._penstyle = self._penstyle._replace(nib=max(strokewidth, 0.0001))
        self._preserve.add('nib')
    nib = strokewidth = property(_get_strokewidth, _set_strokewidth)

    def _get_capstyle(self):
        return self._penstyle.cap
    def _set_capstyle(self, style):
        from bezier import BUTT, ROUND, SQUARE
        if style not in (BUTT, ROUND, SQUARE):
            badstyle = 'Line cap style should be BUTT, ROUND or SQUARE.'
            raise DeviceError(badstyle)
        self._penstyle = self._penstyle._replace(cap=style)
        self._preserve.add('cap')
    cap = capstyle = property(_get_capstyle, _set_capstyle)

    def _get_joinstyle(self):
        return self._penstyle.join
    def _set_joinstyle(self, style):
        from bezier import MITER, ROUND, BEVEL
        if style not in (MITER, ROUND, BEVEL):
            badstyle = 'Line join style should be MITER, ROUND or BEVEL.'
            raise DeviceError(badstyle)
        self._penstyle = self._penstyle._replace(join=style)
        self._preserve.add('join')
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
        self._preserve.add('dash')
    dash = dashstyle = property(_get_dashstyle, _set_dashstyle)

class StyleMixin(Grob):
    """Mixin class for transparency layer support.
    Adds the alpha, blend, and shadow attributes to the class."""
    ctxAttrs = ('_stylesheet', '_typestyle', '_fillcolor',)

    def __init__(self, **kwargs):
        from .typography import Stylesheet
        super(StyleMixin, self).__init__(**kwargs)
        if 'fill' in kwargs:
            self.fill = kwargs['fill'] # override color
        self._override = Stylesheet._spec(**kwargs) # inline style params

    @property
    def stylesheet(self):
        """An Effect object merging inherited alpha/blend/shadow with local overrides"""
        merged = self._stylesheet.copy()
        merged._baseline = self._typestyle._asdict()
        merged._baseline['fill'] = self.fill
        merged._override = self._override
        return merged

    def _get_fill(self):
        return self._fillcolor
    def _set_fill(self, *args):
        self._fillcolor = Color(*args)
        self._preserve.add('fill')
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

