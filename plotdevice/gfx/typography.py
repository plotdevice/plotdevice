# encoding: utf-8
import re
import sys
from operator import itemgetter, attrgetter
from plotdevice.util import odict, ddict
from ..lib.cocoa import *

from plotdevice import DeviceError
from .atoms import TransformMixin, ColorMixin, EffectsMixin, StyleMixin, BoundsMixin, Grob
from . import _save, _restore, _ns_context
from .transform import Transform, Region, Size, Point
from .colors import Color
from .bezier import Bezier
from ..util.foundry import *
from ..util import _copy_attrs, numlike, XMLParser, read
from ..lib import pathmatics

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
    # from StyleMixin:     stylesheet fill _parse_style()
    stateAttrs = ('_frameset',)
    opts = ('str', 'xml', 'src')

    def __init__(self, *args, **kwargs):
        # bail out quickly if we're just making a copy of an existing Text object
        if args and isinstance(args[0], Text):
            self.inherit(args[0])
            return

        # let the various mixins have a crack at the kwargs
        super(Text, self).__init__(**kwargs)

        # create a text frame to manage layout and glyph-drawing
        self._frameset = FrameSetter(self._style['align'])
        self._frameset.resize(self._bounds)

        # look for a string as the first positional arg or an xml/str kwarg
        txt = None
        fmt = 'xml' if 'xml' in kwargs else 'str'
        if args and isinstance(args[0], basestring):
            txt, args = args[0], args[1:]
        txt = kwargs.pop('xml', kwargs.pop('str', txt))

        # merge in any numlike positional args to define bounds
        for attr, val in zip(['x','y','width','height'], args):
            setattr(self, attr, val)

        # fontify the text arg and store it in the TextFrame
        self.append(**{fmt:txt, "src":kwargs.get('src')})


    def append(self, txt=None, **kwargs):
        """Add a string to the end of the text run (with optional styling)

        Usage:
          txt.append(str, **kwargs) # add the string using included styling kwargs
          txt.append(str="", **kwargs) # equivalent to first usage
          txt.append(xml="", **kwargs) # parses xml for styling before rendering
          txt.append(src="", **kwargs) # reads from the contents of a file or url

        Keyword Args:
          Accepts the same keyword arguments as the text() command. For any styling
          parameters that are omitted the appended string will inherit the style of
          the Text object it's being added to.
        """
        is_xml = 'xml' in kwargs
        txt = kwargs.pop('xml', kwargs.pop('str', txt))
        src = kwargs.pop('src', None)
        attrib_txt = None

        if src is not None:
            # fetch the url or file's contents as unicode
            txt = read(src, format='txt')

            # try building an attributed string out of the contents
            txt_bytes = txt.encode('utf-8')
            decoded, info, err = NSAttributedString.alloc().initWithData_options_documentAttributes_error_(
                NSData.dataWithBytes_length_(txt_bytes, len(txt_bytes)), None, None, None
            )

            # if the data got unpacked into anything more interesting than plain text,
            # preserve its styling. otherwise fall through and style the txt val
            if info.get('UTI') != "public.plain-text":
                attrib_txt = decoded

        if txt and not attrib_txt:
            # try to insulate people from the need to use a unicode constant for any text
            # with high-ascii characters (while waiting for the other shoe to drop)
            decoded = txt if isinstance(txt, unicode) else txt.decode('utf-8')

            # use the inherited baseline style but allow one-off overrides from kwargs
            merged_style = dict(self._style)
            merged_style.update(self._parse_style(**kwargs))
            attrib_txt = self.stylesheet._apply(decoded, merged_style, is_xml)

        if attrib_txt:
            # only bother the typesetter if there's text to display
            self._frameset.add_text(attrib_txt)
            self._frameset.resize(self._bounds)

    @property
    def text(self):
        return unicode(self._frameset)

    @property
    def font(self):
        return Font(**self._style)

    @property
    def frames(self):
        """Returns a list of one or more TextFrames defining the bounding box for layout"""
        return list(self._frameset)

    def flow(self, layout=None):
        """Add as many text frames as necessary to fully lay out the string

        When called without arguments, returns a generator that you can iterate through to
        set the position and size of each frame in turn (starting with the second). Each frame
        is initialized with the same dimensions as the previous frame in the sequence.

        The optional layout argument can be a reference to a function which takes a single
        TextFrame argument. If present, your layout function will be called once for each
        frame added to the stream.
        """
        if not layout:
            return self._frameset.reflow   # return the generator for iteration
        map(layout, self._frameset.reflow) # apply the layout function to each frame in sequence

    @property
    def metrics(self):
        """Returns the size of the actual text (typically a subset of the bounds)"""
        return self._frameset.metrics

    @property
    def bounds(self):
        """Returns the bounding box in which the text will be laid out"""
        (dx, dy), (w, h) = self._frameset.bounds
        baseline = self._frameset.baseline
        origin = Point(self.x + dx, self.y + dy - baseline)
        return Region(origin, (w,h))

    def _get_width(self):
        return self._bounds.w
    def _set_width(self, w):
        BoundsMixin._set_width(self, w)
        self._frameset.resize(self._bounds)
    w = width = property(_get_width, _set_width)

    def _get_height(self):
        return self._bounds.h
    def _set_height(self, h):
        BoundsMixin._set_height(self, h)
        self._frameset.resize(self._bounds)
    h = height = property(_get_height, _set_height)

    @property
    def _screen_transform(self):
        """Returns the Transform object that will be used to draw the text block.

        The transform incorporates the global context state but also accounts for
        the column-width/height constraints set in the constructor. If the text
        has been flowed to multiple textframes, dimensions are calculated based on
        the union of the various bounds boxes."""

        # gather the relevant text metrics
        x, y = self.x, self.y
        baseline = self._frameset.baseline

        # accumulate transformations in a fresh matrix
        xf = Transform()

        if self._transformmode == CENTER:
            # calculate the (reversible) translation offset for centering
            (dx, dy), (w, h) = self._frameset.bounds
            nudge = Transform().translate(dx+w/2.0, dy+h/2.0)

            xf.translate(x, y-baseline) # set the position before applying transforms
            xf.prepend(nudge)           # nudge the block to its center
            xf.prepend(self.transform)  # add context's CTM.
            xf.prepend(nudge.inverse)   # Move back to the real origin.
        else:
            xf.prepend(self.transform)  # in CORNER mode simply apply the CTM
            xf.translate(x, y-baseline) # then move to the baseline origin point
        return xf

    def _draw(self):
        with _ns_context():                  # save and restore the gstate
            self._screen_transform.concat()  # transform so text can be drawn at the origin
            with self.effects.applied():     # apply any blend/alpha/shadow effects
                for frame in self._frameset:
                    frame._draw()

                    # debug: draw a grey background for the text's bounds
                    # with _ns_context():
                    #     NSColor.colorWithDeviceWhite_alpha_(0,.2).set()
                    #     NSBezierPath.fillRect_(Region(frame.offset, frame.bounds.size))

    @property
    def path(self):
        # calculate the proper transform for alignment and flippedness
        trans = Transform()
        trans.translate(self.x, self.y - self._frameset.baseline)
        trans.scale(1.0,-1.0)

        # generate an unflipped bezier with all the glyphs
        path = Bezier()
        for frame in self._frameset:
            path._nsBezierPath.appendBezierPath_(frame._nsBezierPath)
        path.inherit(self)

        (dx, dy), (w, h) = self._frameset.bounds
        baseline = self._frameset.baseline
        path._fulcrum = Point(dx + self.x + w/2.0,
                              dy + self.y - baseline + h/2.0 )
        return trans.apply(path)

