import objc, os, re, time, math, zlib
from ..util import autorelease
from .cocoa import CGBitmapContextCreateImage, CGContextBeginPage, CGContextEndPage, CGPDFContextClose, \
                   CGPDFContextCreateWithURL, CGRectMake, NSBitmapImageRep, NSURL, CGColorSpaceCopyICCData, \
                   CGColorSpaceGetNumberOfComponents

for cls in ["AnimatedGif", "Pages", "SysAdmin", "Video"]:
    globals()[cls] = objc.lookUpClass(cls)

re_obj = re.compile(rb'(\d+) 0 obj\s*(.*?)\s*(stream\r?\n|endobj)', re.S)
re_group_cs = re.compile(rb'(/Group\s*<<[^>]*?/S\s*/Transparency[^>]*?/CS\s+)(\d+)(\s+0\s+R)')
re_icc_space = re.compile(rb'\[\s*/ICCBased\s+(\d+)\s+0\s+R\s*\]')
re_length = re.compile(rb'/Length\s+(\d+)\b(?!\s+\d+\s+R)')
re_pdf_date = re.compile(rb"D:(\d{4})(\d\d)(\d\d)(\d\d)(\d\d)(\d\d)(?:(Z)|([+-])(\d\d)'?(\d\d))?")

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

def pdf_text(text):
    """A PDF string"""
    if all(ord(c) < 128 for c in text):
        return b'(%s)' % re.sub(rb'([\\()])', rb'\\\1', text.encode('ascii'))
    return b'<FEFF%s>' % text.encode('utf-16-be').hex().upper().encode()

