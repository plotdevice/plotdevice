# encoding: utf-8
import re
import sys
import objc
import weakref
from unicodedata import normalize
from collections import namedtuple
from Quartz import CGContextSetTextMatrix, CGContextSetTextPosition, CGAffineTransformMake
from ..lib.cocoa import *

from plotdevice import DeviceError
from .typography import *
from .geometry import Transform, Region, Size, Point, Pair, IDENTITY, _pivot, _hull
from .colors import Color, Pattern
from .bezier import Bezier
from .atoms import TransformMixin, ColorMixin, EffectsMixin, StyleMixin, FrameMixin, Grob
from ..util import _copy_attrs, trim_zeroes, numlike, ordered, XMLParser, Element, read
from ..lib import foundry
from . import _ns_context, _cg_port, _inkmode

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

# TextKit treats sizes this big as unlimited: form feeds no longer break blocks, and lines no longer align
_UNLIMITED = 10000000

# CoreText functions for drawing single-line texts
objc.loadBundleFunctions(NSBundle.bundleWithPath_('/System/Library/Frameworks/CoreText.framework'), globals(), [
    ('CTLineCreateWithAttributedString', b'@@', '', {'retval': {'already_retained': True}}),
    ('CTLineGetTypographicBounds', b'd@o^do^do^d'),
    ('CTLineGetTrailingWhitespaceWidth', b'd@'),
    ('CTLineGetGlyphRuns', b'@@'),
    ('CTRunGetAttributes', b'@@'),
    ('CTRunGetStringRange', b'{CFRange=qq}@'),
    ('CTLineDraw', b'v@^{CGContext=}'),
    ('CTRunDraw', b'v@^{CGContext=}{CFRange=qq}'),
    ('CTTypesetterCreateWithAttributedString', b'@@', '', {'retval': {'already_retained': True}}),
    ('CTTypesetterSuggestLineBreak', b'q@qd'),
])

# measures fonts as a Text's engine does
_METRICS = NSLayoutManager.alloc().init()
_METRICS.setUsesScreenFonts_(False)
_METRICS.setUsesFontLeading_(False)

# line breaks and control chars, left to TextKit
_BREAKS = re.compile('[\x00-\x08\x0a-\x1f\x7f\x85\u2028\u2029]')

# right-to-left scripts, left to TextKit
_RTL = re.compile('[\u0590-\u08ff\ufb1d-\ufdff\ufe70-\ufeff\U00010800-\U00010fff\U0001e800-\U0001efff]')

# printable ascii
_ASCII = NSCharacterSet.characterSetWithRange_((0x20, 0x5f))

# a CoreText-typeset line and its placement
LineLayout = namedtuple('LineLayout', ['ctline', 'x', 'baseline', 'width', 'height', 'frame_x', 'frame_w', 'ascender', 'fonts'])

# a font's line metrics and charset
FontInfo = namedtuple('FontInfo', ['line_height', 'baseline', 'ascender', 'charset', 'covers_ascii', 'covered'])