class FrameSetter(object):
    def __init__(self, alignment):
        self._main = TextFrame()
        self._overflow = []
        self._align = alignment

    def __getitem__(self, index):
        return ([self._main]+self._overflow)[index]

    def __delitem__(self, index):
        dropped = self.__getitem__(index)
        if not isinstance(index, slice):
            dropped = [dropped]

        for frame in dropped:
            self._overflow.remove(frame)
            frame._eject()

    def __iter__(self):
        yield self._main
        for frame in self._overflow:
            yield frame

    def __len__(self):
        return len(self._overflow) + 1

    def __unicode__(self):
        return self._main.store.string()

    def copy(self):
        clone = FrameSetter(self._align)
        clone._main.store.setAttributedString_(self._main.store)
        clone._overflow = [next(clone._main) for i in range(len(self)-len(clone))]
        for src, dst in zip(self, clone):
            dst.offset, dst.size = src.offset, src.size
        return clone

    def add_text(self, attrib_str):
        self._main.store.appendAttributedString_(attrib_str)

    def resize(self, dims):
        # start with the max w/h passed by the Text object
        frame = self._main
        frame.size = (dims.w, dims.h)
        frame.offset = (0,0)

        # if the rect isn't fully specified, size it to fit
        if not (dims.w and dims.h):
            # compute the portion that's actually filled and add some extra padding to the
            # calculated width (b/c believe it or not usedRectForTextContainer is buggy...)
            min_w, min_h = frame.metrics
            min_w += 1

            # shift the offset if not left-aligned and drawing to a point
            nudge = {RIGHT:min_w, CENTER:min_w/2.0}
            if self._align in nudge and dims.w is None:
                frame.x -= nudge[self._align]

            # shrink-to-fit any dims that were previously undefined
            if not dims.w:
                frame.width = min_w
            if not dims.h:
                frame.height = min_h

    @property
    def reflow(self):
        # wipe out any previously set frames then keep adding new ones until
        # the glyphs are fully laid out
        while self._overflow:
            self._overflow.pop()._eject()
        frame = self._main
        while sum(frame._glyphs) < frame.layout.numberOfGlyphs():
            frame = next(frame)
            self._overflow.append(frame)
            yield frame

    @property
    def metrics(self):
        # compute the used portion of the full bounding box
        bbox = Region()
        for frame in self:
            bbox = bbox.union(frame.offset, frame.metrics)
        return bbox.size

    @property
    def bounds(self):
        # compute the size of the full layout region
        bbox = Region()
        for frame in self:
            bbox = bbox.union(frame.offset, frame.size)
        return bbox

    @property
    def baseline(self):
        main = self._main
        if not main.store.length():
            return 0
        txtFont, _ = main.store.attribute_atIndex_effectiveRange_("NSFont", main._glyphs.location, None)
        return main.layout.defaultLineHeightForFont_(txtFont)


