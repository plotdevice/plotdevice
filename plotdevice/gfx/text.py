# encoding: utf-8
import re
import sys
from collections import namedtuple
from ..lib.cocoa import *

from plotdevice import DeviceError
from .typography import *
from .geometry import Transform, Region, Size, Point, Pair
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
        self._layout.setUsesFontLeading_(False)
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
            self._resized()


    ### flowing text into new Text objects or subsidiary TextFrames ###

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

    ### Layout geometry ###

    @property
    def bounds(self):
        """Returns the bounding box in which the text will be laid out"""
        bbox = Region()
        for frame in self._frames:
            bbox = bbox.union(frame.bounds)
        return bbox

    @property
    def layout(self):
        """Returns the size & position of the actual text (typically a subset of the bounds)"""
        lbox = Region()
        for frame in self._frames:
            lbox = lbox.union(frame.layout)
        return lbox

    @property
    def metrics(self):
        """Returns the size of the actual text (shorthand for Text.layout.size)"""
        return self.layout.size

    def _get_baseline(self):
        """Returns the Text object's baseline `origin point'"""
        return Point(self.x, self.y)
    def _set_baseline(self, baseline):
        self.x, self.y = baseline
    baseline = property(_get_baseline, _set_baseline)


    ### Searching for substrings (and their layout geometry) ###

    def __getitem__(self, index):
        """Subscripting a Text using indices into its .text string returns a TextMatch"""
        match = TextMatch(self)
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

    def find(self, regex, matches=0):
        """Find all matching portions of the text string using regular expressions

        Syntax:
          txt.find(re.compile(r'...', re.I)) # match a regex object
          txt.find(r'antidisest.*?ism') # match a pattern string
          txt.find(r'foo (.*?) baz') # match the parenthesized group
          txt.find(r'the', 10) # find the first 10 occurrences of `the'

        Args:
          `regex` can be a pattern string or a regex object. Pattern strings without
          any uppercase characters will be case-insensitively matched. Patterns with
          mixed case will be case-sensitive. In addition, the re.DOTALL flag will be
          passed by default (meaning r'.' will match any character, including newlines).
          Compiled regexes can define their own flags.

          `matches` optionally set the maximum number of results to be returned. If
          omitted, find() will return a TextMatch object for every match that's
          visible in one of the Text object's TextFrames. Matches that lie in the
          overflow beyond the Text's bounds can be included however: pass the `all`
          keyword as the `matches` arg.

        Returns:
          a list of TextMatch objects
        """
        if isinstance(regex, str):
            regex = regex.decode('utf-8')
        if isinstance(regex, unicode):
            flags = (re.I|re.S) if regex.lower()==regex else (re.S)
            regex = re.compile(regex, flags)
        if not hasattr(regex, 'pattern'):
            nonregex = "Text.find() must be called with an re.compile'd pattern object or a regular expression string"
            raise DeviceError(nonregex)
        return self._seek(regex.finditer(self.text), matches)

    def select(self, tag_name, matches=0):
        """Find all matching portions of the text string using regular expressions

        Syntax:
          txt.select('em')) # find all visible `em' tag regions
          txt.select('p', all) # find every `p' tag, even in the overflow

        Args:
          `tag_name` is a string that corresponds to one of the element names you
          used when calling text() or txt.append() with an `xml` argument. Note that
          any tag-attributes you defined in the xml will be available through the
          resulting TextMatch object's `attrs` property.

          `matches` optionally set the maximum number of results to be returned. If
          omitted, select() will return a TextMatch object for every match that's
          visible in one of the Text object's TextFrames. Matches that lie in the
          overflow beyond the Text's bounds can be included however: pass the `all`
          keyword as the `matches` arg.

        Returns:
          a list of TextMatch objects
        """
        if isinstance(tag_name, str):
            tag_name = tag_name.decode('utf-8')
        return self._seek(self._nodes.get(tag_name, []), matches)

    def _seek(self, stream, limit):
        found = []
        for m in stream:
            match = TextMatch(self, m)
            if not match.frames and limit is not all:
                break
            found.append(match)
            if len(found) == limit:
                break
        return found

    @property
    def text(self):
        """Returns the unicode string being typeset"""
        return unicode(self._store.string())

    @property
    def words(self):
        """Returns a TextMatch for each word in the text string (whitespace separated)"""
        return [TextMatch(self, w) for w in self._store.words()]

    @property
    def paragraphs(self):
        """Returns a TextMatch for each `line' in the text string (newline separated)"""
        return [TextMatch(self, w) for w in self._store.paragraphs()]

    @property
    def frames(self):
        """Returns a list of one or more TextFrames defining the bounding box for layout"""
        return list(self._frames)

    @property
    def lines(self):
        """Returns a list of LineFragments, one for each line in all of the TextFrames"""
        return foundry.line_fragments(self)

    ### Calculating dimensions & rendering ###

    def _resized(self):
        """Ensure that the first TextFrame's bounds are kept in sync with the Text's.
        Called by the BoundsMixin when the width or size is reassigned."""

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
            nudge = {RIGHT:min_w, CENTER:min_w/2.0}.get(frame._alignment)
            if nudge and dims.w is None:
                frame.x -= nudge

            # shrink-to-fit any dims that were previously undefined
            if not dims.w:
                frame.width = min_w
            if not dims.h:
                frame.height = min_h

    @property
    def _headroom(self):
        """Returns the distance between the Text's origin and the top of its bounds box"""
        if not self._store.length():
            return 0
        return self._frames[0]._from_px(self._layout.locationForGlyphAtIndex_(0).y)

    @property
    def _flipped_transform(self):
        """Returns a Transform object that positions unflipped beziers returned by trace_text"""
        xf = Transform()
        xf.translate(self.x, self.y - self._headroom)
        xf.scale(1.0,-1.0)
        return xf

    @property
    def _screen_transform(self):
        """Returns the Transform object that will be used to draw the text block.

        The transform incorporates the global context state but also accounts for
        the column-width/height constraints set in the constructor. If the text
        has been flowed to multiple textframes, dimensions are calculated based on
        the union of the various bounds boxes."""

        # gather the relevant text metrics (and convert them from canvas- to pixel-units)
        x, y = self._to_px(Point(self.x, self.y))
        baseline = self._to_px(self._headroom)

        # accumulate transformations in a fresh matrix
        xf = Transform()

        if self._transformmode == CENTER:
            # calculate the (reversible) translation offset for centering (in px)
            bounds = self._to_px(self.bounds)
            shift = bounds.origin + bounds.size/2.0 - (x, y-baseline)
            nudge = Transform().translate(*shift)

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
                    px_offset = self._to_px(frame.offset)
                    self._layout.drawGlyphsForGlyphRange_atPoint_(frame._glyphs, px_offset)

                    # debug: draw a grey background for the text's bounds
                    # NSColor.colorWithDeviceWhite_alpha_(0,.2).set()
                    # NSBezierPath.fillRect_(Region(frame.offset, frame.size))

    @property
    def path(self):
        """Traces the laid-out glyphs and returns them as a single Bezier object"""

        # generate an unflipped bezier with all the glyphs
        path = Bezier(foundry.trace_text(self))
        path.inherit(self)

        # set its center-rotation fulcrum based on the frames' bounds rect
        origin, size = self.bounds
        path._fulcrum = origin + size/2.0

        # flip the assembled path and slide it into the proper x/y position
        return self._flipped_transform.apply(path)


