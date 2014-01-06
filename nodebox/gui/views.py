import sys
import os
import traceback
import objc

from Foundation import *
from AppKit import *
from Quartz import CGColorCreateGenericRGB
from nodebox import graphics
from nodebox.util import stacktrace

DARK_GREY = NSColor.blackColor().blendedColorWithFraction_ofColor_(0.8, NSColor.whiteColor())

class ExportCommand(NSScriptCommand):
    pass

class NodeBoxBackdrop(NSView):
    """A container that sits between the NSClipView and NodeBoxGraphicsView

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
        self = super(NodeBoxBackdrop, self).setFrame_(frame)

    def didAddSubview_(self, subview):
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "viewFrameDidChange:", NSViewFrameDidChangeNotification, subview)
        self.gfxView = subview

    def willRemoveSubview_(self, subview):
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self, NSViewFrameDidChangeNotification, subview)

    def drawRect_(self, rect):
        DARK_GREY.setFill()
        NSRectFillUsingOperation(rect, NSCompositeCopy)
        super(NodeBoxBackdrop, self).drawRect_(rect)

    def viewFrameDidChange_(self, note):
        self.setFrame_(self.frame())
        newframe = self.frame()
        gfxframe = self.gfxView.frame()
        if newframe.size.width > gfxframe.size.width:
            gfxframe.origin.x = (newframe.size.width-gfxframe.size.width)/2.0
        else:
            gfxframe.origin.x = 0
        if newframe.size.height > gfxframe.size.height:
            gfxframe.origin.y = (newframe.size.height-gfxframe.size.height)/2.0
        else:
            gfxframe.origin.y = 0
        self.gfxView.setFrame_(gfxframe)


# class defined in NodeBoxGraphicsView.xib
class NodeBoxGraphicsView(NSView):
    document = objc.IBOutlet()
    zoomLevel = objc.IBOutlet()
    zoomField = objc.IBOutlet()
    zoomSlider = objc.IBOutlet()

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
        self.scrollwheel = False
        self.wheeldelta = 0.0
        self._zoom = 1.0
        self.setFrameSize_( (graphics.DEFAULT_WIDTH, graphics.DEFAULT_HEIGHT) )
        self.setFocusRingType_(NSFocusRingTypeExterior)
        clipview = self.superview().superview()
        if clipview is not None:
            clipview.setDrawsBackground_(True)
            clipview.setBackgroundColor_(DARK_GREY)

    def setCanvas(self, canvas, rasterize=False):
        self.canvas = canvas
        if canvas is not None:
            scrollview = self.superview().superview().superview()
            visible = scrollview.documentVisibleRect()
            oldframe = self.frame()
            x_pct = NSMidX(visible) / NSWidth(oldframe)
            y_pct = NSMidY(visible) / NSHeight(oldframe)

            w, h = [s*self._zoom for s in self.canvas.size]
            self.setFrameSize_([w, h])

            half_w = NSWidth(visible) / 2.0
            half_h = NSHeight(visible) / 2.0
            self.scrollPoint_( (x_pct*w-half_w, y_pct*h-half_h) )
        self._raster = self.canvas.rasterize(zoom=self.zoom) if rasterize else None
        self.setNeedsDisplay_(True)

    def recache(self):
        self._raster = self.canvas.rasterize(zoom=self.zoom)

    def _get_zoom(self):
        return self._zoom
    def _set_zoom(self, zoom):
        self._zoom = zoom
        self.zoomLevel.setTitle_("%i%%" % (self._zoom * 100.0))
        self.zoomSlider.setFloatValue_(self._zoom * 100.0)
        self.setCanvas(self.canvas, rasterize=True)
    zoom = property(_get_zoom, _set_zoom)

    @objc.IBAction
    def dragZoom_(self, sender):
        self.zoom = self.zoomSlider.floatValue() / 100.0
        self.setCanvas(self.canvas)

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

    @objc.IBAction
    def zoomIn_(self, sender):
        idx, direct = self.findNearestZoomIndex(self.zoom)
        # Direct hits are perfect, but indirect hits require a bit of help.
        # Because of the way indirect hits are calculated, they are already
        # rounded up to the upper zoom level; this means we don't need to add 1.
        if direct:
            idx += 1
        idx = max(min(idx, len(self.zoomLevels)-1), 0)
        self.zoom = self.zoomLevels[idx]

    @objc.IBAction
    def zoomOut_(self, sender):
        idx, direct = self.findNearestZoomIndex(self.zoom)
        idx -= 1
        idx = max(min(idx, len(self.zoomLevels)-1), 0)
        self.zoom = self.zoomLevels[idx]

    @objc.IBAction
    def resetZoom_(self, sender):
        self.zoom = 1.0

    def zoomTo_(self, zoom):
        self.zoom = zoom

    @objc.IBAction
    def zoomToFit_(self, sender):
        w, h = self.canvas.size
        fw, fh = self.superview().frame()[1]
        factor = min(fw / w, fh / h)
        self.zoom = factor

    def setFrameSize_(self, size):
        NSView.setFrameSize_(self, size)

    def isOpaque(self):
        return False

    def isFlipped(self):
        return True

    def drawRect_(self, rect):
        if self._raster:
            # if the script isn't currently running (and we'll be redrawing the same grobs for a while),
            # use a cached, zoom-specific nsimage for redraws
            self._raster.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
                rect, rect, NSCompositeCopy, 1.0, True, None
            )
        elif self.canvas is not None:
            # if the cached image doesn't exist (most likely to keep the frame rate up in an ongoing animation),
            # zoom the context appropriately and have the grobs draw themselves to the view itself
            NSGraphicsContext.currentContext().saveGraphicsState()
            try:
                if self.zoom != 1.0:
                    t = NSAffineTransform.transform()
                    t.scaleBy_(self.zoom)
                    t.concat()
                    clip = NSBezierPath.bezierPathWithRect_( ((0, 0), (self.canvas.width, self.canvas.height)) )
                    clip.addClip()
                self.canvas.draw()
            except:
                # Display the error in the output view.
                # (this is where invalid args passed to grobs will throw exceptions)
                errtxt = stacktrace.prettify(self.document.fileName())
                document.echo((False, errtxt))
            NSGraphicsContext.currentContext().restoreGraphicsState()


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


class Footer(NSView):
    zoomPanel = objc.IBOutlet()
    progressPanel = objc.IBOutlet()

    def awakeFromNib(self):
        self._mode = 'zoom'
        if self.progressPanel:
            self.progressPanel.setHidden_(True)

    def setMode_(self, mode):
        if mode==self._mode:
            return
        incoming = self.progressPanel if mode=='export' else self.zoomPanel
        outgoing = self.zoomPanel if mode=='export' else self.progressPanel

        incoming.setAlphaValue_(0)
        incoming.setHidden_(False)
        NSAnimationContext.beginGrouping()
        dt = 0.666
        ctx = NSAnimationContext.currentContext()
        ctx.setDuration_(dt)
        incoming.animator().setAlphaValue_(1)
        outgoing.animator().setAlphaValue_(0)
        NSAnimationContext.endGrouping()
        self.performSelector_withObject_afterDelay_("endModeSwitch:", mode, dt)
        self._mode = mode

    def setMessage_(self, msg):
        self.progressPanel.message.setStringValue_(msg)

    def endModeSwitch_(self, mode):
        incoming = self.progressPanel if mode=='export' else self.zoomPanel
        outgoing = self.zoomPanel if mode=='export' else self.progressPanel
        outgoing.setHidden_(True)
        incoming.setHidden_(False)

class ProgressPanel(NSView):
    bar = objc.IBOutlet()
    cancel = objc.IBOutlet()
    message = objc.IBOutlet()

class ZoomPanel(NSView):
    pass

