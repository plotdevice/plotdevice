import objc, cIO, os
from PyObjCTools import AppHelper
for cls in ["AnimatedGif", "ImageSequence", "SysAdmin", "Video"]:
    globals()[cls] = objc.lookUpClass(cls)

### Session objects which wrap the GCD-based export managers ###

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
        self._status = None

    def begin(self, frames=None, pages=None, console=False):
        from plotdevice.gui import set_timeout
        self.total = frames if frames is not None else pages
        self.poll = set_timeout(self, "update:", 0.1, repeat=True)

    def update_(self, note):
        self.written = self.writer.framesWritten()
        if self._progress:
            # let the delegate update the progress bar
            self._progress(self.written, self.total, self.cancelled)

        total = self.total if not self.cancelled else self.added
        if self.written == total:
            if self._status:
                self._status('complete')

            # AppHelper.callLater(0.2, self._shutdown)
            self._shutdown()

    def next(self):
        if self.cancelled or self.added==self.total:
            return None
        return self.added + 1

    def add(self, canvas):
        if self.cancelled:
            return False
        self.added += 1
        return True

    def cancel(self):
        if self.cancelled:
            return # be idem potent

        self.cancelled = True
        if self._status:
            self._status('cancelled')

    def done(self):
        if self._status and not self.cancelled:
            self._status('finishing')
        if self.writer:
            self.writer.closeFile()

    def _shutdown(self):
        self.running = False
        self._progress = None
        self._status = None
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

    def on_status(self, cb):
        if self.running:
            self._status = cb

class ImageExportSession(ExportSession):
    def __init__(self, fname, format='pdf', first=1, last=1, book=False, console=False, **rest):
        super(ImageExportSession, self).__init__()
        last = last or first
        self.begin(pages=last-first+1, console=console)
        self.format = format
        self.fname = fname
        self.book = book and format=='pdf'
        self.single_page = first==last
        self.writer = ImageSequence.alloc().initWithFile_paginated_(self.fname, self.book)

    def add(self, canvas):
        if super(ImageExportSession, self).add(canvas):
            image = canvas._getImageData(self.format)
            if self.single_page:
                with file(self.fname, 'w') as f:
                    f.write(image)
            else:
                self.writer.addPage_(image)

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

    def add(self, canvas):
        if super(MovieExportSession, self).add(canvas):
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

