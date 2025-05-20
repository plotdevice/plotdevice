# encoding: utf-8
import os, sys, re
from operator import attrgetter

# files & io
from io import open, StringIO, BytesIO
from os.path import abspath, dirname, exists, join, splitext, expanduser
from plotdevice import DeviceError, INTERNAL

# data formats
import json, csv
from collections import defaultdict
from dataclasses import make_dataclass, replace
from codecs import iterencode, iterdecode
from xml.parsers import expat

# http
from urllib.parse import urlparse
from Foundation import NSDateFormatter, NSLocale, NSTimeZone, NSDate


### XML handling ###

Element = make_dataclass('Element', ['tag', 'attrs', 'parents', 'start', 'end'])
escapes = [('break','0C'), ('indent', '09'), ('flush', '08')]
doctype = '<!DOCTYPE plod [ %s ]>' % "".join(['<!ENTITY %s "&#xE0%s;" >'%e for e in escapes])
HEAD = "%s<%s>" % (doctype, INTERNAL)
TAIL = "</%s>" % INTERNAL
class XMLParser(object):
    _log = 0

    def __init__(self, txt, offset=0):
        # configure the parsing machinery/callbacks
        p = expat.ParserCreate()
        p.StartElementHandler = self._enter
        p.EndElementHandler = self._leave
        p.CharacterDataHandler = self._chars
        self._expat = p

        # shift the range values in .nodes by offset (in case we're appending)
        self._offset = offset

        # set up state attrs to record the parse results
        self.stack = []
        self.cursor = offset
        self.regions = defaultdict(list)
        self.nodes = defaultdict(list)
        self.body = []

        # wrap everything in a root node (and include the whitespace entities which shift
        # the tty escapes into the unicode PUA for the duration)
        if isinstance(txt, str):
            txt = txt.encode('utf-8')
        self._xml = HEAD.encode('utf-8') + txt + TAIL.encode('utf-8')

        # parse the input xml string
        try:
            self._expat.Parse(self._xml, True)
        except expat.ExpatError as e:
            self._expat_error(e)

    @property
    def text(self):
        # returns the processed string (with all markup removed and tty-escapes un-shifted)
        return "".join(self.body).translate({0xE000+v:v for v in (8,9,12)})

    def _expat_error(self, e):
        # correct the column and line-string for our wrapper element
        col = e.offset
        err = "\n".join(e.args)
        line = self._xml.decode('utf-8').split("\n")[e.lineno-1]
        if line.startswith(HEAD):
            line = line[len(HEAD):]
            col -= len(HEAD)
            err = re.sub(r'column \d+', 'column %i'%col, err)
        if line.endswith(TAIL):
            line = line[:-len(TAIL)]

        # move the column range with the typo into `measure` chars
        measure = 80
        snippet = line
        if col>measure:
            snippet = snippet[col-measure:]
            col -= col-measure
        snippet = snippet[:max(col+12, measure-col)]
        col = min(col, len(snippet))

        # show which ends of the line are truncated
        clipped = [snippet]
        if not line.endswith(snippet):
            clipped.append('...')
        if not line.startswith(snippet):
            clipped.insert(0, '...')
            col+=3
        caret = ' '*(col-1) + '^'

        # raise the exception
        msg = 'Text: ' + err
        stack = 'stack: ' + " ".join(['<%s>'%elt.tag for elt in self.stack[1:]]) + ' ...'
        xmlfail = "\n".join([msg, "".join(clipped), caret, stack])
        raise DeviceError(xmlfail)

    def log(self, s=None, indent=0):
        if not isinstance(s, str):
            if s is None:
                return self._log
            self._log = int(s)
            return
        if not self._log: return
        if indent<0: self._log-=1
        msg = ('  '*self._log)+(s if s.startswith('<') else repr(s)[1:])
        print((msg.encode('utf-8')))
        if indent>0: self._log+=1

    def _enter(self, name, attrs):
        parents = tuple(reversed([e.tag for e in self.stack[1:]]))
        elt = Element(name, attrs, parents, self.cursor, end=None)
        self.stack.append(elt)
        self.log('<%s>'%(name), indent=1)

    def _chars(self, data):
        selector = tuple([e.tag for e in self.stack])

        # handle special case where a self-closed tag precedes a '\n'
        if hasattr(self, '_crlf'):
            if data == "\n":
                selector = selector + (self._crlf.tag,)
            del self._crlf

        self.regions[selector].append(tuple([self.cursor-self._offset, len(data)]))
        self.cursor += len(data)
        self.body.append(data)
        self.log(data)

    def _leave(self, name):
        node = replace(self.stack.pop(), end=self.cursor)

        # hang onto line-ending self-closed tags so they can be applied to the next '\n' in _chars
        if node.start==node.end:
            at = self._expat.CurrentByteIndex
            if self._xml[at-2:at]=='/>' and self._xml[at:at+1]=="\n":
                node = replace(node, end=node.start+1)
                self._crlf = node

        self.nodes[name].append(node)
        self.log('</%s>'%(name), indent=-1)

        # if we've exited the root node, clean up the parsed elements
        if name == INTERNAL:
            del self.nodes[INTERNAL]
            self.nodes = {tag:sorted(elts, key=attrgetter('start')) for tag,elts in self.nodes.items()}


### CSV unpacking ###

