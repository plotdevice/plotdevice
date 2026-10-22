# encoding: utf-8
import os
import re
import sys
import json
import queue
import threading
import warnings
import math
import objc
from contextlib import contextmanager
from urllib.parse import urlparse
from ..lib.cocoa import *

from plotdevice import DeviceError
from ..util import _copy_attrs, autorelease
from ..util.readers import get_http_session, last_modified
from ..lib.io import MovieExportSession, ImageExportSession
from .geometry import Region, Size, Point, Transform, CENTER, IDENTITY, _pivot
from .atoms import TransformMixin, EffectsMixin, FrameMixin, Grob
from .colors import RGB, CMYK
from . import _ns_context, _cg_port, _frame

PDSVGImageRep = objc.lookUpClass('PDSVGImageRep')

_ctx = None
__all__ = ("Image", 'ImageWriter')

### The bitmap/vector image-container (a.k.a. NSImage proxy) ###

class Image(EffectsMixin, TransformMixin, FrameMixin, Grob):
    stateAttrs = ('_nsImage',)
    opts = ('data', 'src', 'image')

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
            elif isinstance(src, str):
                self._nsImage = self._lazyload(path=src)
            else:
                invalid = "Not a valid image source: %r" % type(src)
                raise DeviceError(invalid)
        else:
            undefined = "Image requires either a source (path/url/Image) or image data"
            raise DeviceError(undefined)

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

    def copy(self):
        clone = Image.__new__(Image)
        clone._nsImage = self._nsImage # never edited in place, so copies share it
        clone._frame = self._frame.copy()
        clone._transform = self._transform.copy()
        clone._effects = self._effects.copy()
        clone._grid, clone._transformmode = self._grid, self._transformmode
        return clone

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
            if b'<svg' in data.getBytes_length_(None, 128):
                image = NSImage.svgFromData_(data)
            else:
                image = NSImage.alloc().initWithData_(data)
        elif path is not None:
            if re.match(r'https?:', path):
                # load from url
                key = err_info = path
                resp = get_http_session().get(path)
                mtime = last_modified(resp)
                # return a cached image if possible...
                if path in _cache and _cache[path][1] >= mtime:
                    return _cache[path][0]
                # ...or load from the data
                data = NSData.dataWithBytes_length_(resp.content, len(resp.content))
                if 'svg' in resp.headers['Content-Type'] or urlparse(path).path.lower().endswith('.svg'):
                    image = NSImage.svgFromData_(data)
                else:
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
                if path.lower().endswith('.svg'):
                    image = NSImage.svgFromURL_(NSURL.fileURLWithPath_(path))
                else:
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
        warnings.warn("The 'image' attribute is deprecated. Please use _nsImage instead.", FutureWarning, stacklevel=2)
        return self._nsImage

    @property
    def _nsBitmap(self):
        for bitmap in self._nsImage.representations():
            # if we already have a bitmap representation, use that...
            if isinstance(bitmap, NSBitmapImageRep):
                break
        else:
            # ...otherwise convert the vector image to a bitmap at its native size.
            # it will only be used for a hasAlpha() check in effects.py, so the actual
            # pixel data needn't match its _screen_size
            tiffdata = self._nsImage.TIFFRepresentation()
            image = NSImage.alloc().initWithData_(tiffdata)
            bitmap = image.representations()[0]
        return bitmap

    @property
    def _ciImage(self):
        """A CIImage suitable for use as a clip()/mask() stencil.

        Raster sources are used as-is. Vector sources are scaled to the size
        they'll actually occupy on the canvas before being rasterized.
        """

        # if the image is raster-based, use its bitmap as-is
        for bitmap in self._nsImage.representations():
            if isinstance(bitmap, NSBitmapImageRep):
                break
        else:
            # if vector-based, rasterize it at its 'actual' on-screen size
            w, h = self._screen_size

            # create an offscreen bitmap context and rasterize the scaled image into it
            bitmap_opts = kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Host
            bitmap_ctx = CGBitmapContextCreate(None, w, h, 8, w*4, CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3), bitmap_opts)
            CGContextTranslateCTM(bitmap_ctx, 0, h)
            CGContextScaleCTM(bitmap_ctx, 1, -1)
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.setCurrentContext_(
              NSGraphicsContext.graphicsContextWithCGContext_flipped_(bitmap_ctx, True)
            )
            self._nsImage.drawInRect_fromRect_operation_fraction_(((0,0),(w,h)), NSZeroRect, NSCompositeSourceOver, 1.0)
            NSGraphicsContext.restoreGraphicsState() # NB: class-level restore also resets currentContext

            bitmap = NSBitmapImageRep.alloc().initWithCGImage_(CGBitmapContextCreateImage(bitmap_ctx))

        # core-image needs to be told to compensate for our flipped coords
        flip = NSAffineTransform.transform()
        flip.translateXBy_yBy_(0, bitmap.pixelsHigh())
        flip.scaleXBy_yBy_(1,-1)

        ciImage = CIImage.alloc().initWithBitmapImageRep_(bitmap)
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
    def _screen_matrix(self):
        """The transform incorporates the global context state but also accounts for
        centering and max width/height values set in the constructor."""

        # set scale factor so entire image fits in the given rect or dimension
        factor = self._scalefactor

        # calculate the pixel dimensions (accounting for the canvas's units)
        dx, dy = self._to_px(Point(self.x, self.y))

        matrix = tuple(self.transform.matrix)
        if self._transformmode == CENTER and matrix != IDENTITY:
            w, h = self._to_px(self.size)
            a, b, c, d, tx, ty = _pivot(matrix, w * factor / 2, h * factor / 2, dx, dy)
        else:
            # in CORNER mode (or if untransformed) simply apply the CTM
            a, b, c, d, mx, my = matrix
            tx, ty = mx + dx, my + dy
        return (a * factor, b * factor, c * factor, d * factor, tx, ty) # scale to fit size constraints (if any)

    @property
    def _screen_transform(self):
        """Returns the Transform object that will be used to draw the image."""
        return Transform(self._screen_matrix)

    @property
    def _screen_size(self):
        """Returns the image's real pixel dimensions.

        Raster-backed images return their native size, but vector-based images incorporate
        the canvas's current CTM and the image's scaling based on its _screen_transform."""

        # if the image is raster-based, use its native size
        for bitmap in self._nsImage.representations():
            if isinstance(bitmap, NSBitmapImageRep):
                return bitmap.pixelsWide(), bitmap.pixelsHigh()

        # if vector-based, use the canvas's CTM and the image's _screen_transform to
        # determine its 'actual' size (rather than just using its mediabox 1:1)
        ctm = CGContextGetCTM(_cg_port())
        ctm_scale = max(math.hypot(ctm.a, ctm.b), math.hypot(ctm.c, ctm.d))
        xf_a, xf_b, xf_c, xf_d, _, _ = self._screen_matrix
        xf_scale = max(math.hypot(xf_a, xf_b), math.hypot(xf_c, xf_d))
        scale = max(ctm_scale * xf_scale, 1.0)
        src_w, src_h = self._nsImage.size()

        return max(1, round(src_w * scale)), max(1, round(src_h * scale))

    @property
    def _outline(self):
        """A Bezier in the image's local pixel space tracing its shape(s), for use
        as a vector clip()/mask() stencil (channel='outline').

        Raster images get a rect matching their dimensions. PDF/SVG images get
        the union of every shape in the graphic (PDFs are traced from their raw
        content stream; SVGs are traced from the parsed shape/command list)."""
        from .bezier import Bezier
        from ..lib import pathmatics

        w, h = self._nsImage.size()
        for bitmap in self._nsImage.representations():
            if isinstance(bitmap, NSBitmapImageRep):
                outline = Bezier()
                outline.rect(0, 0, w, h)
                return outline
            if isinstance(bitmap, NSPDFImageRep):
                ns_path = pathmatics.pdf_outline(bitmap.PDFRepresentation())
                # pdf content streams are y-up/bottom-left; flip to match our y-down convention
                flip = Transform()
                flip.translate(0, h)
                flip.scale(1, -1)
                return flip.apply(Bezier(ns_path))
            if isinstance(bitmap, PDSVGImageRep):
                # svg paths are already y-down
                return Bezier(bitmap.outline())

        # no rep we know how to trace
        return Bezier()

    def _draw(self):
        """Draw an image on the given coordinates."""

        with _ns_context():
            self._screen_transform.concat() # move the image into place via transforms
            with self.effects.applied(self):  # apply any blend/alpha/shadow effects
                NSGraphicsContext.currentContext().setImageInterpolation_(NSImageInterpolationHigh)
                image = self._nsImage
                frame = _frame.get()
                if frame is not None and frame.outputmode == CMYK and frame.colors is not None:
                    rep = next((r for r in image.representations() if isinstance(r, NSBitmapImageRep)), None)
                    cg = rep.CGImage() if rep is not None else None
                    if cg is not None and CGColorSpaceGetModel(CGImageGetColorSpace(cg)) == kCGColorSpaceModelCMYK:
                        image = NSImage.alloc().initWithCGImage_size_(CGImageCreateCopyWithColorSpace(cg, CGColorSpaceCreateDeviceCMYK()), image.size())
                        image.setFlipped_(True)
                bounds = ((0,0), image.size()) # draw the image at (0,0)
                image.drawAtPoint_fromRect_operation_fraction_((0,0), bounds, NSCompositeSourceOver, self.alpha)
                # NB: the nodebox source warns about quartz bugs triggered by drawing
                # EPSs to other origin points. no clue whether this still applies...

