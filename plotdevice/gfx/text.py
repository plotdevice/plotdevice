# encoding: utf-8
import re
import sys
from collections import namedtuple
from ..lib.cocoa import *

from plotdevice import DeviceError
from .typography import *
from .geometry import Transform, Region, Size, Point
from .colors import Color
from .bezier import Bezier
from .atoms import TransformMixin, ColorMixin, EffectsMixin, StyleMixin, BoundsMixin, Grob
from ..util import _copy_attrs, trim_zeroes, numlike, ordered, XMLParser, read
from ..lib import foundry
from . import _ns_context

_ctx = None
__all__ = ("Text",)

class Text(EffectsMixin, TransformMixin, BoundsMixin, StyleMixin, Grob):
    # from TransformMixin: transform transformmode translate() rotate() scale() skew() reset()
    # from EffectsMixin:   alpha blend shadow
    # from BoundsMixin:    x y width height
    # from StyleMixin:     stylesheet fill _parse_style()
    stateAttrs = ('_nodes', )
    opts = ('str', 'xml', 'src')

    def __init__(self, *args, **kwargs):

        # assemble the NSMachinery
        self._layout = NSLayoutManager.alloc().init()
        self._layout.setUsesScreenFonts_(False)
        self._store = NSTextStorage.alloc().init()
        self._store.addLayoutManager_(self._layout)

        if args and isinstance(args[0], Text):
            # create a parallel set of nstext objects when copying an existing Text
            # then bail out immediately (ignoring any other args)
            orig = args[0]
            self.inherit(orig)
            self._frames = [TextFrame(self) for f in orig._frames]
            for src, dst in zip(orig._frames, self._frames):
                dst.offset, dst.size = src.offset, src.size
            self._store.appendAttributedString_(orig._store)
            return

        # let the various mixins have a crack at the kwargs
        super(Text, self).__init__(**kwargs)

        # create a text frame to manage layout and glyph-drawing
        self._frames = [TextFrame(self)]

        # maintain a lookup table of nodes within xml input
        self._nodes = {}

        # look for a string as the first positional arg or an xml/str kwarg
        if args and isinstance(args[0], basestring):
            kwargs['str'], args = args[0], args[1:]

        # merge in any numlike positional args to define bounds
        if args:
            self._bounds._parse(args)

        # fontify the str/xml/src arg and store it in the TextFrame
        self.append(**{k:v for k,v in kwargs.items() if k in self.opts})

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
        StyleMixin.validate(kwargs)
        attrib_txt = None

        if src is not None:
            # fetch the url or file's contents as unicode
            txt = read(src, format='txt')
            is_xml = src.lower().endswith('.xml')

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
            # convert non-textual `str` args to strings
            if not isinstance(txt, basestring) and not is_xml:
                txt = repr(txt)

            # try to insulate people from the need to use a unicode constant for any text
            # with high-ascii characters (while waiting for the other shoe to drop)
            decoded = txt if isinstance(txt, unicode) else txt.decode('utf-8')

            # use the inherited baseline style but allow one-off overrides from kwargs
            merged_style = self._style
            merged_style.update(self._parse_style(kwargs))

            # if the text is xml, parse it an overlay any stylesheet entries that map to
            # its tag names. otherwise apply the merged style to the entire string
            _cascade = self.stylesheet._cascade
            if is_xml:
                # find any tagged regions that need styling
                parser = XMLParser(decoded, offset=len(self.text))

                # update our internal lookup table of nodes
                for tag, elts in parser.nodes.items():
                    old_elts = self._nodes.get(tag, [])
                    self._nodes[tag] = old_elts + elts

                # start building the display-string (with all the tags now removed)
                attrib_txt = NSMutableAttributedString.alloc().initWithString_(parser.text)

                # generate the proper `ns' font attrs for each unique cascade of xml tags
                attrs = {seq:_cascade(merged_style, *seq) for seq in sorted(parser.regions)}

                # apply the attributes to the runs found by the parser
                for cascade, runs in parser.regions.items():
                    style = attrs[cascade]
                    for rng in runs:
                        attrib_txt.setAttributes_range_(style, rng)

            else:
                # don't parse as xml, just apply the current font(), align(), and fill()
                attrs = _cascade(merged_style)
                attrib_txt = NSAttributedString.alloc().initWithString_attributes_(decoded, attrs)

        if attrib_txt:
            # only bother the typesetter if there's text to display
            self._store.appendAttributedString_(attrib_txt)
            self._autosize()

    def overleaf(self):
        """Returns a Text object containing any characters that did not fit within this object's bounds.
        If the entire string fits within the current object, returns None."""
        seen = u"".join(getattr(f, 'text') for f in self._frames)
        full = self.text
        if full not in seen:
            next_pg = self.copy()
            next_pg._store.deleteCharactersInRange_([0, len(seen)])
            return next_pg

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
            return self._reflow   # return the generator for iteration
        map(layout, self._reflow) # apply the layout function to each frame in sequence

    @property
    def _reflow(self):
        # wipe out any previously set frames then keep adding new ones until
        # the glyphs are fully laid out
        while self._frames[1:]:
            self._frames.pop()._eject()
        frame = self._frames[0]
        while sum(frame._glyphs) < self._layout.numberOfGlyphs():
            frame = TextFrame(frame)
            self._frames.append(frame)
            yield frame

    @property
    def metrics(self):
        """Returns the size of the actual text (typically a subset of the bounds)"""
        bbox = Region()
        for frame in self._frames:
            bbox = bbox.union(frame.offset, frame.metrics)
        return bbox.size

    @property
    def bounds(self):
        """Returns the bounding box in which the text will be laid out"""
        bbox = Region()
        for frame in self._frames:
            bbox = bbox.union(frame.offset, frame.size)
        bbox.origin += Point(self.x, self.y-self.baseline)
        return bbox

    @property
    def baseline(self):
        if not self._store.length():
            return 0
        return self._frames[0]._from_px(self._layout.locationForGlyphAtIndex_(0).y)

    def _get_x(self):
        return self._bounds.x
    def _set_x(self, x):
        self._bounds.x = x
    x = property(_get_x, _set_x)

    def _get_y(self):
        return self._bounds.y
    def _set_y(self, y):
        self._bounds.y = y
    y = property(_get_y, _set_y)

    def _get_width(self):
        return self._bounds.w
    def _set_width(self, w):
        self._bounds.width = w
        self._autosize()
    w = width = property(_get_width, _set_width)

    def _get_height(self):
        return self._bounds.h
    def _set_height(self, h):
        self._bounds.height = h
        self._autosize()
    h = height = property(_get_height, _set_height)

    def _autosize(self):
        # start with the max w/h passed by the Text object
        dims = self._bounds.size
        frame = self._frames[0]

        # start at the maximal size before shrinking-to-fit
        frame.offset = (0,0)
        frame.size = (dims.w, dims.h)

        # if the rect isn't fully specified, size it to fit
        if not (dims.w and dims.h):
            # compute the portion that's actually filled and add 1px of extra padding to the
            # calculated width (b/c believe it or not usedRectForTextContainer is buggy...)
            min_w, min_h = frame.metrics
            min_w += frame._from_px(1)

            # shift the offset if not left-aligned and drawing to a point
            nudge = {RIGHT:min_w, CENTER:min_w/2.0}.get(frame.alignment)
            if nudge and dims.w is None:
                frame.x -= nudge

            # shrink-to-fit any dims that were previously undefined
            if not dims.w:
                frame.width = min_w
            if not dims.h:
                frame.height = min_h

    @property
    def _screen_transform(self):
        """Returns the Transform object that will be used to draw the text block.

        The transform incorporates the global context state but also accounts for
        the column-width/height constraints set in the constructor. If the text
        has been flowed to multiple textframes, dimensions are calculated based on
        the union of the various bounds boxes."""

        # gather the relevant text metrics (and convert them from canvas- to pixel-units)
        x, y = self._to_px(Point(self.x, self.y))
        baseline = self._to_px(self.baseline)

        # accumulate transformations in a fresh matrix
        xf = Transform()

        if self._transformmode == CENTER:
            # calculate the (reversible) translation offset for centering (in px)
            (dx, dy), (w, h) = self._to_px(self.bounds)
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
                for frame in self._frames:
                    frame._draw()

                    # debug: draw a grey background for the text's bounds
                    # with _ns_context():
                    #     NSColor.colorWithDeviceWhite_alpha_(0,.2).set()
                    #     NSBezierPath.fillRect_(Region(frame.offset, frame.bounds.size))

    @property
    def path(self):
        # calculate the proper transform for alignment and flippedness
        trans = Transform()
        trans.translate(self.x, self.y - self.baseline)
        trans.scale(1.0,-1.0)

        # generate an unflipped bezier with all the glyphs
        path = Bezier()
        for frame in self._frames:
            path._nsBezierPath.appendBezierPath_(frame._nsBezierPath)
        path.inherit(self)

        (dx, dy), (w, h) = self.bounds
        baseline = self.baseline
        path._fulcrum = Point(dx + self.x + w/2.0,
                              dy + self.y - baseline + h/2.0 )

        # flip the assembled path and slide it into the proper x/y position
        return trans.apply(path)


    def __getitem__(self, index):
        match = TextMatch(self)
        match.text = self.text[index]
        if isinstance(index, slice):
            match.start, match.end, _ = index.indices(len(self))
        else:
            if index < 0:
                index += len(self)
            if not 0 <= index < len(self):
                raise IndexError
            match.start, match.end = index, index+1
        return match

    def __len__(self):
        return len(self.text)

    def _seek(self, stream, limit):
        found = []
        for m in stream:
            match = TextMatch(self, m)
            if not match.layout and limit is not all:
                break
            found.append(match)
            if len(found) == limit:
                break
        return found

    def find(self, regex, matches=0):
        if isinstance(regex, str):
            regex = regex.decode('utf-8')
        if isinstance(regex, basestring):
            regex = re.compile(regex, re.S)
        if not hasattr(regex, 'pattern'):
            nonregex = "Text.find() must be called with an re.compile'd pattern object or a regular expression string"
            raise DeviceError(nonregex)
        return self._seek(regex.finditer(self.text), matches)

    def select(self, tag_name, matches=0):
        if isinstance(tag_name, str):
            tag_name = tag_name.decode('utf-8')
        return self._seek(self._nodes.get(tag_name, []), matches)

    @property
    def text(self):
        return unicode(self._store.string())

    @property
    def words(self):
        return [TextMatch(self, w) for w in self._store.words()]

    @property
    def paragraphs(self):
        return [TextMatch(self, w) for w in self._store.paragraphs()]

    @property
    def frames(self):
        """Returns a list of one or more TextFrames defining the bounding box for layout"""
        return list(self._frames)

    @property
    def lines(self):
        return foundry.line_fragments(self)