def csv_rows(file_obj, dialect=csv.excel, **kwargs):
    csvreader = csv.reader(file_obj, dialect=dialect, **kwargs)
    for row in csvreader:
        yield row

def csv_dict(file_obj, dialect=csv.excel, cols=None, dict=dict, **kwargs):
    if not isinstance(cols, (list, tuple)):
        cols=None
    for row in csv_rows(file_obj, dialect, **kwargs):
        if not cols:
          cols = row
          continue
        yield dict(list(zip(cols,row)))

def csv_tuple(file_obj, dialect=csv.excel, cols=None, **kwargs):
    spaced = lambda a: [s.strip().replace(' ', '_') for s in a] if a else a

    if isinstance(cols, (list, tuple)):
        Row = make_dataclass('Row', spaced(cols))
    else:
        cols = None

    for row in csv_rows(file_obj, dialect, **kwargs):
        if not cols:
            cols = spaced(row)
            Row = make_dataclass('Row', cols)
            continue
        yield Row(**dict(list(zip(cols, row))))

def csv_dialect(fd):
    snippet = fd.read(1024)
    fd.seek(0)
    return csv.Sniffer().sniff(snippet)


### HTTP utils ###

HTTP = None

def get_http_session():
    """Returns a cached HTTP session (creating it if necessary)"""
    global HTTP
    if HTTP is None:
        try:
            from cachecontrol import CacheControl
            from cachecontrol.caches import FileCache
            from cachecontrol.heuristics import LastModified
            import requests
            
            cache_dir = join(expanduser('~'), 'Library/Caches/PlotDevice')
            HTTP = CacheControl(requests.Session(), 
                              cache=FileCache(cache_dir), 
                              heuristic=LastModified())
        except ImportError as e:
            raise ImportError("HTTP dependencies not available. Install with: pip install requests cachecontrol[filecache]") from e
    return HTTP

def binaryish(content, format):
    bin_types = ('pdf','eps','png','jpg','jpeg','heic','gif','tiff','tif','zip','tar','gz')
    bin_formats = ('raw','bytes','img','image')
    if any(b in content for b in bin_types):
        return True
    if format:
        return any(b in format for b in bin_types+bin_formats)
    return False

_nsdf = NSDateFormatter.alloc().init()
_nsdf.setLocale_(NSLocale.alloc().initWithLocaleIdentifier_("en_US_POSIX"))
_nsdf.setDateFormat_("EEE',' dd' 'MMM' 'yyyy HH':'mm':'ss zzz")
_nsdf.setTimeZone_(NSTimeZone.timeZoneForSecondsFromGMT_(0))

def last_modified(resp):
    """Return the last modified date as a unix time_t"""
    last_mod = _nsdf.dateFromString_(resp.headers.get('Last-Modified'))
    if not last_mod:
        last_mod = NSDate.date()
    return last_mod.timeIntervalSince1970()


### File/URL Reader ###

def read(pth, format=None, encoding=None, cols=None, **kwargs):
    """Returns the contents of a file into a string or format-dependent data
    type (with special handling for json and csv files).

    The format will either be inferred from the file extension or can be set
    explicitly using the `format` arg. Text will be read using the specified
    `encoding` or default to UTF-8.

    JSON files will be parsed and an appropriate python type will be selected
    based on the top-level object defined in the file. The optional keyword
    argument `dict` can be set to `adict` or `odict` if you'd prefer not to use
    the standard python dictionary for decoded objects.

    CSV files will return a list of rows. By default each row will be an ordered
    list of column values. If the first line of the file defines column names,
    you can call read() with cols=True in which case each row will be a dataclass
    using those names as keys. If the file doesn't define its own column names,
    you can pass a list of strings as the `cols` parameter. Rows can be formatted
    as column-keyed dictionaries by passing True as the `dict` parameter.
    """

    if re.match(r'https?:', pth):
        session = get_http_session()  # Get the session only when needed
        resp = session.get(pth)
        resp.raise_for_status()

        extension_type = splitext(urlparse(pth).path)[-1]
        content_type = resp.headers.get('content-type', extension_type).lower()

        for data_t in ['json', 'csv']:
            if data_t in content_type:
                extension_type = data_t

        if binaryish(content_type, format):
            fd = BytesIO(resp.content)
        else:
            if encoding:
                resp.encoding = encoding
            elif 'charset' not in content_type:
                resp.encoding = resp.apparent_encoding
            fd = StringIO(resp.text)
    else:
        enc = encoding or 'utf-8'
        extension_type = splitext(pth)[-1].lower()

        if binaryish(extension_type, format):
            fd = open(os.path.expanduser(pth), 'rb')
        else:
            fd = open(os.path.expanduser(pth), 'rt', encoding=enc)

    if kwargs.get('dict') is True:
        kwargs['dict'] = dict
    elif kwargs.get('dict') is False:
        del kwargs['dict']
    dict_type = kwargs.get('dict', dict)
    format = (format or extension_type).lstrip('.')

    if format=='json':
        return json.load(fd, object_pairs_hook=dict_type)
    elif format=='csv':
        dialect = csv_dialect(fd)
        if cols:
            if kwargs.get('dict'):
                return list(csv_dict(fd, dialect=dialect, cols=cols, dict=dict_type))
            else:
                return list(csv_tuple(fd, dialect=dialect, cols=cols))
        return list(csv_rows(fd, dialect=dialect))
    else:
        return fd.read()