class TextFrame(object):
    def __init__(self):
        # assemble nsmachinery (or just inherit it)
        self.store = NSTextStorage.alloc().init()
        self.layout = NSLayoutManager.alloc().init()
        self.store.addLayoutManager_(self.layout)

        # create a new container and add it to the layout manager
        self.block = NSTextContainer.alloc().init()
        self.block.setLineFragmentPadding_(0)
        self.layout.addTextContainer_(self.block)
        self.offset = (0,0)

    def __repr__(self):
        return "TextFrame(offset=%r, size=%r)"%(tuple(self.offset), tuple(self.size))

    @property
    def idx(self):
        """An integer marking this frame's place in the flow sequence"""
        return self.layout.textContainers().index(self.block)

    @property
    def text(self):
        """The portion of the parent Text object's string that is visible in this frame"""
        rng, _ = self.layout.characterRangeForGlyphRange_actualGlyphRange_(self._glyphs, None)
        return self.store.string().substringWithRange_(rng)

    @property
    def metrics(self):
        """The size of the rendered text"""
        self.layout.glyphRangeForTextContainer_(self.block) # force layout & glyph gen
        return Region(*self.layout.usedRectForTextContainer_(self.block)).size

    def next(self):
        frame = TextFrame()
        for attr in 'store', 'layout', 'offset', 'size':
            setattr(frame, attr, getattr(self, attr))
        self.layout.addTextContainer_(frame.block)
        return frame

    def _eject(self):
        idx = self.layout.textContainers().index(self.block)
        self.layout.removeTextContainerAtIndex_(idx)

    def _get_x(self):
        return self.offset.x
    def _set_x(self, x):
        self.offset = (x, self.y)
    x = property(_get_x, _set_x)

    def _get_y(self):
        return self.offset.y
    def _set_y(self, y):
        self.offset = (self.x, y)
    y = property(_get_y, _set_y)

    def _get_offset(self):
        return Point(self._offset)
    def _set_offset(self, dims):
        if numlike(dims):
            dims = [dims]*2
        self._offset = Point(*dims)
    offset = property(_get_offset, _set_offset)

    def _get_size(self):
        return Size(*self.block.containerSize())
    def _set_size(self, dims):
        new_size = [d or 10000000 for d in dims]
        if new_size != self.size:
            self.block.setContainerSize_(new_size)
    size = property(_get_size, _set_size)

    def _get_width(self):
        return self.size.width
    def _set_width(self, width):
        self.size = (width, self.height)
    w = width = property(_get_width, _set_width)

    def _get_height(self):
        return self.size.height
    def _set_height(self, height):
        self.size = (self.width, height)
    h = height = property(_get_height, _set_height)

    @property
    def _glyphs(self):
        return self.layout.glyphRangeForTextContainer_(self.block)

    def _draw(self):
        self.layout.drawGlyphsForGlyphRange_atPoint_(self._glyphs, self.offset)

    @property
    def _nsBezierPath(self):
        return pathmatics.trace_text(frame=self)

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
        new = self.__class__(self._styles)
        return new

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

    def _apply(self, words, defaults, is_xml=False):
        """Convert a string to an attributed string, either based on inline tags or the `style` arg"""

        if is_xml:
            # find any tagged regions that need styling
            parser = XMLParser(words)

            # start building the display-string (with all the tags now removed)
            astr = NSMutableAttributedString.alloc().initWithString_(parser.text)

            # generate the proper `ns' font attrs for each unique cascade of xml tags
            attrs = {seq:self._cascade(defaults, *seq) for seq in sorted(parser.regions)}

            # apply the attributes to the runs found by the parser
            for cascade, runs in parser.regions.items():
                style = attrs[cascade]
                for rng in runs:
                    astr.setAttributes_range_(style, rng)
        else:
            # don't parse as xml, just apply the current font(), align(), and fill()
            attrs = self._cascade(defaults)
            astr = NSMutableAttributedString.alloc().initWithString_attributes_(words, attrs)

        return astr

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
        graf.setLineHeightMultiple_(spec['leading'])
        graf.setHyphenationFactor_(spec['hyphenate'])
        # graf.setLineSpacing_(extra_px_of_lead)
        # graf.setParagraphSpacing_(1em?)
        # graf.setMinimumLineHeight_(self._lineheight)

        if not spec['tracking']:
            # None means `kerning off entirely', 0 means `default letterspacing'
            kern = 0 if spec['tracking'] is None else sys.float_info.epsilon
        else:
            # convert the em-based tracking val to a point-based kerning val
            kern = (spec['tracking'] * font.size)/1000.0

        # build the dict of features for this combination of styles
        return dict(NSFont=font._nsFont, NSColor=color, NSParagraphStyle=graf, NSKern=kern)


