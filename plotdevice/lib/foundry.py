# encoding: utf-8
import os
import re
import objc
import difflib
from operator import itemgetter, attrgetter
from collections import namedtuple, OrderedDict as odict, defaultdict as ddict
from .cocoa import *
from ..util import numlike
import cFoundry

from plotdevice import DeviceError

__all__ = ["font_family", "font_encoding", "font_face", "best_face",
           "family_names", "family_members", "standardized", "sanitized",
           "fontspec", "line_metrics", "aat_attrs", "aat_features",
           ]

Face = namedtuple('Face', ['family', 'psname', 'weight','wgt', 'width','wid', 'variant', 'italic',])
LineFragment = namedtuple("LineFragment", ["bounds", "line", "baseline", "span", "text", "frame"])
Vandercook = objc.lookUpClass('Vandercook')

# introspection methods for postscript names/nsfonts

def font_names():
    return _fm.availableFonts()

def font_exists(fontname):
    """Return whether a font exists based on psname"""
    return fontname in _FAMILIES._hash

def font_family(psname):
    """Return family name given a psname"""
    if psname not in _FAMILIES._leafnodes:
        font = NSFont.fontWithName_size_(psname, 12)
        _FAMILIES._leafnodes[psname] = font.familyName()
    return _FAMILIES._leafnodes[psname]

def font_encoding(psname):
    """Return encoding name given a psname"""
    font = NSFont.fontWithName_size_(psname, 12)
    enc = font.mostCompatibleStringEncoding()
    enc_name = NSString.localizedNameOfStringEncoding_(enc)
    return re.sub(r' \(Mac OS.*?\)$', '', enc_name)

def font_face(psname):
    for face in family_members(font_family(psname)):
        if face.psname == psname:
            return face
    notfound = 'Font: no matches for Postscript name "%s"'%basis
    raise DeviceError(notfound)

# introspection methods for family names

def family_names():
    """A list of all families installed on the machine"""
    return _FAMILIES.names

def family_name(word):
    """Returns a valid family name if the arg fuzzy matches any existing families"""
    all_fams = family_names()
    word = re.sub(r'  +',' ',word.strip())
    q = sanitized(word)

    # use cached data if possible...
    if q not in _FAMILIES.query:

        # first try for an exact match
        if word in all_fams:
            return word

        # next do a case-insensitive, no-whitespace comparison
        corpus = sanitized(all_fams)
        if q in corpus:
            _FAMILIES.query[q] = all_fams[corpus.index(q)]
        elif q:
            # if still no match, compare against a list of names with all the noise words taken out
            corpus = debranded(all_fams, keep=branding(word))
            if word in corpus:
                _FAMILIES.query[q] = all_fams[corpus.index(word)]
            elif q in sanitized(corpus):
                # case-insensitive with the de-noised names
                _FAMILIES.query[q] = all_fams[sanitized(corpus).index(q)]

        if q not in _FAMILIES.query:
            # give up but first do a broad search and suggest other names in the exception
            in_corpus = difflib.get_close_matches(q, corpus, 4, cutoff=0)
            matches = [all_fams[corpus.index(m)] for m in in_corpus]
            nomatch = "ambiguous font family name \"%s\""%word
            if matches:
                nomatch += '.\nDid you mean: %s'%[m.encode('utf-8') for m in matches]
            _FAMILIES.query[q] = DeviceError(nomatch)

    matched = _FAMILIES.query[q]
    if isinstance(matched, Exception):
        raise matched
    return matched

