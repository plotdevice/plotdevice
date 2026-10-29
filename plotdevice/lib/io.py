import objc, os, re, time, math, zlib
from uuid import UUID
from xml.sax.saxutils import escape
from ..util import autorelease
from .cocoa import CGBitmapContextCreateImage, CGContextBeginPage, CGContextEndPage, CGPDFContextClose, \
                   CGPDFContextCreateWithURL, CGRectMake, NSBitmapImageRep, NSURL, CGColorSpaceCopyICCData, \
                   CGColorSpaceGetNumberOfComponents

for cls in ["AnimatedGif", "Pages", "PDSurface", "SysAdmin", "Video"]:
    globals()[cls] = objc.lookUpClass(cls)

# movie codecs
HEVC, H264, PRORES = 'hevc', 'h264', 'prores'

# PDF/X metadata
XMP = """<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/" xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
    xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/">
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{title}</rdf:li></rdf:Alt></dc:title>
   <xmp:CreateDate>{created}</xmp:CreateDate>
   <xmp:ModifyDate>{modified}</xmp:ModifyDate>
   <xmp:MetadataDate>{modified}</xmp:MetadataDate>
   <xmp:CreatorTool>{creator}</xmp:CreatorTool>
   <pdf:Producer>{producer}</pdf:Producer>
   <pdf:Trapped>False</pdf:Trapped>
   <xmpMM:DocumentID>uuid:{document}</xmpMM:DocumentID>
   <xmpMM:InstanceID>uuid:{instance}</xmpMM:InstanceID>
   <xmpMM:VersionID>1</xmpMM:VersionID>
   <xmpMM:RenditionClass>default</xmpMM:RenditionClass>
   <pdfxid:GTS_PDFXVersion>PDF/X-4</pdfxid:GTS_PDFXVersion>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""

re_obj = re.compile(rb'(\d+) 0 obj\s*(.*?)\s*(stream\r?\n|endobj)', re.S)
re_group_cs = re.compile(rb'(/Group\s*<<[^>]*?/S\s*/Transparency[^>]*?/CS\s+)(\d+)(\s+0\s+R)')
re_icc_space = re.compile(rb'\[\s*/ICCBased\s+(\d+)\s+0\s+R\s*\]')
re_length = re.compile(rb'/Length\s+(\d+)\b(?!\s+\d+\s+R)')
re_pdf_date = re.compile(rb"D:(\d{4})(\d\d)(\d\d)(\d\d)(\d\d)(\d\d)(?:(Z)|([+-])(\d\d)'?(\d\d))?")
re_mediabox = re.compile(rb'/MediaBox\s*(\[[^\]]*\])')
re_parent = re.compile(rb'/Parent\s+(\d+) 0 R')

def pdf_text(text):
    """A PDF string"""
    if all(ord(c) < 128 for c in text):
        return b'(%s)' % re.sub(rb'([\\()])', rb'\\\1', text.encode('ascii'))
    return b'<FEFF%s>' % text.encode('utf-16-be').hex().upper().encode()

class Distiller(object):
    """Construct an incremental update fixing a Quartz PDF's blending and PDF/X"""

    def __init__(self, pdf, space, intent=None, title=None):
        self._pdf, self._space, self._intent, self._title = pdf, space, intent, title
        self._objs = None # None if not laid out by quartz
        self._added, self._heads = {}, {} # new objects, rewritten dicts

        # find quartz's one cross-reference table
        tail = re.search(rb'startxref\s+(\d+)\s+%%EOF\s*$', pdf)
        xref = tail and re.compile(rb'xref\s+0 (\d+)\s+').match(pdf, int(tail.group(1)))
        if not xref:
            return
        count, table = int(xref.group(1)), xref.end()
        trailer = re.compile(rb'\s*trailer\s*<<(.*?)>>\s*startxref', re.S).match(pdf, table + 20 * count)
        if not trailer:
            return

        # locate each object's dict and stream range
        objs = {}
        for offset in re.findall(rb'(\d{10}) \d{5} n', pdf[table:table + 20 * count]):
            m = re_obj.match(pdf, int(offset))
            if not m:
                continue
            head, start, length = m.group(2), None, None
            if m.group(3) != b'endobj':
                length = re_length.search(head)
                if not length:
                    return # an indirect length
                start, length = m.end(), int(length.group(1))
            objs[int(m.group(1))] = (head, start, length)
        self._objs, self._size, self._trailer, self._prev = objs, count, trailer.group(1), int(tail.group(1))

    def endmatter(self):
        """The update to append to the PDF, or b'' if there's nothing to add"""
        if self._objs is None:
            return b''

        # a CMYK press's output intent
        info = None
        if self._intent:
            intent = self._intent
            intent_icc = self._add(b'<< /N 4 /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream' % (len(intent['profile']), intent['profile']))
            registry = b' /RegistryName %s' % pdf_text(intent['registry']) if intent['registry'] else b''
            outputs = self._add(b'[ << /Type /OutputIntent /S /GTS_PDFX /OutputConditionIdentifier %s /OutputCondition %s%s /Info %s /DestOutputProfile %d 0 R >> ]' % (
                pdf_text(intent['identifier']), pdf_text(intent['condition']), registry, pdf_text(intent['condition']), intent_icc))
        self._blend()
        if self._intent:
            info = self._pdfx(outputs)

        if not self._added and not self._heads:
            return b''
        updates = dict(self._added)
        for n, head in self._heads.items():
            updates[n] = head if self._objs[n][1] is None else head + b'\nstream\n' + self._stream(n) + b'\nendstream'

        # append the added/rewritten objects & their xref table
        pdf = self._pdf
        update, offsets = [b'' if pdf.endswith(b'\n') else b'\n'], {}
        pos = len(pdf) + len(update[0])
        for n in sorted(updates):
            obj = b'%d 0 obj\n%s\nendobj\n' % (n, updates[n])
            update.append(obj)
            offsets[n], pos = pos, pos + len(obj)
        keep = b' '.join(re.findall(rb'/(?:Root|Info) \d+ 0 R|/ID\s*\[[^\]]*\]', self._trailer))
        if info is not None:
            keep += b' /Info %d 0 R' % info
        update.append(b'xref\n' + b''.join(b'%d 1\n%010d 00000 n \n' % (n, offsets[n]) for n in sorted(offsets)))
        update.append(b'trailer\n<< /Size %d %s /Prev %d >>\nstartxref\n%d\n%%%%EOF\n' % (self._size, keep, self._prev, pos))
        return b''.join(update)

    def _blend(self):
        # find each transparency group's color space, and the objects whose groups use it
        target = bytes(CGColorSpaceCopyICCData(self._space))
        holders = {}
        for n, (head, _, _) in self._objs.items():
            for m in re_group_cs.finditer(head):
                holders.setdefault(int(m.group(2)), set()).add(n)

        # only ICC-based spaces with some other profile need updating
        mismatched = [g for g in holders if self._profile(g)[1] not in (None, target)]
        if not mismatched:
            return

        # the space to blend in, reusing the file's own space object or profile if it has one
        space_obj = None
        if self._intent:
            # use DeviceCMYK for PDF/X-4 since Acrobat rejects ICC-based cmyk (even if it matches the intent)
            new_space = b'/DeviceCMYK'
        else:
            space_obj = next((n for n in self._objs if self._profile(n)[1] == target), None)
            if space_obj is not None:
                icc = self._profile(space_obj)[0]
            else:
                profiles = [n for n, (head, start, _) in self._objs.items() if start is not None and re.search(rb'/N\s+[134]\b', head) and b'/Subtype' not in head]
                icc = next((n for n in profiles if self._data(n) == target), None)
                if icc is None:
                    compressed = zlib.compress(target)
                    components = CGColorSpaceGetNumberOfComponents(self._space)
                    alternate = b'/DeviceCMYK' if components == 4 else b'/DeviceRGB'
                    icc = self._add(b'<< /N %d /Alternate %s /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream' % (components, alternate, len(compressed), compressed))
            new_space = b'[ /ICCBased %d 0 R ]' % icc

        # quartz shares a group's space with images, so either repoint the groups at the
        # new space or redefine the old one and give its other users a copy
        written = lambda ns: sum(len(self._objs[n][0]) + (self._objs[n][2] or 0) for n in ns) # bytes a rewrite adds
        for g in mismatched:
            ref = re.compile(rb'(?<![\d.])%d\s+0\s+R' % g)
            others = [] # objects that use g other than as a group's space
            for n in self._objs:
                head = self._head(n)
                group_refs = sum(int(m.group(2)) == g for m in re_group_cs.finditer(head))
                if len(ref.findall(head)) > group_refs:
                    others.append(n)
            repoint = others and written(holders[g]) < written(others)
            if repoint:
                if space_obj is None:
                    space_obj = self._add(new_space)
                for n in holders[g]:
                    self._heads[n] = self._regroup(self._head(n), g, space_obj)
            else:
                self._added[g] = new_space
                if others:
                    # point everything else at a copy of the old space, leaving their groups on g
                    copy = self._add(self._objs[g][0])
                    for n in others:
                        self._heads[n] = self._regroup(ref.sub(b'%d 0 R' % copy, self._head(n)), copy, g)

    def _pdfx(self, outputs):
        # add PDF/X keys, returning any new Info object
        from plotdevice import __version__
        objs = self._objs
        title = self._title or 'Untitled'
        creator = 'PlotDevice %s' % __version__

        # the dates and producer from the file's Info dict (to be merged into the XMP)
        info = re.search(rb'/Info (\d+) 0 R', self._trailer)
        info_n = int(info.group(1)) if info else None
        info_head = objs[info_n][0] if info else b'<< >>'
        created = re.search(rb'/CreationDate\s*\((.*?)\)', info_head)
        modified = re.search(rb'/ModDate\s*\((.*?)\)', info_head) or created
        producer = re.search(rb'/Producer\s*\(((?:\\.|[^\\)])*)\)', info_head)
        producer_text = re.sub(rb'\\(.)', rb'\1', producer.group(1)).decode('latin-1') if producer else creator

        # an XMP packet with the same metadata, identified by the trailer's IDs
        ids = re.findall(rb'<([0-9a-fA-F]{32})>', self._trailer)
        nil = '00000000-0000-0000-0000-000000000000'
        document, instance = (str(UUID(ids[0].decode())), str(UUID(ids[-1].decode()))) if ids else (nil, nil)
        packet = XMP.format(title=escape(title), created=self.iso(created), modified=self.iso(modified), creator=creator,
                            producer=escape(producer_text), document=document, instance=instance).encode('utf-8')
        metadata = self._add(b'<< /Type /Metadata /Subtype /XML /Length %d >>\nstream\n%s\nendstream' % (len(packet), packet))

        # the catalog: PDF 1.6, the output intent, and the XMP
        root = int(re.search(rb'/Root (\d+) 0 R', self._trailer).group(1))
        catalog = re.sub(rb'\s*/(Version\s*/[\d.]+|OutputIntents\s+\d+ 0 R)', b'', objs[root][0])
        self._heads[root] = catalog[:catalog.rindex(b'>>')] + b' /Version /1.6 /OutputIntents %d 0 R /Metadata %d 0 R >>' % (outputs, metadata)

        # the Info dict's updated PDF/X keys or a new Info with just the new entries
        entries = b' /Title %s /Creator (%s) /Trapped /False /GTS_PDFXVersion (PDF/X-4)' % (pdf_text(title), creator.encode())
        new_info = None
        if info:
            info_head = re.sub(rb'\s*/(Title|Creator|Trapped|GTS_PDFXVersion)\s*(\((?:\\.|[^\\)])*\)|<[^>]*>|/\w+)', b'', info_head)
            self._heads[info_n] = info_head[:info_head.rindex(b'>>')] + entries + b' >>'
        else:
            new_info = self._add(b'<<%s >>' % entries)

        # a TrimBox for each page, from its own MediaBox or the nearest ancestor's
        for n, (head, _, _) in objs.items():
            if re.search(rb'/Type\s*/Page\b', head) and b'/TrimBox' not in head:
                box, parent = re_mediabox.search(head), re_parent.search(head)
                while not box and parent and int(parent.group(1)) in objs:
                    ancestor = objs[int(parent.group(1))][0]
                    box, parent = re_mediabox.search(ancestor), re_parent.search(ancestor)
                if box:
                    page = self._head(n)
                    self._heads[n] = page[:page.rindex(b'>>')] + b' /TrimBox %s >>' % box.group(1)
        return new_info

    def _add(self, body):
        n = self._size
        self._size += 1
        self._added[n] = body
        return n

    def _head(self, n):
        return self._heads.get(n, self._objs[n][0])

    def _stream(self, n):
        head, start, length = self._objs[n]
        return self._pdf[start:start + length]

    def _data(self, n):
        return zlib.decompress(self._stream(n)) if b'/FlateDecode' in self._objs[n][0] else self._stream(n)

    def _profile(self, n):
        # an ICCBased space's stream and data
        objs = self._objs
        m = re_icc_space.fullmatch(objs[n][0]) if n in objs else None
        icc = int(m.group(1)) if m else None
        if icc not in objs or objs[icc][1] is None:
            return None, None
        return icc, self._data(icc)

    @staticmethod
    def _regroup(head, old, new):
        return re_group_cs.sub(lambda m: m.group(1) + (b'%d' % new if int(m.group(2)) == old else m.group(2)) + m.group(3), head)

    @staticmethod
    def iso(date):
        m = date and re_pdf_date.match(date.group(1))
        if not m:
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        y, mo, d, h, mi, sec, z, sign, oh, om = [g.decode() if g else g for g in m.groups()]
        return '%s-%s-%sT%s:%s:%s%s' % (y, mo, d, h, mi, sec, 'Z' if z or not sign else '%s%s:%s' % (sign, oh, om))

