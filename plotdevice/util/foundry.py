# encoding: utf-8
import os
import re
import difflib
from pprint import pprint, pformat
from operator import itemgetter, attrgetter
from collections import namedtuple, Counter, OrderedDict as odict, defaultdict as ddict
from ..lib.cocoa import *

from plotdevice import DeviceError

__all__ = ["standardized", "sanitized", "fammy", "facey", "widthy", "weighty",
           "font_exists", "font_family", "font_encoding", "font_face",
           "family_names", "family_name", "family_members", "Face"]

Face = namedtuple('Face', ['family', 'psname', 'weight','wgt', 'width','wid', 'variant', 'italic', 'traits'])

# introspection methods for postscript names/nsfonts

def nsfont(func):
    return lambda font:func(font if isinstance(font, NSFont) else NSFont.fontWithName_size_(font, 12))

def psfont(func):
    return lambda font:func(font.fontName() if isinstance(font, NSFont) else font)

def font_names():
    return _fm.availableFonts()

@psfont
def font_exists(fontname):
    """Return whether a font exists based on psname"""
    f = NSFont.fontWithName_size_(fontname, 12)
    return f is not None

@nsfont
def font_family(font):
    """Return family name given a psname or nsfont"""
    return font.familyName()

@nsfont
def font_encoding(font):
    """Return encoding name given a psname or nsfont"""
    mask = font.mostCompatibleStringEncoding()
    for nm,val in ns_encodings.items():
        if mask==val: return nm
    for nm,val in cf_encodings.items():
        if mask==val: return nm
    return None

@nsfont
def font_face(font):
    for face in family_members(font.familyName()):
        if face.psname == font.fontName():
            return face
    notfound = 'Font: no matches for Postscript name "%s"'%basis
    raise DeviceError(notfound)

# introspection methods for family names

def family_names():
    """A list of all families installed on the machine"""
    return sorted(_fm.availableFontFamilies())

def family_name(word):
    """Returns a valid family name if the arg fuzzy matches any existing families"""
    all_fams = family_names()
    word = re.sub(r'  +',' ',word.strip())
    q = sanitized(word)

    # first try for an exact match
    if word in all_fams:
        return word

    # next do a case-insensitive, no-whitespace comparison
    corpus = sanitized(all_fams)
    if q in corpus:
        return all_fams[corpus.index(q)]

    # if still no match, compare against a list of names with all the noise words taken out
    corpus = debranded(all_fams, keep=branding(word))
    if word in corpus:
        return all_fams[corpus.index(word)]

    # case-insensitive with the de-noised names
    # corpus = sanitized(corpus)
    if q in sanitized(corpus):
        return all_fams[sanitized(corpus).index(q)]

    # otherwise look for near matches above a reasonable cutoff
    q, corpus = word.lower(), [f.lower() for f in corpus]
    in_corpus = difflib.get_close_matches(q, corpus, cutoff=0.6)
    matches = [all_fams[corpus.index(m)] for m in in_corpus]

    for m in matches:
        # look for whole substring
        if sanitized(q) in sanitized(m):
            return m
        # bug: this means 'univers' will match 'Univers LT Std' even though "Univers Next" is comparable....
        #      should only accept it if it's not `really' ambiguous (i.e. len(q in matches)==1)

    word_bits = set(word.lower().split(' '))
    for m in matches:
        # look for all the individual words (ignoring order)
        if word_bits.issubset(m.lower().split(' ')):
            return m

    # give up but first do a broad search and suggest other names in the exception
    in_corpus = difflib.get_close_matches(q, corpus, 4, cutoff=0)
    matches = [all_fams[corpus.index(m)] for m in in_corpus]
    nomatch = "ambiguous family name \"%s\""%word
    if matches:
        nomatch += '.\nDid you mean: %s'%[m.encode('utf-8') for m in matches]
    raise DeviceError(nomatch)

def family_members(famname, names=False):
    """Returns a sorted list of Face tuples for the fonts in a family"""

    # use cached data if possible...
    if famname in _FAMILIES:
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
        fam.append(Face(famname, psname, weight, wgt, width, wid, var, slanted, traits))

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
    same_slant = lambda x,y: ('italic' in x.traits)==('italic' in y.traits)
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

# sausage gets made below:

