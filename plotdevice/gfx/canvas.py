# encoding: utf-8
import os
import objc
from objc import super

from ..lib.cocoa import *
from ..lib import pathmatics
from _plotdevice import PDPath
from ..lib.io import Distiller
from ..util import trim_zeroes, autorelease
from .geometry import Size, px, inch, mm, cm, pica
from .profiles import Output, RGB, CMYK
from .colors import Gradient
from .effects import Effect, Stencil, Frob, _commit_all
from .bezier import Bezier
from .image import Image
from .. import gfx, DeviceError

class Canvas(object):
    _ctx = None

    def __init__(self, width=512, height=512, unit=px):
        self.unit = unit
        self.width = width
        self.height = height
        self.speed = None
        self.mousedown = False
        self.clear() # set up the container & stack

    @trim_zeroes
    def __repr__(self):
        return 'Canvas(%0.3f, %0.3f, %s)'%(self.width, self.height, self.unit.name)

    def reset(self):
        """Reset dimensions & animation state then clear"""
        self.__init__()

    def clear(self, *grobs):
        """Erase the canvas entirely (or remove specified grobs)"""
        if not grobs:
            self._grobs = self._container = []
            self._stack = [self._container]
        else:
            for grob in grobs:
                self._drop(grob, self._grobs)

    def _drop(self, grob, container):
        if grob in container:
            container.remove(grob)
        for frob in [f for f in container if hasattr(f, 'contents')]:
            self._drop(grob, frob.contents)

    @property
    def size(self):
        """The canvas's size in terms of its default unit"""
        return Size(self.width, self.height)

    @property
    def pagesize(self):
        """The canvas's size in Postscript points"""
        dpx = self.unit.basis
        return Size(self.width*dpx, self.height*dpx)

    def _get_unit(self):
        return self._unit
    def _set_unit(self, u):
        if u not in (px, inch, pica, cm, mm):
            nonstandard = 'Canvas units must be one of: px, inch, pica, cm, or mm (not %r)'%u
            raise DeviceError(nonstandard)
        self._unit = u
    unit = property(_get_unit, _set_unit)

    def __iter__(self):
        for grob in self._grobs:
            yield grob

    def __len__(self):
        return len(self._grobs)

    def __getitem__(self, index):
        return self._grobs[index]

    def append(self, el):
        # when beziers, images, and text are added, they're placed in the current
        # tail of the container stack (see push/pop)
        self._container.append(el)

    def push(self, containerFrob):
        # when Frobs like Stencils or Effects are added, they become their own container
        # that applies to all grobs drawn until the frob is popped off the stack
        self._stack.insert(0, containerFrob)
        self._container.append(containerFrob)
        self._container = containerFrob

    def pop(self):
        try:
            del self._stack[0]
            self._container = self._stack[0]
        except IndexError as e:
            raise DeviceError("pop: too many canvas pops!")

    def commit(self, output=None, proof=None):
        """Commit the canvas's current contents to a renderable Frame"""
        return Frame(self, output, proof)

    @property
    def _nsImage(self):
        # Allow the canvas to be used with the image() command
        return self.commit()._nsImage

    def _getImageData(self, format, zoom=1.0, colors=None):
        return self.commit(Output.parse(colors, format))._getImageData(format, zoom)

    def save(self, fname, format=None, zoom=1.0, cmyk=False, colors=None):
        """Write the current graphics objects to an image file (in `colors`, or CMYK if `cmyk` is set)"""
        format = (format or fname.rsplit('.',1)[-1]).lower()
        self.commit(Output.parse(CMYK if cmyk else colors, format)).save(fname, format, zoom)


