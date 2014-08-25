# encoding: utf-8
import sys
import os
import traceback

from ..lib.cocoa import *
from ..gfx import Color
from PyObjCTools import AppHelper

DARK_GREY = NSColor.blackColor().blendedColorWithFraction_ofColor_(0.7, NSColor.whiteColor())

class PlotDeviceBackdrop(NSView):
    """A container that sits between the NSClipView and PlotDeviceGraphicsView

       It resizes to fit the size of the canvas and centers it when the canvas
       is smaller than the display space in the NSSplitView. It also draws the
       background color and maintains an isOpaque=True to take advantage of
       Responsive Scrolling in 10.9
    """
    gfxView = None

    def isFlipped(self):
        return True

    def isOpaque(self):
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
        self = super(PlotDeviceBackdrop, self).setFrame_(frame)

    def didAddSubview_(self, subview):
        if isinstance(subview, PlotDeviceGraphicsView):
            self.gfxView = subview
            nc = NSNotificationCenter.defaultCenter()
            nc.addObserver_selector_name_object_(self, "viewFrameDidChange:", NSViewFrameDidChangeNotification, subview)

    def __del__(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_(self)

    def willRemoveSubview_(self, subview):
        if isinstance(subview, PlotDeviceGraphicsView):
            nc = NSNotificationCenter.defaultCenter()
            nc.removeObserver_name_object_(self, NSViewFrameDidChangeNotification, subview)

    def drawRect_(self, rect):
        DARK_GREY.setFill()
        NSRectFillUsingOperation(rect, NSCompositeCopy)
        super(PlotDeviceBackdrop, self).drawRect_(rect)

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

# class defined in PlotDeviceGraphicsView.xib
class PlotDeviceGraphicsView(NSView):
    script = IBOutlet()
    placeholder = NSImage.imageNamed_('placeholder.pdf')

    # The zoom levels are 10%, 25%, 50%, 75%, 100%, 200% and so on up to 2000%.
    zoomLevels = [0.1, 0.25, 0.5, 0.75]
    zoom = 1.0
    while zoom <= 20.0:
        zoomLevels.append(zoom)
        zoom += 1.0

    def awakeFromNib(self):
        self.canvas = None
        self._raster = None
        self.mousedown = False
        self.keydown = False
        self.key = None
        self.keycode = None
        # self.scrollwheel = False
        # self.wheeldelta = 0.0
        self._zoom = 1.0
        self._volatile = False
        if self.placeholder:
            self.setFrameSize_( self.placeholder.size() )
        self.setFocusRingType_(NSFocusRingTypeExterior)
        clipview = self.superview().superview()
        if clipview is not None:
            clipview.setDrawsBackground_(True)
            clipview.setBackgroundColor_(DARK_GREY)

    def setCanvas(self, canvas, rasterize=False):
        first_run = self.canvas is None

        self.canvas = canvas
        if canvas is not None:
            bg = canvas.background
            is_dark = bool(isinstance(bg, Color) and bg.brightness <= .5)
            scrollview = self.superview().superview().superview()
            scrollview.setScrollerKnobStyle_(2 if is_dark else 1) # NSScrollerKnobStyleDark/Light

            visible = scrollview.documentVisibleRect()
            oldframe = self.frame()
            x_pct = NSMidX(visible) / NSWidth(oldframe)
            y_pct = NSMidY(visible) / NSHeight(oldframe)

            # resize
            w, h = [s*self._zoom for s in self.canvas.pagesize]
            self.setFrameSize_([w, h])

            # preserve the prior scrollpoint (if it exists)
            if not first_run:
                half_w = NSWidth(visible) / 2.0
                half_h = NSHeight(visible) / 2.0
                self.scrollPoint_( (x_pct*w-half_w, y_pct*h-half_h) )

            # cache the canvas image (if requested)
            self._raster = self.canvas.rasterize(zoom=self.zoom) if rasterize else None
            self.setNeedsDisplay_(True)

    def cache(self):
        if self.canvas and not self.volatile:
            try:
                self._raster = self.canvas.rasterize(zoom=self.zoom)
            except:
                # Display the error in the output view.
                # (this is where invalid args passed to grobs will throw exceptions)
                #
                # wait, really? won't this always be a dupe of something that was
                # rendered during the volatile phase?
                #
                # self.script.crash()
                pass

    def _get_zoom(self):
        return self._zoom
    def _set_zoom(self, zoom):
        self._zoom = zoom
        self.setCanvas(self.canvas, rasterize=True)
    zoom = property(_get_zoom, _set_zoom)

    def _get_volatile(self):
        return self._volatile
    def _set_volatile(self, volatile):
        if self._volatile == volatile:
            return
        self._volatile = volatile
        if not volatile:
            AppHelper.callLater(0.2, self.cache)
        else:
            self._raster = None
    volatile = property(_get_volatile, _set_volatile)

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

    def setFrameSize_(self, size):
        NSView.setFrameSize_(self, size)

    def isOpaque(self):
        return False

    def isFlipped(self):
        return True

    def drawRect_(self, rect):
        if self._raster and not self.volatile:
            # if the script isn't currently running (and we'll be redrawing the same grobs for a while),
            # use a cached, zoom-specific nsimage for redraws
            self._raster.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
                rect, rect, NSCompositeSourceOver, 1.0, True, None
            )
        elif self.canvas is not None:
            # if the cached image doesn't exist (most likely to keep the frame rate up in an ongoing animation),
            # zoom the context appropriately and have the grobs draw themselves to the view itself
            NSGraphicsContext.currentContext().saveGraphicsState()
            try:
                NSBezierPath.bezierPathWithRect_(rect).addClip()
                if self.zoom != 1.0:
                    t = NSAffineTransform.transform()
                    t.scaleBy_(self.zoom)
                    t.concat()
                    clip = NSBezierPath.bezierPathWithRect_( ((0, 0), self.canvas.pagesize) )
                    clip.addClip()
                self.canvas.draw()
            except:
                # Display the error in the output view.
                # (this is where invalid args passed to grobs will throw exceptions)
                self.script.crash()
            NSGraphicsContext.currentContext().restoreGraphicsState()
        elif self.placeholder:
            # until the script runs (and generates a meaningful canvas) display the placeholder
            frame = ((0,0), self.placeholder.size())
            self.placeholder.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
                frame, frame, NSCompositeSourceOver, 1.0, True, None
            )

    # pasteboard delegate method
    def pasteboard_provideDataForType_(self, pboard, type):
        if NSPDFPboardType:
            pboard.setData_forType_(self.pdfData, NSPDFPboardType)
        elif NSPostScriptPboardType:
            pboard.setData_forType_(self.epsData, NSPostScriptPboardType)
        elif NSTIFFPboardType:
            pboard.setData_forType_(self.tiffData, NSTIFFPboardType)

    def _get_pdfData(self):
        if self.canvas:
            return self.canvas._getImageData('pdf')
    pdfData = property(_get_pdfData)

    def _get_epsData(self):
        if self.canvas:
            return self.canvas._getImageData('eps')
    epsData = property(_get_epsData)

    def _get_tiffData(self):
        return self.canvas._getImageData('tiff')
    tiffData = property(_get_tiffData)

    def _get_pngData(self):
        return self.canvas._getImageData('png')
    pngData = property(_get_pngData)

    def _get_gifData(self):
        return self.canvas._getImageData('gif')
    gifData = property(_get_gifData)

    def _get_jpegData(self):
        return self.canvas._getImageData('jpeg')
    jpegData = property(_get_jpegData)

    def mouseDown_(self, event):
        self.mousedown = True

    def mouseUp_(self, event):
        self.mousedown = False

    def keyDown_(self, event):
        self.keydown = True
        self.key = event.characters()
        self.keycode = event.keyCode()

        if self.keycode==53: # stop animating on ESC
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
        # self.scrollwheel = False
        # self.wheeldelta = 0.0
        return self

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

        if self.keycode==53: # stop animating on ESC
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

