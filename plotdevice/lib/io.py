import objc, os, re
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
            self.shutdown()

    def next(self):
        if self.cancelled or self.added==self.total:
            return None
        return self.added + 1

    def cancel(self):
        if self.cancelled:
            return # be idem potent

        self.cancelled = True
        if self._status:
            self._status('cancelled')

    def done(self):
        # if self._status:
        #     self._status('finishing')
        if self.writer:
            self.writer.closeFile()

    def shutdown(self):
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

    def on(self, **handlers):
        for event, cb in handlers.items():
            setattr(self, '_'+event, cb)
        if 'complete' in handlers and not self.running:
            self.shutdown() # call the handler immediately

re_padded = re.compile(r'{(\d+)}')
class ImageExportSession(ExportSession):
    def __init__(self, fname, format='pdf', first=1, last=None, single=False, **rest):
        super(ImageExportSession, self).__init__()
        self.single_file = single or first==last
        if last is not None:
            self.begin(pages=last-first+1)
        self.format = format

        m = re_padded.search(fname)
        pad = '%%0%id' % int(m.group(1)) if m else None

        if self.single_file:
            # output a single file (potentially a multipage PDF)
            if pad:
                fname = re_padded.sub(pad%0, fname, count=1)
            self.writer = Pages.alloc().initWithFile_(fname)
        else:
            # output multiple, sequentially-named files
            if pad:
                name_tmpl = re_padded.sub(pad, fname, count=1)
            else:
                basename, ext = os.path.splitext(fname)
                name_tmpl = "".join([basename, '-%04d', ext])
            self.writer = Pages.alloc().initWithPattern_(name_tmpl)

    def add(self, canvas):
        image = canvas._getImageData(self.format)
        self.writer.addPage_(image)
        self.added += 1

class MovieExportSession(ExportSession):
    def __init__(self, fname, format='mov', first=1, last=None, fps=30, bitrate=1, loop=0, **rest):
        super(MovieExportSession, self).__init__()
        try:
            os.unlink(fname)
        except:
            pass
        if last is not None:
            self.begin(frames=last-first+1)
        self.fname = fname
        self.format = format
        self.fps = fps
        self.loop = loop
        self.bitrate = bitrate

    def add(self, canvas):
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
                print 'unrecognized output format: %s' % self.format
                return self.shutdown()
        self.writer.addFrame_(image)
        self.added += 1