class Frame(object):
    """A committed copy of a Canvas (or of another Frame, with output/proof settings)"""

    def __init__(self, src, output=None, proof=None):
        copying = isinstance(src, Frame) # its texts must keep their own colors
        if proof is not None and proof.output is not None:
            output = proof.output # drawn in the colors being proofed
        if output is None:
            # the working space, in the canvas's mode
            mode = src.output.mode if copying else (src._ctx._output.mode if src._ctx else RGB)
            output = Output.working(mode)
        self.output = output # from export(colors=), else the working space

        # texts resolve their colors while committing
        with gfx._state.using(committing=self):
            self.grobs = _commit_all(src.grobs, held=True) if copying else _commit_all(src._grobs)
        self.width, self.height = src.width, src.height
        self.pagesize = src.pagesize
        self.background = src.background
        self._bounds = FrameBounds(self.grobs)
        self.proof = proof # the window's Proof Colors setting

    def draw(self, cancelled=None, within=None):
        """Render the frame into the current graphics context"""
        with gfx._render_lock, gfx._state.rendering(self, within):
            if self.background is not None:
                rect = ((0,0), self.pagesize)
                if isinstance(self.background, Gradient):
                    self.background.fill(rect)
                else:
                    CGContextSetFillColorWithColor(gfx._state.port, self.background.cgColor)
                    NSRectFillUsingOperation(rect, NSCompositeSourceOver)

            with autorelease():
                for grob in gfx._state.visible(self.grobs):
                    if cancelled is not None and cancelled():
                        return
                    gfx._render_lock.checkpoint()
                    grob._draw()

    @property
    def _nsImage(self):
        # convert to a 2x bitmap in P3
        bitmap = NSBitmapImageRep.alloc().initWithCGImage_(self._render_to_cgimage(1.0, 2.0))
        bitmap.setSize_(self.pagesize)
        img = NSImage.alloc().initWithSize_(self.pagesize)
        img.addRepresentation_(bitmap)
        img.setFlipped_(True)
        return img

    def _traced(self, grobs):
        # the union of the grobs' shapes, in the frame's px space
        from .effects import Stencil
        outline = PDPath()
        for grob in grobs:
            if isinstance(grob, Stencil):
                # the contents within a clip(), or outside a mask()
                contents = self._traced(grob.contents)
                if hasattr(grob, 'path'):
                    stencil, masked = grob.path._screen_transform.apply(grob.path)._pdpath, grob.evenodd
                else:
                    stencil = grob.bmp._screen_transform.apply(grob.bmp._outline)._pdpath # a bitmap stencil's image
                    masked = grob.invert != (grob.channel == 'black')
                shape = pathmatics.difference(contents, stencil, 0.6) if masked else pathmatics.intersect(contents, stencil, 0.6)
            elif isinstance(grob, Frob):
                shape = self._traced(grob.contents)
            elif isinstance(grob, Image):
                shape = grob._screen_transform.apply(grob._outline)._pdpath
            elif isinstance(grob, Bezier):
                shape = grob._pdpath if grob._fillcolor is not None else PDPath()
                if grob._strokecolor is not None:
                    stroked = grob.trace(grob.nib, grob.joinstyle, grob.capstyle)._pdpath
                    shape = pathmatics.union(shape, stroked, 0.6)
                shape = grob._screen_transform.apply(shape)
            else:
                path = grob.path # text's glyphs
                shape = path._screen_transform.apply(path)._pdpath
            outline = pathmatics.union(outline, shape, 0.6)
        return outline

    def _raster_size(self, scale):
        return tuple(max(int(dim * scale), 1) for dim in self.pagesize)

    def _render_to_cgimage(self, zoom=1.0, dpr=1.0):
        """Rasterize to a CGImage at `zoom` (points per canvas-unit) times `dpr`
        (pixels per point).

        Draws into a private bitmap context rather than borrowing lockFocus's
        thread-global focus stack, so it's also safe to call from a non-main
        thread."""
        scale = zoom * dpr
        size = Size(*self._raster_size(scale))
        colorspace, opts = CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3), kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Host
        bitmapContext = CGBitmapContextCreate(None, size.width, size.height, 8, size.width * 4, colorspace, opts)
        self._render_to_context(bitmapContext, scale)
        return CGBitmapContextCreateImage(bitmapContext)

    def _render_to_surface(self, surface, scale, cancelled=None, origin=None, size=None):
        """Rasterize into a PDSurface at `scale` pixels per point"""
        w, h = size or (surface.width(), surface.height())
        H = surface.height()
        surface.lock()
        port = surface.context()
        CGContextSaveGState(port)
        try:
            # the surface's top-left w x h pixels
            CGContextClipToRect(port, ((0, H - h), (w, h)))
            CGContextClearRect(port, ((0, H - h), (w, h)))
            offset = within = None
            if origin is not None:
                offset = (-origin[0], origin[1] + H)
                within = (origin[0] / scale, origin[1] / scale, w / scale, h / scale)

            # convert colors if a Proof profile has been selected
            proof = self.proof.space if self.proof is not None else None
            if proof is None:
                self._render_to_context(port, scale, cancelled, offset, within)
            else:
                # render via a bitmap in the proof space
                cmyk = CGColorSpaceGetModel(proof) == kCGColorSpaceModelCMYK
                bitmap = CGBitmapContextCreate(None, w, h, 8, w * 4, proof, kCGImageAlphaNone if cmyk else kCGImageAlphaPremultipliedLast)
                CGContextSetRenderingIntent(bitmap, kCGRenderingIntentRelativeColorimetric)
                x, y = offset or (0, self.pagesize.height * scale)
                self._render_to_context(bitmap, scale, cancelled, (x, y - (H - h)), within)
                image = CGBitmapContextCreateImage(bitmap)
                if self.proof.vision is not None:
                    image = CGImageCreateCopyWithColorSpace(image, self.proof.vision)
                CGContextSetRenderingIntent(port, kCGRenderingIntentRelativeColorimetric)
                CGContextDrawImage(port, ((0, H - h), (w, h)), image)
            CGContextFlush(port)
        finally:
            CGContextRestoreGState(port)
            surface.unlock()

    def _render_to_context(self, cgContext, zoom, cancelled=None, offset=None, within=None):
        with autorelease():
            ns_ctx = NSGraphicsContext.graphicsContextWithCGContext_flipped_(cgContext, True)
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.setCurrentContext_(ns_ctx)
            NSGraphicsContext.saveGraphicsState()
            try:
                trans = NSAffineTransform.transform()
                trans.translateXBy_yBy_(*(offset or (0, self.pagesize.height*zoom)))
                trans.scaleXBy_yBy_(zoom,-zoom)
                trans.concat()
                self.draw(cancelled, within)
            finally:
                NSGraphicsContext.restoreGraphicsState()
                NSGraphicsContext.restoreGraphicsState()

    def _getImageData(self, format, zoom=1.0, title=None):
        return self._encode(format, zoom, title=title)[0]

    def _encode(self, format, zoom=1.0, cancelled=None, title=None):
        """Render and encode as `format`, returning the data and surface"""
        if format == 'pdf':
            w, h = self.pagesize
            cgData = NSMutableData.alloc().init() # owned, not autoreleased
            dataConsumer = CGDataConsumerCreateWithCFData(cgData)
            pdfContext = CGPDFContextCreate(dataConsumer, CGRectMake(0, 0, w*zoom, h*zoom), None)
            CGPDFContextBeginPage(pdfContext, None)
            with gfx._state.using(pdf=(pdfContext, {})):
                self._render_to_context(pdfContext, zoom)
                with gfx._render_lock: # pattern tiles draw during EndPage, after the render released the lock
                    CGPDFContextEndPage(pdfContext)
            CGPDFContextClose(pdfContext)
            pdfContext = None
            if self.output.profile.space is not None: # plain CMYK is left as is
                press = self.output.press
                intent = press.intent if press else None
                update = Distiller(bytes(cgData), self.output.profile.space, intent=intent, title=title).endmatter()
                cgData.appendBytes_length_(update, len(update))
            return cgData, None
        elif format == 'eps':
            with autorelease(), gfx._render_lock: # AppKit draws pattern tiles after drawRect_ returns
                view = PostScriptView.alloc().initWithCanvas_(self)
                return view.dataWithEPSInsideRect_(view.bounds()), None
        else:
            cgTypes = {"gif":  'com.compuserve.gif',
                       "jpg":  'public.jpeg',
                       "jpeg": 'public.jpeg',
                       "png":  'public.png',
                       "tiff": 'public.tiff',
                       "heic": 'public.heic'}

            size = Size(*[int(dim*zoom) for dim in self.pagesize])
            surface = None
            press = self.output.press
            if format in ('jpeg', 'jpg', 'tiff') and self.output.mode == CMYK and self.output.format is not None:
                # a bitmap in the press's space
                colorspace, opts = press.space if press else CGColorSpaceCreateDeviceCMYK(), kCGImageAlphaNone
                bitmapContext = CGBitmapContextCreate(None, size.width, size.height, 8, size.width * 4, colorspace, opts)
                if press:
                    CGContextSetRenderingIntent(bitmapContext, kCGRenderingIntentRelativeColorimetric)
                self._render_to_context(bitmapContext, zoom, cancelled)
                cgImage = CGBitmapContextCreateImage(bitmapContext)
            else:
                # a surface the window can display
                surface = objc.lookUpClass('PDSurface').alloc().initWithWidth_height_space_(size.width, size.height, self.output.surface_space)
                self._render_to_surface(surface, zoom, cancelled)
                surface.lock()
                cgImage = CGBitmapContextCreateImage(surface.context())
                surface.unlock()
            if cancelled is not None and cancelled():
                return None, None

            cgData = NSMutableData.alloc().init() # owned, not autoreleased
            cgDest = CGImageDestinationCreateWithData(cgData, cgTypes[format], 1, None)
            cgProperies = {kCGImagePropertyDPIWidth: 72*zoom, kCGImagePropertyDPIHeight: 72*zoom}
            if format in ('jpg', 'jpeg'):
                cgProperies[kCGImageDestinationLossyCompressionQuality] = 1.0
            # ImageIO keeps the properties forever, so hand it a native dict
            CGImageDestinationAddImage(cgDest, cgImage, NSDictionary.dictionaryWithDictionary_(cgProperies))
            CGImageDestinationFinalize(cgDest)
            return cgData, surface

    def save(self, fname, format=None, zoom=1.0):
        """Write the current graphics objects to an image file"""
        if format is None:
            format = fname.rsplit('.',1)[-1].lower()
        data = self._getImageData(format, zoom, os.path.splitext(os.path.basename(fname))[0])
        fname = NSString.stringByExpandingTildeInPath(fname)
        data.writeToFile_atomically_(fname, False)

