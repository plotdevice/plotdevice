# encoding: utf-8
import re
from operator import itemgetter, attrgetter
from plotdevice.util import odict, ddict
from ..lib.cocoa import *

from plotdevice import DeviceError, INTERNAL as DEFAULT
from .atoms import TransformMixin, ColorMixin, EffectsMixin, StyleMixin, BoundsMixin, Grob
from . import _save, _restore, _ns_context
from .transform import Transform, Region, Size
from .colors import Color
from .bezier import Bezier
from ..util.foundry import *
from ..util import _copy_attrs, numlike, XMLParser

_ctx = None
__all__ = ("Text", "Family", "Font", "Stylesheet",
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

# utility method for filtering through the font library
def families(like=None, western=True):
    all_fams = family_names()
    if like:
        all_fams = [name for name in all_fams if sanitized(like) in sanitized(name)]

    representatives = {fam:family_members(fam, names=True)[0] for fam in all_fams}
    in_region = {fam:font_encoding(fnt)=="MacOSRoman" for fam,fnt in representatives.items()}
    if not western:
        in_region = {fam:not macroman for fam,macroman in in_region.items()}

    # return [Family(fam) for fam in all_fams if in_region[fam]]
    return [fam for fam in all_fams if in_region[fam]]

class Text(TransformMixin, EffectsMixin, BoundsMixin, StyleMixin, Grob):
    # from TransformMixin: transform transformmode translate() rotate() scale() skew() reset()
    # from EffectsMixin:   alpha blend shadow
    # from BoundsMixin:    x y width height
    # from StyleMixin:     stylesheet fill
    stateAttrs = ('_style', 'text')

    def __init__(self, text, *args, **kwargs):
        super(Text, self).__init__(**kwargs)

        if isinstance(text, Text):
            self.inherit(text)
            return

        if not isinstance(text, basestring):
            raise DeviceError("text() must be called with a string as its first argument")
        for attr, val in zip(['x','y','width','height'], args):
            setattr(self, attr, val)

        # let _screen_transform handle alignment for single-line text
        if self.width is None:
            self.stylesheet._styles[DEFAULT]['align'] = LEFT

        # try to insulate people from the need to use a unicode constant for any text
        # with high-ascii characters (while waiting for the other shoe to drop)
        self.text = text.decode('utf-8') if isinstance(text, str) else unicode(text)

    @property
    def font(self):
        return self._typography.font._nsFont

    @property
    def _screen_position(self):
        """Returns the origin point for a Bezier containing the outlined text.

        The coordinates will reflect the current text-alignment and baseline heigh."""

        printer = self._spool
        if self.width is None:
            col_w, col_h = 0, 0
        else:
            col_w, col_h = printer.colsize

        x,y = self.x, self.y
        (dx, dy), (w, h) = printer.typeblock
        if self._typography.align == RIGHT:
            x += col_w - w
        elif self._typography.align == CENTER:
            x += (col_w-w)/2
        y -= printer.offset
        return (x,y)

    @property
    def _screen_transform(self):
        """Returns the Transform object that will be used to draw the text block.

        The transform incorporates the global context state but also accounts for
        text alignment and column-width/height constraints set in the constructor."""

        # gather the relevant text metrics
        printer = self._spool
        (dx, dy), (w, h) = printer.typeblock
        col_w, col_h = printer.colsize
        offset = printer.offset

        # adjust the positioning for alignment on single-line runs
        x, y = self.x, self.y
        if self.width is None:
            if self._typography.align == RIGHT:
                x -= w
            elif self._typography.align == CENTER:
                x -= w/2.0
        # accumulate transformations in a fresh matrix
        xf = Transform()

        # calculate the translation offset for centering (if any)
        nudge = Transform()
        if self._transformmode == CENTER:
            width = w if self.width is None else self.width
            height = h if self.height is None else self.height
            nudge.translate(width/2, height/2)

            xf.translate(x, y-offset)  # set the position before applying transforms
            xf.prepend(nudge)          # nudge the block to its center (or not)
            xf.prepend(self.transform) # add context's CTM.
            xf.prepend(nudge.inverse)  # Move back to the real origin.
        else:
            xf.prepend(self.transform) # in CORNER mode simply apply the CTM
            xf.translate(x, y-offset)  # then move to the baseline origin point
        return xf

    @property
    def path(self):
        # calculate the proper transform for alignment and flippedness
        trans = Transform()
        trans.translate(*self._screen_position)
        trans.scale(1.0,-1.0)

        # generate an unflipped bezier with all the glyphs
        path = Bezier(self._spool.nsBezierPath)
        path.inherit(self)
        return trans.apply(path)

    @property
    def _spool(self):
        if not hasattr(self, '_typesetter'):
            attrib_str = self.stylesheet._apply(self.text, self.style)
            self._typesetter = Typesetter(attrib_str, self.width, self.height)
        return self._typesetter

    def _draw(self):
        with _ns_context():                  # save and restore the gstate
            self._screen_transform.concat()  # transform so text can be drawn at the origin
            with self.effects.applied():     # apply any blend/alpha/shadow effects

                # debug: draw a grey background for the text's bounds
                # with _ns_context():
                #     NSColor.colorWithDeviceWhite_alpha_(0,.2).set()
                #     NSBezierPath.fillRect_(self._spool.typeblock)

                self._spool.draw_glyphs(0,0) # and let 'er rip

    @property
    def metrics(self):
        return self._spool.typeblock.size

class Stylesheet(object):
    kwargs = StyleMixin.opts

    def __init__(self, styles=None):
        super(Stylesheet, self).__init__()
        self._styles = dict(styles or {})

    def __repr__(self):
        styles = repr({k.replace(DEFAULT,'DEFAULT'):v for k,v in self._styles.items() if k is not DEFAULT})
        if DEFAULT in self._styles:
            styles = '{DEFAULT: %r, '%self._styles[DEFAULT] + styles[1:]
        return "Stylesheet(%s)"%(styles)

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
        new = self.__class__(self._styles)
        return new

    @property
    def styles(self):
        return dict(self._styles)

    def style(self, name, *args, **kwargs):
        if not kwargs and any(a in (None,'inherit') for a in args[:1]):
            del self[name]
        elif args or kwargs:
            spec = fontspec(*args, **kwargs)
            spec.update(typespec(**kwargs))
            color = kwargs.get('fill')
            if color and not isinstance(color, Color):
                if isinstance(color, basestring):
                    color = (color,)
                color = Color(*color)
            if color:
                spec['fill'] = color
            self._styles[name] = spec
        return self[name]

    def _apply(self, words, style):
        """Convert a string to an attributed string, either based on inline tags or the `style` arg"""

        # if the string begins and ends with a root element, treat it as xml
        # unless called w/ text(…, style=False)
        is_xml = bool(re.match(r'<([^>]*)>.*</\1>$', words, re.S))

        if style and is_xml:
            # find any tagged regions that need styling
            parser = XMLParser(words)

            # start building the display-string (with all the tags now removed)
            astr = NSMutableAttributedString.alloc().initWithString_(parser.text)

            # apply formatting (either based on the style kwarg, or by mapping tags to styles)
            if style in self._styles:
                # use specified style for entire string
                attrs = self._cascade(DEFAULT, style)
                astr.setAttributes_range_(attrs, (0,astr.length()))
            else:
                # generate the proper `ns' font attrs for each unique cascade of xml tags
                attrs = {seq:self._cascade(*seq) for seq in sorted(parser.regions)}

                # apply the attributes to the runs found by the parser
                for cascade, runs in parser.regions.items():
                    style = attrs[cascade]
                    for rng in runs:
                        astr.setAttributes_range_(style, rng)

        elif style in self._styles:
            # don't parse as xml, use specified style name
            attrs = self._cascade(DEFAULT, style)
            astr = NSMutableAttributedString.alloc().initWithString_attributes_(words, attrs)

        else:
            # don't parse as xml, just apply the current font(), align(), and fill()
            attrs = self._cascade(DEFAULT)
            astr = NSMutableAttributedString.alloc().initWithString_attributes_(words, attrs)

        return astr

    def _cascade(self, *styles):
        """Apply the listed styles in order and return nsattibutedstring attrs"""

        # use the inherited context settings as a baseline spec
        spec = dict(self._styles[DEFAULT])

        # layer the styles to generate a final font and color
        for tag in styles:
            spec.update(self._styles.get(tag,{}))

        # assign a font and color based on the coalesced spec
        font = Font.select({k:v for k,v in spec.items() if k in Stylesheet.kwargs})
        color = Color(spec.pop('fill')).nsColor
        kern = (spec['tracking'] * font.size)/1000.0

        # factor the relevant attrs into a paragraph style
        graf = NSMutableParagraphStyle.alloc().init()
        graf.setLineBreakMode_(NSLineBreakByWordWrapping)
        graf.setAlignment_(_TEXT[spec['align']])
        graf.setLineHeightMultiple_(spec['leading'])
        # graf.setLineSpacing_(extra_px_of_lead)
        # graf.setParagraphSpacing_(1em?)
        # graf.setMinimumLineHeight_(self._lineheight)

        # build the dict of features for this combination of styles
        return dict(NSFont=font._nsFont, NSColor=color, NSParagraphStyle=graf, NSKern=kern)



class Typesetter(object):

    def __init__(self, attrib_str, width, height):
        # collect nstext system objects
        store = NSTextStorage.alloc().init()
        layout = NSLayoutManager.alloc().init()
        column = NSTextContainer.alloc().init()

        # assemble nsmachinery
        layout.addTextContainer_(column)
        store.addLayoutManager_(layout)
        column.setLineFragmentPadding_(0)

        # pour in the styled text
        store.setAttributedString_(attrib_str)
        column.setContainerSize_([d or 1000000 for d in (width,height)])

        # save the nsmachinery for later
        self.store, self.layout, self.column = store, layout, column

    def draw_glyphs(self, x, y):
        self.layout.drawGlyphsForGlyphRange_atPoint_(self.visible, (x,y))

    @property
    def typeblock(self):
        return Region(*self.layout.boundingRectForGlyphRange_inTextContainer_(self.visible, self.column))

    @property
    def visible(self):
        return self.layout.glyphRangeForTextContainer_(self.column)

    @property
    def colsize(self):
        return Size(*self.column.containerSize())

    @property
    def offset(self):
        if not self.store.length():
            return 0

        txtFont, _ = self.store.attribute_atIndex_effectiveRange_("NSFont", 0, None)
        return self.layout.defaultLineHeightForFont_(txtFont)

    @property
    def nsBezierPath(self):
        (dx, dy), (w, h) = self.typeblock
        preferredWidth, preferredHeight = self.colsize

        length = self.layout.numberOfGlyphs()
        path = NSBezierPath.bezierPath()
        for glyphIndex in range(length):
            txtIndex = self.layout.characterIndexForGlyphAtIndex_(glyphIndex)
            txtFont, txtRng = self.store.attribute_atIndex_effectiveRange_("NSFont", txtIndex, None)
            lineFragmentRect, _ = self.layout.lineFragmentRectForGlyphAtIndex_effectiveRange_(glyphIndex, None)

            # convert glyph location from container coords to canvas coords
            layoutPoint = self.layout.locationForGlyphAtIndex_(glyphIndex)
            finalPoint = list(lineFragmentRect[0])
            finalPoint[0] += layoutPoint[0] - dx
            finalPoint[1] += layoutPoint[1] - dy
            g = self.layout.glyphAtIndex_(glyphIndex)

            if g == 0: continue # when does glyphAtIndex return nil in practice?
            path.moveToPoint_((finalPoint[0], -finalPoint[1]))
            path.appendBezierPathWithGlyph_inFont_(g, txtFont)
            path.closePath()
        return path



class Font(object):
    _aat = ('lig','sc','osf','tab','vpos','frac')

    def __init__(self, psname, size=None, **features):
        if isinstance(psname, Font):
            _copy_attrs(psname, self, ('_face','_size','_features'))
        else:
            self._face = font_face(psname)
            self._size = _ctx._typography.font.size if size is None else max(0.1, float(size))
            self._features = {}
            for feat, val in features.items():
                if feat not in self._aat:
                    misfeature = 'Unknown typographic feature %r. Stick with %r' % (feat,self._aat)
                    raise DeviceError(misfeature)

                val = int(val) if val is not all else val
                if val is not None:
                    self._features[feat] = val

    def __repr__(self):
        spec = [self.family, self.weight, self.face]
        if self._face.variant:
            spec.insert(2, self._face.variant)
        spec.insert(1, '/' if self._face.italic else '|')
        if self._size:
            spec.insert(1, ("%rpt"%self._size).replace('.0pt','pt'))
        return (u'Font(%s)'%" ".join(spec)).encode('utf-8')

    def __enter__(self):
        if not hasattr(self, '_rollback'):
            self._rollback = _ctx._typography
        _ctx._typography = _ctx._typography._replace(font = self)
        return self

    def __exit__(self, type, value, tb):
        _ctx._typography = self._rollback
        del self._rollback

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
    def size(self):
        return self._size

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

    ### internals ###

    @property
    def _nsFont(self):
        fd = NSFontDescriptor.fontDescriptorWithName_size_(self._face.psname, self._size)
        if self._features:
            fd = fd.fontDescriptorByAddingAttributes_(aat_attrs(self._features))
        return NSFont.fontWithDescriptor_textTransform_(fd,None)

    @property
    def _spec(self):
        spec = {axis:getattr(self._face, axis) for axis in ('family','weight','width','variant','italic')}
        spec['size'] = self._size
        spec.update(self._features)
        return spec

    @classmethod
    def select(self, *args, **kwargs):
        if args and hasattr(args[0], 'items'):
            # treat dict as output of a prior call to fontspec()
            new_spec = dict(args[0])
        else:
            # validate & standardize the kwargs first
            new_spec = fontspec(*args, **kwargs)
        if not new_spec:
            return _ctx._typography.font

        # collect the attrs from the current font and merge in changes from the new spec
        current = _ctx._typography.font
        cur_spec = current._spec
        for axis, num_axis in dict(weight='wgt', width='wid').items():  
            # convert weight & width to integer values
            cur_spec[num_axis] = getattr(current._face, num_axis)
            if axis in new_spec:
                name, val = standardized(axis, new_spec[axis])
                new_spec.update({axis:name, num_axis:val})
        
        spec = dict(cur_spec.items() + new_spec.items()) # our criteria
        faces = family_members(spec['family'])           # the candidates

        # map the requested weight/width onto what's available in the family
        w_spans = {"wgt":[1,14], "wid":[-15,15]}
        for axis, num_axis in dict(weight='wgt', width='wid').items():
            w_vals = [getattr(f, num_axis) for f in faces]
            w_min, w_max = min(w_vals), max(w_vals)
            spec[num_axis] = max(w_min, min(w_max, spec[num_axis]))
            w_spans[num_axis] = [w_min, w_max]

        # wipe out any inherited variants that don't exist in this family
        if spec.get('variant'):
            if sanitized(spec['variant']) not in [sanitized(f.variant) for f in faces]:
                spec['variant'] = None

        def score(axis, f):
            val = spec[axis]
            vs = getattr(f,axis)
            if axis in ('wgt','wid'):
                w_min, w_max = w_spans[axis]
                agree = 1 if val==vs else -abs(val-vs) / float(max(w_max-w_min, 1))
            elif axis == 'variant':
                agree = 1 if sanitized(val) == sanitized(vs) else 0
            else:
                agree = 1 if (val or None) == (vs or None) else -1
            return agree

        scores = {}
        for f in faces:
            scores[f] = sum([score(axis,f) for axis in 'italic', 'wgt', 'wid', 'variant'])

        candidates = [dict(score=s, face=f, ps=f.psname) for f,s in scores.items()]
        candidates.sort(key=itemgetter('score'), reverse=True)

        features = ({k:v for k,v in spec.items() if k in self._aat})

        return Font(candidates[0]['ps'], spec['size'], **features)

class Family(object):
    def __init__(self, famname=None, of=None):
        if of:
            famname = font_family(of)
        elif not famname:
            badarg = 'Family: requires either a name or a Font object'%famname
            raise DeviceError(badarg)

        q = famname.strip().lower().replace(' ','')
        matches = [fam for fam in family_names() if q==fam.lower().replace(' ','')]
        if not matches:
            notfound = 'Unknown font family "%s"'%famname
            raise DeviceError(notfound)
        self._name = matches[0]

        faces = family_members(self._name)
        self.encoding = font_encoding(faces[0].psname)
        self._faces = odict( (f.psname,f) for f in faces )

        fam = {"weights":[], "widths":[], "variants":[]}
        has_italic = False
        for f in sorted(faces, key=attrgetter('wgt')):
            for axis in ('weights','variants'):
                old, new = fam[axis], getattr(f,axis[:-1])
                if new not in old:
                    fam[axis].append(new)
            # has_italic = has_italic or 'italic' in f.traits
            has_italic = has_italic or f.italic
        self.has_italic = has_italic

        for f in sorted(faces, key=attrgetter('wid')):
            if f.width in fam['widths']: continue
            fam['widths'].append(f.width)

        for axis, vals in fam.items():
            if axis in ('widths','variants') and any(vals) and None in vals:
                if axis=='widths':
                    pass # for widths, the default should be preserved in sort order
                else:
                    # for variants, default should be first
                    fam[axis] = [None] + filter(None,vals)
            else:
                fam[axis] = filter(None,vals) # otherwise wipe out the sole None
            setattr(self, axis, tuple(fam[axis]))

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
        return odict( (k,Font(v)) for k,v in self._faces.items())