def family_members(famname, names=False):
    """Returns a sorted list of Face tuples for the fonts in a family"""

    # use cached data if possible...
    if famname in _FAMILIES:
        if names:
            return [f[0] for f in _FAMILIES[famname]]
        else:
            return _FAMILIES[famname]

    # ...otherwise build the list of faces
    all_members = _fm.availableMembersOfFontFamily_(famname)
    if names:
        return [f[0] for f in all_members]

    # merge the apple-data and parsed-string info for each face
    fam = []
    for psname, dname, questionable_wgt, traits in all_members:
        weight, wgt, width, wid, var = parse_display_name(dname)
        traits = tuple([k for k,v in ns_traits.items() if v&traits])
        slanted = 'italic' in traits
        fam.append(Face(famname, psname, weight, wgt, width, wid, var, slanted))

    # if the font is totally nuts and doesn't have anything recognizable as a weight in
    # its name, pick one from the standard list based on the wgt value (because surely
    # that's set to something sane...)
    if not any(set(f.weight for f in fam)):
        fam = [f._replace(weight=std_weights[f.wgt][0].title()) for f in fam]


    # if something that looks like a weight pops up as a variant in a face, wipe it out
    seen_weights = filter(None, set(f.weight for f in fam))
    seen_vars = filter(None, set(f.variant for f in fam))
    iffy_vars = [v for v in seen_vars if v in seen_weights]
    for i,f in enumerate(fam):
        if f.variant in iffy_vars:
            fam[i] = f._replace(variant=None)

    # lots of times an italic in the ‘default’ weight will leave that out of its name.
    # fill this info back in by trying to match its wgt against other weights with
    # more verbose naming.
    same_slant = lambda x,y: x.italic==y.italic
    weightless = lambda: (f for f in fam if f.weight is None)
    weighted = lambda: (f for f in fam if f.weight is not None)

    if weightless():
        # built a wgt-val to weight-str lookup table
        wgt_map = ddict(set)
        for f in weighted():
            wgt_map[f.wgt].add(f.weight)
        wgt_map = {k:list(v) for k,v in wgt_map.items()}

        # if there's only one weight name for this wgt value, it's easy
        for i,f in enumerate(fam):
            if f not in weightless(): continue
            match = wgt_map.get(f.wgt,[])
            if len(match)==1:
                fam[i] = f._replace(weight=match[0])

        # otherwise try looking for open slots
        for i,f in enumerate(fam):
            if f not in weightless(): continue

            # start with the set of all faces with a named weight
            candidates = wgt_map.get(f.wgt,[])
            if not candidates:
                # if the wgt doesn't match any of them, go through them in
                # order of distance from the actual value
                for wgt in sorted(wgt_map.keys(), key=lambda x:abs(x-f.wgt)):
                    candidates.extend(wgt_map[wgt])
            others = [o for o in weighted() if o.weight in candidates]

            # try a strict comparison (vs italic) based on weightless face's width
            sibs = [o.weight for o in others if same_slant(o,f) and o.wid==f.wid]
            diff = [o.weight for o in others if not same_slant(o,f) and o.wid==f.wid]
            for candidate in candidates:
                if candidate in diff and candidate not in sibs:
                    fam[i] = f._replace(weight=candidate)
                    break
            else:
                # look outside of the current width, but try again to plug an italic/roman
                # hole in the lineup
                sibs = [o.weight for o in others if same_slant(o,f)]
                diff = [o.weight for o in others if not same_slant(o,f)]
                for candidate in candidates:
                    if candidate in diff and candidate not in sibs:
                        fam[i] = f._replace(weight=candidate)
                        break
                else:
                    if candidates:
                        # otherwise just use the weight that was closest to the wgt number
                        fam[i] = f._replace(weight=candidates[0])
                    else:
                        # or give up utterly
                        fam[i] = f._replace(weight='Regular')

    # save the collection to the cache before returning it
    _FAMILIES[famname] = sorted(fam, key=attrgetter('italic','wid','wgt'))
    return _FAMILIES[famname]

def best_face(spec):
    """Returns the PostScript name of the best match for a given fontspec"""

    _canon = ('family','weight','italic','width','variant')
    q = hash(tuple(spec[k] for k in _canon))
    if q in _FAMILIES.face:
        return font_face(_FAMILIES.face[q])

    # the candidates
    faces = family_members(spec['family'])

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

    _FAMILIES.face[q] = candidates[0]['ps']
    return font_face(_FAMILIES.face[q])

# typography arg validators/standardizers

def fontspec(*args, **kwargs):
    # convert any bytestrings to unicode (presuming utf8 everywhere)
    for k,v in kwargs.items():
        if isinstance(v, str):
            kwargs[k] = v.decode('utf-8')
    args = [v.decode('utf-8') if isinstance(v,str) else v for v in args]

    # start with kwarg values as the canonical settings
    _canon = ('family','size','weight','italic','width','variant')
    spec = {k:v for k,v in kwargs.items() if k in _canon}

    # be backward compatible with the old arg names
    if 'fontsize' in kwargs:
        spec.setdefault('size', kwargs['fontsize'])
    if 'italic' in spec:
        spec['italic'] = bool(spec['italic'])
    if 'family' in spec:
        spec['family'] = family_name(spec['family'])

    # validate the weight and width args (if any)
    if not weighty(spec.get('weight','regular')):
        print 'Font: unknown weight "%s"' % spec.pop('weight')
    if not widthy(spec.get('width','condensed')) and spec.get('width') is not None:
        print 'Font: unknown width "%s"' % spec.pop('width')

    # look for a postscript name passed as `face` or `fontname` and validate it
    basis = kwargs.get('face', kwargs.get('fontname'))
    if basis and not font_exists(basis):
        notfound = 'Font: no matches for Postscript name "%s"'%basis
        raise DeviceError(notfound)
    elif basis:
        # if the psname exists, inherit its attributes
        face = font_face(basis)
        for axis in ('family','weight','width','variant','italic'):
            spec.setdefault(axis, getattr(face, axis))

    # search the positional args for either name/size or a Font object
    # we want the kwargs to have higher priority, so setdefault everywhere...
    for item in args:
        if hasattr(item, '_spec'):
            # existing Font object
            for k,v in item._spec.items():
                spec.setdefault(k,v)
        elif isinstance(item, unicode):
            # name-like values
            if fammy(item):
                spec.setdefault('family', family_name(item))
            elif widthy(item):
                spec.setdefault('width', item)
            elif weighty(item):
                spec.setdefault('weight', item)
            else:
                family_name(item) # raise an exception suggesting family names
        elif numlike(item) and 'size' not in kwargs:
            spec['size'] = float(item)

    # incorporate line- and character-typesetting features
    spec.update(line_metrics(kwargs))
    spec.update(aat_features(kwargs))
    return spec

