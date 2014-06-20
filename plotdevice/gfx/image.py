# encoding: utf-8
import os
import re
import json
import warnings
import math
from contextlib import contextmanager
from AppKit import *
from Foundation import *
from Quartz import *
from Quartz.PDFKit import *

from plotdevice import DeviceError
from ..util import _copy_attrs
from ..lib.io import MovieExportSession, ImageExportSession
from .transform import Region, Size, Point, Transform, CENTER
from .atoms import TransformMixin, EffectsMixin, BoundsMixin, Grob
from . import _ns_context

_ctx = None
__all__ = ("Image", 'ImageSequence', 'Movie', 'PDF', )


### The bitmap/vector image-container (a.k.a. NSImage proxy) ###

class Image(EffectsMixin, TransformMixin, BoundsMixin, Grob):
    stateAttrs = ('_nsImage',)
    kwargs = ('data','width','height')

    # def __init__(self, path, x=0, y=0, width=None, height=None, **kwargs):
    def __init__(self, *args, **kwargs):
        """
        Positional parameters:
          - path: the path to an image file, or an existing Image object
          - x & y: position of top-left corner
          - width & height: limit either or both dimensions to a maximum size
              If a width and height are both given, the narrower dimension is used
              If both are omitted default to full-size

        Optional keyword parameters:
          - data: a stream of bytes of image data. If the data begins with the
                  characters "base64," the remainder of the stream will be
                  decoded before loading
          - alpha: the image opacity (0-1.0)
          - blend: a blend mode name

         Example usage:
           x,y, w,h = 10,10, 200,200
           Image("foo.png", x, y, w, h)
           Image(<Image object>, x, y, height=h)
           Image(x, y, data='<raw bytes from an image file>')
           Image(x, y, data='base64,<b64-encoded bytes>')
        """
        super(Image, self).__init__(**kwargs)

        # look for a path or Image as the first arg, or a `data` kwarg
        args = list(args)
        data = kwargs.get('data', None)
        src = kwargs.get('path', None)
        if args and not (src or data):
            src = args.pop(0)

        # self.x, self.y = kwargs.get('x',0), kwargs.get('y',0)
        # self.width, self.height = kwargs.get('width',None), kwargs.get('height',None)
        for attr, val in zip(['x','y','width','height'], args):
            setattr(self, attr, val)

        if data:
            self._nsImage = self._lazyload(data=data)
        elif src:
            if isinstance(src, NSImage):
                self._nsImage = image
                self._nsImage.setFlipped_(True)
            elif isinstance(src, Image):
                self.inherit(src)
            elif isinstance(src, basestring):
                self._nsImage = self._lazyload(path=src)
            else:
                invalid = "Not a valid image source: %r" % type(src)
                raise DeviceError(invalid)

    def _lazyload(self, path=None, data=None):
        # loads either a `path` or `data` kwarg and returns an NSImage
        # `path` should be the path of a valid image file
        # `data` should be the bytestring contents of an image file, or base64-encoded
        #        with the characters "base64," prepended to it
        NSDataBase64DecodingIgnoreUnknownCharacters = 1
        _cache = _ctx._imagecache

        if data is not None:
            # convert the str into an NSData (possibly decoding along the way)
            if isinstance(data, str) and data.startswith('base64,'):
                data = NSData.alloc().initWithBase64EncodedString_options_(data[7:], NSDataBase64DecodingIgnoreUnknownCharacters)
            elif not isinstance(data, NSData):
                data = NSData.dataWithBytes_length_(data, len(data))
            key, mtime, err_info = data.hash(), None, type(data)

            # return a cached image if possible...
            if key in _cache:
                return _cache[key][0]
            # ...or load from the data
            image = NSImage.alloc().initWithData_(data)
        elif path is not None:
            # return a cached image if possible...
            try:
                path = NSString.stringByExpandingTildeInPath(path)
                mtime = os.path.getmtime(path)
                if path in _cache and _cache[path][1] >= mtime:
                    return _cache[path][0]
            except:
                notfound = 'Image "%s" not found.' % path
                raise DeviceError(notfound)
            key = err_info = path
            # ...or load from the file
            image = NSImage.alloc().initWithContentsOfFile_(path)

        # if we wound up with a valid image, configure and cache the NSImage
        # before returning it
        if image is None:
            invalid = "Doesn't look like image data in: %r" % err_info
            raise DeviceError(invalid)
        image.setFlipped_(True)
        image.setCacheMode_(NSImageCacheNever)
        _cache[key] = (image, mtime)
        return _cache[key][0]

    @property
    def image(self):
        warnings.warn("The 'image' attribute is deprecated. Please use _nsImage instead.", DeprecationWarning, stacklevel=2)
        return self._nsImage

    @property
    def _nsBitmap(self):
        for bitmap in self._nsImage.representations():
            # if we already have a bitmap representation, use that...
            if isinstance(bitmap, NSBitmapImageRep):
                break
        else:
            # ...otherwise convert the vector image to a bitmap
            # (note that this should use _screen_transform somehow but currently doesn't)
            tiffdata = self._nsImage.TIFFRepresentation()
            image = NSImage.alloc().initWithData_(tiffdata)
            bitmap = image.representations()[0]
        return bitmap

    @property
    def _ciImage(self):
        # core-image needs to be told to compensate for our flipped coords
        flip = NSAffineTransform.transform()
        flip.translateXBy_yBy_(0, self.size.height)
        flip.scaleXBy_yBy_(1,-1)

        ciImage = CIImage.alloc().initWithBitmapImageRep_(self._nsBitmap)
        transform = CIFilter.filterWithName_("CIAffineTransform")
        transform.setValue_forKey_(ciImage, "inputImage")
        transform.setValue_forKey_(flip, "inputTransform")
        return transform.valueForKey_("outputImage")

    @property
    def bounds(self):
        #
        # hrm, so this should probably reflect the scale factor, no?
        #
        origin = self.transform.apply(Point(self.x, self.y))
        return Region(origin.x, origin.y, *self._nsImage.size())

    @property
    def size(self):
        return Size(*self._nsImage.size())

    @property
    def _scalefactor(self):
        """Fits the image into any specified width & height constraints. If neither was
        included in the call to image(), defaults to the image file's full size."""
        src = self.size
        if not any([self.width, self.height]):
            factor = 1.0
        elif all([self.width, self.height]):
            factor = min(self.width/src.width, self.height/src.height)
        else:
            dim, src_dim = max((self.width, src.width), (self.height, src.height))
            factor = dim/src_dim
        return factor

    @property
    def _screen_transform(self):
        """Returns the Transform object that will be used to draw the image.

        The transform incorporates the global context state but also accounts for
        centering and max width/height values set in the constructor."""

        # accumulate transformations in a fresh matrix
        xf = Transform()

        # set scale factor so entire image fits in the given rect or dimension
        factor = self._scalefactor

        # calculate the translation offset for centering (if any)
        nudge = Transform()
        if self._transformmode == CENTER:
            nudge.translate(self.size.width*factor/2, self.size.height*factor/2)

        xf.translate(self.x, self.y) # set the position before applying transforms
        xf.prepend(nudge)            # nudge the image to its center (or not)
        xf.prepend(self.transform)   # add context's CTM.
        xf.prepend(nudge.inverse)    # Move back to the real origin.
        xf.scale(factor)             # scale to fit size constraints (if any)
        return xf

    def _draw(self):
        """Draw an image on the given coordinates."""

        with _ns_context() as ns_ctx:
            self._screen_transform.concat() # move the image into place via transforms
            with self.effects.applied():    # apply any blend/alpha/shadow effects
                ns_ctx.setImageInterpolation_(NSImageInterpolationHigh)
                bounds = ((0,0), self.size) # draw the image at (0,0)
                self._nsImage.drawAtPoint_fromRect_operation_fraction_((0,0), bounds, NSCompositeSourceOver, self.alpha)
                # NB: the nodebox source warns about quartz bugs triggered by drawing
                # EPSs to other origin points. no clue whether this still applies...

