import os
from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

class ImageExportSession(object):
    def __init__(self, fname, pages, format, batches=[]):
        self.pages = pages
        self.format = format
        self.fname = fname
        self.batches = batches
        self.added = 0
        self.seq = ImageSequence.alloc().initWithFormat_pages_(format, pages)
        self.progress = ProgressBarController.alloc().initWithCallback_(self.progress)
        self.progress.begin("Generating %s pages..." % pages, 2 * pages)

    def progress(self, cancel=False):
        if cancel:
            self.batches = []
            self._shutdown()
        written = self.seq.pagesWritten()
        if written == self.pages:
            AppHelper.callLater(0.4, self._shutdown)
        return self.added + written

    def add(self, canvas_or_context, frame):
        basename, ext = os.path.splitext(self.fname)
        fn = "%s-%05d%s" % (basename, frame, ext)
        image = canvas_or_context._getImageData(self.format)
        self.seq.writeData_toFile_(image, fn)
        self.added += 1

    def done(self):
        pass

    def _shutdown(self):
        self.progress.end()


class MovieExportSession(object):
    movie = None

    def __init__(self, fname, frames=60, fps=30, loop=0, batches=[]):
        try:
            os.unlink(fname)
        except:
            pass

        basename, ext = fname.rsplit('.',1)
        self.fname = fname
        self.ext = ext.lower()
        self.fps = fps
        self.loop = loop
        self.frames = frames
        self.batches = batches
        self.added = 0
        self.progress = ProgressBarController.alloc().initWithCallback_(self.progress)
        self.progress.begin("Generating %s frames..." % frames, 2 * frames)

    def progress(self, cancel=False):
        if cancel:
            NSLog("halt Movie Export")
            self.batches = []
            self._shutdown()
        if not self.movie:
            return 0
        written = self.movie.framesWritten()
        if written == self.frames:
            AppHelper.callAfter(self._shutdown)
        return self.added + written

    def add(self, canvas_or_context, frame):
        image = canvas_or_context._nsImage
        if not self.movie:
            if self.ext == 'mov':
                self.movie = Animation.alloc().initWithFile_size_fps_(
                   self.fname, image.size(), self.fps
                )
            elif self.ext == 'gif':
                self.movie = AnimatedGif.alloc().initWithFile_size_fps_loop_(
                   self.fname, image.size(), self.fps, self.loop
                )
            else:
                raise 'unrecognized output format: %s' % ext
                self._shutdown()

        self.movie.addFrame_(image)
        self.added += 1

    def done(self):
        self.movie.closeFile()

    def _shutdown(self):
        self.progress.end()

class ProgressBarController(NSWindowController):
    messageField = objc.IBOutlet()
    progressBar = objc.IBOutlet()
    poll = None
    update_fn = None

    def initWithCallback_(self, cb):
        NSBundle.loadNibNamed_owner_("ProgressBarSheet", self)
        self.poll = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                                    0.05,self,"update:",None,True)
        self.update_fn = cb
        return self

    def begin(self, message, maxval):
        self.value = 0
        self.message = message
        self.maxval = maxval
        self.progressBar.setMaxValue_(self.maxval)
        self.messageField.cell().setTitle_(self.message)
        parentWindow = NSApp().keyWindow()
        NSApp().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(self.window(), parentWindow, self, None, 0)
        self.poll.fire()

    def update_(self, note):
        self.step(self.update_fn())

    def step(self, toVal):
        self.value = toVal
        self.progressBar.setDoubleValue_(self.value)

    def end(self):
        self.poll.invalidate()
        NSApp().endSheet_(self.window())
        self.window().orderOut_(self)

    @objc.IBAction
    def cancelOperation_(self, sender):
        self.update_fn(cancel=True)