def pdf_update(pdf, blend_space, intent=None, title=None):
    tail = re.search(rb'startxref\s+(\d+)\s+%%EOF\s*$', pdf)
    xref = tail and re.compile(rb'xref\s+0 (\d+)\s+').match(pdf, int(tail.group(1)))
    if not xref:
        return b''
    count, table = int(xref.group(1)), xref.end()
    trailer = re.compile(rb'\s*trailer\s*<<(.*?)>>\s*startxref', re.S).match(pdf, table + 20 * count)
    if not trailer:
        return b''

    objs = {}
    for offset in re.findall(rb'(\d{10}) \d{5} n', pdf[table:table + 20 * count]):
        m = re_obj.match(pdf, int(offset))
        if not m:
            continue
        head, start, length = m.group(2), None, None
        if m.group(3) != b'endobj':
            length = re_length.search(head)
            if not length:
                return b'' # (a length in an object of its own)
            start, length = m.end(), int(length.group(1))
        objs[int(m.group(1))] = (head, start, length)

    def stream(n):
        head, start, length = objs[n]
        return pdf[start:start + length]

    def data(n):
        return zlib.decompress(stream(n)) if b'/FlateDecode' in objs[n][0] else stream(n)

    def profile(n):
        m = re_icc_space.fullmatch(objs[n][0]) if n in objs else None
        icc = int(m.group(1)) if m else None
        if icc not in objs or objs[icc][1] is None:
            return None, None
        return icc, data(icc)

    added, heads, size = {}, {}, count # (heads: the rewritten objects' dictionaries)

    if intent:
        intent_icc, outputs, size = size, size + 1, size + 2
        added[intent_icc] = b'<< /N 4 /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream' % (len(intent['profile']), intent['profile'])
        registry = b' /RegistryName %s' % pdf_text(intent['registry']) if intent['registry'] else b''
        added[outputs] = b'[ << /Type /OutputIntent /S /GTS_PDFX /OutputConditionIdentifier %s /OutputCondition %s%s /Info %s /DestOutputProfile %d 0 R >> ]' % (
            pdf_text(intent['identifier']), pdf_text(intent['condition']), registry, pdf_text(intent['condition']), intent_icc)

    target = bytes(CGColorSpaceCopyICCData(blend_space))
    holders = {}
    for n, (head, _, _) in objs.items():
        for m in re_group_cs.finditer(head):
            holders.setdefault(int(m.group(2)), set()).add(n)
    relabel = [g for g in holders if profile(g)[1] not in (None, target)]
    if relabel:
        found = [] if intent else [(n, icc) for n in objs for icc, icc_data in [profile(n)] if icc_data == target]
        space = None # (an ICCBased space of the profile, made only if the groups' objects are pointed at one)
        if intent:
            icc = None
        elif found:
            space, icc = found[0]
        else:
            profiles = [n for n, (head, start, _) in objs.items() if start is not None and re.search(rb'/N\s+[134]\b', head) and b'/Subtype' not in head]
            icc = next((n for n in profiles if data(n) == target), None)
            if icc is None:
                compressed = zlib.compress(target)
                components = CGColorSpaceGetNumberOfComponents(blend_space)
                alternate = b'/DeviceCMYK' if components == 4 else b'/DeviceRGB'
                icc, size = size, size + 1
                added[icc] = b'<< /N %d /Alternate %s /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream' % (components, alternate, len(compressed), compressed)

        new_space = b'/DeviceCMYK' if intent else b'[ /ICCBased %d 0 R ]' % icc

        def cost(ns):
            return sum(len(objs[n][0]) + (objs[n][2] or 0) for n in ns)

        def regroup(head, old, new):
            return re_group_cs.sub(lambda m: m.group(1) + (b'%d' % new if int(m.group(2)) == old else m.group(2)) + m.group(3), head)

        for g in relabel:
            ref = re.compile(rb'(?<![\d.])%d\s+0\s+R' % g)
            others = []
            for n in objs:
                head = heads.get(n, objs[n][0])
                group_refs = sum(int(m.group(2)) == g for m in re_group_cs.finditer(head))
                if len(ref.findall(head)) > group_refs:
                    others.append(n)
            if others and cost(holders[g]) < cost(others):
                if space is None:
                    space, size = size, size + 1
                    added[space] = new_space
                for n in holders[g]:
                    heads[n] = regroup(heads.get(n, objs[n][0]), g, space)
            else:
                added[g] = new_space
                if others:
                    copy, size = size, size + 1
                    added[copy] = objs[g][0]
                    for n in others:
                        heads[n] = regroup(ref.sub(b'%d 0 R' % copy, heads.get(n, objs[n][0])), copy, g)

    if intent:
        root = int(re.search(rb'/Root (\d+) 0 R', trailer.group(1)).group(1))
        info = re.search(rb'/Info (\d+) 0 R', trailer.group(1))
        info_head = objs[int(info.group(1))][0] if info else b'<< >>'
        created = re.search(rb'/CreationDate\s*\((.*?)\)', info_head)
        modified = re.search(rb'/ModDate\s*\((.*?)\)', info_head)
        producer = re.search(rb'/Producer\s*\(((?:\\.|[^\\)])*)\)', info_head)
        ids = re.findall(rb'<([0-9a-fA-F]{32})>', trailer.group(1))
        def iso(date):
            m = date and re_pdf_date.match(date.group(1))
            if not m:
                return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            y, mo, d, h, mi, sec, z, sign, oh, om = [g.decode() if g else g for g in m.groups()]
            return '%s-%s-%sT%s:%s:%s%s' % (y, mo, d, h, mi, sec, 'Z' if z or not sign else '%s%s:%s' % (sign, oh, om))
        def uuid(hex_id):
            h = hex_id.decode().lower()
            return '%s-%s-%s-%s-%s' % (h[:8], h[8:12], h[12:16], h[16:20], h[20:])
        def xml(text):
            return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        from plotdevice import __version__
        title = title or 'Untitled'
        creator = 'PlotDevice %s' % __version__
        producer_text = re.sub(rb'\\(.)', rb'\1', producer.group(1)).decode('latin-1') if producer else creator
        packet = XMP.format(title=xml(title), created=iso(created), modified=iso(modified or created), creator=creator,
                            producer=xml(producer_text), document=uuid(ids[0]) if ids else '00000000-0000-0000-0000-000000000000',
                            instance=uuid(ids[-1]) if ids else '00000000-0000-0000-0000-000000000000').encode('utf-8')
        metadata, size = size, size + 1
        added[metadata] = b'<< /Type /Metadata /Subtype /XML /Length %d >>\nstream\n%s\nendstream' % (len(packet), packet)

        catalog = re.sub(rb'\s*/(Version\s*/[\d.]+|OutputIntents\s+\d+ 0 R)', b'', objs[root][0])
        heads[root] = catalog[:catalog.rindex(b'>>')] + b' /Version /1.6 /OutputIntents %d 0 R /Metadata %d 0 R >>' % (outputs, metadata)
        entries = b' /Title %s /Creator (%s) /Trapped /False /GTS_PDFXVersion (PDF/X-4)' % (pdf_text(title), creator.encode())
        info_head = re.sub(rb'\s*/(Title|Creator|Trapped|GTS_PDFXVersion)\s*(\((?:\\.|[^\\)])*\)|<[^>]*>|/\w+)', b'', info_head)
        if info:
            heads[int(info.group(1))] = info_head[:info_head.rindex(b'>>')] + entries + b' >>'
        else:
            info_obj, size = size, size + 1
            added[info_obj] = b'<<%s >>' % entries

        for n, (head, _, _) in objs.items():
            if re.search(rb'/Type\s*/Page\b', head) and b'/TrimBox' not in head:
                box = re.search(rb'/MediaBox\s*(\[[^\]]*\])', head)
                parent = re.search(rb'/Parent\s+(\d+) 0 R', head)
                while not box and parent and int(parent.group(1)) in objs: # (inherited)
                    up = objs[int(parent.group(1))][0]
                    box, parent = re.search(rb'/MediaBox\s*(\[[^\]]*\])', up), re.search(rb'/Parent\s+(\d+) 0 R', up)
                if box:
                    page = heads.get(n, head)
                    heads[n] = page[:page.rindex(b'>>')] + b' /TrimBox %s >>' % box.group(1)


    if not added and not heads:
        return b''
    updates = dict(added)
    for n, head in heads.items():
        updates[n] = head if objs[n][1] is None else head + b'\nstream\n' + stream(n) + b'\nendstream'

    update, offsets = [b'' if pdf.endswith(b'\n') else b'\n'], {}
    pos = len(pdf) + len(update[0])
    for n in sorted(updates):
        obj = b'%d 0 obj\n%s\nendobj\n' % (n, updates[n])
        update.append(obj)
        offsets[n], pos = pos, pos + len(obj)
    keep = b' '.join(re.findall(rb'/(?:Root|Info) \d+ 0 R|/ID\s*\[[^\]]*\]', trailer.group(1)))
    if intent and not re.search(rb'/Info \d+ 0 R', keep):
        keep += b' /Info %d 0 R' % info_obj
    update.append(b'xref\n' + b''.join(b'%d 1\n%010d 00000 n \n' % (n, offsets[n]) for n in sorted(offsets)))
    update.append(b'trailer\n<< /Size %d %s /Prev %d >>\nstartxref\n%d\n%%%%EOF\n' % (size, keep, int(tail.group(1)), pos))
    return b''.join(update)

