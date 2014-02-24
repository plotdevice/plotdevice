# encoding: utf-8
from operator import itemgetter, attrgetter
from nodebox.util import odict, ddict
from AppKit import *
from Foundation import *

from nodebox import NodeBoxError
from nodebox.util.foundry import *

class Font(object):
    kwargs = ('family','size','weight','width','variant','italic','heavier','lighter','face','fontname','fontsize')

    def __init__(self, ctx, *args, **kwargs):
        badargs = [k for k in kwargs if k not in Font.kwargs]
        if badargs:
            eg = '"'+'", "'.join(badargs)+'"'
            badarg = 'Font: unknown keyword argument%s %s'%('' if len(badargs)==1 else 's', eg)
            raise NodeBoxError(badarg)

        # Gather specs from the args/kwargs and fill in the blanks from the global state
        _spec = ('family','size','weight','italic','width','variant')

        # start with kwarg values as the canonical settings
        spec = {k:v for k,v in kwargs.items() if k in _spec}
        if 'fontsize' in kwargs: # be backward compatible with the old arg names
            spec.setdefault('size', kwargs['fontsize'])

        # look for a postscript name passed as `face` or `fontname` and convert
        # it into a Face tuple
        basis = kwargs.get('face', kwargs.get('fontname'))
        if isinstance(basis, basestring):
            basis = font_face(basis)
        if isinstance(basis, Face):
            spec['basis'] = basis

        # search the positional args for either name/size or a Font object
        # we want the kwargs to have higher priority, so setdefault everywhere...
        for item in args:
            if isinstance(item, Face):
                spec.setdefault('basis', item)
            if isinstance(item, Font):
                spec.setdefault('basis', item._face)
                spec.setdefault('size', item._size)
            elif isinstance(item, basestring):
                if facey(item):
                    spec.setdefault('basis', item)
                elif widthy(item):
                    spec.setdefault('width', item)
                elif weighty(item):
                    spec.setdefault('weight', item)
                elif fammy(item):
                    spec.setdefault('family', family_name(item))
                else:
                    print 'No clue what to make of "%s"'%item
            elif isinstance(item, (int, float, long)):
                spec.setdefault('size', item)

        # initialize our internals based on the spec
        self._ctx = ctx
        if not basis or any(arg not in ('basis','size') for arg in spec):
            self._update_face(**spec)
        else:
            self._face = spec['basis']
        self._size = float(spec.get('size', ctx._fontsize))

        # if a weight-modulation arg was included, step the weight
        mod = kwargs.get('heavier', kwargs.get('lighter', 0))
        mod = 1 if mod is True else mod
        if kwargs.get('lighter'):
            mod = -mod
        if mod:
            self.modulate(mod)

    def __enter__(self):
        if hasattr(self, '_prior'):
            self._rollback = self._prior
            del self._prior
        else:
            self._rollback = self._get_ctx()
        self._update_ctx()
        return self

    def __exit__(self, type, value, tb):
        self._update_ctx(*self._rollback)

    def __repr__(self):
        spec = (u'"%(family)s"|-|%(weight)s|-|<%(psname)s>'%(self._face._asdict())).split('|-|')
        if self._face.variant:
            spec.insert(2, self._face.variant)
        spec.insert(1, '/' if self._face.italic else '|')
        if self._size:
            spec.insert(1, ("%rpt"%self._size).replace('.0pt','pt'))
        return (u'Font(%s)'%" ".join(spec)).encode('utf-8')

    def __call__(self, *args, **kwargs):
        return Font(self._ctx, self, *args, **kwargs)

    def _get_ctx(self):
        return (self._ctx._fontname, self._ctx._fontsize)

    def _update_ctx(self, face=None, size=None):
        face, size = (face or self.face), (size or self.size)
        self._ctx._fontname, self._ctx._fontsize = face, size

    def _update_face(self, **spec):
        # use the basis kwarg (or this _face if omitted) as a starting point
        basis = spec.get('basis', getattr(self,'_face', self._ctx._fontname))
        if isinstance(basis, basestring):
            basis = font_face(basis)

        # if there weren't any args to fine tune the fam/weight/width/variant, just 
        # use the basis Face as is and bail out
        if not {'family','weight','width','variant','italic'}.intersection(spec):
            self._face = basis
            return

        # otherwise try to find the best match for the new attributes within either
        # the family in the spec, or the current family if omitted
        try:
            spec['basis'] = basis
            fam = Family(self._ctx, spec.get('family', basis.family))
            candidates, scores = zip(*fam.select(spec).items())
            self._face = candidates[0]
        except IndexError:
              nomatch = "Font: couldn't find a face matching criteria %r"%spec
              raise NodeBoxError(nomatch)

    def _use(self):
        # called right after allocation by the font() command. remembers the font state
        # from before applying itself since by the time __enter__ takes a snapshot the 
        # prior state will already be overwritten
        self._prior = self._get_ctx()
        self._update_ctx()
        return self

    # .name
    def _get_name(self):
        return self._face.family
    def _set_name(self, f):
        self.family = f
    name = property(_get_name, _set_name)

    # .family
    def _get_family(self):
        return Family(self._ctx, self._face.family)
    def _set_family(self, f):
        if isinstance(f, Family):
            f = f.name
        self._update_face(family=family_name(f))
    family = property(_get_family, _set_family)

    # .weight
    def _get_weight(self):
        return self._face.weight
    def _set_weight(self, w):
        self._update_face(weight=w)
    weight = property(_get_weight, _set_weight)

    # .width
    def _get_width(self):
        return self._face.width
    def _set_width(self, w):
        self._update_face(width=w)
    width = property(_get_width, _set_width)

    # .variant
    def _get_variant(self):
        return self._face.variant
    def _set_variant(self, v):
        self._update_face(variant=v)
    variant = property(_get_variant, _set_variant)

    # .size
    def _get_size(self):
        return self._size
    def _set_size(self, s):
        self._size = float(s)
    size = property(_get_size, _set_size)

    # .italic
    def _get_italic(self):
        return self._face.italic
    def _set_italic(self, ital):
        if ital != self.italic:
            self._update_face(italic=ital)
    italic = property(_get_italic, _set_italic)

    # .face
    def _get_face(self):
        return self._face.psname
    def _set_face(self, face):
        self._face = font_face(face)
    face = property(_get_face, _set_face)

    @property
    def traits(self):
        return self._face.traits

    @property
    def weights(self):
        return self.family.weights

    @property
    def widths(self):
        return self.family.widths

    @property
    def variants(self):
        return self.family.variants

    @property
    def siblings(self):
        return self.family.fonts

    def heavier(self, steps=1):
        self.modulate(steps)

    def lighter(self, steps=1):
        self.modulate(-steps)

    def modulate(self, steps):
        if not steps: 
            return
        seq = self.weights
        idx = seq.index(self.weight)
        less, more = list(reversed(seq[:idx+1])), seq[idx:]
        if steps<0:
            match = less[abs(steps):abs(steps)+1] or [less[-1]]
        elif steps>0:
            match = more[steps:steps+1] or [more[-1]]
        self.weight = match[0]

