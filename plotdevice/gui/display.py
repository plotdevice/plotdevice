# encoding: utf-8
import sys
import math
import time
import queue
import threading
import objc
from Foundation import NSRunLoop, NSRunLoopCommonModes
from PyObjCTools import AppHelper
from AppKit import (NSApplication, NSDate, NSEventMaskAny,
                    NSEventMaskMouseMoved, NSEventMaskMouseEntered, NSEventMaskMouseExited,
                    NSEventMaskCursorUpdate, NSEventMaskPeriodic, NSEventMaskAppKitDefined,
                    NSEventMaskSystemDefined, NSEventMaskApplicationDefined)
from Quartz import CACurrentMediaTime
from . import set_timeout
from .. import free_threaded
from ..util import autorelease
from ..lib.cocoa import *
from ..gfx.colors import Color, RGB

class FrameClock:
    """Triggers a selector at a target FPS, synced to the display"""

    MIN_IDLE = 0.001 # run-loop time between overruns

    # input worth holding a late frame for
    INPUT = NSEventMaskAny & ~(NSEventMaskMouseMoved | NSEventMaskMouseEntered | NSEventMaskMouseExited
                              | NSEventMaskCursorUpdate | NSEventMaskPeriodic | NSEventMaskAppKitDefined
                              | NSEventMaskSystemDefined | NSEventMaskApplicationDefined)

    def __init__(self, view, target, sel, fps):
        self._link = self._timer = self._restart = self._restart_at = None
        self._target, self._sel = target, sel
        self._rate = float(fps)
        self._period = 1.0 / fps
        self._credit = 1.0       # frames owed, starting at one
        self._tick = None        # when credit was last updated
        self._refresh = 1.0 / 60 # display refresh (measured below)
        self._started = None     # when the in-flight draw began
        self._last = None        # when the last draw finished
        self._gap = None         # smoothed time between frames
        self._due = None         # next due time, for NSTimer
        if view is not None and hasattr(view, 'displayLinkWithTarget_selector_'):
            # should_draw() downsamples vblanks
            link = view.displayLinkWithTarget_selector_(target, sel)
            link.addToRunLoop_forMode_(NSRunLoop.mainRunLoop(), NSRunLoopCommonModes)
            self._link = link
        else:
            self._timer = set_timeout(target, sel, self._period, repeat=True)

    def should_draw(self, delivered=False):
        """True when a frame is due and the run loop has had its turn"""
        now = CACurrentMediaTime()
        if not self.isValid():
            return False # paused or stopped
        if self._started is not None:
            return False # re-entered mid-frame
        fired = self._restart is not None and now >= self._restart_at - 1e-5
        if fired:
            self._restart = None # forget the expired restart timer
        if self._link is None:
            # within a quarter period, for jitter
            if self._due is not None and now < self._due - 0.25 * self._period:
                return False
            # the next is due a period later
            scheduled = now if self._due is None else self._due
            self._due = max(scheduled, now - self._period) + self._period
            self._started = now
            return True
        t = self._link.timestamp()
        vblank = self._link.targetTimestamp() - t
        if vblank > 0:
            self._refresh = vblank

        # frames owed, by the clock
        if self._tick is not None:
            self._credit += self._rate * (now - self._tick)
        self._tick = now

        # a frame is due on the vblank closest to when it's owed, not the first one after
        slack = 0.0 if delivered else 0.5 * min(1.0, self._rate * self._refresh)
        if self._credit < 1.0 - slack:
            return False
        if self._last is not None and now < self._last + self.MIN_IDLE - 1e-5:
            # due, but let the run loop breathe first
            self._schedule_restart(now, self._last + self.MIN_IDLE)
            return False
        if self._gap is not None and self._gap > self._period and self._input_pending():
            # let lagging frames yield to input
            self._schedule_restart(now, now + self.MIN_IDLE)
            return False
        if self._restart is not None:
            # a vblank beat a pending restart to the punch
            self._restart.invalidate()
            self._restart = None
        self._credit = min(self._credit - 1.0, 1.0)
        self._started = now
        return True

    def _schedule_restart(self, now, at):
        if self._restart is None:
            self._restart_at = at
            self._restart = set_timeout(self._target, self._sel, max(0.0, at - now))

    def _input_pending(self):
        """Whether the user has keyboard/mouse events waiting in the queue"""
        app = NSApplication.sharedApplication()
        probe = app.nextEventMatchingMask_untilDate_inMode_dequeue_(self.INPUT, NSDate.distantPast(), 'PlotDeviceFrameClockPeek', False)
        return probe is not None

    def frame_done(self):
        """Fold the finished draw into the pacing stats"""
        now = CACurrentMediaTime()
        ema = lambda old, new: new if old is None else old + 0.2 * (new - old)
        drew = None if self._started is None else now - self._started
        if self._last is not None:
            self._gap = ema(self._gap, now - self._last)
        self._last = now
        self._started = None

        if self._link is not None and drew is not None and drew >= self._period:
            self._schedule_restart(now, now + self.MIN_IDLE)

    @property
    def period(self):
        """The time between frames at the requested fps"""
        return self._period

    def isValid(self):
        return (self._link is not None) or bool(self._timer and self._timer.isValid())

    def invalidate(self):
        if self._restart is not None:
            self._restart.invalidate()
            self._restart = None
        if self._link is not None:
            self._link.invalidate()      # also removes it from the run loop
            self._link = None
        elif self._timer is not None:
            self._timer.invalidate()
            self._timer = None

