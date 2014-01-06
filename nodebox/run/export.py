import sys, os
from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper
from math import floor

try:
    import cIO
except ImportError:
    from pprint import pprint
    pprint(sys.path)

IMG_BATCH_SIZE = 8
MOV_BATCH_SIZE = 16

# map in the objc classes from the cIO module
AnimatedGif, ImageSequence, Installer, Video = [objc.lookUpClass(c) for c in "AnimatedGif", "ImageSequence", "Installer", "Video"]

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
        self.poll = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                                    0.1,self,"update:",None,True)

    def update_(self, note):
        if self.writer:
            self.written = self.writer.framesWritten()
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
        self.writer = ImageSequence.alloc().init()

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

    def add(self, canvas, frame):
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
                self._shutdown()
        self.writer.addFrame_(image)
        self.added += 1

    def done(self):
        if self.writer:
            self.writer.closeFile()
