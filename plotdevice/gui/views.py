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
    """Draws a view's frames into PDSurfaces on the window's render thread"""
    DEPTH = FrameQueue.DEPTH + 2 # in-flight frames plus the double-buffered display surfaces
    BACKDROP_SIDE = 2048 # longest side of the low-res preview behind the zoom tiles
    HEADROOM = 1.15 # viewport ring's room to grow
    SHRINK = 0.5    # remade below this share of it

    def __init__(self):
        self._size = None
        self._surfaces = [] # ring of render-targets + on-screen surfaces
        self._onscreen = () # just the on-screen surfaces

    def render(self, frame, scale, cancelled, rect=None):
        """Draw the frame (or rect within it) at the correct density, into the next free surface"""
        if rect is None:
            origin, need = None, frame._raster_size(scale)
            size = need
        else:
            origin, need = rect[:2], tuple(rect[2:])
            ring = self._size or (0, 0)
            fits = need[0] <= ring[0] and need[1] <= ring[1]
            snug = need[0] * need[1] >= self.SHRINK * ring[0] * ring[1]
            if fits and snug:
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

    def render_tiles(self, tiles, coords, cancelled):
        """Draw each tile into its own surface, as (tile, surface) pairs"""
        self._size, self._surfaces = None, [] # the ring is unused while the view is tiled
        rendered = []
        for tile in coords:
            if cancelled():
                break
            x, y, w, h = tiles.rect(tile)
            surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(w, h)
            tiles.frame._render_to_surface(surface, tiles.scale, cancelled, (x, y))
            rendered.append((tile, surface.surface()))
        return rendered

    def render_backdrop(self, frame, cancelled):
        """Draw the whole frame scaled so its longest side is BACKDROP_SIDE pixels"""
        scale = self.BACKDROP_SIDE / max(frame.pagesize)
        surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(*frame._raster_size(scale))
        frame._render_to_surface(surface, scale, cancelled)
        return surface.surface()

    def shown(self, surface):
        """Mark a surface as being display-only (so it won't be drawn to)"""
        self._onscreen = (surface,) + self._onscreen[:1]

class CenteringClipView(NSClipView):
    """Centers small canvases and confines scrolling over large ones"""

    def setFrameSize_(self, size):
        super(CenteringClipView, self).setFrameSize_(size)
        doc = self.documentView()
        if isinstance(doc, GraphicsView):
            doc.fitToViewport()

    def constrainBoundsRect_(self, proposed):
        rect = super(CenteringClipView, self).constrainBoundsRect_(proposed)
        doc = self.documentView()
        if isinstance(doc, GraphicsView) and doc.canvasSize is not None:
            def confine(origin, extent, inset, canvas, document):
                if extent >= canvas: # center if canvas is smaller than the view
                    return inset + (canvas - extent) / 2.0
                if canvas < document: # prevent zooms from targeting margins
                    return min(max(origin, inset), inset + canvas - extent)
                return origin # use AppKit's elastic overshoot behavior

            (ox, oy, cw, ch), (W, H) = doc.canvasRect(), doc.frame().size
            rect.origin.x = confine(rect.origin.x, rect.size.width, ox, cw, W)
            rect.origin.y = confine(rect.origin.y, rect.size.height, oy, ch, H)
        return rect

    def scrollToPoint_(self, point):
        # scrolling needs to apply the bounds-constraint logic manually
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
        # support option-scroll zooming
        doc = self.documentView()
        zooming = bool(event.modifierFlags() & NSAlternateKeyMask)
        zoomable = isinstance(doc, GraphicsView) and doc.canvas is not None
        if zooming and zoomable:
            doc.scrollWheel_(event)
        else:
            super(CenteringClipView, self).scrollWheel_(event)