def line_metrics(spec):
    # start with kwarg values as the canonical settings
    _canon = ('size','align','leading','tracking','hyphenate')
    spec = {k:v for k,v in spec.items() if k in _canon}

    # validate alignment
    if spec.get('align','left') not in ('left','right','center','justify'):
        chaoticneutral = 'Text alignment must be LEFT, RIGHT, CENTER, or JUSTIFY'
        raise DeviceError(chaoticneutral)

    # floatify dimensions and hyphenation (mapping bools to 0/1)
    for attr in 'size', 'leading', 'tracking', 'hyphenate':
        if attr in spec:
            spec[attr] = float(spec[attr])

    # be backward compatible with the old arg names
    if 'lineheight' in spec:
        spec.setdefault('leading', spec['lineheight'])
    return spec

def aat_features(spec):
    """Validate features in a Font spec and normalize settings values"""
    features = {}

    for k,v in spec.items():
        if k=='ss':
            # unpack & validate the ss arg (which might be a sequence of ints)
            ss = (int(v),) if numlike(v) or isinstance(v, bool) else v
            if ss is None or ss==(0,):
                features['ss'] = tuple()
            elif ss is all:
                features['ss'] = tuple(range(1,21))
            else:
                try:
                    if not all([numlike(val) and 0<val<21 for val in ss]):
                        raise TypeError()
                    features['ss'] = tuple(set(int(n) for n in ss))
                except TypeError:
                    badset = 'The `ss` argument must be an integer in the range 1-20 or a list of them (not %s)' % repr(ss)
                    raise DeviceError(badset)
        elif k in aat_options:
            # with all the other features, just check that the arg value is in the dict
            try:
                aat_options[k][v] # crash if argname or val is invalid
                features[k] = int(v) if not callable(v) else v
            except KeyError:
                badstyle = 'Bad `%s` argumeent: %r'%(k,v)
                raise DeviceError(badstyle)
    return features

aat_options = {
    "lig":{
        0:[("Ligatures", "CommonOff"), ("Ligatures", "RareOff")],
        1:[("Ligatures", "CommonOn")],
        all:[("Ligatures", "CommonOn"), ("Ligatures", "RareOn")],
    },

    "sc":{
        0:[("LowerCase", "DefaultCase"), ("UpperCase", "DefaultCase")],
        1:[("LowerCase", "SmallCaps")],
        all:[("LowerCase", "SmallCaps"), ("UpperCase", "SmallCaps")],
        -1:[("UpperCase", "SmallCaps")],
    },

    "osf":{
        0:[("NumberCase", "UpperCaseNumbers")],
        1:[("NumberCase", "LowerCaseNumbers")],
    },

    "tab":{
        0:[("NumberSpacing", "Proportional")],
        1:[("NumberSpacing", "Monospaced")],
    },

    "frac":{
        0:[("Fractions", "NoFractions")],
        1:[("Fractions", "Diagonal")],
    },

    "vpos":{
        1:[("VerticalPosition", "Superiors")],
        0:[("VerticalPosition", "NormalPosition")],
        -1:[("VerticalPosition", "Inferiors")],
        ord:[("VerticalPosition", "Ordinals")]
    },

    "ss":{n:[('Alternates', n)] for n in range(1,21)}
}


# objc-bridged methods for generating beziers from glyphs, measuring text runs, and AAT-styling

