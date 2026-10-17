# encoding: utf-8
import sys
import os
import traceback
import objc

from . import set_timeout, FrameRenderer
from ..lib.cocoa import *
from ..gfx import Color
from ..gfx.atoms import KEY_ESC
from objc import super

class SurfaceRing(object):
    DEPTH = FrameRenderer.DEPTH + 2

    def __init__(self, width, height):
        PDSurface = objc.lookUpClass('PDSurface')
        self.size = (width, height)
        self._surfaces = [PDSurface.surfaceWithWidth_height_(width, height) for _ in range(self.DEPTH)]

    def render(self, frame, scale, cancelled=None, onscreen=()):
        surface = next(s for s in self._surfaces if s.surface() not in onscreen)
        self._surfaces.remove(surface)
        self._surfaces.append(surface)
        frame._render_to_surface(surface, scale, cancelled)
        return surface.surface()

def _rendered(view, frame, scale, cancelled=None):
    width, height = [max(int(dim * scale), 1) for dim in frame.pagesize]
    ring = getattr(view, '_ring', None)
    if ring is None or ring.size != (width, height):
        ring = view._ring = SurfaceRing(width, height)
    return ring.render(frame, scale, cancelled, onscreen=getattr(view, '_onscreen', ()))

def _show(view, surface):
    view.layer().setContents_(surface)
    view._onscreen = (surface,) + getattr(view, '_onscreen', ())[:1]

DARK_GREY = NSColor.blackColor().blendedColorWithFraction_ofColor_(0.7, NSColor.whiteColor())

def _confine(origin, extent, inset, canvas, document):
    if extent >= canvas:
        return inset + (canvas - extent) / 2.0
    if canvas < document:
        return min(max(origin, inset), inset + canvas - extent)
    return origin

class CenteringClipView(NSClipView):

    def awakeFromNib(self):
        scrollview = self.enclosingScrollView()
        if scrollview is not None:
            scrollview.setWantsLayer_(True)

    def setFrameSize_(self, size):
        super(CenteringClipView, self).setFrameSize_(size)
        doc = self.documentView()
        if isinstance(doc, GraphicsView):
            doc._fitToViewport()

    def constrainBoundsRect_(self, proposed):
        rect = super(CenteringClipView, self).constrainBoundsRect_(proposed)
        doc = self.documentView()
        if isinstance(doc, GraphicsView) and doc._canvasSize is not None:
            (ox, oy, cw, ch), (W, H) = doc._canvasRect(), doc.frame().size
            rect.origin.x = _confine(rect.origin.x, rect.size.width, ox, cw, W)
            rect.origin.y = _confine(rect.origin.y, rect.size.height, oy, ch, H)
        return rect

    def scrollToPoint_(self, point):
        doc = self.documentView()
        if isinstance(doc, GraphicsView) and doc._canvasSize is not None:
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