class Family(object):
    def __init__(self, ctx, famname=None, of=None):
        self._ctx = ctx
        if of:
            famname = font_family(of)
        elif not famname:
            badarg = 'Family: requires either a name or a Font object'%famname
            raise NodeBoxError(badarg)

        q = famname.strip().lower().replace(' ','')
        matches = [fam for fam in family_names() if q==fam.lower().replace(' ','')]
        if not matches:
            notfound = 'Unknown font family "%s"'%famname
            raise NodeBoxError(notfound)
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
            has_italic = has_italic or 'italic' in f.traits
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
        return odict( (k,Font(self._ctx, v)) for k,v in self._faces.items())

    def select(self, spec):
        current = spec.get('basis', self._ctx._fontname)
        if isinstance(current, basestring):
            current = font_face(current)

        axes = ('weight','width','italic','variant')
        opts = {k:v for k,v in spec.items() if k in axes}
        defaults = dict( (k, getattr(current, k)) for k in axes + ('wid', 'wgt'))
        
        # map the requested weight/width onto what's available in the family
        w_spans = {"wgt":[1,14], "wid":[-15,15]}
        for axis, num_axis in dict(weight='wgt', width='wid').items():
            w_vals = [getattr(f, num_axis) for f in self._faces.values()]
            w_spans[num_axis] = [min(w_vals), max(w_vals)]
            dst = opts if axis in opts else defaults
            wname, wval = self._closest(axis, opts.get(axis, getattr(current,axis)))
            dst.update({axis:wname, num_axis:wval})

        def score(axis, f):
            bonus = 2 if axis in opts else 1
            val = opts[axis] if axis in opts else defaults.get(axis)
            vs = getattr(f,axis)
            if axis in ('wgt','wid'):
                w_min, w_max = w_spans[axis]
                agree = 1 if val==vs else -abs(val-vs) / float(max(w_max-w_min, 1))
            elif axis in ('weight','width'):
                # agree = 1 if (val or None) == (vs or None) else 0
                agree = 0
            else:
                agree = 1 if (val or None) == (vs or None) else -1
            return agree * bonus

        scores = ddict(int)
        for f in self.faces.values():
            # consider = 'italic', 'weight', 'width', 'variant', 'wgt', 'wid'
            # print [score(axis,f) for axis in consider], [getattr(f,axis) for axis in consider]
            scores[f] += sum([score(axis,f) for axis in 'italic', 'weight', 'width', 'variant', 'wgt', 'wid'])

        candidates = [dict(score=s, face=f, ps=f.psname) for f,s in scores.items()]
        candidates.sort(key=itemgetter('ps'))
        candidates.sort(key=itemgetter('score'), reverse=True)
        # for c in candidates[:10]:
        #     print "  %0.2f"%c['score'], c['face']
        return odict( (c['face'],c['score']) for c in candidates)

    def _closest(self, axis, val):
        # validate the width/weight string and make sure it either conforms to the 
        # family's names, or can be turned into an std. integer value
        num_axis = dict(weight='wgt', width='wid')[axis]
        corpus = {getattr(f,axis):getattr(f,num_axis) for f in self._faces.values()}
        w_names, w_vals = corpus.keys(), corpus.values()

        if sanitized(val) in sanitized(w_names):
            wname = w_names[sanitized(w_names).index(sanitized(val))]
            return wname, corpus[wname]

        # if the name doesn't exist in the family, find its standard name/num values 
        # then truncate them by the range of the face (so e.g., asking for `obese' will 
        # only turn into `semibold' if that's as heavy as the family gets)
        wname, wval = standardized(axis, val)
        wval = max(min(w_vals), min(max(w_vals), wval))
        if wval in w_vals:
            wname = w_names[w_vals.index(wval)]
        return wname, wval

if __name__=='__main__':
    test()

__all__ = ["Family", "Font"]