class PDFBook(object):

    def __init__(self, fname, zoom=1.0, press=None):
        from ..gfx.colors import _output_intent # (gfx imports this module)
        self.fname = fname
        self.zoom = zoom
        self.pages = 0
        self.closed = False
        self.intent = _output_intent(press) if press else None # (a press's output intent, added once it's closed)
        self.blend_space = None # the space its groups blend in, from its first page's output mode
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
                update = pdf_update(f.read(), self.blend_space, self.intent, os.path.splitext(os.path.basename(self.fname))[0])
            with open(self.fname, 'ab') as f:
                f.write(update)
        self.closed = True

    def framesWritten(self):
        return self.pages

    def doneWriting(self):
        return self.closed

### Session objects which wrap the GCD-based export managers ###

class ExportSession(object):
    unfinished = set() # the sessions whose files are still being written (the app waits for them to quit)

    def __init__(self):
        # state flags
        self.running = True
        self.cancelled = False
        self.closing = False # whether done() has been called
        self.closed = False  # and has closed the writer's file
        self.added = 0
        self.rendered = 0 # frames handed to the writer (not those dropped by a cancel)
        self.written = 0
        self.total = 0
        self.failed = False # whether the writer gave up, leaving no file

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
        if self.cancelled:
            return # be idem potent

        self.cancelled = True
        if drop is not None and not self.closing:
            drop()
        if self._status:
            self._status('cancelled')

    def done(self, render=None):
        # if self._status:
        #     self._status('finishing')
        self.closing = True
        if self.writer and not self.closed:
            writer = self.writer
            def close(cancelled=None):
                if not self.closed:
                    self.closed = True
                    writer.closeFile()
            if render is None or self.on_main:
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
        from ..gfx.colors import _output_colors, _output_mode, CMYK # (gfx imports this module)
        super(ImageExportSession, self).__init__()
        self.single_file = single or first==last
        if last is not None:
            self.begin(pages=last-first+1)
        self.format = format
        self.zoom = zoom
        self.colors = _output_colors(colors, format)
        self.on_main = format == 'eps' # (it's drawn through an NSView)
        cmyk_bitmap = _output_mode(self.colors) == CMYK and format in ('jpeg', 'jpg', 'tiff')
        self.presents = format not in ('pdf', 'eps') and not cmyk_bitmap

        m = re_padded.search(fname)
        pad = '%%0%id' % int(m.group(1)) if m else None

        if self.single_file:
            # output a single file (potentially a multipage PDF)
            if pad:
                fname = re_padded.sub(pad%0, fname, count=1)
            if format == 'pdf':
                self.writer = PDFBook(fname, zoom, self.colors if _output_mode(self.colors) == CMYK and self.colors != CMYK else None)
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
        frame = canvas.commit(self.colors, self.format)
        writer, format, zoom = self.writer, self.format, self.zoom
        def work(cancelled):
            if isinstance(writer, PDFBook):
                writer.addPage_(frame)
                self.rendered += 1
                return None
            image, surface = frame._encode(format, zoom, cancelled)
            if image is not None:
                writer.addPage_(image)
                self.rendered += 1
            return surface
        if render is None or self.on_main:
            with autorelease():
                work(None)
        else:
            render(frame, work)
        self.added += 1