class GraphicsView(NSView):
    renderer = None # the window's FrameRenderer, set by the ScriptController that owns the view
    script = IBOutlet()
    canvas = None
    _canvasSize = None # the canvas at the displayed zoom, in points (class-level: the clip view may ask before awakeFromNib)

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
        self._seq = self._shownSeq = 0  # sequence number of the latest committed / displayed frame
        self._dpr = self.window().backingScaleFactor()
        self._magnifyReady = False
        self._zoomApply = None
        # self.scrollwheel = False
        # self.wheeldelta = 0.0

        # set up layer `hosting' and disable implicit anims
        self.setLayer_(CALayer.new())
        self.setWantsLayer_(True)
        self.layer().setContentsGravity_(kCAGravityCenter)
        self.layer().setContentsScale_(self._dpr)
        inaction = {k:None for k in ["onOrderOut", "sublayers", "contents", "contentsScale", "position", "bounds"]}
        self.layer().setActions_(inaction)

        # display the placeholder image until we're passed a canvas (and keep it in sync with appearance)
        self.updatePlaceholder(NSAppearance.currentDrawingAppearance())

    @objc.python_method
    def updatePlaceholder(self, appearance):
        if self.canvas is None:
            placeholder = NSImage.imageNamed_('placeholder-{mode}.pdf'.format(
                mode = 'dark' if 'Dark' in appearance.name() else 'light'
            ))
            if placeholder:
                self._canvasSize = tuple(placeholder.size())
                self._fitToViewport()
                self.layer().setContents_(placeholder)

    @objc.python_method
    def render(self, canvas, focus=None, onerror=None, ondone=None):
        self.canvas = canvas
        self._committed = canvas.commit()
        self._seq += 1
        self._submit(focus, onerror=onerror, ondone=ondone)

    @objc.python_method
    def rerender(self, focus=None, finish=None):
        if getattr(self, '_committed', None) is not None:
            self._submit(focus, finish=finish)

    @objc.python_method
    def _submit(self, focus=None, onerror=None, ondone=None, finish=None):
        frame, seq, zoom, dpr = self._committed, self._seq, self._wantZoom, self._dpr
        def work(cancelled):
            return _rendered(self, frame, zoom * dpr, cancelled)
        def deliver(surface, err):
            if err is not None:
                if onerror is not None:
                    onerror(err)
            elif seq >= self._shownSeq and (zoom, dpr) == (self._wantZoom, self._dpr) and self.window() is not None:
                if finish is not None:
                    finish()
                self._zoom = zoom
                self._shownSeq = seq
                self._applyFrame(frame, surface, focus)
            if ondone is not None:
                ondone()
        self.renderer.submit(work, deliver)

    @objc.python_method
    def _applyFrame(self, frame, surface, focus=None):
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
        resized, self._canvasSize = size != self._canvasSize, size
        self._fitToViewport()

        if self._magnifyReady:
            scrollview.setMinMagnification_(self.zoomLevels[0] / self._zoom)
            scrollview.setMaxMagnification_(self.zoomLevels[-1] / self._zoom)

        if not self._displayed:
            # draw from top-left corner if first-run
            self.scrollPoint_( (0,0) )
            self._displayed = True
        elif focused or resized:
            vw, vh = scrollview.contentView().bounds().size
            ox, oy, w, h = self._canvasRect()
            self.scrollPoint_( (ox + focus[0]*w - vw/2.0, oy + focus[1]*h - vh/2.0) )

        self.layer().setContentsScale_(self._dpr)
        _show(self, surface)

    @objc.python_method
    def _canvasRect(self):
        W, H = self.frame().size
        cw, ch = self._canvasSize or (W, H)
        return ((W - cw) / 2.0, (H - ch) / 2.0, cw, ch)

    @objc.python_method
    def _fitToViewport(self):
        if self._canvasSize is None:
            return
        cw, ch = self._canvasSize
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
        if self._canvasSize is None:
            return (0.5, 0.5)
        vis = self.enclosingScrollView().documentVisibleRect()
        ox, oy, cw, ch = self._canvasRect()
        clamp = lambda v: max(0.0, min(1.0, v))
        return (clamp((NSMidX(vis) - ox) / cw), clamp((NSMidY(vis) - oy) / ch))

    @objc.python_method
    def canvasPoint(self, pt):
        """A point in the view's coordinates, in canvas units"""
        ox, oy, _, _ = self._canvasRect()
        return ((pt[0] - ox) / self._zoom, (pt[1] - oy) / self._zoom)

    def _get_zoom(self):
        return self._zoom

    @objc.python_method
    def _set_zoom(self, zoom):
        self._wantZoom = zoom
        self.rerender()
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
        self.rerender(focus=focus, finish=lambda: scrollview.setMagnification_(scrollview.magnification() / mag))

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
        self.rerender()

    def viewWillMoveToWindow_(self, window):
        super(GraphicsView, self).viewWillMoveToWindow_(window)
        if window is None:
            if self._zoomApply is not None:
                self._zoomApply.invalidate()
                self._zoomApply = None
            if self._magnifyReady:
                nc = NSNotificationCenter.defaultCenter()
                nc.removeObserver_name_object_(self, NSScrollViewDidEndLiveMagnifyNotification, None)
                self._magnifyReady = False

    @objc.python_method
    def findNearestZoomIndex(self, zoom):
        """Returns the nearest zoom level, and whether we found a direct, exact
        match or a fuzzy match."""
        try: # Search for a direct hit first.
            idx = self.zoomLevels.index(zoom)
            return idx, True
        except ValueError: # Can't find the zoom level, try looking at the indexes.
            idx = 0
            try:
                while self.zoomLevels[idx] < zoom:
                    idx += 1
            except KeyError: # End of the list
                idx = len(self.zoomLevels) - 1 # Just return the last index.
            return idx, False

    @IBAction
    def zoomIn_(self, sender):
        idx, direct = self.findNearestZoomIndex(self.zoom)
        # Direct hits are perfect, but indirect hits require a bit of help.
        # Because of the way indirect hits are calculated, they are already
        # rounded up to the upper zoom level; this means we don't need to add 1.
        if direct:
            idx += 1
        idx = max(min(idx, len(self.zoomLevels)-1), 0)
        self.zoom = self.zoomLevels[idx]

    @IBAction
    def zoomOut_(self, sender):
        idx, direct = self.findNearestZoomIndex(self.zoom)
        idx -= 1
        idx = max(min(idx, len(self.zoomLevels)-1), 0)
        self.zoom = self.zoomLevels[idx]

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
        self.zoom = factor

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
    renderer = None # the window's FrameRenderer, set by the ScriptController that owns the view

    def init(self):
        super(FullscreenView, self).init()
        self.canvas = None
        self.mousedown = False
        self.keydown = False
        self.key = None
        self.keycode = None
        self.mousehide = None
        self._seq = self._shownSeq = 0  # sequence number of the latest committed / displayed frame
        # self.scrollwheel = False
        # self.wheeldelta = 0.0

        self.setLayer_(CALayer.new())
        self.setWantsLayer_(True)
        self.layer().setBackgroundColor_(NSColor.blackColor().CGColor())
        self.layer().setContentsGravity_(kCAGravityResizeAspect)
        inaction = {k:None for k in ["onOrderOut", "sublayers", "contents", "position", "bounds"]}
        self.layer().setActions_(inaction)
        return self

    @objc.python_method
    def render(self, canvas, focus=None, onerror=None, ondone=None):
        self.canvas = canvas
        if not hasattr(self, "screenRect"):
            self.screenRect = NSScreen.mainScreen().frame()
            cw, ch = self.canvas.pagesize
            sw, sh = self.screenRect[1]
            self.scalingFactor = calc_scaling_factor(cw, ch, sw, sh)
            nw, nh = cw * self.scalingFactor, ch * self.scalingFactor
            self.scaledSize = nw, nh
            self.dx = (sw - nw) / 2.0
            self.dy = (sh - nh) / 2.0
        win = self.window()
        dpr = win.backingScaleFactor() if win else NSScreen.mainScreen().backingScaleFactor()
        frame = self._committed = canvas.commit()
        self._seq += 1
        seq = self._seq
        scale = self.scalingFactor * (dpr or 1.0)
        def work(cancelled):
            return _rendered(self, frame, scale, cancelled)
        def deliver(surface, err):
            if err is not None:
                if onerror is not None:
                    onerror(err)
            elif seq >= self._shownSeq:
                self._shownSeq = seq
                _show(self, surface)
            if ondone is not None:
                ondone()
        self.renderer.submit(work, deliver)

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
        if self.mousehide:
            self.mousehide.invalidate()
        else:
            NSCursor.unhide()
        self.mousehide = set_timeout(self, 'hideMouse:', 1)

    def hideMouse_(self, timer):
        self.mousehide = None
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

def calc_scaling_factor(width, height, maxwidth, maxheight):
    return min(float(maxwidth) / width, float(maxheight) / height)