class RenderJob:
    """A job submitted to a FrameQueue"""

    def __init__(self, queue):
        self._queue = queue
        self._generation = queue._generation
        self._delivered = False
        self.elapsed = None # how long its work took

    @property
    def cancelled(self):
        """Whether the queue's cancel() has dropped it"""
        return self._generation <= self._queue._cancelled

    @property
    def pending(self):
        """Whether it's neither delivered nor cancelled"""
        return not self._delivered and not self.cancelled

class FrameQueue:
    """Renders a window's committed Frames on the render thread"""

    # if the GIL is disabled, allow drawing and rendering to overlap
    DEPTH = 2 if free_threaded and not sys._is_gil_enabled() else 1

    def __init__(self):
        self._jobs = queue.Queue()
        self._generation = 0 # from the latest submission
        self._cancelled = 0  # dropped up to this generation
        self._pending = 0    # not yet delivered
        self._thread = threading.Thread(target=self._loop, daemon=True, name='frame-queue')
        self._thread.start()

    @property
    def idle(self):
        """Whether every job submitted has been delivered"""
        return self._pending == 0

    @property
    def ready(self):
        """Whether another frame fits in the pipeline"""
        return self._pending < self.DEPTH

    def submit(self, work, deliver):
        """Queue work for the render thread and return its RenderJob"""
        self._generation += 1
        self._pending += 1
        job = RenderJob(self)
        self._jobs.put((job, work, deliver))
        return job

    def cancel(self):
        """Drop every job submitted so far"""
        self._cancelled = self._generation

    def shutdown(self):
        """Cancel outstanding work and end the thread"""
        self.cancel()
        self._jobs.put(None)
        self._thread.join(1.0)

    def _loop(self):
        while True:
            with autorelease():
                item = self._jobs.get()
                if item is None:
                    return
                job, work, deliver = item
                cancelled = lambda: job.cancelled
                result = err = None
                if not cancelled():
                    try:
                        started = time.perf_counter()
                        result = work(cancelled)
                        job.elapsed = time.perf_counter() - started
                    except Exception as e:
                        err = e
                AppHelper.callAfter(self._deliver, job, deliver, result, err)
                del item, job, work, deliver, result, err, cancelled

    def _deliver(self, job, deliver, result, err):
        self._pending -= 1
        if not job.cancelled:
            deliver(result, err)
        job._delivered = True

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
        color = bg._rgb if frame.output.mode == RGB else bg._cmyk
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
