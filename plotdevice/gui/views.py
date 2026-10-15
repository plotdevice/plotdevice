# encoding: utf-8
import sys
import os
import traceback
import objc

from . import set_timeout
from ..lib.cocoa import *
from ..gfx import Color
from ..gfx.atoms import KEY_ESC
from objc import super

DARK_GREY = NSColor.blackColor().blendedColorWithFraction_ofColor_(0.7, NSColor.whiteColor())

class CenteringClipView(NSClipView):

    def constrainBoundsRect_(self, proposed):
        rect = super(CenteringClipView, self).constrainBoundsRect_(proposed)
        doc = self.documentView()
        if doc is not None:
            d = doc.frame().size
            if rect.size.width > d.width:
                rect.origin.x = (d.width - rect.size.width) / 2.0
            if rect.size.height > d.height:
                rect.origin.y = (d.height - rect.size.height) / 2.0
        return rect

    def scrollWheel_(self, event):
        doc = self.documentView()
        if (event.modifierFlags() & NSAlternateKeyMask) and isinstance(doc, GraphicsView) and doc.canvas is not None:
            doc.scrollWheel_(event)
        else:
            super(CenteringClipView, self).scrollWheel_(event)

class GraphicsView(NSView):
    script = IBOutlet()
    canvas = None

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
        self._dpr = self.window().backingScaleFactor()
        self._magnifyReady = False
        self._zoomApply = None
        # self.scrollwheel = False
        # self.wheeldelta = 0.0

        # set up layer `hosting' and disable implicit anims
        self.setLayer_(CALayer.new())
        self.setWantsLayer_(True)
        inaction = {k:None for k in ["onOrderOut", "sublayers", "contents", "position", "bounds"]}
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
                self.setFrameSize_(placeholder.size())
                self.layer().setContents_(placeholder)

    @objc.python_method
    def setCanvas(self, canvas, focus=None):
        # set the scroller color based on the background
        bg = canvas.background
        is_dark = bool(isinstance(bg, Color) and bg.brightness <= .5)
        scrollview = self.enclosingScrollView()
        scrollview.setScrollerKnobStyle_(2 if is_dark else 1) # NSScrollerKnobStyleDark/Light

        self._configureMagnification(scrollview)

        if focus is None:
            visible = scrollview.documentVisibleRect()
            oldframe = self.frame()
            focus = (NSMidX(visible) / NSWidth(oldframe), NSMidY(visible) / NSHeight(oldframe))

        # render (and possibly bomb...)
        ns_image = canvas._render_to_image(self.zoom)
        bitmap = ns_image.layerContentsForContentsScale_(self._dpr)

        w, h = [s*self.zoom for s in canvas.pagesize]
        self.setFrame_(((0, 0), (w, h)))

        if self._magnifyReady:
            scrollview.setMinMagnification_(self.zoomLevels[0] / self._zoom)
            scrollview.setMaxMagnification_(self.zoomLevels[-1] / self._zoom)

        if self.canvas is None:
            # draw from top-left corner if first-run
            self.scrollPoint_( (0,0) )
        else:
            vw, vh = scrollview.contentView().frame().size
            self.scrollPoint_( (focus[0]*w - vw/2.0, focus[1]*h - vh/2.0) )

        # cache the canvas image
        self.layer().setContents_(bitmap)

        # keep a reference to the canvas so we can zoom later on
        self.canvas = canvas

    def _get_zoom(self):
        return self._zoom

    @objc.python_method
    def _set_zoom(self, zoom):
        self._zoom = zoom
        if self.canvas is not None:
            self.setCanvas(self.canvas)
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
        vis = scrollview.documentVisibleRect()
        oldframe = self.frame()
        focus = (NSMidX(vis) / NSWidth(oldframe), NSMidY(vis) / NSHeight(oldframe))
        target = self._zoom * mag
        target = max(self.zoomLevels[0], min(self.zoomLevels[-1], target))
        scrollview.setMagnification_(1.0)
        self._zoom = target
        self.setCanvas(self.canvas, focus=focus)

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
        if getattr(self, 'canvas', None) is not None:
            self.setCanvas(self.canvas)

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

    def init(self):
        super(FullscreenView, self).init()
        self.mousedown = False
        self.keydown = False
        self.key = None
        self.keycode = None
        self.mousehide = None
        # self.scrollwheel = False
        # self.wheeldelta = 0.0
        return self

    @objc.python_method
    def setCanvas(self, canvas):
        self.canvas = canvas
        self.setNeedsDisplay_(True)
        if not hasattr(self, "screenRect"):
            self.screenRect = NSScreen.mainScreen().frame()
            cw, ch = self.canvas.pagesize
            sw, sh = self.screenRect[1]
            self.scalingFactor = calc_scaling_factor(cw, ch, sw, sh)
            nw, nh = cw * self.scalingFactor, ch * self.scalingFactor
            self.scaledSize = nw, nh
            self.dx = (sw - nw) / 2.0
            self.dy = (sh - nh) / 2.0

    def drawRect_(self, rect):
        NSGraphicsContext.currentContext().saveGraphicsState()
        NSColor.blackColor().set()
        NSRectFill(rect)
        if self.canvas is not None:
            t = NSAffineTransform.transform()
            t.translateXBy_yBy_(self.dx, self.dy)
            t.scaleBy_(self.scalingFactor)
            t.concat()
            clip = NSBezierPath.bezierPathWithRect_( ((0, 0), self.canvas.pagesize) )
            clip.addClip()
            self.canvas.draw()
        NSGraphicsContext.currentContext().restoreGraphicsState()

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