### core-image filters for channel separation and inversion ###

def ciFilter(opt, img):
    _filt = _inversionFilter if isinstance(opt, bool) else _channelFilter
    return _filt(opt, img)

def _channelFilter(channel, img):
    """Generate a greyscale image by isolating a single r/g/b/a channel"""

    rgb = ('red', 'green', 'blue')
    if channel=='alpha':
        transmat = [(0, 0, 0, 1)] * 3
        transmat += [ (0,0,0,0), (0,0,0,1) ]
    elif channel in rgb:
        rgb_row = [0,0,0]
        rgb_row.insert(rgb.index(channel), 1.0)
        transmat = [tuple(rgb_row)] * 3
        transmat += [ (0,0,0,0), (0,0,0,1) ]
    elif channel in ('black', 'white'):
        transmat = [(.333, .333, .333, 0)] * 3
        transmat += [ (0,0,0,0), (0,0,0,1) ]
    return _matrixFilter(transmat, img)

def _inversionFilter(identity, img):
    """Conditionally turn black to white and up to down"""

    # set up a matrix that's either identity or an r/g/b inversion
    polarity = -1.0 if not identity else 1.0
    bias = 0 if polarity>0 else 1
    transmat = [(polarity, 0, 0, 0), (0, polarity, 0, 0), (0, 0, polarity, 0),
                (0, 0, 0, 0), (bias, bias, bias, 1)]
    return _matrixFilter(transmat, img)

