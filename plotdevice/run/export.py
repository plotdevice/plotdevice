import sys, os, re
from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper
from math import floor
import plotdevice

from plotdevice.lib.io import AnimatedGif, SysAdmin, Video, ImageSequence as _ImageSequence

IMG_BATCH_SIZE = 8
MOV_BATCH_SIZE = 16

#
# GUI-based exports
#
class ExportSession(object):
    running = True
    cancelled = False
    writer = None
    added = 0
    written = 0
    total = 0

    def __init__(self):
        self._complete = None
        self._progress = None
        super(ExportSession, self).__init__()

    def begin(self, frames=None, pages=None, console=False):
        self.total = frames if frames is not None else pages
        if plotdevice.app:
            # only rely on a runloop if one exists. let plotdevice.script invocations handle their own timers
            self.poll = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                                    0.1,self,"update:",None,True)

    def count(self):
        self.written = self.writer.framesWritten()
        return self.written, self.added

    def update_(self, note):
        self.count()

        if self.writer:
            if self._progress:
                # let the delegate update the progress bar
                self._progress(self.written, self.total, self.cancelled)

            total = self.total if not self.cancelled else self.added
            if self.written == total:
                AppHelper.callLater(0.2, self._shutdown)

    def cancel(self):
        self.cancelled = True
        self.batches = []

    def _shutdown(self):
        self.running = False
        self._progress = None
        if self.poll:
            self.poll.invalidate()
            self.poll = None
        if self._complete:
            self._complete()
            self._complete = None
        self.writer = None

    def on_complete(self, cb):
        if not self.running:
            cb()
        else:
            self._complete = cb

    def on_progress(self, cb):
        if self.running:
            self._progress = cb

class ImageExportSession(ExportSession):
    def __init__(self, fname, format='pdf', first=1, last=1, console=False, **rest):
        super(ImageExportSession, self).__init__()
        last = last or first
        self.begin(pages=last-first+1, console=console)
        self.format = format
        self.fname = fname
        self.single_page = first==last
        self.batches = [(n, min(n+IMG_BATCH_SIZE-1,last)) for n in range(first, last+1, IMG_BATCH_SIZE)]
        self.writer = _ImageSequence.alloc().init()

    def add(self, canvas, frame):
        if self.cancelled: return
        if self.single_page:
            fn = self.fname
        else:
            basename, ext = os.path.splitext(self.fname)
            fn = "%s-%05d%s" % (basename, frame, ext)
        image = canvas._getImageData(self.format)
        self.writer.writeData_toFile_(image, fn)
        self.added += 1

    def done(self):
        pass

class MovieExportSession(ExportSession):
    def __init__(self, fname, format='mov', first=1, last=150, fps=30, bitrate=1, loop=0, console=False, **rest):
        super(MovieExportSession, self).__init__()
        try:
            os.unlink(fname)
        except:
            pass
        self.begin(frames=last-first+1, console=console)
        self.fname = fname
        self.format = format
        self.fps = fps
        self.loop = loop
        self.bitrate = bitrate
        self.batches = [(n, min(n+MOV_BATCH_SIZE-1,last)) for n in range(first, last+1, MOV_BATCH_SIZE)]

    def add(self, canvas, frame=1):
        if self.cancelled: return
        image = canvas.rasterize()
        if not self.writer:
            dims = image.size()
            if self.format == 'mov':
                self.writer = Video.alloc()
                self.writer.initWithFile_size_fps_bitrate_(self.fname, dims, self.fps, self.bitrate)
            elif self.format == 'gif':
                self.writer = AnimatedGif.alloc()
                self.writer.initWithFile_size_fps_loop_(self.fname, dims, self.fps, self.loop)
            else:
                NSLog('unrecognized output format: %s' % self.format)
                return self._shutdown()
        self.writer.addFrame_(image)
        self.added += 1

    def done(self):
        if self.writer:
            self.writer.closeFile()




#
# Headless exports - export() command and format-specific context managers
#
import time, sys, re
from contextlib import contextmanager
from Quartz.PDFKit import *

# create the appropriate context manager and return it
def export(ctx, fname, fps=None, loop=None, bitrate=1.0):
    format = fname.rsplit('.',1)[1]
    fname = re.sub(r'^~(?=/|$)',os.getenv('HOME'),fname)
    if format=='mov' or (format=='gif' and fps or loop is not None):
        fps = fps or 30 # set a default for .mov exports
        loop = {True:-1, False:0, None:0}.get(loop, loop) # convert bool args to int
        return Movie(ctx, fname, format, fps=fps, bitrate=bitrate, loop=loop)
    elif format=='pdf':
        return PDF(ctx, fname)
    elif format in ('eps','png','jpg','gif','tiff'):
        return ImageSequence(ctx, fname, format)
    else:
        unknown = 'Unknown export format "%s"'%format
        raise RuntimeError(unknown)

# Context manager returned by `export` when an animation file extension is provided
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
    def __init__(self, ctx, *args, **opts):
        self._ctx = ctx
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
        self._ctx._saveContext()
        self._ctx.canvas.clear()
        yield
        self.add()
        self._ctx._restoreContext()

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

# Context manager returned by `export` when an image-type file extension is provided
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
    def __init__(self, ctx, fname, format):
        self._ctx = ctx
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
        self._ctx._saveContext()
        self._ctx.canvas.clear()
        return self
    def __exit__(self, type, value, tb):
        if self.idx is None:
            self._ctx.canvas.save(self.fname, self.format)
        self._ctx._restoreContext()

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
        self._ctx._saveContext()
        self._ctx.canvas.clear()
        yield
        if self.idx is None:
            self.idx = 1
        self._ctx.canvas.save(self.tmpl%self.idx, self.format)
        self.idx += 1
        self._ctx._restoreContext()

# Context manager returned by `export` for PDF files (allowing single or multi-page docs)
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
    def __init__(self, ctx, fname):
        self._ctx = ctx
        self.fname = fname
        self.doc = None
    def __enter__(self):
        self._ctx._saveContext()
        self._ctx.canvas.clear()
        return self
    def __exit__(self, type, value, tb):
        self.finish() or self._ctx.canvas.save(self.fname, 'pdf')
        self._ctx._restoreContext()

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
        self._ctx._saveContext()
        self._ctx.canvas.clear()
        yield
        self.add()
        self._ctx._restoreContext()

    def add(self):
        """Add a new page to the PDF with the current contents of the canvas."""
        pagedoc = PDFDocument.alloc().initWithData_(canvas._getImageData('pdf'))
        if not self.doc:
            self.doc = pagedoc
        else:
            self.doc.insertPage_atIndex_(pagedoc.pageAtIndex_(0), self.doc.pageCount())

    def finish(self):
        """Writes the fully-assembled PDF to disk"""
        if self.doc:
            self.doc.writeToFile_(self.fname)
        return self.doc