class FrameBounds(object):
    """Where a frame's grobs can draw"""

    # blend modes that reach outside the shape
    _UNBOUNDED_BLENDS = {'clear', 'copy', 'sourcein', 'sourceout', 'destinationin', 'destinationatop'}

    def __init__(self, grobs):
        self._grobs = grobs
        self._boxes = None # each grob's box, made lazily
        self._layers = {}  # transparency layers' boxes

    def within(self, rect, grobs):
        """The grobs that could draw inside rect"""
        if self._boxes is None:
            boxes = {}
            for grob in self._grobs:
                boxes[id(grob)] = self._box(grob, boxes)
            self._boxes = boxes
        x, y, w, h = rect
        boxes = [self._boxes[id(grob)] for grob in grobs]
        return [grob for grob, box in zip(grobs, boxes) if box is None or not (
                box[0] > x + w or box[1] > y + h or box[0] + box[2] < x or box[1] + box[3] < y)]

    def layer_box(self, grob):
        """The box of a grob and its own effects"""
        key = id(grob)
        if key not in self._layers:
            self._layers[key] = self._box(grob, {})
        return self._layers[key]

    @classmethod
    def _box(cls, grob, boxes):
        """A grob's box, or None if it may draw anywhere"""
        if not isinstance(grob, Frob):
            # for a single grob, account for its shape's bounds plus room for strokes, miters, and antialiasing
            x, y, w, h = grob._render_box()
            pad = (getattr(grob, 'strokewidth', 0) or 0) * grob._grid.dpx * 5 + 2

            # grow the box further to make room for its effects (shadows etc.)
            fx = getattr(grob, '_effects', None)
            return cls._with_effects((x - pad, y - pad, w + 2 * pad, h + 2 * pad), {} if fx is None else fx._fx)

        # for groups, start by measuring a box for each grob inside
        contents = grob.contents
        for g in contents:
            boxes[id(g)] = cls._box(g, boxes)

        # the group should be the union of the boxes (or unbounded if any box in the group is also unbounded)
        inner = [boxes[id(g)] for g in contents]
        union = None
        if inner and None not in inner:
            x0, y0 = min(b[0] for b in inner), min(b[1] for b in inner)
            x1, y1 = max(b[0] + b[2] for b in inner), max(b[1] + b[3] for b in inner)
            union = (x0, y0, x1 - x0, y1 - y0)

        # an effects group grows to cover its effects
        if isinstance(grob, Effect):
            if grob._fx.get('shadow') is not None:
                nested = list(contents)
                while nested:
                    g = nested.pop()
                    boxes[id(g)] = cls._with_effects(boxes[id(g)], grob._fx)
                    if isinstance(g, Frob):
                        nested.extend(g.contents)
            return cls._with_effects(union, grob._fx)

        if isinstance(grob, Stencil) and getattr(grob, 'path', None) is not None and not grob.evenodd:
            aa = 2 # account for the antialiasing fringe at the clip's edges
            cx, cy, cw, ch = grob.path._render_box()
            if union is None:
                return (cx - aa, cy - aa, cw + 2 * aa, ch + 2 * aa)
            x0, y0 = max(union[0], cx - aa), max(union[1], cy - aa)
            x1, y1 = min(union[0] + union[2], cx + cw + aa), min(union[1] + union[3], cy + ch + aa)
            return (x0, y0, max(x1 - x0, 0), max(y1 - y0, 0))

        # the grob is either a bitmap mask or an inverted clip, so use its inner union
        return union

    @classmethod
    def _with_effects(cls, box, fx):
        # grow the box to account for active effects
        if box is None or fx.get('blend') in cls._UNBOUNDED_BLENDS:
            return None
        shadow = fx.get('shadow')
        if shadow is not None:
            # a shadow extends to its blur radius + antialiasing fringe
            x, y, w, h = box
            (dx, dy), reach = shadow.offset, shadow.blur + 2
            x0, y0 = min(x, x + dx - reach), min(y, y + dy - reach)
            x1, y1 = max(x + w, x + w + dx + reach), max(y + h, y + h + dy + reach)
            box = (x0, y0, x1 - x0, y1 - y0)
        return box

class PostScriptView(NSView):
    # This view was created to provide EPS data. CoreGraphics isn't antiquarian
    # enough to speak EPS so we need to draw to an NSView then use its
    # dataWithEPSInsideRect_ instead

    def initWithCanvas_(self, canvas):
        super(PostScriptView, self).initWithFrame_( ((0, 0), canvas.pagesize) )
        self.canvas = canvas
        return self

    def drawRect_(self, rect):
        self.canvas.draw()

    def isOpaque(self):
        return False

    def isFlipped(self):
        return True