class FrameTiles(object):
    """A still canvas frame broken into tiles at one zoom and density"""
    TILE_SIDE = 1024     # tile edge, in pixels
    BLEED = 2            # overlap to hide seams
    BUDGET = 4096 * 4096 # frames above this pixel count will be tiled
    CACHE = 256 * 2**20  # bytes of already rendered tiles

    def __init__(self, frame, key):
        self.frame = frame
        _, self.zoom, self.dpr = self.key = key
        self.scale = self.zoom * self.dpr
        self._full = frame._raster_size(self.scale)
        self._holder = None
        self._jobs = {}  # tile -> in-flight RenderJob
        self.layers = {} # tile -> layer, ordered LRU first

    def covering(self, rect):
        """The tiles a pixel rect touches"""
        x, y, w, h = rect
        T, full = self.TILE_SIDE, self._full
        cols = range(max(0, int(x // T)), min(math.ceil(full[0] / T), math.ceil((x + w) / T)))
        rows = range(max(0, int(y // T)), min(math.ceil(full[1] / T), math.ceil((y + h) / T)))
        return [(i, j) for j in rows for i in cols]

    def rect(self, tile):
        """A tile's pixel rect, grown by BLEED within the raster"""
        T, B, full = self.TILE_SIDE, self.BLEED, self._full
        x, y = tile[0] * T, tile[1] * T
        x0, y0 = max(0, x - B), max(0, y - B)
        return (x0, y0, min(full[0], x + T + B) - x0, min(full[1], y + T + B) - y0)

    def add(self, rendered):
        """Display rendered (tile, surface) pairs"""
        dpr = self.dpr
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
        """Put the tiles' layers in `holder`"""
        self._holder = holder

    def detach(self):
        """Forget the tiles' layers"""
        self._holder, self.layers = None, {}

    def delivered(self, tile):
        """A render of `tile` has been delivered"""
        self._jobs.pop(tile, None)

    def request(self, visible, submit):
        """Queue renders for the tiles in view, then those around it"""
        # cancelled jobs are never delivered
        self._jobs = {t: job for t, job in self._jobs.items() if job.pending}

        # prefetch half a viewport around the view
        vx, vy, vw, vh = visible
        mx, my = max(vw / 2, self.TILE_SIDE), max(vh / 2, self.TILE_SIDE)
        margin_rect = (vx - mx, vy - my, vw + 2 * mx, vh + 2 * my)

        # evict the least recently used tiles past CACHE
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
            T = self.TILE_SIDE
            distance = lambda t: (((t[0] + .5) * T - cx) ** 2 + ((t[1] + .5) * T - cy) ** 2)
            tile = min(margin, key=distance)
            self._jobs[tile] = submit(tile)

class FrameLayers(object):
    """The canvas layer that shows a tiled or viewport-only frame, and its sublayers"""

    def __init__(self, root):
        self._root = root           # the view's layer
        self._canvas_layer = None   # the canvas, while tiled or viewport-only
        self._backdrop_layer = None # its bottom layer
        self.viewport_layer = None  # a viewport-only render
        self.tiles = None           # the FrameTiles, if tiled
        self.frame = None           # the frame on display
        self.backdrop = None        # zoom preview's (frame, surface)
        self._rect = None           # canvas rect in the root layer

    def place(self, rect):
        """Keep the canvas layer over the canvas's rect"""
        self._rect = rect
        if self._canvas_layer is not None:
            self._canvas_layer.setFrame_(rect)
            self._backdrop_layer.setFrame_(self._canvas_layer.bounds())

    def clear(self):
        """Stop showing a tiled or viewport-only frame"""
        if self._canvas_layer is None:
            return
        self._canvas_layer.removeFromSuperlayer()
        if self.tiles is not None:
            self.tiles.detach()
        self._canvas_layer = self._backdrop_layer = self.viewport_layer = self.tiles = self.frame = None

    def covers(self, rect):
        """Whether the viewport render covers a rect in points"""
        x, y, w, h = rect
        (lx, ly), (lw, lh) = self.viewport_layer.frame()
        from_start = lx <= x + .5 and ly <= y + .5
        to_end = lx + lw >= x + w - .5 and ly + lh >= y + h - .5
        return from_start and to_end

    def show_backdrop(self, backdrop):
        """Set the zoom preview's backdrop"""
        self.backdrop = backdrop
        if self._backdrop_layer is None:
            return
        if backdrop is None:
            self._backdrop_layer.setContents_(None)
        else:
            frame, surface = backdrop
            if self.viewport_layer is not None or self.frame is frame:
                self._backdrop_layer.setContents_(surface)

    def show_tiles(self, frame, tiles, rendered):
        """Show a FrameTiles' rendered (tile, surface) pairs"""
        if self.tiles is not tiles:
            self._new_canvas_layer(frame)
            tiles.attach(self._canvas_layer)
            self.tiles = tiles
        tiles.add(rendered)

    def show_viewport(self, frame, rect, surface, density):
        """Show a render of the pixel rect in view"""
        if self.viewport_layer is None:
            self._new_canvas_layer(frame)
            self.viewport_layer = CALayer.new()
            self.viewport_layer.setActions_({k:None for k in ["contents", "contentsRect", "contentsScale", "position", "bounds"]})
            self._canvas_layer.addSublayer_(self.viewport_layer)

        # each live frame may change the background
        self.frame = frame
        self._canvas_layer.setBackgroundColor_(self._fill(frame))

        # the render fills just the top-left of its surface, so crop to that and place it over its rect
        x, y, w, h = rect
        used_w, used_h = w / surface.width(), h / surface.height()
        top = 0 if self.viewport_layer.contentsAreFlipped() else 1 - used_h
        self.viewport_layer.setContents_(surface)
        self.viewport_layer.setContentsScale_(density)
        self.viewport_layer.setContentsRect_(((0, top), (used_w, used_h)))
        self.viewport_layer.setFrame_(((x / density, y / density), (w / density, h / density)))

    def _new_canvas_layer(self, frame):
        """Replace what's shown with an empty canvas layer for tiles or a viewport render"""
        self.clear()
        self._root.setContents_(None)
        self.frame = frame

        # tiles and the viewport render are placed from the canvas's top-left, so flip unless the root already is
        self._canvas_layer = CALayer.new()
        self._canvas_layer.setGeometryFlipped_(not self._root.contentsAreFlipped())
        self._canvas_layer.setActions_({k:None for k in ["sublayers", "position", "bounds", "backgroundColor"]})
        self._canvas_layer.setBackgroundColor_(self._fill(frame))
        self._root.addSublayer_(self._canvas_layer)

        # a zoom preview's low-res render goes beneath them
        self._backdrop_layer = CALayer.new()
        self._backdrop_layer.setActions_({k:None for k in ["contents", "position", "bounds"]})
        self._backdrop_layer.setContentsGravity_(kCAGravityResize)
        self._canvas_layer.addSublayer_(self._backdrop_layer)
        self.show_backdrop(self.backdrop)

        if self._rect is not None:
            self.place(self._rect)

    @staticmethod
    def _fill(frame):
        bg = frame.background
        if not isinstance(bg, Color) or bg.alpha < 1:
            return None
        color = bg._rgb if frame.outputmode == RGB else bg._cmyk
        return CGColorCreateCopyByMatchingToColorSpace(CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3), kCGRenderingIntentDefault, color, None)

class FramePresenter(object):
    """Renders a view's frames and presents those still wanted"""

    def __init__(self, root):
        self.queue = None                # the window's FrameQueue
        self.attached = True             # whether the view is in a window
        self.at_export_scale = False     # an export's render at another scale is on display
        self._root = root                # the view's layer
        self._rasterizer = Rasterizer()
        self._tracker = ViewTracker()
        self._layers = FrameLayers(root) # a tiled or viewport-only frame
        self._wanted = None              # (zoom, dpr) last asked for
        self._wanted_mode = None         # and its render mode
        self._shown = (0, None, None)    # (seq, zoom, dpr) on display
        self._period = None              # frame interval while live
        self._zooming = False            # a zoom preview is on screen
        self._in_layout = False          # laying out for a frame being shown
        self._refresh = None             # re-render of the shown frame where the view has moved
        self._export_surfaces = ()       # those on screen

    @property
    def viewport_only(self):
        """Whether just the part of an animation frame in view is shown"""
        return self._layers.viewport_layer is not None or self._wanted_mode == 'viewport'

    def present_export(self, frame, seq, zoom, dpr, work, on_layout=None, onerror=None, fallback=None):
        """Queue an export's job and present its surface as the frame"""
        self._wanted, self._wanted_mode = (zoom, dpr), 'full'
        def deliver(surface, err):
            if err is not None:
                if onerror is not None:
                    onerror(err)
                return

            # the view renders the frame itself if the export's surface can't be shown whole
            unshowable = surface is None or surface.width() * surface.height() > FrameTiles.BUDGET
            if unshowable:
                if fallback is not None:
                    fallback()
                return
            if not self._is_current(seq, zoom, dpr):
                return

            self._shown = (seq, zoom, dpr)
            scale = surface.width() / frame.pagesize.width
            density = scale / zoom
            self._show('full', frame, surface.surface(), density, on_layout)
            # keep the shown surface and the one it replaced, or a movie's buffer pool may reuse them while on screen
            self._export_surfaces = (surface,) + self._export_surfaces[:1]
            self.at_export_scale = abs(scale - zoom * dpr) > 1e-6
        self.queue.submit(work, deliver)

    def render(self, frame, seq, zoom, dpr, period=None, destination=None, on_layout=None, onerror=None, ondone=None):
        """Render a committed frame and present it if still wanted"""
        self._wanted, self._period = (zoom, dpr), period
        width, height = frame._raster_size(zoom * dpr)
        pixels = width * height
        if self._tracker.visible_edges is None:
            # fullscreen, or not yet in a scroll view
            mode = 'full'
        elif period is not None:
            # live frames render just the part in view when the whole is much bigger
            vw, vh = self._tracker.viewport_size
            in_view = vw * vh * dpr ** 2
            mode = 'viewport' if pixels > ViewTracker.RATIO * in_view else 'full'
        else:
            # still frames tile only when too big for memory
            mode = 'tiles' if pixels > FrameTiles.BUDGET else 'full'
        self._wanted_mode = mode
        self._submit(frame, seq, zoom, dpr, mode, destination, on_layout, onerror, ondone)

    def moved(self, visible, canvas_size, viewport_size, magnification):
        """Note where the view is after a scroll, resize, or zoom"""
        self._tracker.moved(visible, canvas_size, viewport_size, magnification)
        self._request_tiles()
        self._refresh_viewport()

    def zoom_started(self):
        """Back a tiled or viewport-only frame with a low-res render for a zoom"""
        self._zooming = True

        # a whole frame needs no backdrop, and one already drawn from this frame is reused
        frame = self._layers.frame
        drawn, _ = self._layers.backdrop or (None, None)
        whole = frame is None
        backed = drawn is frame
        if whole or backed:
            return

        # render it at low res, unless the zoom has ended by the time it arrives
        def work(cancelled):
            return self._rasterizer.render_backdrop(frame, cancelled)
        def deliver(surface, err):
            if err is None and self._zooming:
                self._layers.show_backdrop((frame, surface))
        self.queue.submit(work, deliver)

    def zoom_ended(self):
        """End the zoom preview"""
        self._zooming = False
        if self._layers.viewport_layer is not None:
            self._layers.show_backdrop(None)
        self._request_tiles()

    def place(self, rect):
        """Keep the canvas layer over the canvas's rect"""
        self._layers.place(rect)

    def _is_current(self, seq, zoom, dpr):
        """Whether a render of commit `seq` at (zoom, dpr) should still go on screen"""
        shown_seq, _, _ = self._shown
        return seq >= shown_seq and (zoom, dpr) == self._wanted and self.attached

    def _submit(self, frame, seq, zoom, dpr, mode, destination=None, on_layout=None, onerror=None, ondone=None, refresh=False):
        """Queue a render of the frame in `mode` and return its RenderJob"""
        if mode == 'tiles':
            # the tiles in view (or at its destination) that aren't shown yet
            key = (seq, zoom, dpr)
            tiles = self._layers.tiles
            if tiles is None or tiles.key != key:
                tiles = FrameTiles(frame, key)
            if destination is not None:
                target = [v * dpr for v in destination] # tiles are in pixels
            else:
                target = self._tracker.visible_rect(dpr)
            missing = [t for t in tiles.covering(target) if t not in tiles.layers]
            work = lambda cancelled: (tiles, self._rasterizer.render_tiles(tiles, missing, cancelled))
        elif mode == 'viewport':
            rect, density = self._tracker.plan_render(frame, zoom, dpr, destination, self._period or 0.0)
            scale = zoom * density
            work = lambda cancelled: (rect, self._rasterizer.render(frame, scale, cancelled, rect), density)
        else:
            work = lambda cancelled: self._rasterizer.render(frame, zoom * dpr, cancelled)

        def deliver(result, err):
            if err is None:
                if mode == 'viewport':
                    self._tracker.record_render(job.elapsed, rect[2] * rect[3])
                # a refresh is wanted only over a viewport render
                wanted = not refresh or self._layers.viewport_layer is not None
                if self._is_current(seq, zoom, dpr) and wanted:
                    self._shown = (seq, zoom, dpr)
                    self._export_surfaces, self.at_export_scale = (), False
                    self._show(mode, frame, result, dpr, on_layout)
                    # then fill in whatever the view still lacks
                    if mode == 'tiles':
                        self._request_tiles()
                    elif mode == 'viewport':
                        self._refresh_viewport(just_shown=True)
            elif onerror is not None:
                onerror(err)
            if ondone is not None:
                ondone()

        # deliver reads its job's elapsed time
        job = self.queue.submit(work, deliver)
        return job

    def _request_tiles(self):
        """Queue the renders a tiled frame needs for the part in view"""
        tiles = self._layers.tiles
        untiled = tiles is None
        unplaced = self._tracker.visible_edges is None
        # wait out zoom previews and layouts
        busy = self._zooming or self._in_layout
        if untiled or unplaced or busy:
            return

        # FrameTiles.request picks the tiles, and each delivery asks again until the view is covered
        def submit(tile):
            def work(cancelled):
                return self._rasterizer.render_tiles(tiles, [tile], cancelled)
            def deliver(rendered, err):
                replaced = self._layers.tiles is not tiles
                if replaced:
                    return
                tiles.delivered(tile)
                if err is None and self.attached:
                    tiles.add(rendered)
                    self._request_tiles()
            return self.queue.submit(work, deliver)
        tiles.request(self._tracker.visible_rect(tiles.dpr), submit)

    def _refresh_viewport(self, just_shown=False):
        """Re-render the viewport-only frame if the view has moved past it"""
        seq, zoom, dpr = self._shown
        no_viewport = self._layers.viewport_layer is None
        unplaced = self._tracker.visible_edges is None
        refreshing = self._refresh is not None and self._refresh.pending
        busy = self._in_layout or refreshing
        # a render at the new zoom will replace it anyway
        stale = self._wanted != (zoom, dpr)
        if no_viewport or unplaced or busy or stale:
            return
        # right after a render is shown we can refresh at once, otherwise wait for the render thread to be free
        if not just_shown and not self.queue.ready:
            return

        # only once the view has moved past the render's edges
        visible = self._tracker.visible_rect(1.0)
        _, _, w, h = visible
        empty = w <= 0 or h <= 0
        if empty or self._layers.covers(visible):
            return
        self._refresh = self._submit(self._layers.frame, seq, zoom, dpr, 'viewport', refresh=True)

    def _show(self, mode, frame, result, density, on_layout):
        """Present a delivered render after on_layout()"""
        layers = self._layers

        # clear the tiles or viewport render unless this adds to them (and a whole frame's backdrop)
        same_tiles = mode == 'tiles' and layers.tiles is result[0]
        same_viewport = mode == 'viewport' and layers.viewport_layer is not None
        adding = same_tiles or same_viewport
        if not adding:
            layers.clear()
        if mode == 'full':
            layers.show_backdrop(None)

        # defer moves made while laying out
        self._in_layout = True
        try:
            if on_layout is not None:
                on_layout()
        finally:
            self._in_layout = False

        if mode == 'tiles':
            tiles, rendered = result
            layers.show_tiles(frame, tiles, rendered)
        elif mode == 'viewport':
            rect, surface, viewport_density = result
            layers.show_viewport(frame, rect, surface, viewport_density)
            self._rasterizer.shown(surface)
        else:
            self._root.setContentsScale_(density)
            self._root.setContents_(result)
            self._rasterizer.shown(result)

class ViewTracker(object):
    """Where the view is and how it moves"""
    RATIO = 1.5        # raster/viewport ratio for viewport mode
    START_SPEED = 3000 # max scroll speed, in points/sec
    MARGIN = 0.25      # max margin, as a share of the view
    PREDICT_CAP = 2    # max pixels before the margin, in viewports
    RENDER_CAP = 3     # max lead plus margin, in viewports
    SPEED_WINDOW = .12 # seconds of scrolling an edge's speed is measured over

    def __init__(self):
        self.visible_edges = None   # (x0, y0, x1, y1) in view, in points
        self.canvas_size = None     # in points
        self.viewport_size = None   # in points
        self.magnification = 1.0    # a zoom preview's magnification
        self._recent_edges = []     # (time, edges) within SPEED_WINDOW
        self._avg_render_time = 0.0 # smoothed viewport render time
        self._avg_pixel_time = 0.0  # and per pixel
        self._frame_gap = 0.0       # smoothed time between finished renders
        self._frame_shown = None    # when the last render finished

    def moved(self, visible, canvas_size, viewport_size, magnification):
        """Note the view's visible edges, sizes, and magnification"""
        if visible != self.visible_edges:
            now = time.perf_counter()
            self._recent_edges = [(t, e) for t, e in self._recent_edges if now - t < self.SPEED_WINDOW] + [(now, visible)]
        self.visible_edges, self.canvas_size, self.viewport_size = visible, canvas_size, viewport_size
        self.magnification = magnification

    def record_render(self, elapsed, pixels):
        """Fold a viewport render's time into the averages"""
        now = time.perf_counter()
        self._avg_render_time += .3 * (elapsed - self._avg_render_time)
        self._avg_pixel_time += .3 * (elapsed / pixels - self._avg_pixel_time)
        if self._frame_shown is not None:
            self._frame_gap += .3 * (min(now - self._frame_shown, .5) - self._frame_gap)
        self._frame_shown = now

    def visible_rect(self, scale):
        """The pixel rect at `scale` of the canvas in view"""
        (x0, y0, x1, y1), (cw, ch) = self.visible_edges, self.canvas_size
        x0, y0 = min(max(x0, 0), cw), min(max(y0, 0), ch)
        x1, y1 = max(min(x1, cw), x0), max(min(y1, ch), y0)
        return (x0 * scale, y0 * scale, (x1 - x0) * scale, (y1 - y0) * scale)

    def plan_render(self, frame, zoom, dpr, destination, period):
        """The pixel rect and density for a viewport render"""
        # the view's edges in points, or its destination after a zoom
        moving = destination is None
        if moving:
            x0, y0, x1, y1 = self.visible_edges
        else:
            x0, y0, lw, lh = destination
            x1, y1 = x0 + lw, y0 + lh
        w, h = x1 - x0, y1 - y0
        vw, vh = self.viewport_size
        viewport_pixels = vw * vh * dpr * dpr
        mag = self.magnification

        if moving:
            # each edge's speed over the last ~0.1 s
            now = time.perf_counter()
            recent = [(t, e) for t, e in self._recent_edges if now - t < self.SPEED_WINDOW]
            velocity = (0.0, 0.0, 0.0, 0.0)
            if len(recent) >= 2:
                (t0, before), (t1, after) = recent[0], recent[-1]
                if now - t1 <= .08:
                    velocity = [(b - a) / (t1 - t0) for a, b in zip(before, after)]

            # how far each edge moves before the render is shown, as left, top, right, bottom extensions
            ahead = self._avg_render_time + self._frame_gap
            dx0, dy0, dx1, dy1 = [v * ahead for v in velocity]
            lead = (-min(dx0, 0), -min(dy0, 0), max(dx1, 0), max(dy1, 0))

            # room for a scroll that starts in the meantime, up to MARGIN of the view
            reach = self.START_SPEED * ahead / mag
            margin_x, margin_y = min(reach, self.MARGIN * w), min(reach, self.MARGIN * h)

            # less detail while magnified down or widening, but never more than the current zoom
            future_w = w + dx1 - dx0
            density = dpr * min(1.0, mag * min(1.0, w / max(future_w, 1.0)))
        else:
            lead = (0, 0, 0, 0)
            margin_x = margin_y = 0
            density = dpr

        # trim the lead to PREDICT_CAP viewports, then the margin to what renders in a frame (1 to RENDER_CAP viewports)
        frame_budget = viewport_pixels * max(1.0, min(self.RENDER_CAP, period / max(self._avg_pixel_time * viewport_pixels, 1e-9)))
        margin = (margin_x, margin_y, margin_x, margin_y)
        pixels = lambda lead_share, margin_share: (w + lead_share * (lead[0] + lead[2]) + margin_share * 2 * margin_x) * \
                                                  (h + lead_share * (lead[1] + lead[3]) + margin_share * 2 * margin_y) * density ** 2
        lead_share = 1.0
        while lead_share > 0 and pixels(lead_share, 0) > self.PREDICT_CAP * viewport_pixels:
            lead_share = max(lead_share - .1, 0)
        margin_share = 1.0
        while margin_share > 0 and pixels(lead_share, margin_share) > frame_budget:
            margin_share = max(margin_share - .1, 0)
        left, top, right, bottom = [lead_share * a + margin_share * b for a, b in zip(lead, margin)]

        # and keep the view itself within PREDICT_CAP viewports
        density = min(density, math.sqrt(self.PREDICT_CAP * viewport_pixels / max(w * h, 1.0)))

        # as a pixel rect at zoom * density, clipped to the frame's raster
        full_w, full_h = frame._raster_size(zoom * density)
        x, y = max(int((x0 - left) * density), 0), max(int((y0 - top) * density), 0)
        width = int(math.ceil((x1 + right) * density)) - x
        height = int(math.ceil((y1 + bottom) * density)) - y
        return (x, y, max(min(width, full_w - x), 1), max(min(height, full_h - y), 1)), density

class GraphicsView(NSView):
    script = IBOutlet()
    proofArgs = {} # Canvas.commit args for the proof
    zoomLevels = [0.1, 0.25, 0.5, 0.75] + [float(z) for z in range(1, 21)] # from 10% to 2000%

    ### setup ###

    def initWithFrame_(self, frame):
        # nib loading calls back into the view (scrolls, a backing change) before awakeFromNib
        self = super(GraphicsView, self).initWithFrame_(frame)
        self.canvas = None
        self.canvasSize = None
        self.mousedown = False
        self.keydown = False
        self.key = None
        self.keycode = None
        self._committed = None
        self._copied = None
        self._displayed = False # a frame has been shown
        self._seq = 0           # latest commit's sequence number
        self._dpr = None        # derived from the window once it exists
        self._zoom = 1.0        # default to 100%
        self._zoomTarget = 1.0  # becomes _zoom once shown
        self._zoomApply = None  # applies an Option-scroll zoom once the wheel stops
        self._zoomEnd = None    # ends the zoom preview once its re-render is shown
        # self.scrollwheel = False
        # self.wheeldelta = 0.0

        # set up layer `hosting' and disable implicit anims
        self.setLayer_(CALayer.new())
        self.setWantsLayer_(True)
        self.layer().setContentsGravity_(kCAGravityCenter)
        inaction = {k:None for k in ["onOrderOut", "sublayers", "contents", "contentsScale", "position", "bounds"]}
        self.layer().setActions_(inaction)
        self._presenter = FramePresenter(self.layer())
        return self

    def awakeFromNib(self):
        self._dpr = self.window().backingScaleFactor()
        self.layer().setContentsScale_(self._dpr)

        # display the placeholder image until we're passed a canvas (and keep it in sync with appearance)
        self.updatePlaceholder(NSAppearance.currentDrawingAppearance())

    def _get_queue(self):
        return self._presenter.queue

    @objc.python_method
    def _set_queue(self, queue):
        # set by the ScriptController
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

    ### window ###

    def viewDidMoveToWindow(self):
        super(GraphicsView, self).viewDidMoveToWindow()
        scrollview = self.enclosingScrollView()
        if self.window() is None or scrollview is None:
            return
        # small scrollers, and observers for pinches and for scrolling tiles into view
        scrollview.horizontalScroller().setControlSize_(NSSmallControlSize)
        scrollview.verticalScroller().setControlSize_(NSSmallControlSize)
        scrollview.contentView().setPostsBoundsChangedNotifications_(True)
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "scrollViewDidEndLiveMagnify:",
                                             NSScrollViewDidEndLiveMagnifyNotification, scrollview)
        nc.addObserver_selector_name_object_(self, "scrollViewWillStartLiveMagnify:",
                                             NSScrollViewWillStartLiveMagnifyNotification, scrollview)
        nc.addObserver_selector_name_object_(self, "clipBoundsChanged:",
                                             NSViewBoundsDidChangeNotification, scrollview.contentView())

    def viewWillMoveToWindow_(self, window):
        super(GraphicsView, self).viewWillMoveToWindow_(window)
        # drop renders that finish outside a window
        self._presenter.attached = window is not None
        # drop the observers on teardown
        if window is None:
            if self._zoomApply is not None:
                self._zoomApply.invalidate()
                self._zoomApply = None
            nc = NSNotificationCenter.defaultCenter()
            nc.removeObserver_name_object_(self, NSScrollViewDidEndLiveMagnifyNotification, None)
            nc.removeObserver_name_object_(self, NSScrollViewWillStartLiveMagnifyNotification, None)
            nc.removeObserver_name_object_(self, NSViewBoundsDidChangeNotification, None)

    def viewDidChangeBackingProperties(self):
        # re-render for a display with a different pixel density
        super(GraphicsView, self).viewDidChangeBackingProperties()
        win = self.window()
        if win is None:
            return
        dpr = win.backingScaleFactor()
        if dpr == self._dpr:
            return
        self._dpr = dpr
        self._rerender()

    def isOpaque(self):
        return False

    def isFlipped(self):
        return True

    ### rendering ###

    @objc.python_method
    def render(self, canvas, focus=None, onerror=None, ondone=None):
        """Commit the canvas and have the presenter render it for this view"""
        self.canvas = canvas
        self._committed = canvas.commit(**self.proofArgs)
        self._seq += 1
        self._request(focus, onerror=onerror, ondone=ondone)

    @objc.python_method
    def present(self, frame, work, onerror=None):
        """Show an export job's surface, or render the frame as usual"""
        self._committed = frame
        self._seq += 1
        self._request(onerror=onerror, work=work)

    @objc.python_method
    def liveEnded(self):
        """Re-render a viewport-only or export-scaled frame as a still"""
        if self._presenter.viewport_only or self._presenter.at_export_scale:
            self._rerender()

    @objc.python_method
    def _rerender(self, focus=None, zoom_end=None):
        if self._committed is not None:
            self._request(focus, zoom_end=zoom_end)

    @objc.python_method
    def _request(self, focus=None, onerror=None, ondone=None, zoom_end=None, work=None):
        """Ask the presenter for the committed frame, shown centered on `focus`"""
        frame, seq, zoom, dpr = self._committed, self._seq, self._zoomTarget, self._dpr
        if zoom_end is None:
            # a pending zoom applies when the next frame is shown
            zoom_end = self._zoomEnd
        if not self._displayed:
            # on first draw, tell the presenter where the view is
            self._moved()

        # determine whether the view rect needs to move to reflect zoom or canvas size changes
        scrollview = self.enclosingScrollView()
        canvas_size = tuple(dim * zoom for dim in frame.pagesize)
        zooming = zoom_end is not None or zoom != self._zoom
        resized = canvas_size != tuple(self.canvasSize or ())
        moves = zooming or resized or not self._displayed

        # calculate a target view rect that keeps the same part of the canvas centered at the new size
        target = None
        def centered_on(focus):
            cw, ch = canvas_size
            vw, vh = scrollview.contentView().frame().size
            vw, vh = min(vw, cw), min(vh, ch)
            fx, fy = focus
            # center on `focus` but stay within the canvas's bounds
            return (
              min(max(fx * cw - vw / 2.0, 0), cw - vw),
              min(max(fy * ch - vh / 2.0, 0), ch - vh),
              vw,
              vh
            )
        if moves and scrollview is not None:
            if not self._displayed:
                target = centered_on((0, 0)) # the top-left corner
            else:
                target = centered_on(focus if focus is not None else self._focus())

        # once the render arrives, update the view rect as needed before displaying
        def on_layout():
            if zoom_end is not None:
                zoom_end()

            # keep the current content centered unless a `focus` was provided
            shown = target
            if target is not None and focus is None and self._displayed:
                shown = centered_on(self._focus())

            # choose scroller colors based on the background
            bg = frame.background
            is_dark = bool(isinstance(bg, Color) and bg.brightness <= .5)
            scrollview.setScrollerKnobStyle_(2 if is_dark else 1) # NSScrollerKnobStyleDark/Light

            # reflect the current zoom setting (clamped to the supported range)
            self._zoom = zoom
            self.canvasSize = canvas_size
            self.fitToViewport()
            scrollview.setMinMagnification_(self.zoomLevels[0] / zoom)
            scrollview.setMaxMagnification_(self.zoomLevels[-1] / zoom)

            # scroll to the render's target location
            if shown is not None:
                ox, oy, _, _ = self.canvasRect()
                x, y, _, _ = shown
                self.scrollPoint_((ox + x, oy + y))

            # enable zoom since there's non-placeholder content being displayed now
            scrollview.setAllowsMagnification_(True)
            self._displayed = True

        live = self.script is not None and self.script.live
        period = self.script.framePeriod if live else None
        if work is not None:
            self._presenter.present_export(frame, seq, zoom, dpr, work, on_layout, onerror, self._rerender)
        else:
            self._presenter.render(frame, seq, zoom, dpr, period, target, on_layout, onerror, ondone)

    ### geometry ###

    @objc.python_method
    def canvasRect(self):
        """The canvas's rect within the frame, centered in any margin"""
        W, H = self.frame().size
        cw, ch = self.canvasSize or (W, H)
        return ((W - cw) / 2.0, (H - ch) / 2.0, cw, ch)

    @objc.python_method
    def canvasPoint(self, pt):
        """A point in the view's coordinates, in canvas units"""
        ox, oy, _, _ = self.canvasRect()
        return ((pt[0] - ox) / self._zoom, (pt[1] - oy) / self._zoom)

    @objc.python_method
    def fitToViewport(self):
        """Size the frame to the larger of the canvas and the viewport"""
        if self.canvasSize is None:
            return
        cw, ch = self.canvasSize
        scrollview = self.enclosingScrollView()
        if scrollview is None:
            w, h = cw, ch
        else:
            # bounds shrink during a zoom preview
            vw, vh = scrollview.contentView().frame().size
            w, h = max(cw, vw), max(ch, vh)
            scrollview.setHorizontalScrollElasticity_(NSScrollElasticityAllowed if cw > vw else NSScrollElasticityNone)
            scrollview.setVerticalScrollElasticity_(NSScrollElasticityAllowed if ch > vh else NSScrollElasticityNone)
        if (w, h) != tuple(self.frame().size):
            self.setFrameSize_((w, h))
        # keep the canvas layer over the canvas
        ox, oy, cw, ch = self.canvasRect()
        if not self.layer().contentsAreFlipped():
            oy = self.frame().size.height - oy - ch
        self._presenter.place(((ox, oy), (cw, ch)))
        self._moved()

    @objc.python_method
    def _focus(self):
        # the canvas point at the viewport's center
        if self.canvasSize is None:
            return (0.5, 0.5)
        vis = self.enclosingScrollView().documentVisibleRect()
        ox, oy, cw, ch = self.canvasRect()
        clamp = lambda v: max(0.0, min(1.0, v))
        return (clamp((NSMidX(vis) - ox) / cw), clamp((NSMidY(vis) - oy) / ch))

    @objc.python_method
    def _moved(self):
        scrollview = self.enclosingScrollView()
        if scrollview:
            (vx, vy), (vw, vh) = scrollview.documentVisibleRect()
            ox, oy, cw, ch = self.canvasRect()
            visible = (vx - ox, vy - oy, vx - ox + vw, vy - oy + vh)
            # bounds shrink during a zoom preview
            viewport_size = tuple(scrollview.contentView().frame().size)
            self._presenter.moved(visible, (cw, ch), viewport_size, scrollview.magnification())

    def clipBoundsChanged_(self, note):
        self._moved()

    ### zooming ###

    def _get_zoom(self):
        return self._zoom

    @objc.python_method
    def _set_zoom(self, zoom):
        # _zoom changes once the re-render is shown
        self._zoomTarget = zoom
        self._rerender()
    zoom = property(_get_zoom, _set_zoom)

    @IBAction
    def zoomIn_(self, sender):
        # the next level up, or the highest
        idx = bisect.bisect_right(self.zoomLevels, self.zoom)
        self.zoom = self.zoomLevels[min(idx, len(self.zoomLevels) - 1)]

    @IBAction
    def zoomOut_(self, sender):
        # the next level down, or the lowest
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
        # stay within the zoom levels
        self.zoom = max(self.zoomLevels[0], min(self.zoomLevels[-1], factor))

    def scrollViewWillStartLiveMagnify_(self, note):
        self._presenter.zoom_started()

    def scrollWheel_(self, event):
        # Option-scroll magnifies like a pinch
        scrollview = self.enclosingScrollView()
        zooming = bool(event.modifierFlags() & NSAlternateKeyMask)
        zoomable = self.canvas is not None and scrollview is not None
        if not (zooming and zoomable):
            super(GraphicsView, self).scrollWheel_(event)
            return

        # make wheel ticks and trackpad deltas feel alike
        dy = event.scrollingDeltaY()
        factor = 0.004 if event.hasPreciseScrollingDeltas() else 0.05
        step = 1.0 + max(-15.0, min(15.0, dy)) * factor
        if step != 1.0:
            if abs(scrollview.magnification() - 1.0) < 1e-3:
                self._presenter.zoom_started()
            mag = scrollview.magnification() * step
            center = scrollview.contentView().convertPoint_fromView_(event.locationInWindow(), None)
            scrollview.setMagnification_centeredAtPoint_(mag, center)

        if self._zoomApply is not None:
            self._zoomApply.invalidate()
        self._zoomApply = set_timeout(self, 'applyMagnification:', 0.2)

    def scrollViewDidEndLiveMagnify_(self, note):
        # trackpad pinch gesture settled
        self.applyMagnification_(note)

    def applyMagnification_(self, sender):
        # update the magnification during a scroll/pinch zoom then re-render once it settles
        if self._zoomApply is not None:
            self._zoomApply.invalidate()
            self._zoomApply = None
        scrollview = self.enclosingScrollView()
        if scrollview is None:
            return
        mag = scrollview.magnification()
        if abs(mag - 1.0) < 1e-3:
            self._presenter.zoom_ended()
            return
        # keep what's centered now
        focus = self._focus()
        target = self._zoom * mag
        target = max(self.zoomLevels[0], min(self.zoomLevels[-1], target))
        # keep the preview up until the re-render is shown
        self._zoomTarget = target
        def zoom_end():
            if self._zoomEnd is not zoom_end:
                return  # already folded in or replaced
            self._zoomEnd = None
            scrollview.setMagnification_(scrollview.magnification() / mag)
            self._presenter.zoom_ended()
        self._zoomEnd = zoom_end
        self._rerender(focus=focus, zoom_end=zoom_end)

    ### pasteboard ###

    @IBAction
    def copyImageAsPDF_(self, sender):
        """Put the latest frame on the pasteboard, without any proof"""
        self._copied = self._committed
        if self.proofArgs and self.canvas is not None:
            self._copied = self.canvas.commit()
        if self._copied is not None:
            pboard = NSPasteboard.generalPasteboard()
            pboard.declareTypes_owner_([NSPasteboardTypePDF, NSPasteboardTypeTIFF], self)

    def pasteboard_provideDataForType_(self, pboard, type):
        formats = {NSPasteboardTypePDF:"pdf",
                   NSPasteboardTypeTIFF:"tiff"}
        frame = self._copied
        if frame is not None and type in formats:
            img_type = formats[type]
            # the window may have closed since the copy
            screen = self.window() or NSScreen.mainScreen()
            mag = screen.backingScaleFactor() if img_type=='tiff' else 1.0
            pboard.setData_forType_(frame._getImageData(img_type, mag), type)

    ### event handling ###

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
    proofArgs = {} # proof when Run Fullscreen began

    def init(self):
        super(FullscreenView, self).init()
        self.canvas = None
        self.mousedown = False
        self.keydown = False
        self.key = None
        self.keycode = None
        self._mousehide = None
        self._scalingFactor = None
        self._seq = 0  # latest commit's sequence number
        # self.scrollwheel = False
        # self.wheeldelta = 0.0

        # letterboxed against black
        self.setLayer_(CALayer.new())
        self.setWantsLayer_(True)
        self.layer().setBackgroundColor_(NSColor.blackColor().CGColor())
        self.layer().setContentsGravity_(kCAGravityResizeAspect)
        inaction = {k:None for k in ["onOrderOut", "sublayers", "contents", "position", "bounds"]}
        self.layer().setActions_(inaction)
        self._presenter = FramePresenter(self.layer())
        return self

    def _get_queue(self):
        return self._presenter.queue

    @objc.python_method
    def _set_queue(self, queue):
        # set by the ScriptController
        self._presenter.queue = queue
    queue = property(_get_queue, _set_queue)

    @objc.python_method
    def render(self, canvas, focus=None, onerror=None, ondone=None):
        """Commit the canvas and have the presenter render it whole"""
        self.canvas = canvas
        if self._scalingFactor is None:
            cw, ch = self.canvas.pagesize
            sw, sh = NSScreen.mainScreen().frame().size
            self._scalingFactor = min(sw / cw, sh / ch)
        win = self.window()
        dpr = win.backingScaleFactor() if win else NSScreen.mainScreen().backingScaleFactor()
        frame = canvas.commit(**self.proofArgs)
        self._seq += 1
        self._presenter.render(frame, self._seq, self._scalingFactor, dpr, onerror=onerror, ondone=ondone)

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
