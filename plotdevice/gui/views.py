# encoding: utf-8
import sys
import os
import math
import bisect
import time
import traceback
import objc

from . import set_timeout, FrameQueue
from ..lib.cocoa import *
from ..gfx.colors import Color, RGB
from ..gfx.atoms import KEY_ESC
from objc import super

class Rasterizer(object):
    DEPTH = FrameQueue.DEPTH + 2
    BACKDROP = 2048  # longest side, in pixels, of the low-res frame shown during a zoom gesture
    HEADROOM = 1.15  # a ring made for a viewport render fits ones up to this much bigger each way
    SHRINK = 0.5     # and is made afresh once they need less than this share of it

    def __init__(self):
        self._size = None
        self._surfaces = []
        self._onscreen = ()  # the surface on screen and the one it replaced

    def render(self, frame, scale, cancelled=None, rect=None):
        if rect is None:
            origin, need = None, frame._raster_size(scale)
            size = need
        else:
            origin, need = rect[:2], tuple(rect[2:])
            fits = self._size is not None and need[0] <= self._size[0] and need[1] <= self._size[1]
            if fits and need[0] * need[1] >= self.SHRINK * self._size[0] * self._size[1]:
                size = self._size
            else:
                size = tuple(int(math.ceil(v * self.HEADROOM)) for v in need)
        if size != self._size:
            PDSurface = objc.lookUpClass('PDSurface')
            self._size = size
            self._surfaces = [PDSurface.surfaceWithWidth_height_(*size) for _ in range(self.DEPTH)]
        surface = next(s for s in self._surfaces if s.surface() not in self._onscreen)
        self._surfaces.remove(surface)
        self._surfaces.append(surface)
        frame._render_to_surface(surface, scale, cancelled, origin, need)
        return surface.surface()

    def render_tiles(self, tiles, coords, cancelled=None):
        self._size, self._surfaces = None, []
        rendered = []
        for tile in coords:
            if cancelled is not None and cancelled():
                break
            x, y, w, h = tiles.rect(tile)
            rendered.append((tile, self._render_once(tiles.frame, tiles.scale, (w, h), cancelled, (x, y))))
        return rendered

    def render_backdrop(self, frame, cancelled=None):
        scale = self.BACKDROP / max(frame.pagesize)
        return self._render_once(frame, scale, frame._raster_size(scale), cancelled)

    def shown(self, surface):
        self._onscreen = (surface,) + self._onscreen[:1]

    def _render_once(self, frame, scale, size, cancelled=None, origin=None):
        surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(*size)
        frame._render_to_surface(surface, scale, cancelled, origin)
        return surface.surface()

class CenteringClipView(NSClipView):

    def awakeFromNib(self):
        scrollview = self.enclosingScrollView()
        if scrollview is not None:
            scrollview.setWantsLayer_(True)

    def setFrameSize_(self, size):
        super(CenteringClipView, self).setFrameSize_(size)
        doc = self.documentView()
        if isinstance(doc, GraphicsView):
            doc.fitToViewport()

    @objc.python_method
    def _confine(self, origin, extent, inset, canvas, document):
        if extent >= canvas:
            return inset + (canvas - extent) / 2.0
        if canvas < document:
            return min(max(origin, inset), inset + canvas - extent)
        return origin

    def constrainBoundsRect_(self, proposed):
        rect = super(CenteringClipView, self).constrainBoundsRect_(proposed)
        doc = self.documentView()
        if isinstance(doc, GraphicsView) and doc.canvasSize is not None:
            (ox, oy, cw, ch), (W, H) = doc.canvasRect(), doc.frame().size
            rect.origin.x = self._confine(rect.origin.x, rect.size.width, ox, cw, W)
            rect.origin.y = self._confine(rect.origin.y, rect.size.height, oy, ch, H)
        return rect

    def scrollToPoint_(self, point):
        doc = self.documentView()
        if isinstance(doc, GraphicsView) and doc.canvasSize is not None:
            (vw, vh), (W, H) = self.bounds().size, doc.frame().size
            x, y = point
            centered = self.constrainBoundsRect_(((x, y), (vw, vh))).origin
            x = min(max(x, -vw / 4), W - vw + vw / 4) if W > vw else centered.x
            y = min(max(y, -vh / 4), H - vh + vh / 4) if H > vh else centered.y
            point = (x, y)
        super(CenteringClipView, self).scrollToPoint_(point)

    def scrollWheel_(self, event):
        doc = self.documentView()
        if (event.modifierFlags() & NSAlternateKeyMask) and isinstance(doc, GraphicsView) and doc.canvas is not None:
            doc.scrollWheel_(event)
        else:
            super(CenteringClipView, self).scrollWheel_(event)