class TextMatch(object):
    """Represents a substring region within a Text object (via its `find` or `select` method)

    Properties:
      `start` and `end` - the character range of the match
      `text` - the matched substring
      `layout` - a list of one or more LineFragments describing glyph geometry

    Additional properties when .find'ing a regular expression:
      `m` - a regular expression Match object

    Additional properties when .select'ing an xml element:
      `tag` - a string with the matched element's name
      `attrs` - a dictionary with the element's attributes (if any)
      `parents` - a tuple with the parent, grandparent, etc. tag names
    """
    def __init__(self, parent, match=None):
        self._parent = parent
        self.tag, self.attrs, self.parents = None, {}, ()
        self.m = None

        if hasattr(match, 'range'): # NSSubText
            self.start, n = match.range()
            self.end = self.start + n
            self.text = match.string()
        elif hasattr(match, 'span'): # re.Match
            self.start, self.end = match.span()
            self.text = match.group()
            self.m = match
        elif hasattr(match, '_asdict'): # xml Element
            for k,v in match._asdict().items():
                setattr(self, k, v)

    def __len__(self):
        return self.end-self.start

    def __repr__(self):
        msg = []
        try:
            pat = self.m.re.pattern
            if len(pat)>18:
                pat = "%s..." % (pat[:15])
            msg.append("r'%s'" % pat)
        except:
            if self.tag:
                msg.append("<%s>" % self.tag)
            if self.attrs:
                msg.append("attrs=%i" % len(self.attrs))
        msg.append("start=%i" % self.start)
        msg.append("len=%i" % (self.end-self.start))
        return 'TextMatch(%s)' % (", ".join(msg))

    @property
    def layout(self):
        if not hasattr(self, '_layout'):
            rng = (self.start, self.end-self.start)
            self._layout = foundry.line_fragments(self._parent, rng)
        return self._layout

