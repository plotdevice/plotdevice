# encoding: utf-8
import sys
import os
import math
import bisect
import time
import traceback
import objc

from . import set_timeout, FrameQueue
from .display import FramePresenter
from ..lib.cocoa import *
from ..gfx.colors import Color, RGB
from ..gfx.atoms import KEY_ESC
from objc import super

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

class GraphicsView(NSView):
    script = IBOutlet()
    proof = None # the View > Proof Colors setting
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
        self._committed = canvas.commit(proof=self.proof)
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
        if self.proof is not None and self.canvas is not None:
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
    proof = None # proof when Run Fullscreen began

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
        frame = canvas.commit(proof=self.proof)
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