class PaperbackWriter(object):
    """Draws each frame it's given as the next page of one PDF file"""

    def __init__(self, fname, zoom=1.0, press=None):
        from ..gfx.colors import Press
        self.fname = fname
        self.zoom = zoom
        self.pages = 0
        self.closed = False
        self.intent = Press.named[press].intent if press else None
        self.blend_space = None # set by the first page
        self.context = CGPDFContextCreateWithURL(NSURL.fileURLWithPath_(fname), None, None)

    def addPage_(self, frame):
        if not self.pages:
            self.blend_space = frame._blend_space
        w, h = frame.pagesize
        CGContextBeginPage(self.context, CGRectMake(0, 0, w * self.zoom, h * self.zoom))
        frame._render_to_context(self.context, self.zoom)
        CGContextEndPage(self.context)
        self.pages += 1

    def closeFile(self):
        CGPDFContextClose(self.context)
        self.context = None
        if self.blend_space is not None:
            with open(self.fname, 'rb') as f:
                title = os.path.splitext(os.path.basename(self.fname))[0]
                endmatter = Distiller(f.read(), self.blend_space, intent=self.intent, title=title).endmatter()
            with open(self.fname, 'ab') as f:
                f.write(endmatter)
        self.closed = True

    def framesWritten(self):
        return self.pages

    def doneWriting(self):
        return self.closed