class Font(object):
    def __init__(self, *args, **kwargs):

        # handle the bootstrap case where we're initializing the ctx's font
        if args==(None,):
            self._face = font_face("HelveticaNeue")
            self._size = 24.0
            self._features = {}
            return

        # check for invalid kwarg names
        rest = [k for k in kwargs if k not in StyleMixin.opts]
        if rest:
            unknown = 'Invalid keyword argument%s: %s'%('' if len(rest)==1 else 's', ", ".join(rest))
            raise DeviceError(unknown)

        # accept Font objects or spec dicts as first positional arg
        first = args[0] if args else None
        if isinstance(first, Font):
            # make a copy of the existing font obj
            _copy_attrs(first, self, ('_face','_size','_features'))
            return
        elif hasattr(first, 'items'):
            # treat dict as output of a prior call to fontspec()
            new_spec = dict(first)
        else:
            # validate & standardize the kwargs first
            new_spec = fontspec(*args, **kwargs)

        # collect the attrs from the current font to fill in any gaps
        current = _ctx._typography.font
        cur_spec = current._spec
        for axis, num_axis in dict(weight='wgt', width='wid').items():
            # convert weight & width to integer values
            cur_spec[num_axis] = getattr(current._face, num_axis)
            if axis in new_spec:
                name, val = standardized(axis, new_spec[axis])
                new_spec.update({axis:name, num_axis:val})

        # merge in changes from the new spec
        spec = dict(cur_spec.items() + new_spec.items()) # our criteria

        self._face = best_face(spec)
        self._size = spec['size']
        self._features = aat_features(spec)

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