def _matrixFilter(matrix, img):
    """Apply a color transform to a CIImage and return the filtered result"""

    vectors = ("inputRVector", "inputGVector", "inputBVector", "inputAVector", "inputBiasVector")
    opts = {k:CIVector.vectorWithX_Y_Z_W_(*v) for k,v in zip(vectors, matrix)}
    opts[kCIInputImageKey] = img
    remap = CIFilter.filterWithName_("CIColorMatrix")
    for k,v in opts.items():
        remap.setValue_forKey_(v, k)
    return remap.valueForKey_("outputImage")


### context managers for calls to `with export(...)` ###

class Movie(object):
    """Represents a movie in the process of being assembled one frame at a time.

    The class can be used procedurally, but you need to be careful to call its methods
    in the correct order or a corrupt file may result:

        movie = export('anim.mov')
        for i in xrange(100):
            canvas.clear() # erase the previous frame
            ...            # (do some drawing)
            movie.add()    # add the canvas to the movie
        movie.finish()     # wait for i/o to complete

    It can be used more simply as a context manager:

        with export('anim.mov') as movie:
            for i in xrange(100):
                with movie.frame:
                    ... # draw the next frame
    """
    def __init__(self, *args, **opts):
        self.session = MovieExportSession(*args, **opts)

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.finish()

    @property
    @contextmanager
    def frame(self):
        """Clears the canvas, runs the code in the `with` block, then adds the canvas to the movie.

        For example, to create a quicktime movie and write a single frame to it you could write:

            with export("anim.mov") as movie:
                canvas.clear()
                ... # draw the frame
                movie.add()

        With the `frame` context manager, this simplifies to:

            with export("anim.mov") as movie:
                with movie.frame:
                    ... # draw the frame
        """
        _ctx._saveContext()
        _ctx.canvas.clear()
        yield
        self.add()
        _ctx._restoreContext()

    def add(self):
        """Add a new frame to the movie with the current contents of the canvas."""
        self.session.add(canvas)
        self._progress()

    def _progress(self):
        sys.stderr.write("\rExporting frame %i/%i"%self.session.count())

    def finish(self):
        """Finish writing the movie file.

        Signal that there are no more frames to be added and print progress messages until
        the background thread has finished encoding the movie.
        """
        self.session.done()
        while True:
            self._progress()
            if self.session.writer.doneWriting():
                break
            time.sleep(0.1)
        sys.stderr.write('\r%s\r'%(' '*80))
        sys.stderr.flush()