### Session objects which wrap the GCD-based export managers ###

class ExportSession(object):
    unfinished = set() # the app waits on these to quit

    def __init__(self):
        # state flags
        self.running = True    # true until shutdown()
        self.cancelled = False # cancel() was called
        self.closing = False   # done() was called
        self.closed = False    # the file was closed
        self.failed = False    # the writer gave up
        self.total = 0         # frames expected, set by begin()
        self.added = 0         # frames passed to add()
        self.rendered = 0      # frames handed to the writer
        self.written = 0       # frames finished by the writer

        # render flags
        self.view_based = False # drawn through an NSView on the calling thread
        self.presents = False   # rendered surfaces can be displayed on screen

        # callbacks
        self._complete = None
        self._progress = None
        self._status = None

        # one of the cIO classes
        self.writer = None

    @classmethod
    def writing(cls):
        """The unfinished sessions whose writers are still writing"""
        return [s for s in ExportSession.unfinished if s.writer is not None and not s.writer.doneWriting()]

    @property
    def backlogged(self):
        """Whether its writer has more than a few frames left to write"""
        if self.writer is None:
            return False
        return self.added - self.writer.framesWritten() > 4

    def begin(self, frames=None, pages=None):
        from plotdevice.gui import set_timeout
        self.total = frames if frames is not None else pages
        self.poll = set_timeout(self, "update:", 0.1, repeat=True)
        ExportSession.unfinished.add(self)

    def update_(self, note):
        self.written = self.writer.framesWritten()
        if self._progress:
            # let the delegate update the progress bar
            goal = self.rendered if self.cancelled else self.total
            self._progress(self.written, goal, self.cancelled)

        if self.writer.doneWriting():
            self.shutdown()

    def next(self):
        if self.cancelled or self.added==self.total:
            return None
        return self.added + 1

    def cancel(self, drop=None):
        """Stop adding frames and drop any awaiting render"""
        if self.cancelled:
            return # be idem potent

        self.cancelled = True
        if drop is not None and not self.closing:
            drop()
        if self._status:
            self._status('cancelled')

    def done(self, render=None):
        self.closing = True
        if self.writer and not self.closed:
            # await queued frames then close (ignoring any subsequent done() calls)
            writer = self.writer
            def close(cancelled=None):
                if not self.closed:
                    self.closed = True
                    writer.closeFile()
            if render is None or self.view_based:
                close()
            else:
                render(None, close)

    def shutdown(self):
        self.running = False
        ExportSession.unfinished.discard(self)
        self._progress = None
        if self._status:
            self._status('failed' if self.failed else 'complete')
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
    def __init__(self, fname, format='pdf', zoom=1.0, first=1, last=None, single=False, colors=None, **rest):
        from ..gfx.colors import _output_colors, _output_mode, CMYK, Press # circular import
        super(ImageExportSession, self).__init__()
        self.single_file = single or first==last
        if last is not None:
            self.begin(pages=last-first+1)
        self.format = format
        self.zoom = zoom
        self.colors = _output_colors(colors, format)
        self.view_based = format == 'eps' # only an NSView can generate EPS
        cmyk_bitmap = _output_mode(self.colors) == CMYK and format in ('jpeg', 'jpg', 'tiff')
        self.presents = format not in ('pdf', 'eps') and not cmyk_bitmap

        m = re_padded.search(fname)
        pad = '%%0%id' % int(m.group(1)) if m else None

        if self.single_file:
            # output a single file (potentially a multipage PDF)
            if pad:
                fname = re_padded.sub(pad%0, fname, count=1)
            if format == 'pdf':
                self.writer = PaperbackWriter(fname, zoom, self.colors if self.colors in Press.named else None)
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
        """Render the canvas and write it out, now or via render()"""
        frame = canvas.commit(self.colors, self.format)
        writer, format, zoom = self.writer, self.format, self.zoom
        def work(cancelled):
            if isinstance(writer, PaperbackWriter):
                writer.addPage_(frame)
                self.rendered += 1
                return None
            image, surface = frame._encode(format, zoom, cancelled)
            if image is not None:
                writer.addPage_(image)
                self.rendered += 1
            return surface
        if render is None or self.view_based:
            with autorelease():
                work(None)
        else:
            render(frame, work)
        self.added += 1

