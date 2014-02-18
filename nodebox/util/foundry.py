# encoding: utf-8
import os
from operator import itemgetter
from collections import OrderedDict as odict
from AppKit import *
from Foundation import *

# introspection methods for postscript names/nsfonts

def font_exists(fontname):
    f = NSFont.fontWithName_size_(fontname, 12)
    return f is not None

def font_family(font):
    if isinstance(font, basestring):
        font = NSFont.fontWithName_size_(font, 12)
    return font.familyName()

def font_italicized(font):
    if isinstance(font, basestring):
        font = NSFont.fontWithName_size_(font, 12)
    return bool(_fm.traitsOfFont_(font) & NSItalicFontMask)

def font_weight(font):
    if isinstance(font, basestring):
        font = NSFont.fontWithName_size_(font, 12)
    italic = font_italicized(font)
    weights = {v:k for k,v in family_weights(font.familyName(), italic).items()}
    return weights[font.fontName()]

def font_w(font):
    if isinstance(font, basestring):
        font = NSFont.fontWithName_size_(font, 12)
    return _fm.weightOfFont_(font)

# introspection methods for family names

def family_exists(famname):
    q = famname.lower().strip()
    matches = [fam for fam in _fm.availableFontFamilies() if q==fam.lower()]
    return matches[0] if matches else None

def _sanitize_weight(weight):
    return weight.lower().strip().replace('-','').replace('oblique','').replace('italic','').replace(' ','')

def weight_exists(famname, weight, italic=False):
    family = family_exists(famname)
    wname = _sanitize_weight(weight)
    if wname in family_weights(family, italic):
        return wname
    for w, group in enumerate(std_weights):
        if wname in group: 
            return closest_weight(w, family, italic)
    return None
    
def family_weights(famname, italic=False, rows=False):
    weights = []
    regular = None
    for nm, dname, w, traits in _fm.availableMembersOfFontFamily_(famname):
        if traits&NSItalicFontMask:
            if not italic: continue
        elif italic:
            continue
        wname = _sanitize_weight(dname)
        if not wname:
            regular = (nm, w)
            continue
        weights.append(dict(psname=nm, wname=wname, w=w))
    if regular:
        # should really be marking this in some other way. it would be nice if the 
        # 'regular' font for each family was called regular...
        nm, w = regular
        curr_weights = [f['wname'] for f in weights]
        for default in std_weights[w]:
            if default not in curr_weights:
               weights.append(dict(psname=nm, wname=unicode(default), w=w))
               break
    if rows:
        return weights
    else:
        return odict( (w['wname'], w['psname']) for w in sorted(weights, key=itemgetter('w')))

# educated guessers 

def font_face(family, weight, **traits):
    # try to match named weights against the display names first
    fam_weights = family_weights(family, traits.get('italic'))
    wname = _sanitize_weight(weight)
    if wname in fam_weights:
        f = NSFont.fontWithName_size_(fam_weights[wname], 12)
        if 'bold' in traits:
            f = _fm.convertFont_toHaveTrait_(f, NSBoldFontMask if traits['bold'] else NSUnboldFontMask)
        if 'italic' in traits:
            f = _fm.convertFont_toHaveTrait_(f, NSItalicFontMask if traits['italic'] else NSUnitalicFontMask)        
        return f.fontName()

    # otherwise use apple's ‘standard’ mapping to the 1-14 scale
    for weight, names in enumerate(std_weights):
        if wname in names: break
    else:
        badweight = 'Unknown font weight name "%s"'%wname
        raise NodeBoxError(badweight)

    # build up a traits bitmask
    mask = NSItalicFontMask if traits.get('italic') else NSUnitalicFontMask
    if traits.get('bold'):
        mask |= NSBoldFontMask

    # cross fingers and let nsfontmanager rummage through the library
    face = _fm.fontWithFamily_traits_weight_size_(family, mask, weight, 12)
    return face.fontName() if face else None

def closest_weight(old_w, famname, italic=False):
    weights = family_weights(famname, italic, rows=True)
    for f in weights:
        f['score'] = abs(old_w - f['w'])
    weights.sort(key=itemgetter('score'))
    if weights:
        return weights[0]['wname']
    return None

_fm = NSFontManager.sharedFontManager()
std_weights = [
   [], ["ultralight"], ["thin"], ["light", "extralight"], 
   ["book"], ["regular", "plain", "display", "roman"], ["medium"], 
   ["demi", "demibold"], ["semi", "semibold"], ["bold"], 
   ["extra", "extrabold"], ["heavy", "heavyface"], ["black", "super"], 
   ["ultra", "ultrablack", "fat"], ["extrablack", "obese", "nord"]
]

__all__ = ("font_exists", "font_family", "font_italicized", "font_weight", "font_w", 
           "family_exists", "weight_exists", "family_weights", 
           "font_face", "closest_weight")
