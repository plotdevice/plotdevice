# encoding: utf-8
import os
import re
import json
import warnings
import math
from contextlib import contextmanager
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import _copy_attrs, autorelease
from ..util.readers import HTTP, last_modified
from ..lib.io import MovieExportSession, ImageExportSession
from .geometry import Region, Size, Point, Transform, CENTER
from .atoms import TransformMixin, EffectsMixin, FrameMixin, Grob
from . import _ns_context

_ctx = None
__all__ = ("Image", 'ImageWriter')

### The bitmap/vector image-container (a.k.a. NSImage proxy) ###

class Image(EffectsMixin, TransformMixin, FrameMixin, Grob):
    stateAttrs = ('_nsImage',)
    opts = ('data',)

    def __init__(self, *args, **kwargs):
        """
        Positional parameters:
          - src: the path to an image file, an existing Image object, or the `canvas` global
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
           Image(x, y, src='path-or-url')
           Image(x, y, data='<raw bytes from an image file>')
           Image(x, y, data='base64,<b64-encoded bytes>')
           Image(canvas, x, y)
        """
        # let the mixins handle transforms & effects
        super(Image, self).__init__(**kwargs)

        # look for a path or Image as the first arg, or a `data` kwarg (plus `image` for compat)
        args = list(args)
        data = kwargs.get('data', None)
        src = kwargs.get('src', kwargs.get('image', None))
        if args and not (src or data):
            src = args.pop(0) # use first arg if image wasn't in kwargs
        elif args and args[0] is None:
            args.pop(0) # make image(None, 10,20, image=...) work properly for compat

        # get an NSImage reference (once way or another)
        if data:
            self._nsImage = self._lazyload(data=data)
        elif src:
            if isinstance(src, NSImage):
                self._nsImage = src.copy()
                self._nsImage.setFlipped_(True)
            elif hasattr(src, '_nsImage'):
                self._nsImage = src._nsImage
            elif isinstance(src, basestring):
                self._nsImage = self._lazyload(path=src)
            else:
                invalid = "Not a valid image source: %r" % type(src)
                raise DeviceError(invalid)

        # set the bounds (in phases)
        if isinstance(src, Image):
            # if working from an existing Image, inherit its bounds as the default
            for attr in ['x','y','width','height']:
                setattr(self, attr, getattr(src, attr))
        if args:
            # override defaults with positional bounds args (if any)
            self._frame._parse(args)
        if kwargs:
            # finally, let keyword args override the inherited & positional bounds
            for k,v in kwargs.items():
                if k in FrameMixin.opts:
                    setattr(self, k, v)

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
            if re.match(r'https?:', path):
                # load from url
                key = err_info = path
                resp = HTTP.get(path)
                mtime = last_modified(resp)
                # return a cached image if possible...
                if path in _cache and _cache[path][1] >= mtime:
                    return _cache[path][0]
                # ...or load from the data
                bytes = resp.content
                data = NSData.dataWithBytes_length_(bytes, len(bytes))
                image = NSImage.alloc().initWithData_(data)
            else:
                # load from file path
                try:
                    path = NSString.stringByExpandingTildeInPath(path)
                    mtime = os.path.getmtime(path)
                    # return a cached image if possible...
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
            invalid = "Doesn't seem to contain image data: %r" % err_info
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
        w, h = self.size.w*self._scalefactor, self.size.h*self._scalefactor
        return Region(self.x, self.y, w, h)

    @property
    def size(self):
        """Returns the size of the source image in canvas units. Note that any magnification
        via the width and height parameters is not factored in. For the displayed size, see
        the .bounds property."""
        return self._from_px(self._nsImage.size())

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
            dim, src_dim = max((self.width or 0, src.width), (self.height or 0, src.height))
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

        # calculate the pixel dimensions (accounting for the canvas's units)
        dx, dy = self._to_px(Point(self.x, self.y))
        w, h = self._to_px(self.size)

        # calculate the translation offset for centering (if any)
        nudge = Transform()
        if self._transformmode == CENTER:
            nudge.translate(w*factor/2, h*factor/2)

        xf.translate(dx, dy)       # set the position before applying transforms
        xf.prepend(nudge)          # nudge the image to its center (or not)
        xf.prepend(self.transform) # add context's CTM.
        xf.prepend(nudge.inverse)  # Move back to the real origin.
        xf.scale(factor)           # scale to fit size constraints (if any)
        return xf

    def _draw(self):
        """Draw an image on the given coordinates."""

        with _ns_context() as ns_ctx:
            self._screen_transform.concat() # move the image into place via transforms
            with self.effects.applied():    # apply any blend/alpha/shadow effects
                ns_ctx.setImageInterpolation_(NSImageInterpolationHigh)
                bounds = ((0,0), self._nsImage.size()) # draw the image at (0,0)
                self._nsImage.drawAtPoint_fromRect_operation_fraction_((0,0), bounds, NSCompositeSourceOver, self.alpha)
                # NB: the nodebox source warns about quartz bugs triggered by drawing
                # EPSs to other origin points. no clue whether this still applies...