class MovieExportSession(ExportSession):
    CODECS = (HEVC, H264, PRORES)
    BITRATES = (1, 2, 4, 8, 16, 32) # in Mbit/s

    @staticmethod
    def auto_bitrate(width, height, fps=30):
        """The default bitrate for a movie's size and frame rate"""
        # 8 Mbit/s at 720p30, scaled by square roots
        wanted = 8 * math.sqrt(width * height / (1280 * 720.0)) * math.sqrt(fps / 30.0)
        bigger = [rate for rate in MovieExportSession.BITRATES if rate >= wanted]
        return bigger[0] if bigger else MovieExportSession.BITRATES[-1]

    def __init__(self, fname, format='mov', first=1, last=None, fps=30, bitrate=None, loop=0, codec=HEVC, zoom=1.0, colors=None, **rest):
        from ..gfx.colors import _output_colors, P3, SRGB, _REC709, _REC2020
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
        self.bitrate = bitrate # None = auto
        self.codec = codec
        self.zoom = zoom
        self.colors = _output_colors(colors, format)
        self.video_colors = {P3: 'p3', SRGB: 'srgb', _REC709: 'rec709', _REC2020: 'rec2020'}.get(self.colors) # Video's names
        self.presents = True

    def discard_if_failed(self):
        """Remove the partial file if the encoder gave up, returning whether it did"""
        failed = self.format == 'mov' and self.writer is not None and self.writer.failed()
        if failed and os.path.exists(self.fname):
            os.unlink(self.fname)
        return failed

    def shutdown(self):
        self.failed = self.failed or self.discard_if_failed()
        super(MovieExportSession, self).shutdown()

    def add(self, canvas, render=None):
        """Render the canvas and add it to the file"""
        if self.format not in ('mov', 'gif'):
            print('unrecognized output format: %s' % self.format)
            return self.shutdown()

        frame = canvas.commit(self.colors, self.format)
        if not self.writer:
            size = self.size = frame._raster_size(self.zoom)
            if self.format == 'mov':
                # HEVC and H.264 crop to ensure even sizes, ProRes fails on odd heights
                size = self.size = tuple(dim - dim % 2 for dim in size)
                self.writer = Video.alloc()
                bitrate = self.bitrate or MovieExportSession.auto_bitrate(size[0], size[1], self.fps)
                self.writer.initWithFile_size_fps_bitrate_codec_colors_(self.fname, size, self.fps, bitrate, self.codec, self.video_colors)
            else:
                self.writer = AnimatedGif.alloc()
                self.writer.initWithFile_size_fps_loop_(self.fname, size, self.fps, self.loop)
        writer, gif = self.writer, self.format == 'gif'

        def work(cancelled):
            stopped = lambda: cancelled is not None and cancelled()
            if gif:
                surface = PDSurface.surfaceWithWidth_height_space_(*self.size, frame._surface_space)
            else:
                # wait for the encoder to provide a surface to draw in
                while (surface := writer.nextSurface()) is None:
                    if stopped() or writer.failed():
                        return None
                    time.sleep(0.002)
            frame._render_to_surface(surface, self.zoom, cancelled, origin=(0, 0))
            if stopped():
                return None # cancelled mid-render, so don't encode the partial frame

            if gif:
                surface.lock()
                image = CGBitmapContextCreateImage(surface.context())
                surface.unlock()
                writer.addFrame_(NSBitmapImageRep.alloc().initWithCGImage_(image))
            else:
                # ProRes waits for a free buffer to unpremultiply into
                while not writer.addSurface_(surface):
                    if stopped() or writer.failed():
                        return None
                    time.sleep(0.002)
            self.rendered += 1
            return surface

        if render is None:
            # buffers recycle once their surfaces are freed
            with autorelease():
                work(None)
        else:
            render(frame, work)
        self.added += 1