class FrameTiles(object):
    TILE = 1024             # tile edge, in pixels
    BLEED = 2               # pixels each tile overlaps its neighbors, so no seams show when scaled
    BUDGET = 4096 * 4096    # still frames whose full raster has more pixels than this are tiled
    CACHE = 256 * 2**20     # bytes of rendered tiles to keep for a frame (least recently used go first)

    def __init__(self, frame, key):
        self.frame, self.key = frame, key  # key: (seq, zoom, dpr)
        self.scale = key[1] * key[2]
        self._full = frame._raster_size(self.scale)
        self._holder = None
        self.layers = {}  # tile -> its layer, least recently used first
        self._jobs = {}   # tile -> the RenderJob of its in-flight render

    def covering(self, rect):
        """The tiles a pixel rect touches"""
        x, y, w, h = rect
        T, full = self.TILE, self._full
        cols = range(max(0, int(x // T)), min(math.ceil(full[0] / T), math.ceil((x + w) / T)))
        rows = range(max(0, int(y // T)), min(math.ceil(full[1] / T), math.ceil((y + h) / T)))
        return [(i, j) for j in rows for i in cols]

    def rect(self, tile):
        T, B, full = self.TILE, self.BLEED, self._full
        x, y = tile[0] * T, tile[1] * T
        x0, y0 = max(0, x - B), max(0, y - B)
        return (x0, y0, min(full[0], x + T + B) - x0, min(full[1], y + T + B) - y0)

    def add(self, rendered):
        """Display rendered (tile, surface) pairs"""
        dpr = self.key[2]
        for tile, surface in rendered:
            if tile in self.layers:
                continue
            x, y, w, h = self.rect(tile)
            layer = CALayer.new()
            layer.setActions_({k:None for k in ["onOrderIn", "contents", "position", "bounds"]})
            layer.setContentsScale_(dpr)
            layer.setContents_(surface)
            layer.setFrame_(((x / dpr, y / dpr), (w / dpr, h / dpr)))
            self._holder.addSublayer_(layer)
            self.layers[tile] = layer

    def attach(self, holder):
        self._holder = holder

    def detach(self):
        self._holder, self.layers = None, {}

    def delivered(self, tile):
        """A render of `tile` has been delivered"""
        self._jobs.pop(tile, None)

    def request(self, visible, submit):
        self._jobs = {t: job for t, job in self._jobs.items() if job.pending}

        vx, vy, vw, vh = visible
        mx, my = max(vw / 2, self.TILE), max(vh / 2, self.TILE)
        margin_rect = (vx - mx, vy - my, vw + 2 * mx, vh + 2 * my)

        for tile in self.covering(visible):
            if tile in self.layers:
                self.layers[tile] = self.layers.pop(tile)
        keep = set(self.covering(margin_rect))
        size = lambda t: self.rect(t)[2] * self.rect(t)[3] * 4
        cached = sum(size(t) for t in self.layers)
        for tile in [t for t in self.layers if t not in keep]:
            if cached <= self.CACHE:
                break
            cached -= size(tile)
            self.layers.pop(tile).removeFromSuperlayer()

        unrendered = lambda rect: [t for t in self.covering(rect) if t not in self.layers and t not in self._jobs]
        for tile in unrendered(visible):
            self._jobs[tile] = submit(tile)
        if self._jobs:
            return
        margin = unrendered(margin_rect)
        if margin:
            cx, cy = vx + vw / 2, vy + vh / 2
            T = self.TILE
            distance = lambda t: (((t[0] + .5) * T - cx) ** 2 + ((t[1] + .5) * T - cy) ** 2)
            tile = min(margin, key=distance)
            self._jobs[tile] = submit(tile)

class FramePresenter(object):

    def __init__(self, root):
        self.queue = None              # the window's FrameQueue (set through the view)
        self.attached = True           # whether the view is in a window (renders landing while it isn't are dropped)
        self._root = root              # the view's layer
        self._raster = Rasterizer()    # what draws the renders it presents
        self._holder = None            # layer over the canvas, while a frame is shown in parts
        self._backdrop_layer = None    # the bottom layer in the holder
        self._viewport = None          # layer showing an animation frame rendered for the viewport only
        self._tiles = None             # the FrameTiles on display, if the frame is tiled
        self._frame = None             # the frame on display
        self._backdrop = None          # (frame, surface) for a zoom gesture, see _show_backdrop()
        self._rect = None              # the canvas's rect in the root layer
        self._physics = ViewportPhysics()
        self._visible = None           # the edges (x0, y0, x1, y1) of what's in view, from moved()
        self._canvas_size = None       # the canvas's size, in points
        self._viewport_size = None     # the view's size, in points
        self._magnification = 1.0      # a zoom gesture's magnification
        self._wanted = None            # (zoom, dpr) of the latest frame asked for
        self._wanted_mode = None       # and the mode it's rendered in
        self._shown = (0, None, None)  # (seq, zoom, dpr) of the frame on display
        self._period = None            # the time between frames while they're live, else None
        self._gesture = False          # whether a zoom gesture's preview is on screen
        self._landing = False          # whether the view is laying itself out for a frame being presented
        self._patch = None             # RenderJob rendering the frame on screen again, for where the view has moved

    def _show_backdrop(self, backdrop):
        self._backdrop = backdrop
        if self._backdrop_layer is None:
            return
        if backdrop is None:
            self._backdrop_layer.setContents_(None)
        elif self._viewport is not None or self._frame is backdrop[0]:
            self._backdrop_layer.setContents_(backdrop[1])

    @property
    def viewport_only(self):
        return self._viewport is not None or self._wanted_mode == 'viewport'

    def render(self, frame, seq, zoom, dpr, period=None, landing=None, on_land=None, onerror=None, ondone=None):
        self._wanted, self._period = (zoom, dpr), period
        width, height = frame._raster_size(zoom * dpr)
        if self._visible is None:
            mode = 'full'
        elif period is not None:
            vw, vh = self._viewport_size
            mode = 'viewport' if width * height > ViewportPhysics.RATIO * vw * vh * dpr ** 2 else 'full'
        else:
            mode = 'tiles' if width * height > FrameTiles.BUDGET else 'full'
        self._wanted_mode = mode
        self._submit(frame, seq, zoom, dpr, mode, landing, on_land, onerror, ondone)

    def moved(self, visible, canvas_size, viewport_size, magnification):
        if visible != self._visible:
            self._physics.moved(visible)
        self._visible, self._canvas_size, self._viewport_size = visible, canvas_size, viewport_size
        self._magnification = magnification
        self._request_tiles()
        self._request_viewport()

    def gesture_began(self):
        self._gesture = True
        frame, backdrop = self._frame, self._backdrop
        if frame is not None and (backdrop is None or backdrop[0] is not frame):
            def work(raster, cancelled):
                return raster.render_backdrop(frame, cancelled)
            def deliver(surface, err):
                if err is None and self._gesture:
                    self._show_backdrop((frame, surface))
            self._job(work, deliver)

    def gesture_ended(self):
        self._gesture = False
        if self._viewport is not None:
            self._show_backdrop(None)
        self._request_tiles()

    def place(self, rect):
        self._rect = rect
        if self._holder is not None:
            self._holder.setFrame_(rect)
            self._backdrop_layer.setFrame_(self._holder.bounds())

    def _clear(self):
        if self._holder is None:
            return
        self._holder.removeFromSuperlayer()
        if self._tiles is not None:
            self._tiles.detach()
        self._holder = self._backdrop_layer = self._viewport = self._tiles = self._frame = None

    def _submit(self, frame, seq, zoom, dpr, mode, landing=None, on_land=None, onerror=None, ondone=None, again=False):
        if mode == 'tiles':
            tiles = self._tiles
            if tiles is None or tiles.key != (seq, zoom, dpr):
                tiles = FrameTiles(frame, (seq, zoom, dpr))
            coords = [t for t in tiles.covering(landing or self._in_view(zoom * dpr)) if t not in tiles.layers]
            work = lambda raster, cancelled: (tiles, raster.render_tiles(tiles, coords, cancelled))
        elif mode == 'viewport':
            settled = landing is None
            if settled:
                edges = self._visible
            else:
                x0, y0, w, h = [v / dpr for v in landing]
                edges = (x0, y0, x0 + w, y0 + h)
            vw, vh = self._viewport_size
            rect, density = self._physics.region(frame, zoom, dpr, edges, settled, self._magnification,
                                                   vw * vh * dpr * dpr, self._period or 0.0)
            scale = zoom * density
            work = lambda raster, cancelled: (rect, raster.render(frame, scale, cancelled, rect), density)
        else:
            work = lambda raster, cancelled: raster.render(frame, zoom * dpr, cancelled)

        def deliver(result, err):
            if err is not None:
                if onerror is not None:
                    onerror(err)
            else:
                if mode == 'viewport':
                    self._physics.landed(job.elapsed, rect[2] * rect[3])
                current = seq >= self._shown[0] and (zoom, dpr) == self._wanted and self.attached
                if current and (not again or self._viewport is not None):
                    self._shown = (seq, zoom, dpr)
                    self._prepare(mode, result)
                    self._landing = True
                    try:
                        if on_land is not None:
                            on_land()
                    finally:
                        self._landing = False
                    self._present(mode, frame, result, dpr)
                    if mode == 'tiles':
                        self._request_tiles()
                    elif mode == 'viewport':
                        self._request_viewport(landed=True)
            if ondone is not None:
                ondone()
        job = self._job(work, deliver)
        return job

    def _request_tiles(self):
        tiles = self._tiles
        if tiles is None or self._visible is None or self._gesture or self._landing:
            return  # (mid-gesture, applying it renders at the new zoom; mid-landing, this runs once it's presented)
        def submit(tile):
            def work(raster, cancelled):
                return raster.render_tiles(tiles, [tile], cancelled)
            def deliver(rendered, err):
                if self._tiles is not tiles:
                    return
                tiles.delivered(tile)
                if err is None and self.attached:
                    tiles.add(rendered)
                    self._request_tiles()
            return self._job(work, deliver)
        tiles.request(self._in_view(tiles.key[2]), submit)

    def _request_viewport(self, landed=False):
        patching = self._patch is not None and self._patch.pending
        seq, zoom, dpr = self._shown
        if self._viewport is None or self._visible is None or self._landing or patching or self._wanted != (zoom, dpr):
            return
        if not landed and not self.queue.ready:
            return
        x, y, w, h = self._in_view(1.0)
        (lx, ly), (lw, lh) = self._viewport.frame()
        if w <= 0 or h <= 0 or (lx <= x + .5 and ly <= y + .5 and lx + lw >= x + w - .5 and ly + lh >= y + h - .5):
            return
        self._patch = self._submit(self._frame, seq, zoom, dpr, 'viewport', again=True)

    def _in_view(self, scale):
        (x0, y0, x1, y1), (cw, ch) = self._visible, self._canvas_size
        x0, y0 = min(max(x0, 0), cw), min(max(y0, 0), ch)
        x1, y1 = max(min(x1, cw), x0), max(min(y1, ch), y0)
        return (x0 * scale, y0 * scale, (x1 - x0) * scale, (y1 - y0) * scale)

    def _job(self, work, deliver):
        raster = self._raster
        return self.queue.submit(lambda cancelled: work(raster, cancelled), deliver)

    def _prepare(self, mode, result):
        same_tiles = mode == 'tiles' and self._tiles is result[0]
        same_viewport = mode == 'viewport' and self._viewport is not None
        if not (same_tiles or same_viewport):
            self._clear()
        if mode == 'full':
            self._show_backdrop(None)

    def _present(self, mode, frame, result, dpr):
        if mode == 'tiles':
            tiles, rendered = result
            if self._tiles is not tiles:
                self._hold(frame)
                tiles.attach(self._holder)
                self._tiles = tiles
            tiles.add(rendered)
        elif mode == 'viewport':
            rect, surface, density = result
            if self._viewport is None:
                self._hold(frame)
                self._viewport = CALayer.new()
                self._viewport.setActions_({k:None for k in ["contents", "contentsRect", "contentsScale", "position", "bounds"]})
                self._holder.addSublayer_(self._viewport)
            self._frame = frame
            self._holder.setBackgroundColor_(self._fill(frame))
            x, y, w, h = rect
            W, H = surface.width(), surface.height()
            self._viewport.setContentsScale_(density)
            self._viewport.setContents_(surface)
            top = 0 if self._viewport.contentsAreFlipped() else 1 - h / H
            self._viewport.setContentsRect_(((0, top), (w / W, h / H)))
            self._viewport.setFrame_(((x / density, y / density), (w / density, h / density)))
            self._raster.shown(surface)
        else:
            self._root.setContentsScale_(dpr)
            self._root.setContents_(result)
            self._raster.shown(result)

    def _hold(self, frame):
        self._clear()
        self._root.setContents_(None)
        holder = CALayer.new()
        holder.setGeometryFlipped_(not self._root.contentsAreFlipped())
        holder.setActions_({k:None for k in ["sublayers", "position", "bounds", "backgroundColor"]})
        holder.setBackgroundColor_(self._fill(frame))
        backdrop = CALayer.new()
        backdrop.setActions_({k:None for k in ["contents", "position", "bounds"]})
        backdrop.setContentsGravity_(kCAGravityResize)
        if self._backdrop is not None and self._backdrop[0] is frame:
            backdrop.setContents_(self._backdrop[1])
        holder.addSublayer_(backdrop)
        self._root.addSublayer_(holder)
        self._holder, self._backdrop_layer, self._frame = holder, backdrop, frame
        if self._rect is not None:
            self.place(self._rect)

    @staticmethod
    def _fill(frame):
        bg = frame.background
        if not isinstance(bg, Color) or bg.alpha < 1:
            return None
        color = (bg._rgb if frame.outputmode == RGB else bg._cmyk).CGColor()
        return CGColorCreateCopyByMatchingToColorSpace(CGColorSpaceCreateDeviceRGB(), kCGRenderingIntentDefault, color, None)

class ViewportPhysics(object):
    RATIO = 1.5         # animation frames whose full raster is this many times the viewport's render just the viewport
    START_SPEED = 3000  # points per second a scroll (a fling, say) may reach before the next animation frame lands
    MARGIN = 0.25       # most an animation frame renders past each side of the view, as a fraction of it
    PREDICT_CAP = 2     # most pixels an animation frame renders to cover the view's motion, in viewports' worth
    RENDER_CAP = 3      # most it renders with a margin too, if there's time for it in a frame

    def __init__(self):
        self._scrolls = []        # recent (time, edges) of the visible rect, for how fast they're moving
        self._renderTime = 0.0    # smoothed time to render a frame for the viewport
        self._pixelTime = 0.0     # smoothed time those renders take per pixel
        self._frameGap = 0.0      # smoothed time between those frames landing
        self._frameShown = None   # when the last one landed

    def moved(self, edges):
        now = time.perf_counter()
        self._scrolls = [(t, e) for t, e in self._scrolls if now - t < .12] + [(now, edges)]

    def landed(self, elapsed, pixels):
        now = time.perf_counter()
        self._renderTime += .3 * (elapsed - self._renderTime)
        self._pixelTime += .3 * (elapsed / pixels - self._pixelTime)
        if self._frameShown is not None:
            self._frameGap += .3 * (min(now - self._frameShown, .5) - self._frameGap)
        self._frameShown = now

    def region(self, frame, zoom, dpr, edges, moving, mag, viewport, period):
        x0, y0, x1, y1 = edges
        if moving:
            vw, vh = x1 - x0, y1 - y0
            ahead = self._renderTime + self._frameGap
            dx0, dy0, dx1, dy1 = [v * ahead for v in self._edgeVelocity()]
            density = dpr * min(1.0, mag * min(1.0, vw / max(vw + dx1 - dx0, 1.0)))
            margin_x = min(self.START_SPEED * ahead / mag, self.MARGIN * vw)
            margin_y = min(self.START_SPEED * ahead / mag, self.MARGIN * vh)
        else:
            dx0 = dy0 = dx1 = dy1 = margin_x = margin_y = 0
            density = dpr

        spare = viewport * max(1.0, min(self.RENDER_CAP, period / max(self._pixelTime * viewport, 1e-9)))
        lead = (-min(dx0, 0), -min(dy0, 0), max(dx1, 0), max(dy1, 0))  # left, top, right, bottom
        margin = (margin_x, margin_y, margin_x, margin_y)
        pixels = lambda k, j: (x1 - x0 + k * (lead[0] + lead[2]) + j * 2 * margin_x) * \
                              (y1 - y0 + k * (lead[1] + lead[3]) + j * 2 * margin_y) * density ** 2
        k = 1.0
        while k > 0 and pixels(k, 0) > self.PREDICT_CAP * viewport:
            k = max(k - .1, 0)
        j = 1.0
        while j > 0 and pixels(k, j) > spare:
            j = max(j - .1, 0)
        density = min(density, math.sqrt(self.PREDICT_CAP * viewport / max((x1 - x0) * (y1 - y0), 1.0)))
        left, top, right, bottom = [k * a + j * b for a, b in zip(lead, margin)]

        full = frame._raster_size(zoom * density)
        x, y = max(int((x0 - left) * density), 0), max(int((y0 - top) * density), 0)
        w = int(math.ceil((x1 + right) * density)) - x
        h = int(math.ceil((y1 + bottom) * density)) - y
        return (x, y, max(min(w, full[0] - x), 1), max(min(h, full[1] - y), 1)), density

    def _edgeVelocity(self):
        now = time.perf_counter()
        recent = [(t, edges) for t, edges in self._scrolls if now - t < .12]
        if len(recent) < 2 or now - recent[-1][0] > .08:
            return 0.0, 0.0, 0.0, 0.0
        (t0, before), (t1, after) = recent[0], recent[-1]
        return tuple((b - a) / (t1 - t0) for a, b in zip(before, after))

class GraphicsView(NSView):
    script = IBOutlet()
    canvas = None
    _queue = None      # the window's FrameQueue (class-level: the ScriptController may set it before awakeFromNib)
    _presenter = None
    canvasSize = None # the canvas at the displayed zoom, in points (class-level: the clip view may ask before awakeFromNib)

    # The zoom levels are 10%, 25%, 50%, 75%, 100%, 200% and so on up to 2000%.
    zoomLevels = [0.1, 0.25, 0.5, 0.75]
    zoom = 1.0
    while zoom <= 20.0:
        zoomLevels.append(zoom)
        zoom += 1.0

    def awakeFromNib(self):
        self.canvas = None
        self.mousedown = False
        self.keydown = False
        self.key = None
        self.keycode = None
        self._zoom = 1.0
        self._wantZoom = self._zoom  # zoom to render at (adopted as _zoom once displayed)
        self._displayed = False   # whether a frame has been shown yet
        self._seq = 0             # sequence number of the latest committed frame
        self._dpr = self.window().backingScaleFactor()
        self._magnifyReady = False
        self._zoomApply = None
        self._pendingFinish = None  # an applied magnification's finish(), until the zoom it asked for lands
        # self.scrollwheel = False
        # self.wheeldelta = 0.0

        self.setLayer_(CALayer.new())
        self.setWantsLayer_(True)
        self.layer().setContentsGravity_(kCAGravityCenter)
        self.layer().setContentsScale_(self._dpr)
        inaction = {k:None for k in ["onOrderOut", "sublayers", "contents", "contentsScale", "position", "bounds"]}
        self.layer().setActions_(inaction)
        self._presenter = FramePresenter(self.layer())  # what renders and presents the frames it asks for
        self._presenter.queue = self._queue

        # display the placeholder image until we're passed a canvas (and keep it in sync with appearance)
        self.updatePlaceholder(NSAppearance.currentDrawingAppearance())

    def _get_queue(self):
        return self._queue

    @objc.python_method
    def _set_queue(self, queue):
        self._queue = queue
        if self._presenter is not None:
            self._presenter.queue = queue
    queue = property(_get_queue, _set_queue)

    @objc.python_method
    def updatePlaceholder(self, appearance):
        if self.canvas is None:
            placeholder = NSImage.imageNamed_('placeholder-{mode}.pdf'.format(
                mode = 'dark' if 'Dark' in appearance.name() else 'light'
            ))
            if placeholder:
                self.canvasSize = tuple(placeholder.size())
                self.fitToViewport()
                self.layer().setContents_(placeholder)

    @objc.python_method
    def render(self, canvas, focus=None, onerror=None, ondone=None):
        self.canvas = canvas
        self._committed = canvas.commit()
        self._seq += 1
        self._request(focus, onerror=onerror, ondone=ondone)

    @objc.python_method
    def _rerender(self, focus=None, finish=None):
        if getattr(self, '_committed', None) is not None:
            self._request(focus, finish=finish)

    @objc.python_method
    def _request(self, focus=None, onerror=None, ondone=None, finish=None):
        frame, seq, zoom, dpr = self._committed, self._seq, self._wantZoom, self._dpr
        if finish is None:
            finish = self._pendingFinish
        if not self._displayed:
            self._moved()
        settled = finish is None and self._displayed and zoom == self._zoom
        scrollview = self.enclosingScrollView()
        landing = None
        if not settled and scrollview is not None:
            cw, ch = [dim * zoom for dim in frame.pagesize]
            vw, vh = scrollview.contentView().frame().size
            vw, vh = min(vw, cw), min(vh, ch)
            if not self._displayed:
                x, y = 0, 0
            else:
                fx, fy = focus if focus is not None else self._focus()
                x = min(max(fx * cw - vw / 2.0, 0), cw - vw)
                y = min(max(fy * ch - vh / 2.0, 0), ch - vh)
            landing = (x * dpr, y * dpr, vw * dpr, vh * dpr)
        live = self.script is not None and self.script.live
        period = self.script.framePeriod if live else None
        def on_land():
            if finish is not None:
                finish()
            self._zoom = zoom
            self._land(frame, focus)
        self._presenter.render(frame, seq, zoom, dpr, period, landing, on_land, onerror, ondone)

    @objc.python_method
    def _land(self, frame, focus):
        # set the scroller color based on the background
        bg = frame.background
        is_dark = bool(isinstance(bg, Color) and bg.brightness <= .5)
        scrollview = self.enclosingScrollView()
        scrollview.setScrollerKnobStyle_(2 if is_dark else 1) # NSScrollerKnobStyleDark/Light

        self._configureMagnification(scrollview)

        focused = focus is not None
        if focus is None:
            focus = self._focus()

        size = [s*self.zoom for s in frame.pagesize]
        resized, self.canvasSize = size != self.canvasSize, size
        self.fitToViewport()

        if self._magnifyReady:
            scrollview.setMinMagnification_(self.zoomLevels[0] / self._zoom)
            scrollview.setMaxMagnification_(self.zoomLevels[-1] / self._zoom)

        if not self._displayed:
            # draw from top-left corner if first-run
            self.scrollPoint_( (0,0) )
            self._displayed = True
        elif focused or resized:
            vw, vh = scrollview.contentView().bounds().size
            ox, oy, w, h = self.canvasRect()
            self.scrollPoint_( (ox + focus[0]*w - vw/2.0, oy + focus[1]*h - vh/2.0) )

    @objc.python_method
    def liveEnded(self):
        if self._presenter.viewport_only:
            self._rerender()

    @objc.python_method
    def _moved(self):
        scrollview = self.enclosingScrollView()
        if scrollview is None:
            return
        (vx, vy), (vw, vh) = scrollview.documentVisibleRect()
        ox, oy, cw, ch = self.canvasRect()
        visible = (vx - ox, vy - oy, vx - ox + vw, vy - oy + vh)
        viewport_size = tuple(scrollview.contentView().frame().size)
        self._presenter.moved(visible, (cw, ch), viewport_size, scrollview.magnification())

    def scrollViewWillStartLiveMagnify_(self, note):
        self._presenter.gesture_began()

    def clipBoundsChanged_(self, note):
        self._moved()

    @objc.python_method
    def canvasRect(self):
        W, H = self.frame().size
        cw, ch = self.canvasSize or (W, H)
        return ((W - cw) / 2.0, (H - ch) / 2.0, cw, ch)

    @objc.python_method
    def fitToViewport(self):
        if self.canvasSize is None:
            return
        cw, ch = self.canvasSize
        scrollview = self.enclosingScrollView()
        if scrollview is None:
            w, h = cw, ch
        else:
            vw, vh = scrollview.contentView().frame().size
            w, h = max(cw, vw), max(ch, vh)
            scrollview.setHorizontalScrollElasticity_(NSScrollElasticityAllowed if cw > vw else NSScrollElasticityNone)
            scrollview.setVerticalScrollElasticity_(NSScrollElasticityAllowed if ch > vh else NSScrollElasticityNone)
        if (w, h) != tuple(self.frame().size):
            self.setFrameSize_((w, h))
        ox, oy, cw, ch = self.canvasRect()
        if not self.layer().contentsAreFlipped():
            oy = self.frame().size.height - oy - ch
        self._presenter.place(((ox, oy), (cw, ch)))
        self._moved()

    @objc.python_method
    def _focus(self):
        if self.canvasSize is None:
            return (0.5, 0.5)
        vis = self.enclosingScrollView().documentVisibleRect()
        ox, oy, cw, ch = self.canvasRect()
        clamp = lambda v: max(0.0, min(1.0, v))
        return (clamp((NSMidX(vis) - ox) / cw), clamp((NSMidY(vis) - oy) / ch))

    @objc.python_method
    def canvasPoint(self, pt):
        """A point in the view's coordinates, in canvas units"""
        ox, oy, _, _ = self.canvasRect()
        return ((pt[0] - ox) / self._zoom, (pt[1] - oy) / self._zoom)

    def _get_zoom(self):
        return self._zoom

    @objc.python_method
    def _set_zoom(self, zoom):
        self._wantZoom = zoom
        self._rerender()
    zoom = property(_get_zoom, _set_zoom)

    @objc.python_method
    def _configureMagnification(self, scrollview):
        if self._magnifyReady:
            return
        scrollview.horizontalScroller().setControlSize_(NSSmallControlSize)
        scrollview.verticalScroller().setControlSize_(NSSmallControlSize)
        scrollview.setAllowsMagnification_(True)
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "scrollViewDidEndLiveMagnify:",
                                             NSScrollViewDidEndLiveMagnifyNotification, scrollview)
        nc.addObserver_selector_name_object_(self, "scrollViewWillStartLiveMagnify:",
                                             NSScrollViewWillStartLiveMagnifyNotification, scrollview)
        scrollview.contentView().setPostsBoundsChangedNotifications_(True)
        nc.addObserver_selector_name_object_(self, "clipBoundsChanged:",
                                             NSViewBoundsDidChangeNotification, scrollview.contentView())
        self._magnifyReady = True

    @objc.python_method
    def _applyMagnification(self, scrollview):
        mag = scrollview.magnification()
        if abs(mag - 1.0) < 1e-3:
            self._presenter.gesture_ended()
            return
        focus = self._focus()
        target = self._zoom * mag
        target = max(self.zoomLevels[0], min(self.zoomLevels[-1], target))
        self._wantZoom = target
        def finish():
            if self._pendingFinish is not finish:
                return  # folded in already, by an earlier frame (or replaced by a newer one)
            self._pendingFinish = None
            scrollview.setMagnification_(scrollview.magnification() / mag)
            self._presenter.gesture_ended()
        self._pendingFinish = finish
        self._rerender(focus=focus, finish=finish)

    def scrollViewDidEndLiveMagnify_(self, note):
        # trackpad pinch gesture settled
        self._applyMagnification(note.object())

    def viewDidChangeBackingProperties(self):
        super(GraphicsView, self).viewDidChangeBackingProperties()
        win = self.window()
        if win is None:
            return
        dpr = win.backingScaleFactor()
        if not dpr or getattr(self, '_dpr', None) == dpr:
            return
        self._dpr = dpr
        self._rerender()

    def viewWillMoveToWindow_(self, window):
        super(GraphicsView, self).viewWillMoveToWindow_(window)
        if getattr(self, '_presenter', None) is not None:
            self._presenter.attached = window is not None
        if window is None:
            if self._zoomApply is not None:
                self._zoomApply.invalidate()
                self._zoomApply = None
            if self._magnifyReady:
                nc = NSNotificationCenter.defaultCenter()
                nc.removeObserver_name_object_(self, NSScrollViewDidEndLiveMagnifyNotification, None)
                nc.removeObserver_name_object_(self, NSScrollViewWillStartLiveMagnifyNotification, None)
                nc.removeObserver_name_object_(self, NSViewBoundsDidChangeNotification, None)
                self._magnifyReady = False

    @IBAction
    def zoomIn_(self, sender):
        idx = bisect.bisect_right(self.zoomLevels, self.zoom)
        self.zoom = self.zoomLevels[min(idx, len(self.zoomLevels) - 1)]

    @IBAction
    def zoomOut_(self, sender):
        idx = bisect.bisect_left(self.zoomLevels, self.zoom) - 1
        self.zoom = self.zoomLevels[max(idx, 0)]

    @IBAction
    def resetZoom_(self, sender):
        self.zoom = 1.0

    def zoomTo_(self, zoom):
        self.zoom = zoom

    @IBAction
    def zoomToFit_(self, sender):
        if not self.canvas:
            return
        w, h = self.canvas.pagesize
        fw, fh = self.enclosingScrollView().contentView().frame().size
        factor = min(fw / w, fh / h)
        self.zoom = max(self.zoomLevels[0], min(self.zoomLevels[-1], factor))

    def isOpaque(self):
        return False

    def isFlipped(self):
        return True

    ### pasteboard delegate method ###

    def pasteboard_provideDataForType_(self, pboard, type):
        formats = {NSPasteboardTypePDF:"pdf",
                   "com.adobe.encapsulated-postscript":"eps",
                   NSPasteboardTypeTIFF:"tiff"}
        if self.canvas and type in formats:
            img_type = formats[type]
            mag = self.window().backingScaleFactor() if img_type=='tiff' else 1.0
            pboard.setData_forType_(self.canvas._getImageData(img_type, mag), type)

    def mouseDown_(self, event):
        self.mousedown = True

    def mouseUp_(self, event):
        self.mousedown = False

    def keyDown_(self, event):
        self.keydown = True
        self.key = event.characters()
        self.keycode = event.keyCode()

        if self.keycode==KEY_ESC: # stop animating on ESC
            NSApp.sendAction_to_from_('stopScript:', None, self)

    def keyUp_(self, event):
        self.keydown = False
        self.key = event.characters()
        self.keycode = event.keyCode()

    def scrollWheel_(self, event):
        scrollview = self.enclosingScrollView()
        if not (event.modifierFlags() & NSAlternateKeyMask) or self.canvas is None or scrollview is None:
            super(GraphicsView, self).scrollWheel_(event)
            return

        dy = event.scrollingDeltaY()
        factor = 0.004 if event.hasPreciseScrollingDeltas() else 0.05
        step = 1.0 + max(-15.0, min(15.0, dy)) * factor
        if step != 1.0:
            if abs(scrollview.magnification() - 1.0) < 1e-3:
                self._presenter.gesture_began()
            mag = scrollview.magnification() * step
            center = scrollview.contentView().convertPoint_fromView_(event.locationInWindow(), None)
            scrollview.setMagnification_centeredAtPoint_(mag, center)

        if self._zoomApply is not None:
            self._zoomApply.invalidate()
        self._zoomApply = set_timeout(self, 'applyMagnification:', 0.2)

    def applyMagnification_(self, timer):
        self._zoomApply = None
        scrollview = self.enclosingScrollView()
        if scrollview is not None:
            self._applyMagnification(scrollview)

    def canBecomeKeyView(self):
        return True

    def acceptsFirstResponder(self):
        return True


class FullscreenWindow(NSWindow):

    def initWithRect_(self, fullRect):
        super(FullscreenWindow, self).initWithContentRect_styleMask_backing_defer_(fullRect, NSBorderlessWindowMask, NSBackingStoreBuffered, True)
        return self

    def canBecomeKeyWindow(self):
        return True

class FullscreenView(NSView):

    def init(self):
        super(FullscreenView, self).init()
        self.canvas = None
        self.mousedown = False
        self.keydown = False
        self.key = None
        self.keycode = None
        self._mousehide = None
        self._seq = 0  # sequence number of the latest committed frame
        # self.scrollwheel = False
        # self.wheeldelta = 0.0

        self.setLayer_(CALayer.new())
        self.setWantsLayer_(True)
        self.layer().setBackgroundColor_(NSColor.blackColor().CGColor())
        self.layer().setContentsGravity_(kCAGravityResizeAspect)
        inaction = {k:None for k in ["onOrderOut", "sublayers", "contents", "position", "bounds"]}
        self.layer().setActions_(inaction)
        self._presenter = FramePresenter(self.layer())  # what renders and presents the frames it asks for
        return self

    def _get_queue(self):
        return self._presenter.queue

    @objc.python_method
    def _set_queue(self, queue):
        self._presenter.queue = queue
    queue = property(_get_queue, _set_queue)

    @objc.python_method
    def render(self, canvas, focus=None, onerror=None, ondone=None):
        self.canvas = canvas
        if not hasattr(self, "_scalingFactor"):
            cw, ch = self.canvas.pagesize
            sw, sh = NSScreen.mainScreen().frame().size
            self._scalingFactor = min(sw / cw, sh / ch)
        win = self.window()
        dpr = win.backingScaleFactor() if win else NSScreen.mainScreen().backingScaleFactor()
        frame = self._committed = canvas.commit()
        self._seq += 1
        self._presenter.render(frame, self._seq, self._scalingFactor, dpr or 1.0, onerror=onerror, ondone=ondone)

    def updateTrackingAreas(self):
        for area in self.trackingAreas():
            self.removeTrackingArea_(area)
        track = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(),
            (NSTrackingMouseMoved | NSTrackingActiveInKeyWindow),
            self,
            None
        )
        self.addTrackingArea_(track)

    def mouseMoved_(self, event):
        if self._mousehide:
            self._mousehide.invalidate()
        else:
            NSCursor.unhide()
        self._mousehide = set_timeout(self, 'hideMouse:', 1)

    def hideMouse_(self, timer):
        self._mousehide = None
        NSCursor.hide()

    def isFlipped(self):
        return True

    def mouseDown_(self, event):
        self.mousedown = True

    def mouseUp_(self, event):
        self.mousedown = False

    def keyDown_(self, event):
        self.keydown = True
        self.key = event.characters()
        self.keycode = event.keyCode()

        if self.keycode==KEY_ESC: # stop animating on ESC
            NSApp().sendAction_to_from_('stopScript:', None, self)

    def keyUp_(self, event):
        self.keydown = False
        self.key = event.characters()
        self.keycode = event.keyCode()

    # def scrollWheel_(self, event):
    #     self.scrollwheel = True
    #     self.wheeldelta = event.scrollingDeltaY()

    def canBecomeKeyView(self):
        return True

    def acceptsFirstResponder(self):
        return True