class Text(EffectsMixin, TransformMixin, FrameMixin, StyleMixin, Grob):
    # from TransformMixin: transform transformmode translate() rotate() scale() skew() reset()
    # from EffectsMixin:   alpha blend shadow
    # from FrameMixin:    x y width height
    # from StyleMixin:     stylesheet fill _parse_style()
    stateAttrs = ('_nodes', '_nsmode', '_patterns')
    opts = ('str', 'xml', 'src')

    def __init__(self, *args, **kwargs):

        # CoreText lays out single lines, TextKit handles the rest
        self._store = NSMutableAttributedString.new()
        self._engine = None # TextKit's layout manager
        self._line = None   # CoreText's LineLayout
        self._nsmode = None # output mode of the store's NSColors

        if args and isinstance(args[0], Text):
            # create a parallel set of nstext objects when copying an existing Text
            # then bail out immediately (ignoring any other args)
            orig = args[0]
            self.inherit(orig)
            self._store.appendAttributedString_(orig._store)
            if orig._engine is not None:
                self._use_textkit()
                self._blocks += [TextBlock(self) for f in orig._blocks[1:]]
                for src, dst in zip(orig._blocks, self._blocks):
                    dst.offset, dst.size = src.offset, src._frame.size # the dims it was given
            else:
                self._line = orig._line # immutable, and the same string & styles
            return

        # let the various mixins have a crack at the kwargs
        super(Text, self).__init__(**kwargs)

        # maintain a lookup table of nodes within xml input
        self._nodes = {}
        self._patterns = {} # pattern fills, keyed by their runs' PDColor

        # use the first positional arg if no xml/str/src kwarg was passed
        if not any(o in kwargs for o in self.opts) and len(args):
            kwargs['str'], args = str(args[0]), args[1:]

        # merge in any numlike positional args to define bounds
        if args:
            try:
                self._frame._parse(args)
            except:
                raise DeviceError("Expected an x/y point (and optional width/height) but got %r" % (args,))

        # fontify the str/xml/src arg and store it in the TextBlock
        self.append(**{k:v for k,v in kwargs.items() if k in self.opts})
        if not self._store.length():
            self._use_textkit()

    def __repr__(self):
        total = len(self.text)
        displayed = total if self._engine is None else sum(self.blocks[-1]._chars)
        msg = 'chars=%i'%displayed
        if displayed < total:
            msg += ' overflow=%i'%(total-displayed)
        if self.blocks[1:]:
            msg += ' blocks=%i' % len(self.blocks)
        if hasattr(self, 'folio'):
            msg += ' idx=%i folio=%i'%(self.idx, self.folio)
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
                txt = normalize("NFC", txt)
                txt_bytes = txt.encode('utf-8')
                txt_opts = {'CharacterEncoding': NSUTF8StringEncoding}
                txt, info, err = NSMutableAttributedString.alloc().initWithData_options_documentAttributes_error_(
                    NSData.dataWithBytes_length_(txt_bytes, len(txt_bytes)), txt_opts, None, None
                )

                # if the data got unpacked into anything more interesting than plain text,
                # preserve its styling. otherwise fall through and style the txt val
                if re.search(r'(html|rtf)$', info.get('UTI')):
                    attrib_txt = txt

        if txt is not None and not attrib_txt:
            # convert non-textual `str` args to strings
            if not isinstance(txt, str) and not is_xml:
                txt = repr(txt)
            txt = normalize("NFC", txt)

            # use the inherited baseline style but allow one-off overrides from kwargs
            overrides = self._parse_style(**kwargs)

            # if the text is xml, parse it an overlay any stylesheet entries that map to
            # its tag names. otherwise apply the merged style to the entire string
            if is_xml:
                # find any tagged regions that need styling
                parser = XMLParser(txt, offset=len(self.text))

                # update our internal lookup table of nodes
                for tag, elts in parser.nodes.items():
                    old_elts = self._nodes.get(tag, [])
                    self._nodes[tag] = old_elts + elts

                # start building the display-string (with all the tags now removed)
                attrib_txt = NSMutableAttributedString.alloc().initWithString_(parser.text)

                # generate the proper `ns' font attrs for each unique cascade of xml tags
                attrs = {seq:self._fontify(overrides, *seq) for seq in sorted(parser.regions)}

                # apply the attributes to the runs found by the parser
                for cascade, runs in parser.regions.items():
                    style = attrs[cascade]
                    for rng in runs:
                        attrib_txt.setAttributes_range_(style, rng)
            else:
                # don't parse as xml, just apply the current font(), align(), and fill()
                attrs = self._fontify(overrides)
                attrib_txt = NSMutableAttributedString.alloc().initWithString_attributes_(txt, attrs)

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

            # update earlier runs if the cmyk/rgb mode has changed
            if self._nsmode is None:
                self._nsmode = _inkmode()
            self._colorize()

            # switch to TextKit once it exceeds one line
            if self._engine is None:
                self._line = self._typeset_line()
                if self._line is None:
                    self._use_textkit()
            else:
                self._resized()

    def _use_textkit(self):
        # set up TextKit for complex/multiline runs
        if self._engine is not None:
            return
        self._engine = foundry.PDLayoutManager.new()
        self._engine.setUsesScreenFonts_(False)
        self._engine.setUsesFontLeading_(False)
        self._engine.setBackgroundLayoutEnabled_(False) # laid out at commit
        store = NSTextStorage.alloc().initWithAttributedString_(self._store)
        store.addLayoutManager_(self._engine)
        self._store, self._line = store, None
        self._blocks = [TextBlock(self)]
        self._resized()

    def _typeset_line(self):
        # use CoreText if only a single line, otherwise return None
        store, length = self._store, self._store.length()
        string = store.string()
        width, height = self._frame.size
        if not length or height is not None or _BREAKS.search(string) or _RTL.search(string):
            return None

        # skip measuring strings that can't possibly fit
        dpx = self._grid.dpx
        if width is not None and len(string.rstrip()) * 0.15 * self._font.size > width * dpx:
            return None

        # cache interned paragraph styles
        attrs, run = store.attributesAtIndex_effectiveRange_(0, None)
        graf = attrs['NSParagraphStyle']
        cached = foundry.LIBRARY.recall(('paragraph', id(graf)))
        if cached is None or cached[0] is not graf:
            flush = {NSCenterTextAlignment: 0.5, NSRightTextAlignment: 1.0}.get(graf.alignment(), 0.0)
            cached = foundry.LIBRARY.remember(('paragraph', id(graf)), (graf, (graf.firstLineHeadIndent(), -graf.tailIndent(),
                flush, graf.lineHeightMultiple() or 1.0, graf.maximumLineHeight(), graf.minimumLineHeight())))
        head, tail, flush, multiple, most, least = cached[1]
        if head and '\t' in string:
            return None # tab stops differ with a margin

        # determine line metrics and whether any fallback fonts are triggered
        above, below, at, ascii, fallback, fonts = 0.0, 0.0, 0, string.isascii(), False, []
        single = run.length == length # one font asked for
        while True:
            font = attrs['NSFont']
            info = self._font_info(font)
            if not (ascii and info.covers_ascii):
                fallback = fallback or not self._coverage(info, string.nsstring().substringWithRange_((at, run.length)))[0]
            fonts.append(font)
            above, below = max(above, info.baseline), max(below, info.line_height - info.baseline)
            if at == 0:
                first_ascender = info.ascender
            at += run.length
            if at >= length:
                break
            attrs, run = store.attributesAtIndex_effectiveRange_(at, None)

        # check whether the text fits on a single line (omitting trailing spaces)
        ctline = CTLineCreateWithAttributedString(store)
        full = CTLineGetTypographicBounds(ctline, None, None, None)[0]
        visible = full - CTLineGetTrailingWhitespaceWidth(ctline)
        if width is not None:
            room = width * dpx - head - tail
            borderline = room - 0.01 < visible <= room + 0.01
            if visible > room + 0.01:
                return None
            if borderline and CTTypesetterSuggestLineBreak(CTTypesetterCreateWithAttributedString(store), 0, room) < length:
                return None

        # measure the fallback fonts used (if any)
        if fallback:
            no_surrogates = len(string) == length
            above = below = 0.0
            fonts = []
            for ctrun in CTLineGetGlyphRuns(ctline):
                drawn = CTRunGetAttributes(ctrun)['NSFont']
                start, count = CTRunGetStringRange(ctrun)
                asked = font if single else store.attribute_atIndex_effectiveRange_('NSFont', start, None)[0]
                chars = string[start:start + count] if no_surrogates else string.nsstring().substringWithRange_((start, count))
                same = drawn is asked or (drawn.fontName() == asked.fontName() and drawn.pointSize() == asked.pointSize())
                asked_info = self._font_info(asked)
                every, some = self._coverage(asked_info, chars)
                if same != every:
                    return None
                measured = []
                if same or some:
                    measured.append(asked)
                if not same:
                    measured.append(drawn)
                for counted in measured:
                    counted_info = self._font_info(counted)
                    fonts.append(counted)
                    above, below = max(above, counted_info.baseline), max(below, counted_info.line_height - counted_info.baseline)
                if start == 0:
                    first = asked_info if self._coverage(asked_info, chars[0])[0] else self._font_info(drawn)
                    first_ascender = first.ascender
        line_height = (above + below) * multiple
        if most:
            line_height = min(line_height, most)
        line_height = max(line_height, least)

        # apply horizontal alignment, ignoring trailing spaces
        used = visible if flush == 1.0 else full
        if width is None:
            x = head * (1 - flush) - flush * (tail + visible)
            frame_x, frame_w = -flush * (used + 1), used + 1
        else:
            x = head + (width * dpx - head - tail - visible) * flush
            used = min(used, width * dpx - tail - x) # trailing spaces hang past
            frame_x, frame_w = 0.0, width * dpx
        return LineLayout(ctline, x, line_height - below, used, line_height, frame_x, frame_w, first_ascender, fonts)

    @staticmethod
    def _font_info(font):
        # a font's metrics and coverage, cached by name & size
        key = ('font info', font.fontName(), font.pointSize())
        info = foundry.LIBRARY.recall(key)
        if info is None:
            charset = font.coveredCharacterSet()
            info = foundry.LIBRARY.remember(key, FontInfo(_METRICS.defaultLineHeightForFont_(font),
                _METRICS.defaultBaselineOffsetForFont_(font), font.ascender(), charset, bool(charset.isSupersetOfSet_(_ASCII)), {}))
        return info

    @staticmethod
    def _coverage(info, chars):
        # whether a font has all or any of the chars
        every, some = True, False
        for char in chars:
            covered = info.covered.get(char)
            if covered is None:
                free = char == '\t' or (info.covers_ascii and ' ' <= char <= '~')
                covered = info.covered[char] = free or bool(info.charset.longCharacterIsMember_(ord(char)))
            every, some = every and covered, some or covered
        return every, some

    ### NSAttributedString de/manglers ###

    def _fontify(self, overrides, *styles):
        """Layer the overrides and named-styles and return nsattibutedstring attrs"""
        layers = [layer for layer in [overrides] + [self.stylesheet._styles.get(tag) for tag in styles] if layer]
        fill = self._fillcolor
        margin = self._font._metrics['margin']
        for layer in layers:
            fill = layer.get('fill', fill)
            margin = layer.get('margin', margin)

        # a pattern run's PDColor is its identifies its tiles (the black NSColor is just a placeholder)
        pattern = isinstance(fill, Pattern)
        color = Color('black' if pattern else fill)
        paint = str(id(fill)) if pattern else color._src
        if pattern:
            self._patterns[paint] = fill

        # reuse attrs for the same font, fill, & styles
        head, tail = map(self._to_px, margin)
        key = (_inkmode(), paint, head, tail, self._font._key)
        key += tuple(tuple(sorted((k, v) for k, v in layer.items() if k not in ('fill', 'margin'))) for layer in layers)
        attrs = foundry.LIBRARY.recall(key)
        if attrs is not None:
            return attrs

        # layer the styles to generate a final font
        spec = self._font._spec
        for layer in layers:
            spec.update(layer)
        spec.pop('fill', None)

        # assign a font based on the coalesced spec
        font = Font({k:v for k,v in spec.items() if k in Stylesheet.kwargs})

        eps = sys.float_info.epsilon

        # force the typesetter to deal with real leading rather than `lineheight'
        face_height = eps + font.size * (font._face.ascent - font._face.descent) / 1000.0
        multiple, maximum = spec['leading'] * font.size / face_height, font.size*spec['leading'] + eps

        # handle indentation, horizontal margins, and vertical graf spacing
        indent = font.size * spec['indent']
        tabs = abs(indent or font.size)
        top, bot = [font.size*font.leading*d for d in spec['spacing']]
        first, rest = (indent + head, head) if indent > 0 else (head, abs(indent) + head)

        # fold settings into a paragraph style (and intern it)
        values = (spec['align'], spec['hyphenate'], multiple, maximum, tabs, top, bot, tail, first, rest)
        graf = foundry.LIBRARY.recall(('paragraph style', values))
        if graf is None:
            graf = NSMutableParagraphStyle.alloc().init()
            graf.setLineBreakMode_(NSLineBreakByWordWrapping)
            graf.setAlignment_(_TEXT[spec['align']])
            graf.setHyphenationFactor_(spec['hyphenate'])
            graf.setLineHeightMultiple_(multiple)
            graf.setMaximumLineHeight_(maximum)
            graf.setTabStops_(NSArray.array())
            graf.setDefaultTabInterval_(tabs)
            graf.setParagraphSpacingBefore_(top)
            graf.setParagraphSpacing_(bot)
            graf.setTailIndent_(-tail)
            graf.setFirstLineHeadIndent_(first)
            graf.setHeadIndent_(rest)
            graf = foundry.LIBRARY.remember(('paragraph style', values), graf.copy())

        if not spec['tracking']:
            # None means `kerning off entirely', 0 means `default letterspacing'
            kern = 0 if spec['tracking'] is None else eps
        else:
            # convert the em-based tracking val to a point-based kerning val
            kern = (spec['tracking'] * font.size)/1000.0

        # build the features dict out of objc references since TextKit caches them
        attrs = dict(NSFont=font._nsFont, PDColor=paint, NSColor=color.nsColor, NSParagraphStyle=graf, NSKern=kern)
        if pattern:
            attrs['CTForegroundColorFromContext'] = True # coretext uses the context's color (set in _draw)
        return foundry.LIBRARY.remember(key, NSDictionary.dictionaryWithDictionary_(attrs))

    def _colorize(self):
        """Updates the TextStorage, rewriting Colors as rgb or cmyk NSColors based on the current output mode"""
        mode = _inkmode()
        if self._nsmode != mode:
            at = 0
            end = self._store.length()
            while at < end:
                clr, rng = self._store.attribute_atIndex_effectiveRange_('PDColor', at, None)
                # skip pattern runs (since PDColor is just the pattern's key, not a real color)
                if not isinstance(clr, str):
                    self._store.addAttribute_value_range_('NSColor', Color(clr).nsColor, rng)
                at += rng.length
            self._nsmode = mode
            if self._engine is None:
                self._line = self._typeset_line() # update the stale colors from the last run

    @classmethod
    def _dedent(cls, attrib_txt, idx=0, inherit=False):
        """Removes first-line paragraph indentation of at the given attributed-string index.

        Sets the first-line indent equal to the subsequent-line's value (unless the first line
        is outdented; in which case leave it alone).

        Passing inherit=True will override this logic and set the first-indent equal to the
        subsequent-indent without regard for its indent/outdent status.

        Note that this method *modifies* the attrib_txt reference rather than returning a value.
        """
        if not attrib_txt.length(): return
        old_graf, _ = attrib_txt.attribute_atIndex_effectiveRange_("NSParagraphStyle", idx, None);
        first, rest = old_graf.firstLineHeadIndent(), old_graf.headIndent()
        if first > rest or inherit: # leave negative-indentations alone
            cached = foundry.LIBRARY.recall(('dedented', id(old_graf), rest))
            if cached is None or cached[0] is not old_graf:
                graf = old_graf.mutableCopy()
                graf.setFirstLineHeadIndent_(rest)
                cached = foundry.LIBRARY.remember(('dedented', id(old_graf), rest), (old_graf, graf.copy()))
            graf = cached[1]
            attrib_txt.beginEditing()
            attrib_txt.addAttribute_value_range_("NSParagraphStyle", graf, (idx, 1))
            attrib_txt.endEditing()

    ### flowing text into new Text objects or subsidiary TextBlocks ###

    def overleaf(self):
        """Returns a Text object containing any characters that did not fit within this object's bounds.
        If the entire string fits within the current object, returns None."""
        self._use_textkit()
        seen = "".join(getattr(f, 'text') for f in self._blocks)
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
        for block in self._reflow(columns):
            layout(block) # apply the layout function to each block in sequence

    def _reflow(self, count):
        # wipe out any previously set blocks then keep adding new ones until
        # the glyphs are fully laid out
        self._use_textkit()
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
        if self._engine is None:
            line, dpx = self._line, self._grid.dpx
            return Region(self.x + line.frame_x / dpx, self.y - line.ascender / dpx, line.frame_w / dpx, line.height / dpx)
        if len(self._blocks) == 1:
            return self._blocks[0].frame
        box = Region()
        for block in self._blocks:
            box = box.union(block.frame)
        return box

    @property
    def bounds(self):
        """Returns the size & position of the actual text (typically a subset of the bounds)"""
        if self._engine is None:
            # mixes units as TextBlock.bounds does (see bugs.md)
            line, dpx = self._line, self._grid.dpx
            x = line.x - line.frame_x + line.frame_x / dpx + self.x
            return Region(x / dpx, (self.y - line.ascender) / dpx, line.width / dpx, line.height / dpx)
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
        return self._store.string()

    @property
    def words(self):
        """Returns a TextFragment for each word in the text string (whitespace separated)"""
        self._use_textkit()
        return [TextFragment(self, w) for w in self._store.words()]

    @property
    def paragraphs(self):
        """Returns a TextFragment for each `line' in the text string (newline separated)"""
        self._use_textkit()
        return [TextFragment(self, w) for w in self._store.paragraphs()]

    @property
    def blocks(self):
        """Returns a list of one or more TextBlocks defining the bounding box for layout"""
        self._use_textkit()
        return list(self._blocks)

    @property
    def lines(self):
        """Returns a list of TextFragments, one for each line across all child TextBlocks"""
        self._use_textkit()
        return [TextFragment(self, slug) for slug in foundry.line_slugs(self)]

    ### Calculating dimensions & rendering ###

    def _resized(self):
        """Ensure that the first TextBlock's bounds are kept in sync with the Text's.
        Called by the FrameMixin when the width or size is reassigned."""
        self._use_textkit()
        w, h = self._frame.size
        block = self._blocks[0]

        # match the Text's frame (unset dims will shrink to fit when read)
        block.offset = (0, 0)
        block.size = (w, h)

        # use 'unlimited' height so TextKit treats `\f` as a paragraph- rather than block-break
        # and fit unset dims to all of its sections at once
        if '\f' in self.text and not (w and h):
            block._block.setContainerSize_((block._block.containerSize().width, _UNLIMITED))
            fit_w, fit_h = block.metrics
            fit_w += block._from_px(1) # the same 1px of padding as _fit
            block.size = (w or fit_w, h or fit_h)

        # center or right-align point text on its origin
        nudge = {RIGHT:1.0, CENTER:0.5}.get(block._alignment)
        if w is None and nudge:
            block.x -= block.size.w * nudge

    @property
    def _headroom(self):
        """Returns the distance between the Text's origin and the top of its bounds box"""
        if not self._store.length():
            return 0
        if self._engine is None:
            return self._from_px(self._line.baseline)
        return self._blocks[0]._from_px(self._engine.locationForGlyphAtIndex_(0).y)

    @property
    def _flipped_transform(self):
        """Returns a Transform object that positions unflipped beziers returned by trace_text"""
        xf = Transform()
        xf.translate(self.x, self.y - self._headroom)
        xf.scale(1.0,-1.0)
        return xf

    @property
    def _screen_matrix(self):
        """The matrix the text block is drawn with.

        The transform incorporates the global context state but also accounts for
        the column-width/height constraints set in the constructor. If the text
        has been flowed to multiple TextBlocks, dimensions are calculated based on
        the union of the various bounds boxes."""

        # gather the relevant text metrics (and convert them from canvas- to pixel-units)
        dpx = self._grid.dpx
        x, y = self.x * dpx, self.y * dpx
        top = y - self._headroom * dpx
        matrix = tuple(self.transform.matrix)

        # in CORNER mode, apply the CTM at the origin
        if self._transformmode != CENTER or matrix == IDENTITY:
            a, b, c, d, mx, my = matrix
            return (a, b, c, d, mx + a * x + c * top, my + b * x + d * top)

        # union the non-empty blocks' frames
        if self._engine is None:
            line = self._line
            x0, y0 = x + line.frame_x, y - line.ascender
            x1, y1 = x0 + line.frame_w, y0 + line.height
        else:
            xs, ys = [], []
            for block in self._blocks:
                w, h = block._frame.size
                fit = block._fit if not (w and h) else None
                bw = w * dpx if w else fit.width
                bh = h * dpx if h else fit.height
                if bw > 0 and bh > 0:
                    bx = (self.x + block._frame.origin.x) * dpx
                    by = (self.y + block._frame.origin.y) * dpx - block._headroom
                    xs += [bx, bx + bw]
                    ys += [by, by + bh]
            x0, y0, x1, y1 = (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)

        # apply the CTM at the frame's center
        return _pivot(matrix, (x0 + x1) / 2.0 - x, (y0 + y1) / 2.0 - top, x, top)

    @property
    def _screen_transform(self):
        """Returns the Transform object that will be used to draw the text block."""
        return Transform(self._screen_matrix)

    def _commit(self, held):
        # check for both direct references to the Text object and its blocks (and only copy if held)
        for probe in [object()]:
            unheld = sys.getrefcount(probe)
        for block in self._blocks if self._engine is not None else ():
            held = held or sys.getrefcount(block) > unheld
        text = self.copy() if held else self

        # resolve colors and layout so they are already calculated before draw time
        # (prevents deadlocks from multiple threads accessing the TextStorage)
        text._colorize()
        if text._engine is None and text._line is None:
            text._use_textkit()
        if text._engine is not None:
            for block in text._blocks:
                text._engine.glyphRangeForTextContainer_(block._block)
        return text

    def _render_box(self):
        """The box its glyphs can cover where it's drawn"""
        dpx = self._grid.dpx

        # measure the laid-out lines and collect their fonts
        if self._engine is None:
            line = self._line
            x0, y0, w0, h0 = line.x, 0.0, line.width, line.height
            fonts = list(line.fonts)
        else:
            xs, ys = [], []
            for block in self._blocks:
                (ux, uy), (uw, uh) = self._engine.usedRectForTextContainer_(block._block)
                ox, oy = block._frame.origin
                bx, by = ox * dpx - block._shift + ux, oy * dpx + uy
                xs += [bx, bx + uw]
                ys += [by, by + uh]
            x0, y0, w0, h0 = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
            fonts, at, end = [], 0, self._store.length()
            while at < end:
                font, run = self._store.attribute_atIndex_effectiveRange_('NSFont', at, None)
                if font is not None:
                    fonts.append(font)
                at += run.length

        # account for the most each font's glyphs can overflow the line box
        reach = 0
        for font in fonts:
            (gx, gy), (gw, gh) = font.boundingRectForFont()
            reach = max(reach, -gx, -gy, gx + gw, gy + gh)

        if tuple(self.transform.matrix) == IDENTITY:
            x, y, w, h = x0 + self.x * dpx, y0 + (self.y - self._headroom) * dpx, w0, h0
            return (x - reach, y - reach, w + 2 * reach, h + 2 * reach)
        # pad before transforming, so the reach scales with the glyphs
        return _hull(self._screen_matrix, x0 - reach, y0 - reach, w0 + 2 * reach, h0 + 2 * reach)

    def _draw(self):
        with _ns_context():                  # save and restore the gstate
            self._screen_transform.concat()  # transform so text can be drawn at the origin
            with self.effects.applied(self): # apply any blend/alpha/shadow effects
                if self._engine is None:
                    # typeset with CoreText
                    port = _cg_port()
                    CGContextSetTextMatrix(port, CGAffineTransformMake(1, 0, 0, -1, 0, 0))
                    CGContextSetTextPosition(port, self._line.x, self._line.baseline)
                    if not self._patterns:
                        CTLineDraw(self._line.ctline, port)
                    else:
                        for run in CTLineGetGlyphRuns(self._line.ctline):
                            # for pattern runs, pass the tile as its CGColor
                            pattern = self._patterns.get(CTRunGetAttributes(run)['PDColor'])
                            if pattern is not None:
                                CGContextSetFillColorWithColor(port, pattern.cgColor)
                            CTRunDraw(run, port, (0, 0))
                else:
                    # typeset with TextKit (and let PDLayoutManager handle patterned fills)
                    self._engine.setPatternFills_({key: pattern.cgColor for key, pattern in self._patterns.items()})
                    for block in self._blocks:
                        px_offset = self._to_px(block.offset)
                        px_offset.x -= block._shift
                        self._engine.drawGlyphsForGlyphRange_atPoint_(block._glyphs, px_offset)
                    self._engine.setPatternFills_(None)

    @property
    def path(self):
        """Traces the laid-out glyphs and returns them as a single Bezier object"""

        # generate an unflipped bezier with all the glyphs
        self._use_textkit()
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
        parent._use_textkit() # needs TextKit's layout
        self._parent = parent
        self.tag, self.attrs, self.parents = None, {}, ()
        self.m = None

        if isinstance(match, foundry.Slug): # via line_slugs()
            self.start, self.end = match.span
            self._slugs = [match]
        elif hasattr(match, 'range'): # NSSubText
            self.start, n = match.range()
            self.end = self.start + n
        elif isinstance(match, Element): # xml Element
            for k,v in match.__dict__.items():
                setattr(self, k, v)
        elif isinstance(match, TextBlock): # TextBlock
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
        indices = list(range(1, len(self.m.regs)))
        if not indices:
            return ()
        return tuple([m if m else default for m in self.group(*indices)])

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
    # a weak ref to the parent Text to avoid a reference cycle
    def _get_parent(self):
        return self._parent_ref() if self._parent_ref is not None else None
    def _set_parent(self, parent):
        self._parent_ref = None if parent is None else weakref.ref(parent)
    _parent = property(_get_parent, _set_parent)

    def __init__(self, parent):
        self._frame = Region((0,0), (None,None))
        self._grid = parent._grid # use the Text's or prior TextBlock's units

        # create a new container
        self._block = NSTextContainer.new()
        self._block.setLineFragmentPadding_(0)
        self._resized()

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
        (x, y), (w, h) = self._frame.origin, self.size
        parent = self._parent
        return Region(x + parent.x, y + parent.y - self._from_px(self._headroom), w, h)

    @property
    def bounds(self):
        """The position & size of the block's text in canvas coordinates"""
        self._parent._engine.glyphRangeForTextContainer_(self._block) # force layout & glyph gen
        origin, size = self._parent._engine.usedRectForTextContainer_(self._block)
        origin.x -= self._shift    # from container- to block-relative coords
        origin.y -= self._headroom # adjust for the ascent above baseline
        origin += self.offset + self._parent.baseline
        return self._from_px(Region(origin, size))

    @property
    def _fit(self):
        # the shrink-to-fit size in px
        self._parent._engine.glyphRangeForTextContainer_(self._block) # force layout & glyph gen
        size = self._parent._engine.usedRectForTextContainer_(self._block).size
        # add 1px of extra padding to the width (b/c believe it or not usedRectForTextContainer is buggy...)
        return Size(size.width + 1, size.height)

    @property
    def _shift(self):
        # where aligned lines sit in an unbounded container
        if self._frame.size.w:
            return 0
        anchor = {RIGHT:1.0, CENTER:0.5}.get(self._alignment)
        if not anchor:
            return 0
        return anchor * (self._block.containerSize().width - self._fit.width)

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
        # use Text's font metrics for empty text blocks
        parent = self._parent
        if not parent._store.length():
            return parent._font.ascender

        # otherwise use the font from the block's first glyph
        at = 0 if self is parent._blocks[0] else parent._engine.characterIndexForGlyphAtIndex_(self._glyphs.location)
        fnt, _ = parent._store.attribute_atIndex_effectiveRange_("NSFont", at, None)
        if not fnt:
            return parent._font.ascender
        return fnt.ascender()

    def _eject(self):
        idx = self._parent._engine.textContainers().index(self._block)
        self._parent._engine.removeTextContainerAtIndex_(idx)
        self._parent = None

    def _resized(self):
        # called by the FrameMixin when the w or h changed
        dims = [d or self._from_px(_UNLIMITED - 1) for d in self._frame.size] # just under it, so lines align
        self._block.setContainerSize_(self._to_px(Size(*dims)))

    def _get_offset(self):
        return Point(self._frame.origin)
    def _set_offset(self, dims):
        if numlike(dims):
            dims = [dims]*2
        self._frame.origin = dims
    offset = property(_get_offset, _set_offset)

    def _get_size(self):
        # unspecified dims shrink to fit
        w, h = self._frame.size
        if not (w and h):
            fit = self._from_px(self._fit)
            return Size(w or fit.w, h or fit.h)
        return Size(w, h)
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