### context manager for calls to `with export(...)` ###

import time
re_padded = re.compile(r'{(\d+)}')
class ImageWriter(object):
    def __init__(self, fname, format, **opts):
        self.mode = CMYK if opts['cmyk'] else _ctx._outputmode
        self.fname = os.path.expanduser(fname)
        self.format = format
        self.opts = opts
        self.anim = 'fps' in opts
        self.session = None

    def __enter__(self):
        self._pool = NSAutoreleasePool.alloc().init()
        _ctx._saveContext()
        _ctx._outputmode = self.mode
        return self

    def __exit__(self, type, value, tb):
        if not self.session:
            #
            # with export('out.png'):
            #     ... # draw a single frame
            #
            self.opts['single'] = True
            self.add()
        _ctx._restoreContext()
        self.finish()
        del self._pool


    def __del__(self):
        if not self.session:
            #
            # ... # draw a single frame
            # export('out.png')
            #
            m = re_padded.search(self.fname)
            fn = re_padded.sub('0'*int(m.group(1)), self.fname, count=1) if m else self.fname
            _ctx.canvas.save(fn, self.format)

    @property
    def page(self):
        """Clears the canvas, runs the code in the `with` block, then adds the canvas as a new pdf page.

        For example, to create a pdf with two pages, you could write:

            with export("multipage.pdf") as pdf:
                clear(all)
                ... # draw first page
                pdf.add()
                clear(all)
                ... # draw the next page
                pdf.add()

        With the `page` context manager it simplifies to:

            with export("multipage.pdf") as pdf:
                with pdf.page:
                    ... # draw first page
                with pdf.page:
                    ... # draw the next page
        """
        if self.format != 'pdf':
            badform = 'The `page` property can only be used in PDF exports (not %r)'%self.format
            raise DeviceError(badform)
        self.opts['single'] = True
        return self.frame

    @property
    @contextmanager
    def frame(self):
        """Clears the canvas, runs the code in the `with` block, then adds the canvas to the
        animation or image sequence.

        For example, to create a quicktime movie and write a single frame to it you could write:

            with export("anim.mov") as movie:
                canvas.clear()
                ... # draw the frame
                movie.add()

        With the `frame` context manager, this simplifies to:

            with export("anim.mov") as movie:
                with movie.frame:
                    ... # draw the frame

        You can also use the `frame` property when writing to a series of sequentially-named
        files. For example, to generate 'output-0001.png' through 'output-0100.png':

            with export('output.png') as seq:
                for i in xrange(100):
                    with seq.frame:
                        ... # draw the next image in the sequence

        Or if you'd like to control the numbering, specify a padding-width and location in
        the file name by including a '{n}' in the call to export(). The following will
        generate files named '01-output.png' through '100-output.png':

            with export('{2}-output.png') as seq:
                for i in xrange(100):
                    with seq.frame:
                        ... # draw the next image in the sequence
        """
        with autorelease():
            _ctx._saveContext()
            yield
            self.add()
            _ctx._restoreContext()

    def add(self):
        """Add a new frame or page with the current contents of the canvas."""
        if not self.session:
            if self.anim:
                self.session = MovieExportSession(self.fname, self.format, **self.opts)
            else:
                self.session = ImageExportSession(self.fname, self.format, **self.opts)
        self.session.add(_ctx.canvas)

    def finish(self):
        """Blocks until disk I/O is complete"""
        self.session.done()
        while True:
            if self.session.writer.doneWriting():
                break
            time.sleep(0.1)