def trace_text(frame):
    """Returns an NSBezierPath with the glyphs contained by a TextFrame object"""
    # assemble the glyphs in px units then transform them back to screen units
    # (since whatever Bezier it's appended to will handle screen->px conversion)
    offset = frame._to_px(frame.offset)
    nspath = Vandercook.traceGlyphs_atOffset_withLayout_(frame._glyphs, offset, frame._parent._layout)
    return frame._from_px(nspath)

def line_fragments(txt_obj, rng=None):
    """Returns a list of dictionaries describing the line fragments in the entire Text object
    or a sub-range of it based on character indices"""
    if rng is None:
        rng = (0, len(txt_obj.text))

    lines = []
    for frag in Vandercook.lineFragmentsInRange_withLayout_(rng, txt_obj._layout):
        frame = txt_obj._frames[frag['frame']]
        txt_range = frag['range'].rangeValue()
        info = {
            "line":frame._from_px(frag['line'].rectValue()),
            "bounds":frame._from_px(frag['bounds'].rectValue()),
            "baseline":frame._from_px(frag['baseline'].pointValue()),
            "span":(txt_range.location, txt_range.location+txt_range.length),
            "text":frag['text'],
        }

        txt_offset = (txt_obj.x, txt_obj.y-txt_obj.baseline)
        info['baseline'] += frame.offset + txt_offset
        info['line'].origin += frame.offset + txt_offset
        info['bounds'].origin += frame.offset + txt_offset
        info['frame'] = frame
        lines.append(LineFragment(**info))

    return lines

def aat_attrs(spec):
    """Converts a validated features spec to a dict suitable for NSFontDescriptor"""
    settings = []
    for k,v in spec.items():
        if k not in aat_options: continue
        for vv in (v,) if not isinstance(v, tuple) else v:
            settings += aat_options[k][vv]
    return Vandercook.aatAttributes_(settings)

# sausage gets made below:

_fm = NSFontManager.sharedFontManager()
re_italic = re.compile(r'^(?:(italic|oblique|slanted)|it(a(l(ics?)?)?)?)$', re.I)
ns_traits = {"bold":2,"compressed":512,"condensed":64,"expanded":32,"fixedpitch":1024,"italic":1,"narrow":16,"nonstandardcharset":8,"poster":256,"smallcaps":128,"unbold":4,"unitalic":16777216}
std_branding = 'adobe','std','pro','mt','ms','itc','let','tt'
std_weights = [
   [], ["ultralight"], ["thin"], ["light", "extralight"],
   ["book"], ["regular", "plain", "roman"], ["medium"],
   ["demi", "demibold"], ["semi", "semibold"], ["bold"],
   ["extra", "extrabold"], ["heavy", "heavyface"], ["black", "super", "superbold"],
   ["extrablack", "ultra", "ultrabold", "fat"], ["ultrablack", "obese", "nord"]
]
wgt_mods = ["demi","semi","extra","super","ultra"]
wgt_corpus = [w for group in std_weights for w in group]


wid_mods = ['semi', None, 'extra','super','ultra']
wid_steps = ['compressed','narrow','condensed', None, 'extended','expanded','wide']
wid_abbrevs = dict(cond='Condensed', comp='Compressed', compr='Compressed', ext='Extended')
wid_corpus  = [(prefix or '')+w for w in wid_steps[:wid_steps.index(None)] for prefix in reversed(wid_mods)]
wid_corpus += [(prefix or '')+w for w in wid_steps[wid_steps.index(None)+1:] for prefix in wid_mods]

def _sanitize(s):
    return s.strip().lower().replace('-','').replace(' ','') if s else None

def sanitized(unclean):
    if isinstance(unclean, dict):
        return {_sanitize(k):v for k,v in unclean.items()}
    elif isinstance(unclean, (list,tuple)):
        return [_sanitize(s) for s in unclean]
    else:
        return _sanitize(unclean)

def fammy(word):
    try:
        family_name(word)
    except DeviceError:
        return False
    return True

def facey(word):
    if word in _fm.availableFontFamilies():
        return False
    return word in _fm.availableFonts() or NSFont.fontWithName_size_(word,9)

def widthy(word):
    return sanitized(word) in wid_corpus+wid_abbrevs.keys()

def weighty(word):
    return sanitized(word) in wgt_corpus

def italicky(word, strict=False):
    m = re_italic.search(word)
    if m and not strict:
        return True
    elif m and m.group(1):
        return True
    return False

def branding(name):
    return [bit for bit in name.split(' ') if sanitized(bit) in std_branding]

