import sys, os
from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper
from math import floor

IMG_BATCH_SIZE = 8
MOV_BATCH_SIZE = 40

class ExportSession(object):
    running = True
    writer = None
    callback = None
    added = 0
    written = 0
    total = 0

    def __init__(self):
        super(ExportSession, self).__init__()

    def begin(self, frames=None, pages=None, console=False):
        ProgBar = ASCIIProgressBar if console else ProgressBarController
        self.progress = ProgBar.alloc().initWithCallback_(self.status)
        if frames is not None:
            msg = "Generating %s frames" % frames
            self.total = frames
        else:
            msg = "Generating %s pages" % pages
            self.total = pages
        self.progress.begin(msg, self.total)

        
    def status(self, cancel=False):
        if cancel:
            self.batches = []
            self._shutdown()
            return

        if not self.writer:
            return 0
        self.written = self.writer.framesWritten()
        if self.written == self.total:
            self._complete()
        return self.written

    def _complete(self):
        self.progress.complete()
        AppHelper.callLater(0.2, self._shutdown)

    def _shutdown(self):
        self.running = False
        self.progress.end()
        if self.callback:
            self.callback()
            self.callback = None

    def on_complete(self, cb):
        if not self.running: cb()
        else: self.callback = cb

class ImageExportSession(ExportSession):
    def __init__(self, fname, pages, format, first=1, console=False):
        super(ImageExportSession, self).__init__()
        self.begin(pages=pages-first+1, console=console)
        self.format = format
        self.fname = fname
        self.batches = [(n, min(n+IMG_BATCH_SIZE-1,pages)) for n in range(first, pages+1, IMG_BATCH_SIZE)]
        self.writer = ImageSequence.alloc().init()

    def add(self, canvas_or_context, frame):
        basename, ext = os.path.splitext(self.fname)
        fn = "%s-%05d%s" % (basename, frame, ext)
        image = canvas_or_context._getImageData(self.format)
        self.writer.writeData_toFile_(image, fn)
        self.added += 1

    def done(self):
        pass

class MovieExportSession(ExportSession):
    def __init__(self, fname, frames=60, fps=30, loop=0, first=1, console=False):
        super(MovieExportSession, self).__init__()
        try:
            os.unlink(fname)
        except:
            pass
        self.begin(frames=frames-first+1, console=console)
        basename, ext = fname.rsplit('.',1)
        self.fname = fname
        self.ext = ext.lower()
        self.fps = fps
        self.loop = loop
        self.batches = [(n, min(n+MOV_BATCH_SIZE-1,frames)) for n in range(first, frames+1, MOV_BATCH_SIZE)]

    def add(self, canvas_or_context, frame):
        image = canvas_or_context._nsImage
        if not self.writer:
            dims = image.size()
            if self.ext == 'mov':
                self.writer = Animation.alloc()
                self.writer.initWithFile_size_fps_(self.fname, dims, self.fps)
            elif self.ext == 'gif':
                self.writer = AnimatedGif.alloc()
                self.writer.initWithFile_size_fps_loop_(self.fname, dims, self.fps, self.loop)
            else:
                NSLog('unrecognized output format: %s' % ext)
                self._shutdown()
        self.writer.addFrame_(image)
        self.added += 1

    def done(self):
        if self.writer:
            self.writer.closeFile()

class ASCIIProgressBar(NSObject):
    poll = None
    status_fn = None
    _stderr = None

    def initWithCallback_(self, cb):
        self.status_fn = cb
        self._stderr = sys.stderr
        return self

    def begin(self, message, maxval):
        self.value = 0
        self.message = '%s:'%message
        self.maxval = maxval
        self.poll = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                                    0.1,self,"update:",None,True)
        self.poll.fire()

    def update_(self, note):
        self.step(self.status_fn())

    def _render(self, width=20):
        pct = int(floor(width*self.value/self.maxval))
        dots = "".join(['#'*pct]+['.']*(width-pct))
        msg = "\r%s [%s]\n"%(self.message, dots)
        self._stderr.write(msg)
        self._stderr.flush()

    def step(self, toVal):
        if self.poll.isValid():
            self.value = toVal
            self._render()

    def complete(self):
        self.value = self.maxval
        self._render()
        if self.poll:
            self.poll.invalidate()

    def end(self, delay=0):
        if self.poll:
            self.poll.invalidate()

class ProgressBarController(NSWindowController):
    messageField = objc.IBOutlet()
    progressBar = objc.IBOutlet()
    poll = None
    status_fn = None

    def initWithCallback_(self, cb):
        NSBundle.loadNibNamed_owner_("ProgressBarSheet", self)
        self.poll = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                                    0.25,self,"update:",None,True)
        self.status_fn = cb
        return self

    def begin(self, message, maxval):
        self.value = 0
        self.message = '%s...'%message
        self.maxval = maxval
        self.progressBar.setMaxValue_(self.maxval)
        self.messageField.cell().setTitle_(self.message)
        parentWindow = NSApp().keyWindow()
        NSApp().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(self.window(), parentWindow, self, None, 0)

    def update_(self, note):
        self.step(self.status_fn())

    def step(self, toVal):
        self.value = toVal
        self.progressBar.setDoubleValue_(self.value)

    def complete(self):
        self.progressBar.setDoubleValue_(self.maxval)
        if self.poll:
            self.poll.invalidate()
            self.poll = None

    def end(self, delay=0):
        if self.poll:
            self.poll.invalidate()
            self.poll = None
        NSApp().endSheet_(self.window())
        self.window().orderOut_(self)

    @objc.IBAction
    def cancelOperation_(self, sender):
        self.status_fn(cancel=True)
