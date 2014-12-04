# encoding: utf-8
import sys
import re
from operator import attrgetter
from plotdevice.util import odict
from ..lib.cocoa import *

from plotdevice import DeviceError
from .atoms import StyleMixin
from .colors import Color
from ..util import _copy_attrs
from ..lib.foundry import *

_ctx = None
__all__ = ("Family", "Font", "Stylesheet",
           "LEFT", "RIGHT", "CENTER", "JUSTIFY",)

# text alignments
LEFT = "left"
RIGHT = "right"
CENTER = "center"
JUSTIFY = "justify"
_TEXT=dict(
    left = NSLeftTextAlignment,
    right = NSRightTextAlignment,
    center = NSCenterTextAlignment,
    justify = NSJustifiedTextAlignment
)

class Font(object):
    def __init__(self, *args, **kwargs):

        # handle the bootstrap case where we're initializing the ctx's font
        if args==(None,):
            self._face = font_face("HelveticaNeue")
            self._metrics = dict(size=24.0, leading=1.2, tracking=0, indent=0, align=LEFT, hyphenate=0)
            self._features = {}
            return

        # accept Font objects or spec dicts as first positional arg
        first = args[0] if args else None
        if isinstance(first, Font):
            # make a copy of the existing font obj
            _copy_attrs(first, self, ('_face','_metrics','_features'))
            return
        elif hasattr(first, 'items'):
            # treat dict as output of a prior call to fontspec()
            new_spec = dict(first)
        else:
            # check for invalid kwarg names
            StyleMixin.validate(kwargs)

            # validate & standardize the kwargs first
            new_spec = fontspec(*args, **kwargs)

        # collect the attrs from the current font to fill in any gaps
        cur_spec = _ctx._font._spec
        for axis, num_axis in dict(weight='wgt', width='wid').items():
            # convert weight & width to integer values
            cur_spec[num_axis] = getattr(_ctx._font._face, num_axis)
            if axis in new_spec:
                name, val = standardized(axis, new_spec[axis])
                new_spec.update({axis:name, num_axis:val})

        # merge in changes from the new spec
        spec = dict(cur_spec.items() + new_spec.items()) # our criteria

        # use the combined spec to pick a face then break it into attributes
        self._face = best_face(spec)
        self._metrics = line_metrics(spec)
        self._features = aat_features(spec)

    def __repr__(self):
        spec = [self.family, self.weight, self.face]
        if self._face.variant:
            spec.insert(2, self._face.variant)
        spec.insert(1, '/' if self._face.italic else '|')
        spec.insert(1, ("%.1fpt"%self._metrics['size']).replace('.0pt','pt'))
        return (u'Font(%s)'%" ".join(spec)).encode('utf-8')

    def __enter__(self):
        if not hasattr(self, '_rollback'):
            self._rollback = _ctx._font
        _ctx._font = self
        return self

    def __exit__(self, type, value, tb):
        _ctx._font = self._rollback
        del self._rollback

    def copy(self):
        return Font(self)

    ### face introspection ###

    @property
    def family(self):
        return self._face.family

    @property
    def weight(self):
        return self._face.weight

    @property
    def width(self):
        return self._face.width

    @property
    def variant(self):
        return self._face.variant

    @property
    def italic(self):
        return self._face.italic

    @property
    def face(self):
        return self._face.psname

    ### family introspection ###

    @property
    def weights(self):
        return Family(self.family).weights

    @property
    def widths(self):
        return Family(self.family).widths

    @property
    def variants(self):
        return Family(self.family).variants

    @property
    def siblings(self):
        return Family(self.family).fonts

    ### line metrics ###

    @property
    def ascender(self):
        return self._nsFont.ascender()

    @property
    def descender(self):
        return self._nsFont.descender()

    @property
    def xheight(self):
        return self._nsFont.xHeight()

    @property
    def capheight(self):
        return self._nsFont.capHeight()

    ### line layout ###

    @property
    def size(self):
        return self._metrics['size']

    @property
    def leading(self):
        return self._metrics['leading']

    @property
    def tracking(self):
        return self._metrics['tracking']

    @property
    def hyphenate(self):
        return self._metrics['hyphenate']

    @property
    def align(self):
        return self._metrics['align']

    ### OpenType features ###

    @property
    def features(self):
        return dict(self._features)

    ### internals ###

    @property
    def _nsFont(self):
        fd = NSFontDescriptor.fontDescriptorWithName_size_(self._face.psname, self._metrics['size'])
        if self._features:
            fd = fd.fontDescriptorByAddingAttributes_(aat_attrs(self._features))
        return NSFont.fontWithDescriptor_textTransform_(fd,None)

    @property
    def _spec(self):
        spec = {axis:getattr(self._face, axis) for axis in ('family','weight','width','variant','italic')}
        spec.update(self._features)
        spec.update(self._metrics)
        return spec


