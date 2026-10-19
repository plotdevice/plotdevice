import objc, os, re, time
from .cocoa import CGBitmapContextCreateImage, CGContextBeginPage, CGContextEndPage, CGPDFContextClose, \
                   CGPDFContextCreateWithURL, CGRectMake, NSBitmapImageRep, NSURL

for cls in ["AnimatedGif", "Pages", "SysAdmin", "Video"]:
    globals()[cls] = objc.lookUpClass(cls)

class PDFBook(object):

    def __init__(self, fname, zoom=1.0):
        self.zoom = zoom
        self.pages = 0
        self.closed = False
        self.context = CGPDFContextCreateWithURL(NSURL.fileURLWithPath_(fname), None, None)

    def addPage_(self, frame):
        w, h = frame.pagesize
        CGContextBeginPage(self.context, CGRectMake(0, 0, w * self.zoom, h * self.zoom))
        frame._render_to_context(self.context, self.zoom)
        CGContextEndPage(self.context)
        self.pages += 1

    def closeFile(self):
        CGPDFContextClose(self.context)
        self.context = None
        self.closed = True

    def framesWritten(self):
        return self.pages

    def doneWriting(self):
        return self.closed

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

        self.on_main = False

        self.presents = False

    @property
    def backlogged(self):
        if self.writer is None:
            return False
        return self.added - self.writer.framesWritten() > 4

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

    def done(self, render=None):
        # if self._status:
        #     self._status('finishing')
        if self.writer:
            writer = self.writer
            if render is None or self.on_main:
                writer.closeFile()
            else:
                render(None, lambda cancelled: writer.closeFile())

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
    def __init__(self, fname, format='pdf', zoom=1.0, first=1, last=None, single=False, **rest):
        super(ImageExportSession, self).__init__()
        self.single_file = single or first==last
        if last is not None:
            self.begin(pages=last-first+1)
        self.format = format
        self.zoom = zoom
        self.cmyk = rest.get('cmyk', False)
        self.on_main = format == 'eps' # (it's drawn through an NSView)
        cmyk_bitmap = self.cmyk and format in ('jpeg', 'jpg', 'tiff')
        self.presents = format not in ('pdf', 'eps') and not cmyk_bitmap

        m = re_padded.search(fname)
        pad = '%%0%id' % int(m.group(1)) if m else None

        if self.single_file:
            # output a single file (potentially a multipage PDF)
            if pad:
                fname = re_padded.sub(pad%0, fname, count=1)
            if format == 'pdf':
                self.writer = PDFBook(fname, zoom)
            else:
                self.writer = Pages.alloc().initWithFile_(fname)
        else:
            # output multiple, sequentially-named files
            if pad:
                name_tmpl = re_padded.sub(pad, fname, count=1)
            else:
                basename, ext = os.path.splitext(fname)
                name_tmpl = "".join([basename, '-%04d', ext])
            self.writer = Pages.alloc().initWithPattern_(name_tmpl)

    def add(self, canvas, render=None):
        frame = canvas.commit()
        writer, format, zoom, cmyk = self.writer, self.format, self.zoom, self.cmyk
        def work(cancelled):
            if isinstance(writer, PDFBook):
                writer.addPage_(frame)
                return None
            image, surface = frame._encode(format, zoom, cmyk, cancelled)
            if image is not None:
                writer.addPage_(image)
            return surface
        if render is None or self.on_main:
            work(None)
        else:
            render(frame, work)
        self.added += 1

class MovieExportSession(ExportSession):
    CODECS = ('hevc', 'h264', 'prores') # a .mov's (in Video's numbering), ProRes being 4444 with alpha

    def __init__(self, fname, format='mov', first=1, last=None, fps=30, bitrate=1, loop=0, codec='hevc', **rest):
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
        self.codec = codec
        self.cmyk = False
        self.presents = True

    def add(self, canvas, render=None):
        if self.format not in ('mov', 'gif'):
            print('unrecognized output format: %s' % self.format)
            return self.shutdown()

        frame = canvas.commit()
        if not self.writer:
            size = frame._raster_size(1)
            if self.format == 'mov':
                size = self.size = tuple(dim - dim % 2 for dim in size)
                self.writer = Video.alloc()
                codec = MovieExportSession.CODECS.index(self.codec)
                self.writer.initWithFile_size_fps_bitrate_codec_(self.fname, size, self.fps, self.bitrate, codec)
            else:
                self.writer = AnimatedGif.alloc()
                self.writer.initWithFile_size_fps_loop_(self.fname, size, self.fps, self.loop)
        writer, straight = self.writer, self.codec == 'prores'

        if self.format == 'mov':
            def work(cancelled):
                if straight:
                    rendered = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(*self.size)
                    frame._render_to_surface(rendered, 1, cancelled, origin=(0, 0))
                    if cancelled is not None and cancelled():
                        return None
                    while not writer.addUnpremultiplied_(rendered):
                        stopped = cancelled is not None and cancelled()
                        if stopped or writer.failed():
                            return None
                        time.sleep(0.002)
                    return rendered

                surface = writer.nextSurface()
                while surface is None:
                    stopped = cancelled is not None and cancelled()
                    if stopped or writer.failed():
                        return None
                    time.sleep(0.002)
                    surface = writer.nextSurface()
                frame._render_to_surface(surface, 1, cancelled, origin=(0, 0)) # (from the top-left, so a bottom row is what's lost)
                if cancelled is not None and cancelled():
                    return None # (half-drawn, so never encoded)
                writer.addSurface_(surface)
                return surface
        else:
            def work(cancelled):
                surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(*frame._raster_size(1))
                frame._render_to_surface(surface, 1, cancelled)
                if cancelled is not None and cancelled():
                    return None
                surface.lock()
                image = CGBitmapContextCreateImage(surface.context())
                surface.unlock()
                writer.addFrame_(NSBitmapImageRep.alloc().initWithCGImage_(image))
                return surface
        if render is None:
            work(None)
        else:
            render(frame, work)
        self.added += 1