class ImageSequence(object):
    """Write a single image, or a numbered sequence of them.

    To save a single image:

        with export('output.png') as image:
            ... # draw something

    To draw a sequence of images, you can either handle the naming yourself:

        for i in xrange(100):
            with export('output-%03i.pdf'%i) as image:
                ... # draw the next image in the sequence

    Or you can let the `sequence` context manager number them for you:

        with export('output.jpg') as image:
            for i in xrange(100):
                with image.sequence:
                    ... # draw the next image in the sequence

    """
    def __init__(self, fname, format, mode):
        self._outputmode = mode
        self.fname = fname
        self.format = format
        self.idx = None
        if '#' in fname:
            head, tail = re.split(r'#+', fname, maxsplit=1)
            counter = '%%0%ii' % (len(fname) - len(head) - len(tail))
            self.tmpl = "".join([head,counter,tail.replace('#','')])
        else:
            self.tmpl = re.sub(r'^(.*)(\.[a-z]{3,4})$', r'\1-%04i\2', fname)

    def __enter__(self):
        _ctx._saveContext()
        _ctx.canvas.clear()
        _ctx._outputmode = self._outputmode
        return self
    def __exit__(self, type, value, tb):
        if self.idx is None:
            _ctx.canvas.save(self.fname, self.format)
        _ctx._restoreContext()

    @property
    @contextmanager
    def sequence(self):
        """Clears the canvas, runs the code in the `with` block, then saves a numbered output file.

        For example, to a sequence of 10 images:
            with export('output.png') as image:
                for i in xrange(100):
                    with image.sequence:
                        ... # draw the next image in the sequence
        """
        _ctx._saveContext()
        _ctx.canvas.clear()
        yield
        if self.idx is None:
            self.idx = 1
        _ctx.canvas.save(self.tmpl%self.idx, self.format)
        self.idx += 1
        _ctx._restoreContext()

class PDF(object):
    """Represents a PDF document in the process of being assembled one page at a time.

    The class can be used procedurally to add frames and finish writing the output file:

        pdf = export('multipage.pdf')
        for i in xrange(5):
            canvas.clear() # erase the previous page's graphics from the canvas
            ...            # (do some drawing)
            pdf.add()      # add the canvas to the pdf as a new page
        pdf.finish()       # write the pdf document to disk

    It can be used more simply as a context manager:

        with export('multipage.pdf') as pdf:
            for i in xrange(5):
                with pdf.page:
                    ... # draw the next page

        with export('singlepage.pdf') as pdf:
            ... # draw the one and only page
    """
    def __init__(self, fname, mode):
        self._outputmode = mode
        self.fname = fname
        self.doc = None
    def __enter__(self):
        _ctx._saveContext()
        _ctx.canvas.clear()
        _ctx._outputmode = self._outputmode
        return self
    def __exit__(self, type, value, tb):
        self.finish() or _ctx.canvas.save(self.fname, 'pdf')
        _ctx._restoreContext()

    @property
    @contextmanager
    def page(self):
        """Clears the canvas, runs the code in the `with` block, then adds the canvas as a new pdf page.

        For example, to create a pdf with two pages, you could write:

            with export("multipage.pdf") as pdf:
                canvas.clear()
                ... # draw first page
                pdf.add()
                canvas.clear()
                ... # draw the next page
                pdf.add()

        With the `page` context manager it simplifies to:

            with export("multipage.pdf") as pdf:
                with pdf.page:
                    ... # draw first page
                with pdf.page:
                    ... # draw the next page
        """
        _ctx._saveContext()
        _ctx.canvas.clear()
        yield
        self.add()
        _ctx._restoreContext()

    def add(self):
        """Add a new page to the PDF with the current contents of the canvas."""
        pagedoc = PDFDocument.alloc().initWithData_(_ctx.canvas._getImageData('pdf'))
        if not self.doc:
            self.doc = pagedoc
        else:
            self.doc.insertPage_atIndex_(pagedoc.pageAtIndex_(0), self.doc.pageCount())

    def finish(self):
        """Writes the fully-assembled PDF to disk"""
        if self.doc:
            self.doc.writeToFile_(self.fname)
        return self.doc