class MovieExportSession(ExportSession):
    CODECS = ('hevc', 'h264', 'prores') # a .mov's (in Video's numbering), ProRes being 4444 with alpha
    BITRATES = (1, 2, 4, 8, 16, 32)     # the Export sheet's choices, in Mbit/s

    @staticmethod
    def auto_bitrate(width, height, fps=30):
        wanted = 8 * math.sqrt(width * height / (1280 * 720.0)) * math.sqrt(fps / 30.0)
        bigger = [rate for rate in MovieExportSession.BITRATES if rate >= wanted]
        return bigger[0] if bigger else MovieExportSession.BITRATES[-1]

    def __init__(self, fname, format='mov', first=1, last=None, fps=30, bitrate=None, loop=0, codec='hevc', zoom=1.0, colors=None, **rest):
        from ..gfx.colors import _output_colors # (gfx imports this module)
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
        self.bitrate = bitrate # (None to pick one from the movie's size)
        self.codec = codec
        self.zoom = zoom
        self.colors = _output_colors(colors, format)
        self.presents = True

    def writer_failed(self):
        failed = self.format == 'mov' and self.writer is not None and self.writer.failed()
        if failed and os.path.exists(self.fname):
            os.unlink(self.fname)
        return failed

    def shutdown(self):
        self.failed = self.failed or self.writer_failed()
        super(MovieExportSession, self).shutdown()

    def add(self, canvas, render=None):
        if self.format not in ('mov', 'gif'):
            print('unrecognized output format: %s' % self.format)
            return self.shutdown()

        frame = canvas.commit(self.colors, self.format)
        if not self.writer:
            size = self.size = frame._raster_size(self.zoom)
            if self.format == 'mov':
                size = self.size = tuple(dim - dim % 2 for dim in size)
                self.writer = Video.alloc()
                codec = MovieExportSession.CODECS.index(self.codec)
                bitrate = self.bitrate or MovieExportSession.auto_bitrate(size[0], size[1], self.fps)
                self.writer.initWithFile_size_fps_bitrate_codec_srgb_(self.fname, size, self.fps, bitrate, codec, frame.ink is not None)
            else:
                self.writer = AnimatedGif.alloc()
                self.writer.initWithFile_size_fps_loop_(self.fname, size, self.fps, self.loop)
        writer, straight = self.writer, self.codec == 'prores'

        if self.format == 'mov':
            def work(cancelled):
                if straight:
                    rendered = objc.lookUpClass('PDSurface').surfaceWithWidth_height_space_(*self.size, frame._surface_space)
                    frame._render_to_surface(rendered, self.zoom, cancelled, origin=(0, 0))
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
                frame._render_to_surface(surface, self.zoom, cancelled, origin=(0, 0)) # (from the top-left, so a bottom row is what's lost)
                if cancelled is not None and cancelled():
                    return None # (half-drawn, so never encoded)
                writer.addSurface_(surface)
                self.rendered += 1
                return surface
        else:
            def work(cancelled):
                surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_space_(*self.size, frame._surface_space)
                frame._render_to_surface(surface, self.zoom, cancelled, origin=(0, 0))
                if cancelled is not None and cancelled():
                    return None
                surface.lock()
                image = CGBitmapContextCreateImage(surface.context())
                surface.unlock()
                writer.addFrame_(NSBitmapImageRep.alloc().initWithCGImage_(image))
                self.rendered += 1
                return surface
        if render is None:
            with autorelease():
                work(None)
        else:
            render(frame, work)
        self.added += 1