### context manager for calls to `with export(...)` ###

import time
re_padded = re.compile(r'{(\d+)}')
free_threaded = not getattr(sys, '_is_gil_enabled', lambda: True)()

class SequenceRenderer(object):
    def __init__(self):
        self.error = None
        self._failed = False
        self._jobs = queue.Queue(maxsize=1)
        self._thread = threading.Thread(target=self._loop, daemon=True, name='export-render')
        self._thread.start()

    def __call__(self, frame, work):
        self.check()
        self._jobs.put((frame, work))

    def check(self):
        if self.error is not None:
            error, self.error = self.error, None
            raise error

    def stop(self):
        self._jobs.put(None)
        self._thread.join()

    def _loop(self):
        while (job := self._jobs.get()) is not None:
            frame, work = job
            if self._failed and frame is not None:
                continue
            try:
                with autorelease():
                    work(None)
            except Exception as err:
                self._failed, self.error = True, err

class ImageWriter(object):
    def __init__(self, fname, format, **opts):
        self.mode = CMYK if opts['colors'] == CMYK else RGB
        self.fname = os.path.expanduser(fname)
        self.format = format
        self.opts = opts
        self.anim = 'fps' in opts
        if format == 'pdf' and not self.anim:
            self.opts['single'] = not re_padded.search(self.fname)
        self.session = None
        self.renderer = None # with the GIL off, renders the frames added to a sequence on a thread of their own

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
            self._session().add(_ctx.canvas)
        _ctx._restoreContext()
        try:
            self.finish()
        except Exception:
            if type is None:
                raise # (else the script's own exception is the one to report)
        del self._pool


    def __del__(self):
        if not self.session:
            #
            # ... # draw a single frame
            # export('out.png')
            #
            m = re_padded.search(self.fname)
            fn = re_padded.sub('0'*int(m.group(1)), self.fname, count=1) if m else self.fname
            _ctx.canvas.save(fn, self.format, self.opts['zoom'], colors=self.opts['colors'])

    @property
    def page(self):
        """Clears the canvas, runs the code in the `with` block, then adds the canvas as a new pdf page.
        In a PDF export `frame` does the same, but `page` also checks that the export is a document: a numbered
        file name like 'page-{4}.pdf' writes a sequence of single-page files instead, and `page` refuses it.

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
        if not self.opts['single']:
            numbered = 'The `page` property makes pages of one PDF, but %r is numbered for a sequence of files (use `frame`)' % os.path.basename(self.fname)
            raise DeviceError(numbered)
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

        In a PDF export, each frame is a page of the document (as with `page`), unless the file name
        is numbered (see below), which writes each to a file of its own.

        You can also use the `frame` property when writing to a series of sequentially-named
        files. For example, to generate 'output-0001.png' through 'output-0100.png':

            with export('output.png') as seq:
                for i in range(100):
                    with seq.frame:
                        ... # draw the next image in the sequence

        Or if you'd like to control the numbering, specify a padding-width and location in
        the file name by including a '{n}' in the call to export(). The following will
        generate files named '01-output.png' through '100-output.png':

            with export('{2}-output.png') as seq:
                for i in range(100):
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
        if self.renderer is None and free_threaded:
            self.renderer = SequenceRenderer()
        self._session().add(_ctx.canvas, self.renderer)

    def _session(self):
        if not self.session:
            if self.anim:
                self.session = MovieExportSession(self.fname, self.format, **self.opts)
            else:
                self.session = ImageExportSession(self.fname, self.format, **self.opts)
        return self.session

    def finish(self):
        """Blocks until disk I/O is complete"""
        self.session.done(self.renderer)
        if self.renderer is not None:
            self.renderer.stop()
        while True:
            if self.session.writer.doneWriting():
                break
            time.sleep(0.1)
        if self.renderer is not None:
            self.renderer.check()
        if isinstance(self.session, MovieExportSession) and self.session.writer_failed():
            raise DeviceError("Export failed: encoding error")
