import sys
import os
import traceback
import objc
import time
import json
import socket
import SocketServer

from PyObjCTools import AppHelper
from Foundation import *
from AppKit import *
from threading import Thread
from Queue import Queue, Empty
from nodebox.gui.mac.document import NodeBoxDocument
from nodebox.gui.mac import PyDETextView
from nodebox.gui.mac.util import errorAlert
from nodebox import util
from nodebox import graphics

RPC_PORT = 9000
VERY_LIGHT_GRAY = NSColor.blackColor().blendedColorWithFraction_ofColor_(0.95, NSColor.whiteColor())
DARKER_GRAY = NSColor.blackColor().blendedColorWithFraction_ofColor_(0.8, NSColor.whiteColor())

objc.setVerbose(1)

class NodeBoxAppDelegate(NSObject):

    def awakeFromNib(self):
        self._prefsController = None
        self._docsController = NSDocumentController.sharedDocumentController()
        self._listener = CommandListener()
        libDir = os.path.join(os.getenv("HOME"), "Library", "Application Support", "NodeBox")
        try:
            if not os.path.exists(libDir):
                os.mkdir(libDir)
                f = open(os.path.join(libDir, "README"), "w")
                f.write("In this directory, you can put Python libraries to make them available to your scripts.\n")
                f.close()
            self._listener.start()
        except OSError: pass
        except IOError: pass

    def run_script(self, opts):
        url = NSURL.URLWithString_('file://%s'%opts['file'])
        self._docsController.openDocumentWithContentsOfURL_display_error_(url, True, None)
        stdout = opts['stdout']
        for doc in self._docsController.documents():
            if doc.fileURL() and doc.fileURL().isEqualTo_(url):
                if doc._meta['stdout']:
                    stdout.put("already running: %s"%opts['file'])
                    stdout.put(None)
                    break
                if doc.export['session'] and doc.export['session'].running:
                    stdout.put("already exporting: %s"%opts['file'])
                    stdout.put(None)
                    break
                if opts['activate']:
                    NSApp.activateIgnoringOtherApps_(True)
                doc.scriptedRun(opts)
                break
        else:
            stdout.put("couldn't open script: %s"%opts['file'])
            stdout.put(None)

    def stop_script(self, opts):
        url = NSURL.URLWithString_('file://%s'%opts['file'])
        self._docsController.openDocumentWithContentsOfURL_display_error_(url, True, None)
        for doc in self._docsController.documents():
            if doc.fileURL() and doc.fileURL().isEqualTo_(url):
                doc._meta['live'] = False
                doc.stopScript()

    def applicationWillBecomeActive_(self, note):
        # check for filesystem changes while the app was inactive
        for doc in self._docsController.documents():
            url = doc.fileURL()
            if url and os.path.exists(url.fileSystemRepresentation()):
                doc.refresh()

    @objc.IBAction
    def showPreferencesPanel_(self, sender):
        if self._prefsController is None:
            from nodebox.gui.mac.preferences import NodeBoxPreferencesController
            self._prefsController = NodeBoxPreferencesController.alloc().init()
        self._prefsController.showWindow_(sender)

    @objc.IBAction
    def generateCode_(self, sender):
        """Generate a piece of NodeBox code using OttoBot"""
        from nodebox.util.ottobot import genProgram
        controller = NSDocumentController.sharedDocumentController()
        doc = controller.newDocument_(sender)
        doc = controller.currentDocument()
        doc.setSource_(genProgram())
        doc.runScript()

    @objc.IBAction
    def showHelp_(self, sender):
        url = NSURL.URLWithString_("http://nodebox.net/code/index.php/Reference")
        NSWorkspace.sharedWorkspace().openURL_(url)

    @objc.IBAction
    def showSite_(self, sender):
        url = NSURL.URLWithString_("http://nodebox.net/")
        NSWorkspace.sharedWorkspace().openURL_(url)

    def applicationWillTerminate_(self, note):
        self._listener.join()
        import atexit
        atexit._run_exitfuncs()

class ExportCommand(NSScriptCommand):
    pass    

class ZoomPanel(NSView):
    pass

