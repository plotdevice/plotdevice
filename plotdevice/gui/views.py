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

class GraphicsBackdrop(NSView):
    """A container that sits between the NSClipView and GraphicsView

       It resizes to fit the size of the canvas and centers it when the canvas
       is smaller than the display space in the NSSplitView.
    """
    gfxView = None

    def isFlipped(self):
        return True

    def setFrame_(self, frame):
        if self.gfxView:
            scrollview = self.superview().superview()
            visible = scrollview.documentVisibleRect()
            minsize = self.gfxView.bounds().size
            frame.size.width = max(visible.size.width, minsize.width)
            frame.size.height = max(visible.size.height, minsize.height)
            scrollview.horizontalScroller().setControlSize_(1) #NSSmallControlSize
            scrollview.verticalScroller().setControlSize_(1)
        self = super(GraphicsBackdrop, self).setFrame_(frame)

    def didAddSubview_(self, subview):
        if isinstance(subview, GraphicsView):
            self.gfxView = subview
            nc = NSNotificationCenter.defaultCenter()
            nc.addObserver_selector_name_object_(self, "viewFrameDidChange:", NSViewFrameDidChangeNotification, subview)

    def __del__(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_(self)

    def willRemoveSubview_(self, subview):
        if isinstance(subview, GraphicsView):
            nc = NSNotificationCenter.defaultCenter()
            nc.removeObserver_name_object_(self, NSViewFrameDidChangeNotification, subview)

    def viewFrameDidChange_(self, note):
        self.setFrame_(self.frame())
        newframe = self.frame()
        gfxframe = self.gfxView.frame()
        if newframe.size.width > gfxframe.size.width:
            gfxframe.origin.x = (newframe.size.width-gfxframe.size.width)//2
        else:
            gfxframe.origin.x = 0
        if newframe.size.height > gfxframe.size.height:
            gfxframe.origin.y = (newframe.size.height-gfxframe.size.height)//2
        else:
            gfxframe.origin.y = 0
        self.gfxView.setFrame_(gfxframe)

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
    def setCanvas(self, canvas):
        # set the scroller color based on the background
        bg = canvas.background
        is_dark = bool(isinstance(bg, Color) and bg.brightness <= .5)
        scrollview = self.superview().superview().superview()
        scrollview.setScrollerKnobStyle_(2 if is_dark else 1) # NSScrollerKnobStyleDark/Light

        # find the centerpoint of the visible region
        visible = scrollview.documentVisibleRect()
        oldframe = self.frame()
        x_pct = NSMidX(visible) / NSWidth(oldframe)
        y_pct = NSMidY(visible) / NSHeight(oldframe)

        # render (and possibly bomb...)
        ns_image = canvas._render_to_image(self.zoom)
        bitmap = ns_image.layerContentsForContentsScale_(self._dpr)

        # resize
        w, h = [s*self.zoom for s in canvas.pagesize]
        self.setFrameSize_([w, h])

        if self.canvas is None:
            # draw from top-left corner if first-run
            self.scrollPoint_( (0,0) )
        else:
            # otherwise preserve the prior scrollpoint
            half_w = NSWidth(visible) / 2.0
            half_h = NSHeight(visible) / 2.0
            self.scrollPoint_( (x_pct*w-half_w, y_pct*h-half_h) )

        # cache the canvas image
        self.layer().setContents_(bitmap)

        # keep a reference to the canvas so we can zoom later on
        self.canvas = canvas

    def _get_zoom(self):
        return self._zoom

    @objc.python_method
    def _set_zoom(self, zoom):
        self._zoom = zoom
        self.setCanvas(self.canvas)
    zoom = property(_get_zoom, _set_zoom)

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
        fw, fh = self.superview().superview().frame()[1]
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

    # def scrollWheel_(self, event):
    #     NSResponder.scrollWheel_(self, event)
    #     self.scrollwheel = True
    #     self.wheeldelta = event.scrollingDeltaY()

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

