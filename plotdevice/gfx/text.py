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
from .atoms import TransformMixin, ColorMixin, EffectsMixin, StyleMixin, FrameMixin, Grob
from ..util import _copy_attrs, trim_zeroes, numlike, ordered, XMLParser, read
from ..lib import foundry
from . import _ns_context

_ctx = None
__all__ = ("Text", "LEFT", "RIGHT", "CENTER", "JUSTIFY",)

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


class Text(EffectsMixin, TransformMixin, FrameMixin, StyleMixin, Grob):
    # from TransformMixin: transform transformmode translate() rotate() scale() skew() reset()
    # from EffectsMixin:   alpha blend shadow
    # from FrameMixin:    x y width height
    # from StyleMixin:     stylesheet fill _parse_style()
    stateAttrs = ('_nodes', )
    opts = ('str', 'xml', 'src')

    def __init__(self, *args, **kwargs):

        # assemble the NSMachinery
        self._engine = NSLayoutManager.alloc().init()
        self._engine.setUsesScreenFonts_(False)
        self._engine.setUsesFontLeading_(False)
        self._store = NSTextStorage.alloc().init()
        self._store.addLayoutManager_(self._engine)

        if args and isinstance(args[0], Text):
            # create a parallel set of nstext objects when copying an existing Text
            # then bail out immediately (ignoring any other args)
            orig = args[0]
            self.inherit(orig)
            self._blocks = [TextBlock(self) for f in orig._blocks]
            for src, dst in zip(orig._blocks, self._blocks):
                dst.offset, dst.size = src.offset, src.size
            self._store.appendAttributedString_(orig._store)
            return

        # let the various mixins have a crack at the kwargs
        super(Text, self).__init__(**kwargs)

        # create a text block to manage layout and glyph-drawing
        self._blocks = [TextBlock(self)]

        # maintain a lookup table of nodes within xml input
        self._nodes = {}

        # look for a string as the first positional arg or an xml/str kwarg
        if args and isinstance(args[0], basestring):
            kwargs['str'], args = args[0], args[1:]

        # merge in any numlike positional args to define bounds
        if args:
            self._frame._parse(args)

        # fontify the str/xml/src arg and store it in the TextBlock
        self.append(**{k:v for k,v in kwargs.items() if k in self.opts})

    def __repr__(self):
        total = len(self.text)
        displayed = sum(self.blocks[-1]._chars)
        msg = "%i character%s" % (total, '' if total==1 else 's')
        if displayed < total:
            msg = '%i/%s'%(displayed, msg)
        if self.blocks[1:]:
            msg += ' in %i block(s)' % len(self.blocks)
        return "Text(%s)" % msg

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

            # try using the nsmagic parsing of HTML/RTF to build an attributed string
            if not is_xml:
                txt_bytes = txt.encode('utf-8')
                txt_opts = {u'CharacterEncoding': NSUTF8StringEncoding}
                decoded, info, err = NSMutableAttributedString.alloc().initWithData_options_documentAttributes_error_(
                    NSData.dataWithBytes_length_(txt_bytes, len(txt_bytes)), txt_opts, None, None
                )

                # if the data got unpacked into anything more interesting than plain text,
                # preserve its styling. otherwise fall through and style the txt val
                if re.search(r'(html|rtf)$', info.get('UTI')):
                    attrib_txt = decoded

        if txt and not attrib_txt:
            # convert non-textual `str` args to strings
            if not isinstance(txt, basestring) and not is_xml:
                txt = repr(txt)

            # try to insulate people from the need to use a unicode constant for any text
            # with high-ascii characters (while waiting for the other shoe to drop)
            decoded = txt if isinstance(txt, unicode) else txt.decode('utf-8')

            # use the inherited baseline style but allow one-off overrides from kwargs
            merged_style = self._font._spec
            merged_style.update(fill=self._fillcolor)
            merged_style.update(self._parse_style(**kwargs))

            # if the text is xml, parse it an overlay any stylesheet entries that map to
            # its tag names. otherwise apply the merged style to the entire string
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
                attrs = {seq:self._fontify(merged_style, *seq) for seq in sorted(parser.regions)}

                # apply the attributes to the runs found by the parser
                for cascade, runs in parser.regions.items():
                    style = attrs[cascade]
                    for rng in runs:
                        attrib_txt.setAttributes_range_(style, rng)
            else:
                # don't parse as xml, just apply the current font(), align(), and fill()
                attrs = self._fontify(merged_style)
                attrib_txt = NSMutableAttributedString.alloc().initWithString_attributes_(decoded, attrs)

            # ensure the very-first character of a Text is indented flush left. also watch for
            # double-newlines at the edge of the existing string and the appended chars. grafs
            # can suppress their indentation with a \b (a.k.a. \x08) at the beginning of the
            # line and un-indented lead-grafs can force indentation by beginning with \t
            pre_txt = self._store.string()
            if not pre_txt or re.search(r'\n[\n\x08]$', pre_txt):
                Text._dedent(attrib_txt)
            elif pre_txt.endswith('\n'):
                if re.match(r'\n[^\n]', attrib_txt.string()):
                    Text._dedent(attrib_txt, 1)
                elif re.match(r'\x08', attrib_txt.string()):
                    Text._dedent(attrib_txt)

            # ensure that any paragraph with more than one leading newline is indented flush-left
            # (and let `\n\b` override auto-indentation)
            for m in re.finditer(r'\n\x08|\n\n+[^\n]', attrib_txt.string()):
                Text._dedent(attrib_txt, m.end()-1)

        if attrib_txt:
            # let the typesetter deal with the new substring
            self._store.beginEditing()
            self._store.appendAttributedString_(attrib_txt)
            self._store.endEditing()
            self._resized()

    ### NSAttributedString de/manglers ###

    def _fontify(self, defaults, *styles):
        """Merge the named-styles and defaults in order and return nsattibutedstring attrs"""

        # use the inherited context settings as a baseline spec
        spec = dict(defaults)

        # layer the styles to generate a final font and color
        for tag in styles:
            spec.update(self.stylesheet._styles.get(tag,{}))

        # assign a font and color based on the coalesced spec
        font = Font({k:v for k,v in spec.items() if k in Stylesheet.kwargs})
        color = Color(spec.pop('fill')).nsColor

        # factor the relevant attrs into a paragraph style
        graf = NSMutableParagraphStyle.alloc().init()
        graf.setLineBreakMode_(NSLineBreakByWordWrapping)
        graf.setAlignment_(_TEXT[spec['align']])
        graf.setHyphenationFactor_(spec['hyphenate'])

        eps = sys.float_info.epsilon

        # force the typesetter to deal with real leading rather than `lineheight'
        face_height = eps + font.size * (font._face.ascent - font._face.descent) / 1000.0
        graf.setLineHeightMultiple_(spec['leading'] * font.size / face_height)
        graf.setMaximumLineHeight_(font.size*spec['leading'] + eps)

        # handle indentation, horizontal margins, and vertical graf spacing
        indent = font.size * spec['indent']
        tabs = abs(indent or font.size)
        head, tail = map(self._to_px, spec['margin'])
        top, bot = [font.size*font.leading*d for d in spec['spacing']]
        graf.setTabStops_([])
        graf.setDefaultTabInterval_(tabs)
        graf.setParagraphSpacingBefore_(top)
        graf.setParagraphSpacing_(bot)
        graf.setTailIndent_(-tail)
        if indent > 0:
            graf.setFirstLineHeadIndent_(indent + head)
            graf.setHeadIndent_(head)
        else:
            graf.setFirstLineHeadIndent_(head)
            graf.setHeadIndent_(abs(indent) + head)

        if not spec['tracking']:
            # None means `kerning off entirely', 0 means `default letterspacing'
            kern = 0 if spec['tracking'] is None else eps
        else:
            # convert the em-based tracking val to a point-based kerning val
            kern = (spec['tracking'] * font.size)/1000.0

        # build the dict of features for this combination of styles
        return dict(NSFont=font._nsFont, NSColor=color, NSParagraphStyle=graf, NSKern=kern)

    @classmethod
    def _dedent(cls, attrib_txt, idx=0, inherit=False):
        """Removes first-line paragraph indentation of at the given attributed-string index.

        Sets the first-line indent equal to the subsequent-lines value (unless the first line
        is outdented; in which leave it alone).

        Passing inherit=True will override this logic and set the first-indent equal to the
        subsequent-indent without regard for its indent/outdent status.

        Note that this method *modifies* the attrib_txt reference rather than returning a value.
        """
        attrib_txt.beginEditing()
        old_graf, _ = attrib_txt.attribute_atIndex_effectiveRange_("NSParagraphStyle", idx, None);
        graf = old_graf.mutableCopy()
        first, rest = graf.firstLineHeadIndent(), graf.headIndent()
        if first > rest or inherit: # leave negative-indentations alone
            graf.setFirstLineHeadIndent_(rest)
        attrib_txt.addAttribute_value_range_("NSParagraphStyle", graf, (idx, 1))
        attrib_txt.endEditing()

    ### flowing text into new Text objects or subsidiary TextBlocks ###

    def overleaf(self):
        """Returns a Text object containing any characters that did not fit within this object's bounds.
        If the entire string fits within the current object, returns None."""
        seen = u"".join(getattr(f, 'text') for f in self._blocks)
        full = self.text
        if full not in seen:
            next_pg = self.copy()

            # delete the first page's-worth of chars and update indices
            nc = len(seen)
            next_pg._store.beginEditing()
            next_pg._store.deleteCharactersInRange_([0, nc])
            next_pg._store.endEditing()
            nodes = {}
            for tag, elts in self._nodes.items():
                nodes[tag] = [e._replace(start=e.start-nc, end=e.end-nc) for e in elts if e.end-nc > 0]
            next_pg._nodes = nodes

            # if the page-break is in the middle of a paragraph, preserve the first character's initial
            # indentation (since otherwise it'll be treated as a `first' line of a new paragraph)
            if not seen.endswith('\n'):
                Text._dedent(next_pg._store, inherit=True)
            return next_pg

    def flow(self, columns=all, layout=None):
        """Add as many text blocks as necessary to fully lay out the string

        When called without arguments, returns a generator that you can iterate through to
        set the position and size of each block in turn (starting with the second). Each block
        is initialized with the same dimensions as the previous block in the sequence.

        The optional `columns` argument allows you to specify the maximum number of blocks
        you'd like to have at the end of the process. Note that this count *includes* the
        Text object's original block, so you'll iterate over columns-1 blocks during the flow.

        The optional `layout` argument can be a reference to a function which takes a single
        TextBlock argument. If present, your layout function will be called once for each
        block added to the stream.
        """
        # sanity-check the columns arg
        columns = 1e4 if columns is all else int(columns or 1)
        if columns <= 1:
            # no iteration necessary in the single-block case
            return list(self._reflow(columns))

        if not layout:
            return self._reflow(columns)   # return the generator for iteration
        map(layout, self._reflow(columns)) # apply the layout function to each block in sequence

    def _reflow(self, count):
        # wipe out any previously set blocks then keep adding new ones until
        # the glyphs are fully laid out
        while self._blocks[1:]:
            self._blocks.pop()._eject()
        block = self._blocks[0]
        while len(self._blocks) < count and sum(block._glyphs) < self._engine.numberOfGlyphs():
            block = TextBlock(block)
            self._blocks.append(block)
            yield block

    ### Layout geometry ###

    @property
    def frame(self):
        """Returns the bounding box in which the text will be laid out"""
        box = Region()
        for block in self._blocks:
            box = box.union(block.frame)
        return box

    @property
    def bounds(self):
        """Returns the size & position of the actual text (typically a subset of the bounds)"""
        box = Region()
        for block in self._blocks:
            box = box.union(block.bounds)
        return box

    @property
    def metrics(self):
        """Returns the size of the actual text (shorthand for Text.bounds.size)"""
        return self.bounds.size

    def _get_baseline(self):
        """Returns the Text object's baseline `origin point'"""
        return Point(self.x, self.y)
    def _set_baseline(self, baseline):
        self.x, self.y = baseline
    baseline = property(_get_baseline, _set_baseline)


    ### Searching for substrings (and their layout geometry) ###

    def __getitem__(self, index):
        """Subscripting a Text using indices into its .text string returns a TextFragment"""
        match = TextFragment(self)
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
          txt.find(r'foo (.*?) baz') # match the pattern and capture a sub-group
          txt.find(r'the', 10) # find the first 10 occurrences of `the'

        Args:
          `regex` can be a pattern string or a regex object. Pattern strings without
          any uppercase characters will be case-insensitively matched. Patterns with
          mixed case will be case-sensitive. In addition, the re.DOTALL flag will be
          passed by default (meaning r'.' will match any character, including newlines).
          Compiled regexes can define their own flags.

          `matches` optionally set the maximum number of results to be returned. If
          omitted, find() will return a TextFragment object for every match that's
          visible in one of the Text object's TextBlocks. Matches that lie in the
          overflow beyond the Text's bounds can be included however: pass the `all`
          keyword as the `matches` arg.

        Returns:
          a list of TextFragment objects
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
          resulting TextFragment object's `attrs` property.

          `matches` optionally set the maximum number of results to be returned. If
          omitted, select() will return a TextFragment object for every match that's
          visible in one of the Text object's TextBlocks. Matches that lie in the
          overflow beyond the Text's bounds can be included however: pass the `all`
          keyword as the `matches` arg.

        Returns:
          a list of TextFragment objects
        """
        if isinstance(tag_name, str):
            tag_name = tag_name.decode('utf-8')
        return self._seek(self._nodes.get(tag_name, []), matches)

    def _seek(self, stream, limit):
        found = []
        for m in stream:
            match = TextFragment(self, m)
            if not match.blocks and limit is not all:
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
        """Returns a TextFragment for each word in the text string (whitespace separated)"""
        return [TextFragment(self, w) for w in self._store.words()]

    @property
    def paragraphs(self):
        """Returns a TextFragment for each `line' in the text string (newline separated)"""
        return [TextFragment(self, w) for w in self._store.paragraphs()]

    @property
    def blocks(self):
        """Returns a list of one or more TextBlocks defining the bounding box for layout"""
        return list(self._blocks)

    @property
    def lines(self):
        """Returns a list of TextFragments, one for each line across all child TextBlocks"""
        return [TextFragment(self, slug) for slug in foundry.line_slugs(self)]

    ### Calculating dimensions & rendering ###

    def _resized(self):
        """Ensure that the first TextBlock's bounds are kept in sync with the Text's.
        Called by the FrameMixin when the width or size is reassigned."""

        # start with the max w/h passed by the Text object
        dims = self._frame.size
        block = self._blocks[0]

        # start at the maximal size before shrinking-to-fit
        block.offset = (0,0)
        block.size = (dims.w, dims.h)

        # if the rect isn't fully specified, size it to fit
        if not (dims.w and dims.h):
            # compute the portion that's actually filled and add 1px of extra padding to the
            # calculated width (b/c believe it or not usedRectForTextContainer is buggy...)
            min_w, min_h = block.metrics
            min_w += block._from_px(1)

            # shift the offset if not left-aligned and drawing to a point
            nudge = {RIGHT:min_w, CENTER:min_w/2.0}.get(block._alignment)
            if nudge and dims.w is None:
                block.x -= nudge

            # shrink-to-fit any dims that were previously undefined
            if not dims.w:
                block.width = min_w
            if not dims.h:
                block.height = min_h

    @property
    def _headroom(self):
        """Returns the distance between the Text's origin and the top of its bounds box"""
        if not self._store.length():
            return 0
        return self._blocks[0]._from_px(self._engine.locationForGlyphAtIndex_(0).y)

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
        has been flowed to multiple TextBlocks, dimensions are calculated based on
        the union of the various bounds boxes."""

        # gather the relevant text metrics (and convert them from canvas- to pixel-units)
        x, y = self._to_px(Point(self.x, self.y))
        baseline = self._to_px(self._headroom)

        # accumulate transformations in a fresh matrix
        xf = Transform()

        if self._transformmode == CENTER:
            # calculate the (reversible) translation offset for centering (in px)
            bounds = self._to_px(self.frame)
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
                for block in self._blocks:
                    px_offset = self._to_px(block.offset)
                    self._engine.drawGlyphsForGlyphRange_atPoint_(block._glyphs, px_offset)

                    # debug: draw a grey background for the text's bounds
                    # NSColor.colorWithDeviceWhite_alpha_(0,.2).set()
                    # NSBezierPath.fillRect_(Region(block.offset, block.size))

    @property
    def path(self):
        """Traces the laid-out glyphs and returns them as a single Bezier object"""

        # generate an unflipped bezier with all the glyphs
        path = Bezier(foundry.trace_text(self))
        path.inherit(self)

        # set its center-rotation fulcrum based on the blocks' bounds rect
        origin, size = self.frame
        path._fulcrum = origin + size/2.0

        # flip the assembled path and slide it into the proper x/y position
        return self._flipped_transform.apply(path)


class TextFragment(object):
    """Represents a substring region within a Text object (via its `find` or `select` method)

    Properties:
      `start` and `end` - the character range of the match
      `text` - the matched substring
      `path` - a Bezier object with the glyphs from the matched range
      `lines` - a list of one or more TextFragments describing line-breaking within the Match
      `blocks` - a list of one or more TextBlocks that fully contain the Match

    Additional properties when .select'ing an xml element:
      `tag` - a string with the matched element's name
      `attrs` - a dictionary with the element's attributes (if any)
      `parents` - a tuple with the parent, grandparent, etc. tag names

    Additional properties when .find'ing a regular expression:
      `m` - a regular expression Match object

    Additional methods when .find'ing a regular expression with 'captured' sub-groups
      `group(idx)` - returns a TextFragment corresponding to the numbered or named group
      `groups()` - returns a list of TextFragment objects corresponding to captures in the regex
      `groupdict()` - returns a dictionary mapping captured group names to TextFragment objects
    """
    def __init__(self, parent, match=None):
        self._parent = parent
        self.tag, self.attrs, self.parents = None, {}, ()
        self.m = None

        if isinstance(match, foundry.Slug): # via line_slugs()
            self.start, self.end = match.span
            self._slugs = [match]
        elif hasattr(match, 'range'): # NSSubText
            self.start, n = match.range()
            self.end = self.start + n
        elif hasattr(match, '_asdict'): # xml Element
            for k,v in match._asdict().items():
                setattr(self, k, v)
        elif hasattr(match, '_chars'): # TextBlock
            self.start, n = match._chars
            self.end = self.start + n
        elif hasattr(match, 'span'): # re.Match
            self.start, self.end = match.span()
            self.m = match
        elif isinstance(match, tuple): # regex sub-match
            self.start, self.end, self._group = match

    def __len__(self):
        return self.end-self.start

    def __repr__(self):
        msg = []
        if hasattr(self, '_group'):
            fmt = "r'\\%i'" if numlike(self._group) else "r'P<%s>'"
            msg.append(fmt % self._group)
        try:
            pat = self.m.re.pattern
            if len(pat)>18:
                pat = "%s..." % (pat[:15])
            msg.append("r%s" % repr(pat).lstrip("u"))
        except:
            if self.tag:
                msg.append("<%s>" % self.tag)
            if self.attrs:
                msg.append("attrs=%i" % len(self.attrs))
        msg.append("start=%i" % self.start)
        msg.append("len=%i" % (self.end-self.start))
        return 'TextFragment(%s)' % (", ".join(msg))

    ### Contents ###

    @property
    def text(self):
        return self._parent.text[self.start:self.end]

    def group(self, index=0, *others):
        """Return subgroup(s) of the match by indices or names. Index 0 returns the entire match.

        Works just like https://docs.python.org/2/library/re.html#re.MatchObject.group
        but returns TextFragment objects rather than character strings
        """
        self._is_regex('group')
        subs = []
        for idx in (index,) + others:
            rng = self.m.span(idx) + (idx,)
            subs.append(TextFragment(self._parent, rng) if rng[0]!=-1 else None)
        return tuple(subs) if len(subs)>1 else subs[0]

    def groups(self, default=None):
        """Return a tuple containing all the subgroups of the match, from 1.
        The default argument is used for groups that did not participate in the match

        Works just like https://docs.python.org/2/library/re.html#re.MatchObject.groups
        but returns TextFragment objects rather than character strings
        """
        self._is_regex('groups')
        indices = range(1,len(self.m.regs))
        if not indices:
            return ()
        return tuple(m if m else default for m in self.group(*indices))

    def groupdict(self, default=None):
        """Return a dictionary containing all the named subgroups of the match,
        keyed by the subgroup name. The default argument is used for groups
        that did not participate in the match

        Works just like https://docs.python.org/2/library/re.html#re.MatchObject.groupdict
        but returns TextFragment objects rather than character strings
        """
        self._is_regex('groupdict')
        indices = self.m.groupdict().keys()
        subs = [self.group(nm) for nm in indices]
        return {nm:sub if sub else default for nm, sub in zip(indices, subs)}

    def _is_regex(self, method):
        # an assert to ensure the match supports the group* methods
        if not self.m:
            badmatch = '%s() can only be used with regex-based TextFragment objects (see Text.find)'
            raise DeviceError(badmatch % method)

    ### Geometry ###

    @property
    def slugs(self):
        """A list of one or more line-fragment Slugs describing text layout within the match"""
        if not hasattr(self, '_slugs'):
            rng = (self.start, self.end-self.start)
            self._slugs = foundry.line_slugs(self._parent, rng)
        return self._slugs

    @property
    def lines(self):
        """A list of one or more TextFragments splitting the current object across line-breaks"""
        return [TextFragment(self._parent, lf) for lf in self.slugs]

    @property
    def blocks(self):
        """The list of TextBlock objects that the match spans"""
        rng = (self.start, self.end-self.start)
        return foundry.text_blocks(self._parent, rng)

    @property
    def frame(self):
        """Returns the bounding box for the lines containing the match"""
        box = Region()
        for slug in self.slugs:
            box = box.union(slug.frame)
        return box

    @property
    def bounds(self):
        """Returns the bounding box of the matched characters"""
        box = Region()
        for slug in self.slugs:
            box = box.union(slug.bounds)
        return box

    @property
    def metrics(self):
        """The size of the rendered text"""
        return self.bounds.size

    @property
    def baseline(self):
        """The origin Point of the first glyph in the match (or None if empty)"""
        for slug in self.slugs:
            return slug.baseline
        return None

    @property
    def path(self):
        """Traces the laid-out glyphs and returns them as a single Bezier object"""

        # generate an unflipped bezier with all the glyphs
        path = Bezier(foundry.trace_text(self._parent, (self.start, len(self))))
        path.inherit(self._parent)

        # set its center-rotation fulcrum based on the blocks' bounds rect
        origin, size = self._parent.frame
        path._fulcrum = origin + size/2.0

        # flip the assembled path and slide it into the proper x/y position
        return self._parent._flipped_transform.apply(path)

class TextBlock(FrameMixin, Grob):
    """Defines a layout region for a Text object's typesetter.

    Most Text objects have a single TextBlock which holds the width
    and height of the layout region. You don't need to deal with it
    directly since you can just set the x/y/w/h attributes on the Text
    object itself.

    You can create a multi-column layout by iterating over a Text
    object's .flow() method and manipulating the TextBlocks it returns.
    You can also inspect the existing TextBlocks without adding new ones
    through the Text object's `blocks` property.

    Read/Write Properties:
        `offset` - a Point with the block's position relative to the parent Text's.
        `size` - a Size with the maximum width & height of the layout region
        `x`,`y`,`w`,`h` - shorthand accessors for offset & size components

    Readable Properties:
        `text` - the substring that is visible in the block
        `idx` - a counter marking the block's place in the sequence
        `metrics` - the size of the used portion of the block's w & h
        `lines` - a list of LineFragments contained in the block
        `path` - a Bezier object with all the visible glyphs in the block
    """
    def __init__(self, parent):
        # inherit the canvas-unit methods and a _frame
        self._frame = Region((0,0), (None,None))
        self.inherit()

        # create a new container
        self._block = NSTextContainer.alloc().init()
        self._block.setLineFragmentPadding_(0)

        if isinstance(parent, TextBlock):
            # either piggyback on an existing block...
            self._parent = parent._parent
            self.offset, self.size = parent.offset, parent.size
        else:
            # ... or become the first block of a parent Text object
            self._parent = parent

        # add ourselves to the layout flow
        self._parent._engine.addTextContainer_(self._block)

    @trim_zeroes
    def __repr__(self):
        return "TextBlock(%r, %r)"%(tuple(self.offset), tuple(self.size))

    @property
    def idx(self):
        """An integer marking this block's place in the flow sequence"""
        return self._parent._engine.textContainers().index(self._block)

    @property
    def text(self):
        """The portion of the parent Text object's string that is visible in this block"""
        return self._parent._store.string().substringWithRange_(self._chars)

    @property
    def frame(self):
        """The position & size of the block in canvas coordinates"""
        bbox = Region(self.offset, self.size)
        bbox.origin += self._parent.baseline
        bbox.y -= self._from_px(self._headroom)
        return bbox

    @property
    def bounds(self):
        """The position & size of the block's text in canvas coordinates"""
        self._parent._engine.glyphRangeForTextContainer_(self._block) # force layout & glyph gen
        origin, size = self._parent._engine.usedRectForTextContainer_(self._block)
        origin.y -= self._headroom # adjust for the ascent above baseline
        origin += self.offset + self._parent.baseline
        return self._from_px(Region(origin, size))

    @property
    def metrics(self):
        """The size of the rendered text"""
        return self.bounds.size

    @property
    def lines(self):
        """A list of TextFragments describing the line-layout within the block"""
        slugs = foundry.line_slugs(self._parent, self._chars)
        return [TextFragment(self._parent, slug) for slug in slugs]

    @property
    def path(self):
        """Traces the laid-out glyphs and returns them as a single Bezier object"""
        return TextFragment(self._parent, self).path

    @property
    def _headroom(self):
        if not self._parent.text:
            return self._parent._font.ascender
        fnt, _ = self._parent._store.attribute_atIndex_effectiveRange_("NSFont", self._chars.location, None);
        if not fnt:
            return self._parent._font.ascender
        return fnt.ascender()

    def _eject(self):
        idx = self._parent._engine.textContainers().index(self._block)
        self._parent._engine.removeTextContainerAtIndex_(idx)
        self._parent = None

    def _resized(self):
        # called by the FrameMixin when the w or h changed
        dims = [d or self._from_px(10000000) for d in self._frame.size]
        self._block.setContainerSize_(self._to_px(Size(*dims)))

    def _get_offset(self):
        return Point(self._frame.origin)
    def _set_offset(self, dims):
        if numlike(dims):
            dims = [dims]*2
        self._frame.origin = dims
    offset = property(_get_offset, _set_offset)

    def _get_size(self):
        return self._from_px(self._block.containerSize())
    def _set_size(self, dims):
        if dims != self._frame.size:
            self._frame.size = dims
            self._resized()
    size = property(_get_size, _set_size)

    @property
    def _alignment(self):
        if not self._parent._store.string():
            return LEFT
        graf, _ = self._parent._store.attribute_atIndex_effectiveRange_("NSParagraphStyle", 0, None)
        return {_TEXT[a]:a for a in _TEXT}.get(graf.alignment(), LEFT)

    @property
    def _glyphs(self):
        # NSRange of glyphs in the block
        return self._parent._engine.glyphRangeForTextContainer_(self._block)

    @property
    def _chars(self):
        # NSRange of chars in the block
        rng, _ = self._parent._engine.characterRangeForGlyphRange_actualGlyphRange_(self._glyphs, None)
        return rng

    def draw(self):
        # we inherit from Grob for the methods, not drawability
        codependent = "TextBlocks can't be drawn directly; plot() the parent Text object instead"
        raise DeviceError(codependent)

