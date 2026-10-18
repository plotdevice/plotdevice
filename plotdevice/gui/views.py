# encoding: utf-8
import sys
import os
import bisect
import traceback
import objc

from . import set_timeout, FrameQueue
from ..lib.cocoa import *
from ..gfx.colors import Color
from ..gfx.atoms import KEY_ESC
from objc import super

class Rasterizer(object):
    DEPTH = FrameQueue.DEPTH + 2

    def __init__(self):
        self._size = None
        self._surfaces = []
        self._onscreen = ()  # the surface on screen and the one it replaced

    def render(self, frame, scale, cancelled=None):
        size = frame._raster_size(scale)
        if size != self._size:
            PDSurface = objc.lookUpClass('PDSurface')
            self._size = size
            self._surfaces = [PDSurface.surfaceWithWidth_height_(*size) for _ in range(self.DEPTH)]
        surface = next(s for s in self._surfaces if s.surface() not in self._onscreen)
        self._surfaces.remove(surface)
        self._surfaces.append(surface)
        frame._render_to_surface(surface, scale, cancelled)
        return surface.surface()

    def shown(self, surface):
        self._onscreen = (surface,) + self._onscreen[:1]

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

class FramePresenter(object):

    def __init__(self, root):
        self.queue = None              # the window's FrameQueue (set through the view)
        self.attached = True           # whether the view is in a window (renders landing while it isn't are dropped)
        self._root = root              # the view's layer
        self._raster = Rasterizer()    # what draws the renders it presents
        self._wanted = None            # (zoom, dpr) of the latest frame asked for
        self._shown = (0, None, None)  # (seq, zoom, dpr) of the frame on display

    def render(self, frame, seq, zoom, dpr, on_land=None, onerror=None, ondone=None):
        self._wanted = (zoom, dpr)
        self._submit(frame, seq, zoom, dpr, on_land, onerror, ondone)

    def _submit(self, frame, seq, zoom, dpr, on_land=None, onerror=None, ondone=None):
        work = lambda raster, cancelled: raster.render(frame, zoom * dpr, cancelled)

        def deliver(result, err):
            if err is not None:
                if onerror is not None:
                    onerror(err)
            else:
                current = seq >= self._shown[0] and (zoom, dpr) == self._wanted and self.attached
                if current:
                    self._shown = (seq, zoom, dpr)
                    if on_land is not None:
                        on_land()
                    self._present(result, dpr)
            if ondone is not None:
                ondone()
        self._job(work, deliver)

    def _job(self, work, deliver):
        raster = self._raster
        self.queue.submit(lambda cancelled: work(raster, cancelled), deliver)

    def _present(self, surface, dpr):
        self._root.setContentsScale_(dpr)
        self._root.setContents_(surface)
        self._raster.shown(surface)

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
        def on_land():
            if finish is not None:
                finish()
            self._zoom = zoom
            self._land(frame, focus)
        self._presenter.render(frame, seq, zoom, dpr, on_land=on_land, onerror=onerror, ondone=ondone)

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
        self._magnifyReady = True

    @objc.python_method
    def _applyMagnification(self, scrollview):
        mag = scrollview.magnification()
        if abs(mag - 1.0) < 1e-3:
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

