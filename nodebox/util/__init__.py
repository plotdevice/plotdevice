import os
import re
from collections import OrderedDict, defaultdict
from AppKit import NSFontManager, NSFont, NSMacOSRomanStringEncoding, NSItalicFontMask
from random import choice, shuffle
from nodebox import NodeBoxError

__all__ = ('grid', 'random', 'shuffled', 'choice', 'ordered', 'order', 'files', 'autotext', '_copy_attr', '_copy_attrs', 'odict', 'ddict', 'adict')

### Utilities ###

def grid(cols, rows, colSize=1, rowSize=1, shuffled = False):
    """Returns an iterator that contains coordinate tuples.
    
    The grid can be used to quickly create grid-like structures. A common way to use them is:
        for x, y in grid(10,10,12,12):
            rect(x,y, 10,10)
    """
    # Prefer using generators.
    rowRange = xrange(int(rows))
    colRange = xrange(int(cols))
    # Shuffled needs a real list, though.
    if (shuffled):
        rowRange = list(rowRange)
        colRange = list(colRange)
        shuffle(rowRange)
        shuffle(colRange)
    for y in rowRange:
        for x in colRange:
            yield (x*colSize,y*rowSize)

def random(v1=None, v2=None):
    """Returns a random value.
    
    This function does a lot of things depending on the parameters:
    - If one or more floats is given, the random value will be a float.
    - If all values are ints, the random value will be an integer.
    
    - If one value is given, random returns a value from 0 to the given value.
      This value is not inclusive.
    - If two values are given, random returns a value between the two; if two
      integers are given, the two boundaries are inclusive.
    """
    import random
    if v1 != None and v2 == None: # One value means 0 -> v1
        if isinstance(v1, float):
            return random.random() * v1
        else:
            return int(random.random() * v1)
    elif v1 != None and v2 != None: # v1 -> v2
        if isinstance(v1, float) or isinstance(v2, float):
            start = min(v1, v2)
            end = max(v1, v2)
            return start + random.random() * (end-start)
        else:
            start = min(v1, v2)
            end = max(v1, v2) + 1
            return int(start + random.random() * (end-start))
    else: # No values means 0.0 -> 1.0
        return random.random()

def files(path="*", case=True):
    """Returns a list of files.
    
    You can use wildcards to specify which files to pick, e.g.
        f = files('~/Pictures/*.jpg')

    For a case insensitive search, call files() with case=False
    """
    from iglob import iglob 
    if type(path)==unicode:
        path.encode('utf-8')
    path = re.sub(r'^~(?=/|$)',os.getenv('HOME'),path)
    return list(iglob(path.decode('utf-8'), case=case))

def autotext(sourceFile):
    from nodebox.util.kgp import KantGenerator
    k = KantGenerator(sourceFile)
    return k.output()

### Permutation sugar ###

def _is_sequence(seq):
    if not isinstance(seq, (list, tuple) ):
        badtype = 'ordered, shuffled, and friends only work for tuples and lists (not %d)' % type(seq)
        raise NodeBoxError(badtype)

def _getter(seq, names):
    from operator import itemgetter, attrgetter
    return itemgetter(*names) if names[0] in seq[0] else attrgetter(*names)

def order(seq, *names, **kwargs):
    _is_sequence(seq)
    if not names or not seq:
        reordered = [(it,idx) for idx,it in enumerate(seq)]
    else:
        getter = _getter(seq, names)
        reordered = [(getter(it), idx) for idx,it in enumerate(seq)]
    reordered.sort(**kwargs)
    return [it[1] for it in reordered]

def ordered(seq, *names, **kwargs):
    _is_sequence(seq)
    if kwargs.get('perm') and seq:
        return [seq[idx] for idx in kwargs['perm']]

    if not names or not seq:
        return list(sorted(seq, **kwargs))

    return list(sorted(seq, key=_getter(seq, names), **kwargs))

def shuffled(seq):
    _is_sequence(seq)
    perm = list(seq)
    shuffle(perm)
    return perm

### deepcopy helpers ###

def _copy_attr(v):
    if v is None:
        return None
    elif hasattr(v, "copy"):
        return v.copy()
    elif isinstance(v, list):
        return list(v)
    elif isinstance(v, tuple):
        return tuple(v)
    elif isinstance(v, (int, str, unicode, float, bool, long)):
        return v
    else:
        raise NodeBoxError, "Don't know how to copy '%s'." % v

def _copy_attrs(source, target, attrs):
    for attr in attrs:
        setattr(target, attr, _copy_attr(getattr(source, attr)))

### give ordered- and default-dict a nicer repr ###

class BetterRepr(object):
    def __repr__(self, indent=2):
        result = '%s{'%self.__class__.__name__
        for k,v in self.iteritems():
            if isinstance(v, BetterRepr):
                vStr = v.__repr__(indent + 2)
            else:
                vStr = v.__repr__()
            result += "\n" + ' '*indent + k.__repr__() + ': ' + vStr
        if not result.endswith('{'):
            result += "\n"
        result += '}'
        return result

class odict(BetterRepr,OrderedDict):
    """Dictionary that remembers insertion order

    Normal dict objects return keys in an arbitrary order. An odict will return them in
    the order you add them. To initialize an odict and not lose the ordering in the process,
    avoid using keyword arguments and instead pass a list of (key,val) tuples:

        odict([ ('foo',12), ('bar',14), ('baz', 33) ])

    or as part of a generator expression:

        odict( (k,other[k]) for k in sorted(other.keys()) )

    """
    pass

class ddict(BetterRepr,defaultdict):
    """Dictionary with default factory

    Any time you access a key that was previously undefined, the factory function 
    is called and a default value is inserted in the dictionary. e.g.,

        normal_dict = {}
        normal_dict['foo'].append(42) # raises a KeyError

        lst_dict = ddict(list)
        lst_dict['foo'].append(42)    # sets 'foo' to [42]

        num_dict = ddict(int)
        print num_dict['bar']         # prints '0'
        num_dict['baz'] += 2          # increments 'baz' from 0 to 2

    """
    pass

### the not very pythonic but often convenient dot-notation dict ###

class adict(BetterRepr, dict):
    """A dictionary object whose items may also be accessed with dot notation."""
    def __init__(self, *args, **kw):
        super(adict, self).__init__(*args, **kw)
        self.__initialised = True

    def __getattr__(self, key): 
        try:
            return self[key]
        except KeyError, k:
            raise AttributeError, k
    
    def __setattr__(self, key, value): 
        # this test allows attributes to be set in the __init__ method
        if not self.__dict__.has_key('_adict__initialised'):
            return dict.__setattr__(self, key, value)
        self[key] = value
    
    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError, k:
            raise AttributeError, k
