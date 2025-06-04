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

    def magnifyWithEvent_(self, event):
        if self.gfxView:
            self.gfxView.magnifyWithEvent_(event)
        return None

    def beginGestureWithEvent_(self, event):
        if self.gfxView:
            self.gfxView.beginGestureWithEvent_(event)
        return None

    def endGestureWithEvent_(self, event):
        return None

    def acceptsTouchEvents(self):
        return True

    def scrollWheel_(self, event):
        if self.gfxView:
            self.gfxView.scrollWheel_(event)
        else:
            # Pass the scroll event to the scroll view
            scrollview = self.superview()
            if scrollview:
                scrollview.scrollWheel_(event)

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

        # display the placeholder image until we're passed a canvas (and keep it in sync with appearance)
        self.updatePlaceholder(NSAppearance.currentDrawingAppearance())

        # Enable gesture recognition
        self.setWantsRestingTouches_(True)
        self.setAcceptsTouchEvents_(True)

    @objc.python_method
    def updatePlaceholder(self, appearance):
        if self.canvas is None:
            placeholder = NSImage.imageNamed_('placeholder-{mode}.pdf'.format(
                mode = 'dark' if 'Dark' in appearance.name() else 'light'
            ))
            if placeholder:
                self.setFrameSize_(placeholder.size())
                self.setNeedsDisplay_(True)  # trigger a redraw

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

        # keep a reference to the canvas
        self.canvas = canvas
        
        # trigger a redraw
        self.setNeedsDisplay_(True)

    def _get_zoom(self):
        return self._zoom

    @objc.python_method
    def _set_zoom(self, zoom):
        self._zoom = zoom
        self.setCanvas(self.canvas)
    zoom = property(_get_zoom, _set_zoom)

    @objc.python_method
    def _findNearestZoomLevel(self, zoom):
        """Find the nearest zoom level to the given zoom value"""
        return min(self.zoomLevels, key=lambda x: abs(x - zoom))

    @objc.python_method
    def _applyZoom(self, delta, mouse_point=None):
        """Apply zoom with given delta, centered at mouse_point"""
        # calculate new zoom with smoother scaling
        new_zoom = self.zoom * (1.0 + (delta * 0.8))
        new_zoom = max(0.1, min(20.0, new_zoom))
        
        # if no mouse point provided, just update zoom
        if not mouse_point:
            self.zoom = new_zoom
            return
            
        # get the clip view and current visible area
        clip_view = self.superview().superview()
        visible = clip_view.documentVisibleRect()
        
        # calculate the point in document coordinates that's under the mouse
        doc_x = mouse_point.x
        doc_y = mouse_point.y
        
        # store old zoom and apply new zoom
        old_zoom = self.zoom
        self.zoom = new_zoom
        
        # calculate how much the document point should move
        scale_factor = new_zoom / old_zoom
        dx = doc_x * (scale_factor - 1.0)
        dy = doc_y * (scale_factor - 1.0)
        
        # calculate new scroll position to keep mouse point fixed
        new_x = visible.origin.x + dx
        new_y = visible.origin.y + dy
        
        # apply scroll
        self.scrollPoint_((new_x, new_y))

    @objc.python_method
    def _getMousePointForZoom(self, event):
        """Get mouse position for zoom operations, returns None if no window"""
        window = self.window()
        if window:
            mouse_point = window.mouseLocationOutsideOfEventStream()
            return self.convertPoint_fromView_(mouse_point, None)
        return None

    @objc.python_method
    def _calculateZoomDelta(self, event, is_scroll=False):
        """Convert event input to a normalized zoom delta"""
        if is_scroll:
            # For scroll events, normalize the scroll delta
            return event.scrollingDeltaY() / 100.0
        else:
            # For pinch events, use the magnification directly
            return event.magnification()

    @IBAction
    def zoomIn_(self, sender):
        """Zoom in one level"""
        current = self._findNearestZoomLevel(self.zoom)
        idx = self.zoomLevels.index(current)
        new_idx = min(idx + 1, len(self.zoomLevels) - 1)
        self.zoom = self.zoomLevels[new_idx]

    @IBAction
    def zoomOut_(self, sender):
        """Zoom out one level"""
        current = self._findNearestZoomLevel(self.zoom)
        idx = self.zoomLevels.index(current)
        new_idx = max(idx - 1, 0)
        self.zoom = self.zoomLevels[new_idx]

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

    def scrollWheel_(self, event):
        # check if Command key is pressed for zoom
        if event.modifierFlags() & NSEventModifierFlagCommand:
            # get zoom delta from scroll
            delta = self._calculateZoomDelta(event, is_scroll=True)
            mouse_point = self._getMousePointForZoom(event)
            self._applyZoom(delta, mouse_point)
        else:
            # pass the scroll event to the scroll view
            scrollview = self.superview().superview()
            if scrollview:
                scrollview.scrollWheel_(event)

    def magnifyWithEvent_(self, event):
        # get zoom delta from pinch
        delta = self._calculateZoomDelta(event)
        mouse_point = self._getMousePointForZoom(event)
        self._applyZoom(delta, mouse_point)
        return None

    def beginGestureWithEvent_(self, event):
        return None

    def endGestureWithEvent_(self, event):
        return None

    def canBecomeKeyView(self):
        return True

    def acceptsFirstResponder(self):
        return True

    def acceptsTouchEvents(self):
        return True

    def drawRect_(self, rect):
        if self.canvas is None:
            # draw placeholder if no canvas
            if placeholder := NSImage.imageNamed_('placeholder-{mode}.pdf'.format(
                mode = 'dark' if 'Dark' in NSAppearance.currentDrawingAppearance().name() else 'light'
            )):
                placeholder.drawInRect_(self.bounds())
            return

        # convert the dirty rect to canvas coordinates
        viewToCanvas = NSAffineTransform.transform()
        viewToCanvas.scaleBy_(1.0/self.zoom)
        canvasRect = viewToCanvas.transformRect_(rect)
        
        # set up the graphics state for zoomed drawing
        NSGraphicsContext.currentContext().saveGraphicsState()
        
        # apply zoom transform
        transform = NSAffineTransform.transform()
        transform.scaleBy_(self.zoom)
        transform.concat()
        
        # set up clipping to the intersection of canvas bounds and visible area
        canvasBounds = ((0, 0), self.canvas.pagesize)
        visibleBounds = NSIntersectionRect(canvasRect, canvasBounds)
        clip = NSBezierPath.bezierPathWithRect_(visibleBounds)
        clip.addClip()
        
        # draw the canvas contents
        self.canvas.draw()
        
        # restore the graphics state
        NSGraphicsContext.currentContext().restoreGraphicsState()

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