class TextFrame(object):
    def __init__(self, parent):
        # stash the canvas unit for offset/size calculations
        self._dpx = _ctx.canvas.unit.basis

        # create a new container
        self.block = NSTextContainer.alloc().init()
        self.block.setLineFragmentPadding_(0)

        if isinstance(parent, TextFrame):
            # either piggyback on an existing frame...
            self._parent = parent._parent
            self.offset, self.size = parent.offset, parent.size
        else:
            # ... or a parent Text object
            self._parent = parent
            self.offset = Point(parent.x, parent.y)

        # add ourselves to the layout flow
        self._parent._layout.addTextContainer_(self.block)

    @trim_zeroes
    def __repr__(self):
        return "TextFrame(%r, %r)"%(tuple(self.offset), tuple(self.size))

    @property
    def idx(self):
        """An integer marking this frame's place in the flow sequence"""
        return self._parent._layout.textContainers().index(self.block)

    @property
    def text(self):
        """The portion of the parent Text object's string that is visible in this frame"""
        rng, _ = self._parent._layout.characterRangeForGlyphRange_actualGlyphRange_(self._glyphs, None)
        return self._parent._store.string().substringWithRange_(rng)

    @property
    def metrics(self):
        """The size of the rendered text"""
        self._parent._layout.glyphRangeForTextContainer_(self.block) # force layout & glyph gen
        _, block_size = self._parent._layout.usedRectForTextContainer_(self.block)
        return self._from_px(block_size)

    @property
    def lines(self):
        rng, _ = self._parent._layout.characterRangeForGlyphRange_actualGlyphRange_(self._glyphs, None)
        return foundry.line_fragments(self._parent, rng)

    def _eject(self):
        idx = self._parent._layout.textContainers().index(self.block)
        self._parent._layout.removeTextContainerAtIndex_(idx)

    def _to_px(self, unit):
        """Convert from canvas units to postscript points"""
        if numlike(unit):
            return unit * self._dpx
        return Transform().scale(self._dpx).apply(unit)

    def _from_px(self, px):
        """Convert from postscript points to canvas units"""
        if numlike(px):
            return px / self._dpx
        return Transform().scale(1.0/self._dpx).apply(px)

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
        return self._from_px(self.block.containerSize())
    def _set_size(self, dims):
        new_size = [d or self._from_px(10000000) for d in dims]
        if new_size != self.size:
            self.block.setContainerSize_([self._to_px(d) for d in new_size])
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
    def alignment(self):
        from .typography import _TEXT
        if not self._parent._store.string():
            return LEFT
        graf, _ = self._parent._store.attribute_atIndex_effectiveRange_("NSParagraphStyle", 0, None)
        return {_TEXT[a]:a for a in _TEXT}[graf.alignment()]

    @property
    def _glyphs(self):
        return self._parent._layout.glyphRangeForTextContainer_(self.block)

    def _draw(self):
        px_offset = self._to_px(self.offset)
        self._parent._layout.drawGlyphsForGlyphRange_atPoint_(self._glyphs, px_offset)

    @property
    def _nsBezierPath(self):
        return foundry.trace_text(frame=self)