class TextMatch(object):
    """Represents a substring region within a Text object (via its `find` or `select` method)

    Properties:
      `start` and `end` - the character range of the match
      `text` - the matched substring
      `lines` - a list of one or more LineFragments describing glyph geometry
      `path` - a Bezier object with the glyphs from the matched range

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
        elif hasattr(match, 'span'): # re.Match
            self.start, self.end = match.regs[1] if match.re.groups>0 else match.span()
            self.m = match
        elif hasattr(match, '_asdict'): # xml Element
            for k,v in match._asdict().items():
                setattr(self, k, v)
        elif hasattr(match, '_chars'): # TextFrame
            self.start, n = match._chars
            self.end = self.start + n

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
    def text(self):
        return self._parent.text[self.start:self.end]

    @property
    def lines(self):
        """A list of one or more LineFragments describing text layout within the match"""
        if not hasattr(self, '_lines'):
            rng = (self.start, self.end-self.start)
            self._lines = foundry.line_fragments(self._parent, rng)
        return self._lines

    @property
    def frames(self):
        """The list of TextFrame objects that the match spans"""
        rng = (self.start, self.end-self.start)
        return foundry.text_frames(self._parent, rng)

    @property
    def bounds(self):
        """Returns the bounding box for the lines containing the match"""
        bbox = Region()
        for slug in self.lines:
            bbox = bbox.union(slug.bounds)
        return bbox

    @property
    def layout(self):
        """Returns the bounding box of the matched characters"""
        bbox = Region()
        for slug in self.lines:
            bbox = bbox.union(slug.layout)
        return bbox

    @property
    def path(self):
        """Traces the laid-out glyphs and returns them as a single Bezier object"""

        # generate an unflipped bezier with all the glyphs
        path = Bezier(foundry.trace_text(self._parent, (self.start, len(self))))
        path.inherit(self._parent)

        # set its center-rotation fulcrum based on the frames' bounds rect
        origin, size = self._parent.bounds
        path._fulcrum = origin + size/2.0

        # flip the assembled path and slide it into the proper x/y position
        return self._parent._flipped_transform.apply(path)

class TextFrame(BoundsMixin, Grob):
    """Defines a layout region for a Text object's typesetter.

    Most Text objects have a single TextFrame which holds the width
    and height of the layout region. You don't need to deal with it
    directly since you can just set the x/y/w/h attributes on the Text
    object itself.

    You can create a multi-column layout by iterating over a Text
    object's .flow() method and manipulating the TextFrames it returns.
    You can also inspect the existing TextFrames without adding new ones
    through the Text object's `frames` property.

    Read/Write Properties:
        `offset` - a Point with the frame's position relative to the parent Text's.
        `size` - a Size with the maximum width & height of the layout region
        `x`,`y`,`w`,`h` - shorthand accessors for offset & size components

    Readable Properties:
        `text` - the substring that is visible in the frame
        `idx` - a counter marking the frame's place in the sequence
        `metrics` - the size of the used portion of the frame's w & h
        `lines` - a list of LineFragments contained in the frame
        `path` - a Bezier object with all the visible glyphs in the frame
    """
    def __init__(self, parent):
        # inherit the canvas-unit methods and a _bounds
        self._bounds = Region((0,0), (None,None))
        self.inherit()

        # create a new container
        self._block = NSTextContainer.alloc().init()
        self._block.setLineFragmentPadding_(0)

        if isinstance(parent, TextFrame):
            # either piggyback on an existing frame...
            self._parent = parent._parent
            self.offset, self.size = parent.offset, parent.size
        else:
            # ... or become the first frame of a parent Text object
            self._parent = parent

        # add ourselves to the layout flow
        self._parent._layout.addTextContainer_(self._block)

    @trim_zeroes
    def __repr__(self):
        return "TextFrame(%r, %r)"%(tuple(self.offset), tuple(self.size))

    @property
    def idx(self):
        """An integer marking this frame's place in the flow sequence"""
        return self._parent._layout.textContainers().index(self._block)

    @property
    def text(self):
        """The portion of the parent Text object's string that is visible in this frame"""
        return self._parent._store.string().substringWithRange_(self._chars)

    @property
    def bounds(self):
        """The position & size of the frame in canvas coordinates"""
        bbox = Region(self.offset, self.size)
        bbox.origin += self._parent.baseline - (0, self._from_px(self._headroom))
        return bbox

    @property
    def layout(self):
        """The position & size of the frame's text in canvas coordinates"""
        self._parent._layout.glyphRangeForTextContainer_(self._block) # force layout & glyph gen
        origin, size = self._parent._layout.usedRectForTextContainer_(self._block)
        origin.y -= self._headroom # adjust for the ascent above baseline
        origin += self.offset + self._parent.baseline
        return self._from_px(Region(origin, size))

    @property
    def metrics(self):
        """The size of the rendered text"""
        return self.layout.size

    @property
    def lines(self):
        """A list of LineFragments describing the layout within the frame"""
        return foundry.line_fragments(self._parent, self._chars)

    @property
    def path(self):
        """Traces the laid-out glyphs and returns them as a single Bezier object"""
        return TextMatch(self._parent, self).path

    @property
    def _headroom(self):
        fnt, _ = self._parent._store.attribute_atIndex_effectiveRange_("NSFont", self._chars.location, None);
        return fnt.ascender()

    def _eject(self):
        idx = self._parent._layout.textContainers().index(self._block)
        self._parent._layout.removeTextContainerAtIndex_(idx)
        self._parent = None

    def _resized(self):
        # called by the BoundsMixin when the w or h changed
        dims = [d or self._from_px(10000000) for d in self._bounds.size]
        self._block.setContainerSize_(self._to_px(Size(*dims)))

    def _get_offset(self):
        return Point(self._bounds.origin)
    def _set_offset(self, dims):
        if numlike(dims):
            dims = [dims]*2
        self._bounds.origin = dims
    offset = property(_get_offset, _set_offset)

    def _get_size(self):
        return self._from_px(self._block.containerSize())
    def _set_size(self, dims):
        if dims != self._bounds.size:
            self._bounds.size = dims
            self._resized()
    size = property(_get_size, _set_size)

    @property
    def _alignment(self):
        from .typography import _TEXT
        if not self._parent._store.string():
            return LEFT
        graf, _ = self._parent._store.attribute_atIndex_effectiveRange_("NSParagraphStyle", 0, None)
        return {_TEXT[a]:a for a in _TEXT}[graf.alignment()]

    @property
    def _glyphs(self):
        # NSRange of glyphs in the frame
        return self._parent._layout.glyphRangeForTextContainer_(self._block)

    @property
    def _chars(self):
        # NSRange of chars in the frame
        rng, _ = self._parent._layout.characterRangeForGlyphRange_actualGlyphRange_(self._glyphs, None)
        return rng

    def draw(self):
        # we inherit from Grob for the methods, not drawability
        codependent = "TextFrames can't be drawn directly; plot() the parent Text object instead"
        raise DeviceError(codependent)

