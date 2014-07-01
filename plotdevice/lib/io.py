import objc, os, re
from PyObjCTools import AppHelper
import cIO
for cls in ["AnimatedGif", "Pages", "SysAdmin", "Video"]:
    globals()[cls] = objc.lookUpClass(cls)

### Session objects which wrap the GCD-based export managers ###

class ExportSession(object):

    def __init__(self):
        # state flags
        self.running = True
        self.cancelled = False
        self.added = 0
        self.written = 0
        self.total = 0

        # callbacks
        self._complete = None
        self._progress = None
        self._status = None

        # one of the cIO classes
        self.writer = None

    def begin(self, frames=None, pages=None):
        from plotdevice.gui import set_timeout
        self.total = frames if frames is not None else pages
        self.poll = set_timeout(self, "update:", 0.1, repeat=True)

    def update_(self, note):
        self.written = self.writer.framesWritten()
        if self._progress:
            # let the delegate update the progress bar
            goal = self.added if self.cancelled else self.total
            self._progress(self.written, goal, self.cancelled)

        if self.writer.doneWriting():
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
        if self._status:
            self._status('complete')
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


re_padded = re.compile(r'{(\d+)}')
class ImageExportSession(ExportSession):
    def __init__(self, fname, format='pdf', first=1, last=1, book=False, **rest):
        super(ImageExportSession, self).__init__()
        last = last or first
        self.begin(pages=last-first+1)
        self.single_page = first==last
        self.format = format

        if self.single_page or book:
            # output a single file (potentially a multipage PDF)
            self.writer = Pages.alloc().initWithFile_(fname)
        else:
            # output multiple, sequentially-named files
            m = re_padded.search(fname)
            if m:
                padding = int(m.group(1))
                name_tmpl = re_padded.sub('%%0%id'%padding, fname, count=1)
            else:
                basename, ext = os.path.splitext(fname)
                name_tmpl = "".join([basename, '-%04d', ext])
            self.writer = Pages.alloc().initWithPattern_(name_tmpl)

    def add(self, canvas):
        if super(ImageExportSession, self).add(canvas):
            image = canvas._getImageData(self.format)
            self.writer.addPage_(image)
            if self.single_page:
                self.done()

class MovieExportSession(ExportSession):
    def __init__(self, fname, format='mov', first=1, last=150, fps=30, bitrate=1, loop=0, **rest):
        super(MovieExportSession, self).__init__()
        try:
            os.unlink(fname)
        except:
            pass

        self.begin(frames=last-first+1)
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