class NodeBoxBackdrop(NSView):
    """A container that sits between the NSClipView and NodeBoxGraphicsView

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
        self = super(NodeBoxBackdrop, self).setFrame_(frame)

    def didAddSubview_(self, subview):
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "viewFrameDidChange:", NSViewFrameDidChangeNotification, subview)
        self.gfxView = subview
    
    def willRemoveSubview_(self, subview):
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self, NSViewFrameDidChangeNotification, subview)

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
        self._dirty = False
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
            clipview.setBackgroundColor_(DARKER_GRAY)

    def setCanvas(self, canvas):
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
        self.markDirty()
        
    def _get_zoom(self):
        return self._zoom
    def _set_zoom(self, zoom):
        self._zoom = zoom
        self.zoomLevel.setTitle_("%i%%" % (self._zoom * 100.0))
        self.zoomSlider.setFloatValue_(self._zoom * 100.0)
        self.setCanvas(self.canvas)
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

    def markDirty(self, redraw=True):
        self._dirty = True
        if redraw:
            self.setNeedsDisplay_(True)

    def setFrameSize_(self, size):
        self._image = None
        NSView.setFrameSize_(self, size)

    def isOpaque(self):
        return False

    def isFlipped(self):
        return True
        
    def drawRect_(self, rect):
        if self.canvas is not None:
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
                # A lot of code just to display the error in the output view.
                etype, value, tb = sys.exc_info()
                if tb.tb_next is not None:
                    tb = tb.tb_next  # skip the frame doing the exec
                traceback.print_exception(etype, value, tb)
                data = "".join(traceback.format_exception(etype, value, tb))
                attrs = PyDETextView.getBasicTextAttributes()
                attrs[NSForegroundColorAttributeName] = NSColor.redColor()
                outputView = self.document.outputView
                outputView.setSelectedRange_((outputView.textStorage().length(), 0))
                outputView.setTypingAttributes_(attrs)
                outputView.insertText_(data)
            NSGraphicsContext.currentContext().restoreGraphicsState()

    def _updateImage(self):
        if self._dirty:
            self._image = self.canvas._nsImage
            self._dirty = False

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
        
    def scrollWheel_(self, event):
        NSResponder.scrollWheel_(self, event)
        self.scrollwheel = True
        self.wheeldelta = event.deltaY()

    def canBecomeKeyView(self):
        return True

    def acceptsFirstResponder(self):
        return True



class CommandListener(Thread):

    class CommandHandler(SocketServer.BaseRequestHandler):
        def handle(self):
            self.stdout_q = Queue()
            self.opts = json.loads(self.request.recv(1024).split('\n')[0])
            self.opts['stdout'] = self.stdout_q
            AppHelper.callAfter(NSApp.delegate().run_script, self.opts)
    
            txt = ''
            try:
                while txt is not None:
                    if txt:
                        self.request.sendall(txt)
                    try:
                        self.check_interrupt()
                        txt = self.stdout_q.get_nowait()
                    except Empty:
                        time.sleep(.1)
                        txt = ''
            except socket.error, e:
                pass # if client closed socket, stop sending

        def check_interrupt(self):
            try:
                self.request.setblocking(0)
                interrupt = self.request.recv(1024)
                AppHelper.callAfter(NSApp.delegate().stop_script, self.opts)
            except socket.error, e:
                pass # no input from the client
            finally:
                self.request.settimeout(socket.getdefaulttimeout())

    class SocketListener(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
        daemon_threads = True # Ctrl-C will cleanly kill all spawned threads
        allow_reuse_address = True # much faster rebinding

    active = False
    def __init__(self):
        super(CommandListener, self).__init__()
        try:
            self.server = self.SocketListener(('localhost', RPC_PORT), self.CommandHandler)
            self.ip, self.port = self.server.server_address
            self.active = True
        except socket.error, e:
            NSLog("Another NodeBox instance is listening on port %i"%RPC_PORT)
            NSLog("The nodebox.py command line tool will not be able to communicate with this process")
            pass

    def run(self):
        if self.active:
            self.server.serve_forever()
      
    def join(self, timeout=None):
        if self.active:
            self.server.shutdown()
        super(CommandListener, self).join(timeout)