def debranded(name, keep=[]):
    if isinstance(name, (list, tuple)):
        return [debranded(n, keep) for n in name]
    terms = []
    kill_list = set(std_branding).difference(keep)
    return ' '.join([bit for bit in name.split(' ') if sanitized(bit) not in kill_list])

def standardized(axis, val):
    # take a weight/width string value and harmonize it with the standard names
    # returns a (str,int) tuple with the values for the axis
    if axis=='weight':
        weight = sanitized(val)
        if weight in wgt_corpus:
            if weight in wgt_mods:
                weight+='bold'
            for i,names in enumerate(std_weights):
                if weight in names:
                    return weight.title(), i
            print weight, 'not in', std_weights
    elif axis=='width':
        width = sanitized(val)
        width = sanitized(wid_abbrevs.get(width, width))
        if width is None:
            return None, 0
        if width in wid_corpus:
            midpoint = wid_corpus.index('semiextended')
            idx = wid_corpus.index(width) - midpoint
            idx += 0 if idx<0 else 1
            return width.title(), idx
        else:
            print [width],"not in", wid_corpus

def parse_display_name(dname):
    """Try to extract style attributes from the font's display name"""
    # break the string on spaces and on lc/uc transitions
    elts = filter(None, re.sub(r'(?<=[^ ])([A-Z][a-z]+)',r' \1',dname).split(' '))

    # disregard the first italic-y word in the name (if any)
    for i in xrange(len(elts)-1,-1,-1):
        # look for full italic/oblique/slanted spellings first
        if italicky(elts[i], strict=True):
            elts.pop(i)
            break
    else:
        # if one wasn't found, settle for an it/a/l/ic/s fragment
        for i in xrange(len(elts)-1,-1,-1):
            if italicky(elts[i], strict=False):
                elts.pop(i)
                break

    # next search for width-y words
    width = None
    wid_val = 0
    for i in xrange(len(elts)-2,-1,-1):
        # first look for modifier+width combinations
        prefix, suffix = elts[i:i+2]
        if widthy(prefix+suffix) and sanitized(prefix) in wid_mods:
            if sanitized(prefix)=='semi':
                width = prefix + suffix.lower()
            else:
                width = " ".join([prefix,suffix])
            _, wid_val = standardized('width', width)
            del elts[i:i+2]
            break
    else:
        # otherwise just look for a single-word width (leave width==None if no match)
        for i in xrange(len(elts)-1,-1,-1):
            if widthy(elts[i]):
                width = elts[i]
                _, wid_val = standardized('width', width)
                elts.pop(i)
                break
        else:
            wid_val = 0

    # search for weighty words in what's left
    weight = None
    wgt_val = 5
    for i in xrange(len(elts)-2,-1,-1):
        # first look for modifier+weight combinations
        prefix, suffix = elts[i:i+2]
        if weighty(prefix+suffix) and sanitized(prefix) in wgt_mods:
            spacer = '' if prefix.lower() in ('semi','demi') else ' '
            weight = spacer.join([prefix,suffix]).title()
            _, wgt_val = standardized('weight', weight)
            del elts[i:i+2]
            break
    else:
        # otherwise just look for a single-word weight (leave weight==None if no match)
        for i in xrange(len(elts)-1,-1,-1):
            if weighty(elts[i]):
                weight = elts[i]
                _, wgt_val = standardized('weight', weight)
                # the standard weights allow leaving out the `bold' and just using
                # a modifier name. fill that back in...
                if sanitized(weight) in wgt_mods:
                    suffix = 'bold' if sanitized(weight) in ('semi','demi') else ' Bold'
                    weight += suffix
                elts.pop(i)
                break

    # concat all the non-filtered text as the `variant`
    variant = None
    if elts:
        variant = "".join(elts)

    return weight, wgt_val, width, wid_val, variant

class FontLibrary(object):
    """Caches any families assembled by familiy_members. Watches NSFontManager for invalidation."""
    def __init__(self):
        self._lib = {}
        self._hash = _fm.availableFonts()
        self._names = sorted(_fm.availableFontFamilies())
        self._leafnodes = {} # map psnames to family names
        self._encodings = {} # map psnames to localized encoding strings
        self.query = {} # map fammy names to canonical family names
        self.face = {} # map fontspecs to psnames

    @property
    def names(self):
        self.refresh()
        return self._names[:]

    def __contains__(self, key):
        self.refresh()
        return key in self._lib

    def __getitem__(self, key):
        self.refresh()
        return self._lib[key]

    def __setitem__(self, key, val):
        self._lib[key] = val

    def refresh(self):
        if self._hash != _fm.availableFonts():
            self.__init__()

_FAMILIES = FontLibrary()