class Family(object):
    def __init__(self, famname):
        if isinstance(famname, Font):
            famname = famname.family

        self._name = family_name(famname)
        self._faces = odict( (f.psname,f) for f in family_members(self._name) )
        self.encoding = font_encoding(self._faces.keys()[0])

    def __repr__(self):
        contents = ['"%s"'%self._name, ]
        for group in 'weights', 'widths', 'variants', 'faces':
            n = len(getattr(self, group))
            if n:
                contents.append('%i %s%s' % (n, group[:-1], '' if n==1 else 's'))
        return (u'Family(%s)'%", ".join(contents)).encode('utf-8')

    @property
    def name(self):
        return self._name

    @property
    def faces(self):
        return odict(self._faces)

    @property
    def fonts(self):
        return odict( (k,Font(face=v.psname)) for k,v in self._faces.items())

    @property
    def has_italic(self):
        for f in self._faces.values():
            if f.italic:
                return True
        return False

    @property
    def weights(self):
        w_names = []
        for f in sorted(self._faces.values(), key=attrgetter('wgt')):
            if f.weight not in w_names:
                w_names.append(f.weight)
        return tuple(w_names)

    @property
    def variants(self):
        v_names = []
        for f in sorted(self._faces.values(), key=attrgetter('wgt')):
            if f.variant not in v_names:
                v_names.append(f.variant)
        if any(v_names) and None in v_names:
            return tuple([None] + filter(None,v_names))
        return tuple(v_names)

    @property
    def widths(self):
        w_names = []
        for f in sorted(self._faces.values(), key=attrgetter('wid')):
            if f.width not in w_names:
                w_names.append(f.width)
        if w_names==[None]:
            return ()
        return tuple(w_names)

    @classmethod
    def find(cls, like=None, encoding="western"):
        all_fams = family_names()
        if like:
            all_fams = [name for name in all_fams if sanitized(like) in sanitized(name)]

        if encoding is all:
            return all_fams

        regions = {}
        for fam in all_fams:
            fnt = family_members(fam, names=True)[0]
            enc = font_encoding(fnt)
            regions[enc] = regions.get(enc, []) + [fam]

        try:
            return regions[encoding.title()]
        except:
            if like:
                nosuchzone = "Couldn't find any fonts matching %r with an encoding of %r" % (like, encoding)
            else:
                nosuchzone = "Couldn't find any fonts with an encoding of %r, choose from: %r" % (encoding, regions.keys())
            raise DeviceError(nosuchzone)


class Stylesheet(object):
    kwargs = StyleMixin.opts

    def __init__(self, styles=None):
        self._styles = dict(styles or {})

    def __repr__(self):
        return "Stylesheet(%r)"%(self._styles)

    def __iter__(self):
        return iter(self._styles.keys())

    def __len__(self):
        return len(self._styles)

    def __getitem__(self, key):
        item = self._styles.get(key)
        return dict(item) if item else None

    def __setitem__(self, key, val):
        if val is None:
            del self[key]
        elif hasattr(val, 'items'):
            self.style(key, **val)
        else:
            badtype = 'Stylesheet: when directly assigning styles, pass them as dictionaries (not %s)'%type(val)
            raise DeviceError(badtype)

    def __delitem__(self, key):
        if key in self._styles:
            del self._styles[key]

    def copy(self):
        return Stylesheet(self._styles)

    @property
    def styles(self):
        return dict(self._styles)

    def style(self, name, *args, **kwargs):
        if not kwargs and any(a in (None,'inherit') for a in args[:1]):
            del self[name]
        elif args or kwargs:
            spec = {}
            spec.update(self._styles.get( kwargs.get('style'), {} ))
            spec.update(fontspec(*args, **kwargs))
            color = kwargs.get('fill')
            if color and not isinstance(color, Color):
                if isinstance(color, basestring):
                    color = (color,)
                color = Color(*color)
            if color:
                spec['fill'] = color
            self._styles[name] = spec
        return self[name]

    def _dedent(self, attr_str, first=False):
        """Ensure that any paragraph that has more than one leading newline is un-indented.

        Destructively modifies the attributed-string, zapping indentation on the initial line
        as well if the `first` flag is True.
        """
        zap = [0] if first else [] # `first` means this is the leading char of a Text grob
        for m in re.finditer(r'\n\n+[^\n]', attr_str.string()):
            zap.append(m.end()-1)

        for idx in zap:
            old_graf, _ = attr_str.attribute_atIndex_effectiveRange_("NSParagraphStyle", idx, None);
            graf = old_graf.mutableCopy()
            graf.setFirstLineHeadIndent_(0)
            attr_str.addAttribute_value_range_("NSParagraphStyle", graf, (idx, 1))
        return attr_str

    def _cascade(self, defaults, *styles):
        """Apply the listed styles in order and return nsattibutedstring attrs"""

        # use the inherited context settings as a baseline spec
        spec = dict(defaults)

        # layer the styles to generate a final font and color
        for tag in styles:
            spec.update(self._styles.get(tag,{}))

        # assign a font and color based on the coalesced spec
        font = Font({k:v for k,v in spec.items() if k in Stylesheet.kwargs})
        color = Color(spec.pop('fill')).nsColor

        # factor the relevant attrs into a paragraph style
        graf = NSMutableParagraphStyle.alloc().init()
        graf.setLineBreakMode_(NSLineBreakByWordWrapping)
        graf.setAlignment_(_TEXT[spec['align']])
        graf.setHyphenationFactor_(spec['hyphenate'])

        # force the typesetter to deal with real leading rather than `lineheight'
        face_height = font.size * (font._face.ascent - font._face.descent) / 1000.0
        graf.setLineHeightMultiple_(spec['leading'] * font.size / face_height)
        graf.setMaximumLineHeight_(font.size*spec['leading'])

        indent = spec.get('indent', 0)
        if indent > 0:
            graf.setFirstLineHeadIndent_(font.size*indent)
        elif indent < 0:
            graf.setHeadIndent_(font.size*abs(indent))

        if not spec['tracking']:
            # None means `kerning off entirely', 0 means `default letterspacing'
            kern = 0 if spec['tracking'] is None else sys.float_info.epsilon
        else:
            # convert the em-based tracking val to a point-based kerning val
            kern = (spec['tracking'] * font.size)/1000.0

        # build the dict of features for this combination of styles
        return dict(NSFont=font._nsFont, NSColor=color, NSParagraphStyle=graf, NSKern=kern)