_fm = NSFontManager.sharedFontManager()
re_italic = re.compile(r'^(?:(italic|oblique|slanted)|it(a(l(ics?)?)?)?)$', re.I)
cf_encodings = {"DOSJapanese":8,"EUC_JP":3,"ISOLatin2":9,"ISO_2022_JP":21,"MacSymbol":6,"WindowsCyrillic":11,"WindowsGreek":13,"WindowsLatin2":15,"WindowsLatin5":14}
cf_encodings.update({k:v|(2**31) for k,v in {"ANSEL":1537,"Big5":2563,"Big5_E":2569,"Big5_HKSCS_1999":2566,"CNS_11643_92_P1":1617,"CNS_11643_92_P2":1618,"CNS_11643_92_P3":1619,"DOSArabic":1049,"DOSBalticRim":1030,"DOSCanadianFrench":1048,"DOSChineseSimplif":1057,"DOSChineseTrad":1059,"DOSCyrillic":1043,"DOSGreek":1029,"DOSGreek1":1041,"DOSGreek2":1052,"DOSHebrew":1047,"DOSIcelandic":1046,"DOSKorean":1058,"DOSLatin1":1040,"DOSLatin2":1042,"DOSLatinUS":1024,"DOSNordic":1050,"DOSPortuguese":1045,"DOSRussian":1051,"DOSThai":1053,"DOSTurkish":1044,"EBCDIC_CP037":3074,"EBCDIC_US":3073,"EUC_CN":2352,"EUC_KR":2368,"EUC_TW":2353,"GBK_95":1585,"GB_18030_2000":1586,"GB_2312_80":1584,"HZ_GB_2312":2565,"ISOLatin10":528,"ISOLatin3":515,"ISOLatin4":516,"ISOLatin5":521,"ISOLatin6":522,"ISOLatin7":525,"ISOLatin8":526,"ISOLatin9":527,"ISOLatinArabic":518,"ISOLatinCyrillic":517,"ISOLatinGreek":519,"ISOLatinHebrew":520,"ISOLatinThai":523,"ISO_2022_CN":2096,"ISO_2022_CN_EXT":2097,"ISO_2022_JP_1":2082,"ISO_2022_JP_2":2081,"ISO_2022_JP_3":2083,"ISO_2022_KR":2112,"JIS_C6226_78":1572,"JIS_X0201_76":1568,"JIS_X0208_83":1569,"JIS_X0208_90":1570,"JIS_X0212_90":1571,"KOI8_R":2562,"KOI8_U":2568,"KSC_5601_87":1600,"KSC_5601_92_Johab":1601,"MacArabic":4,"MacArmenian":24,"MacBengali":13,"MacBurmese":19,"MacCeltic":39,"MacCentralEurRoman":29,"MacChineseSimp":25,"MacChineseTrad":2,"MacCroatian":36,"MacCyrillic":7,"MacDevanagari":9,"MacDingbats":34,"MacEthiopic":28,"MacExtArabic":31,"MacFarsi":140,"MacGaelic":40,"MacGeorgian":23,"MacGreek":6,"MacGujarati":11,"MacGurmukhi":10,"MacHFS":255,"MacHebrew":5,"MacIcelandic":37,"MacInuit":236,"MacJapanese":1,"MacKannada":16,"MacKhmer":20,"MacKorean":3,"MacLaotian":22,"MacMalayalam":17,"MacMongolian":27,"MacOriya":12,"MacRomanLatin1":2564,"MacRomanian":38,"MacSinhalese":18,"MacTamil":14,"MacTelugu":15,"MacThai":21,"MacTibetan":26,"MacTurkish":35,"MacUkrainian":152,"MacVT100":252,"MacVietnamese":30,"NextStepJapanese":2818,"ShiftJIS":2561,"ShiftJIS_X0213":1576,"ShiftJIS_X0213_00":1576,"ShiftJIS_X0213_MenKuTen":1577,"UTF7":67109120,"UTF7_IMAP":2576,"VISCII":2567,"WindowsArabic":1286,"WindowsBalticRim":1287,"WindowsHebrew":1285,"WindowsKoreanJohab":1296,"WindowsVietnamese":1288}.items()})
ns_encodings = {"ASCII":1,"ISO2022JP":21,"ISOLatin1":5,"ISOLatin2":9,"JapaneseEUC":3,"MacOSRoman":30,"NEXTSTEP":2,"NonLossyASCII":7,"Proprietary":65536,"ShiftJIS":8,"Symbol":6,"UTF16BigEndian":0x90000100,"UTF16LittleEndian":0x94000100,"UTF32":0x8c000100,"UTF32BigEndian":0x98000100,"UTF32LittleEndian":0x9c000100,"UTF8":4,"Unicode":10,"WindowsCP1250":15,"WindowsCP1251":11,"WindowsCP1252":12,"WindowsCP1253":13,"WindowsCP1254":14}
ns_traits = {"bold":2,"compressed":512,"condensed":64,"expanded":32,"fixedpitch":1024,"italic":1,"narrow":16,"nonstandardcharset":8,"poster":256,"smallcaps":128,"unbold":4,"unitalic":16777216}
std_branding = 'adobe','std','pro','mt','ms','itc','let','tt'
std_weights = [
   [], ["ultralight"], ["thin"], ["light", "extralight"],
   ["book"], ["regular", "plain", "roman"], ["medium"],
   ["demi", "demibold"], ["semi", "semibold"], ["bold"],
   ["extra", "extrabold"], ["heavy", "heavyface"], ["black", "super", "superbold"],
   ["extrablack", "ultra", "ultrabold", "fat"], ["ultrablack", "obese", "nord"]
]

wid_mods = ['semi', None, 'extra','super','ultra']
wid_steps = ['compressed','narrow','condensed', None, 'extended','expanded','wide']
wid_abbrevs = dict(cond='Condensed', comp='Compressed', compr='Compressed', ext='Extended')
wid_corpus  = [(prefix or '')+w for w in wid_steps[:wid_steps.index(None)] for prefix in reversed(wid_mods)]
wid_corpus += [(prefix or '')+w for w in wid_steps[wid_steps.index(None)+1:] for prefix in wid_mods]

wgt_mods = ["demi","semi","extra","super","ultra"]
wgt_corpus = [w for group in std_weights for w in group]

_sanitize = lambda s:s.strip().lower().replace('-','').replace(' ','') if s else None
def sanitized(unclean):
    if isinstance(unclean, dict):
        return {_sanitize(k):v for k,v in unclean.items()}
    single = not isinstance(unclean, (list,tuple))
    lst = [unclean] if single else unclean
    cleaned = [_sanitize(s) for s in lst]
    return cleaned[0] if single else cleaned

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
