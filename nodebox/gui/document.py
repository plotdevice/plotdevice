# encoding: utf-8
import sys
import os
import re
import traceback
import random
import time
import objc

from hashlib import md5
from PyObjCTools import AppHelper
from Foundation import *
from AppKit import *
from nodebox.run import Sandbox
from nodebox.gui.editor import PyDETextView, OutputTextView
from nodebox.gui.preferences import get_default, getBasicTextAttributes
from nodebox.gui.widgets import DashboardController, ExportSheet, MAGICVAR
from nodebox import util, graphics

NSEventGestureAxisVertical = 2

# class defined in NodeBoxDocument.xib
class NodeBoxDocument(NSDocument):
    graphicsView = objc.IBOutlet()
    outputView = objc.IBOutlet()
    textView = objc.IBOutlet()
    window = objc.IBOutlet()
    dashboardController = objc.IBOutlet()
    animationSpinner = objc.IBOutlet()
    footer = objc.IBOutlet()
    mainSplitView = objc.IBOutlet()
    exportSheet = objc.IBOutlet()

    _live = False # whether to re-render the graphic when the script changes
    magicvar = 0  # used for value ladders
    vars = []     # script variables being set by a Dashboard panel
    path = None   # the script file

    def windowNibName(self):
        return "NodeBoxDocument"

    def init(self):
        self = super(NodeBoxDocument, self).init()
        self.vm = Sandbox(self)
        self.animationTimer = None
        self.fullScreen = None
        self.currentView = None
        self.stationery = None
        self.__doc__ = {}
        self._fileMD5 = None
        self._showFooter = True
        return self

    def windowControllerDidLoadNib_(self, controller):
        super(NodeBoxDocument, self).windowControllerDidLoadNib_(controller)
        pth = self.path or self.stationery
        if pth:
            self.readFromUTF8(pth)
        if self.stationery:
            self.setDisplayName_(os.path.basename(self.stationery))
            self.vm.stationery = self.stationery
        font = getBasicTextAttributes()[NSFontAttributeName]
        win = self.textView.window()
        win.setPreferredBackingLocation_(NSWindowBackingLocationVideoMemory)
        win.setRestorable_(True)
        win.setIdentifier_("nodebox-doc")

        self.graphicsView.zoomLevel.cell().setHighlightsBy_(NSContentsCellMask)
        self.graphicsView.zoomLevel.cell().setShowsStateBy_(NSContentsCellMask)
        
        # would like to set:
        #   win.setRestorationClass_(NodeBoxDocument)
        # but the built-in pyobjc can't deal with the block arg in:
        #   restoreDocumentWindowWithIdentifier_state_completionHandler_
        # which we'd need to implement for restoration to work. try
        # again in 10.9.x, or is there a way to monkeypatch the metadata?

        # disable system's auto-smartquotes in the editor pane
        self.textView.setAutomaticQuoteSubstitutionEnabled_(False)
        self.textView.setEnabledTextCheckingTypes_(0)

        win.makeFirstResponder_(self.textView)
        self.currentView = self.graphicsView

        win.setAutorecalculatesContentBorderThickness_forEdge_(True,NSMinYEdge)
        win.setContentBorderThickness_forEdge_(22.0,NSMinYEdge)

        self.outputView.superview().superview().addFloatingSubview_forAxis_(self.animationSpinner,NSEventGestureAxisVertical)
        x = self.outputView.frame().size.width - 17
        self.animationSpinner.setFrame_(((x,3),(16,16)))
 
    def autosavesInPlace(self):
        return True

    def close(self):
        self.stopScript()
        super(NodeBoxDocument, self).close()

    def source(self):
        return self.textView.string()

    def setSource_(self, source):
        self.textView.setString_(source)

    def cancelOperation_(self, sender):
        self.stopScript()

    def _updateWindowAutosave(self):
        if self.path and self.textView: # don't try to access views until fully loaded
            name = 'nodebox:%s'%self.path

            # walk through superviews to set the autosave id for the splitters
            splits = {"lower":None, "upper":None}
            it = self.textView
            while it.superview():
                if type(it) is NSSplitView:
                    side = 'lower' if not splits['lower'] else 'upper'
                    splits[side] = it
                    it.setAutosaveName_(' - '.join([name,side]))
                    if splits['upper']: break
                it = it.superview()
            
            window_ctl = self.windowControllers()[0]
            window_ctl.setShouldCascadeWindows_(False)
            window_ctl.setWindowFrameAutosaveName_(name)

    def _ui_state(self):
        # Set the mouse position
        window = self.currentView.window()
        pt = window.mouseLocationOutsideOfEventStream()
        mx, my = window.contentView().convertPoint_toView_(pt, self.currentView)
        # Hack: mouse coordinates are flipped vertically in FullscreenView.
        # This flips them back.
        if isinstance(self.currentView, FullscreenView):
            my = self.currentView.bounds()[1][1] - my
        if self.fullScreen is None:
            mx /= self.currentView.zoom
            my /= self.currentView.zoom

        return dict(
            # UI events
            MOUSEX=mx, MOUSEY=my,
            mousedown=self.currentView.mousedown,
            keydown=self.currentView.keydown,
            key=self.currentView.key,
            keycode=self.currentView.keycode,
            scrollwheel=self.currentView.scrollwheel,
            wheeldelta=self.currentView.wheeldelta,
        )

    def refresh(self):
        """Reload source from file if it has been modified while the app was inactive"""
        if os.path.exists(self.path):
            try:
                filehash = md5(file(self.path).read()).digest()
                if filehash != self._fileMD5:
                    self.revertToContentsOfURL_ofType_error_(url, self.fileType(), None)
                    if self._live:
                        self.runScript()
            except IOError:
                pass

    def __del__(self):
        # remove the circular references in our helper objects
        self.textView._cleanup()
        self.vm._cleanup()

    # 
    # Reading & writing the script file (and keeping track of its path)
    # 
    def setFileURL_(self, url):
        super(NodeBoxDocument, self).setFileURL_(url)
        if not url: 
            self.path = None
            return
        self.path = url.fileSystemRepresentation()
        self._updateWindowAutosave()
        if self.vm:
            self.vm.script = self.path

    def readFromFile_ofType_(self, path, tp):
        if self.textView is None:
            # we're not yet fully loaded
            self.path = path
        else:
            # "revert"
            self.readFromUTF8(path)
        return True

    def writeToFile_ofType_(self, path, tp):
        text = self.source().encode("utf8")
        self._fileMD5 = md5(text).digest()
        with file(path, 'w') as f:
            f.write(text)
        return True

    def readFromUTF8(self, path):
        with file(path) as f:
            text = f.read()
            self._fileMD5 = md5(text).digest()
            self._updateWindowAutosave()
            self.setSource_(text.decode("utf-8"))
            self.textView.usesTabs = "\t" in text
            self.vm.script = path
            self.vm.source = text.decode("utf-8")

    # 
    # Running the script in the main window
    # 
    def scriptedRun(self, opts):
        meta = dict( (k, opts[k]) for k in ['args', 'virtualenv', 'live', 'first', 'last', 'console'] )
        self._live = meta['live']
        self.vm.metadata = meta
        self.refresh()

        if opts['fullscreen']:
            self.runFullscreen_(None)
        else:
            self.runScript()


    @objc.IBAction
    def toggleStatusBar_(self, sender):
        win = self.graphicsView.window()
        self._showFooter = not self._showFooter
        thickness = 22 if self._showFooter else 0

        # zoom = self.footer.frame()
        # zoom.origin.y = thickness-22

        content = win.contentView().frame()
        content.size.height -= thickness
        content.origin.y += thickness
        
        # self.footer.setFrame_(zoom)
        self.mainSplitView.setFrame_(content)
        win.setContentBorderThickness_forEdge_(thickness, NSMinYEdge)

    @objc.IBAction
    def runFullscreen_(self, sender):
        if self.fullScreen is not None: return
        self.stopScript()
        self.currentView = FullscreenView.alloc().init()
        self.currentView.canvas = None
        fullRect = NSScreen.mainScreen().frame()
        self.fullScreen = FullscreenWindow.alloc().initWithRect_(fullRect)
        self.fullScreen.setContentView_(self.currentView)
        self.fullScreen.makeKeyAndOrderFront_(self)
        self.fullScreen.makeFirstResponder_(self.currentView)
        NSMenu.setMenuBarVisible_(False)
        NSCursor.hide()
        self._runScript()

    @objc.IBAction
    def runScript_(self, sender):
        self.runScript()

    def runScript(self):
        if self.fullScreen is not None: return
        self.currentView = self.graphicsView
        self._runScript()

    def _runScript(self):
        # Check if animationTimer is already running
        if self.animationTimer is not None:
            self.stopScript()

        # execute the script
        if not self.cleanRun():
            # syntax error. bail out before looping
            self.vm.stop()
        elif self.vm.animated:
            # Check whether we are dealing with animation
            if 'draw' not in self.vm.namespace:
                errorAlert("Not a proper NodeBox animation",
                    "NodeBox animations should have at least a draw() method.")
                return

            # Run setup routine
            self.fastRun("setup")
            window = self.currentView.window()
            window.makeFirstResponder_(self.currentView)

            # Start the timer
            self.animationTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0 / self.vm.speed, self, objc.selector(self.doFrame, signature="v@:@"), None, True)
            # Start the spinner
            self.animationSpinner.startAnimation_(None)
        else:
            self.vm.stop()
            focus = self.textView or self.graphicsView
            focus.window().makeFirstResponder_(focus)
            
    def cleanRun(self, method=None):
        self.animationSpinner.startAnimation_(None)
        if (self.outputView):
            self.outputView.clear(timestamp=True)

        # Compile the script
        compilation = self.vm.compile(self.source())
        self.echo(compilation.output)
        if not compilation.ok:
            return False

        # Run the actual script
        success = self.fastRun(method)
        self.animationSpinner.stopAnimation_(None)

        if success and self.vm.vars:
            # Build the interface
            self.dashboardController.buildInterface(self.vm.vars)

        return success

    def fastRun(self, method=None):
        # Run the script
        self.vm.state = self._ui_state()
        result = self.vm.render(method=method)
        self.echo(result.output)

        # only update the view during animations after the script's draw()
        # method is called (otherwise a blank canvas flashes on the screen
        # during the compilation and setup() calls.
        redraw = not self.vm.animated or method=='draw'

        # Display the output of the script
        if result.ok and redraw:
            self.currentView.setCanvas(self.vm.canvas)

        return result.ok

    def doFrame(self):
        ok = self.fastRun("draw")
        if not ok or not self.vm.running:
            self.stopScript()

    def echo(self, output):
        """Pass a list of (isStdErr, txt) tuples to the output window"""
        for isErr, data in output:
            self.outputView.append(data, stream='err' if isErr else 'message')

    # 
    # Exporting to file(s)
    # 
    @objc.IBAction
    def exportAsImage_(self, sender):
        self.exportSheet.beginExport('image')

    @objc.IBAction
    def exportAsMovie_(self, sender):
        self.exportSheet.beginExport('movie')

    def _export(self, kind, fname, opts):
        """Begin actual export (invoked by self.exportSheet unless sheet was cancelled)"""
        self.vm.source = self.source()
        if self.animationTimer is not None:
            self.stopScript()

        if kind=='image' and opts['last'] == opts['first']:
            self.runScript()
            self.vm.canvas.save(fname, format)
        else:
            msg = u"Generating %s %s…"%(opts['last']-opts['first']+1, 'pages' if kind=='image' else 'frames')
            self.footer.setMode_('export')
            self.footer.setMessage_(msg)

            self.vm.export(kind, fname, opts)

    def exportStatus(self, status, canvas=None):
        """Handle export-related events (invoked by self.vm.session object)"""
        if status.output:
            # print any console messages
            self.echo(status.output)

        if status.ok:
            # display the canvas
            self.currentView.setCanvas(canvas)
            self.graphicsView.setNeedsDisplay_(True)
            # give the runloop a chance to collect events (rather than just beachballing)
            date = NSDate.dateWithTimeIntervalSinceNow_(0.05);
            NSRunLoop.currentRunLoop().acceptInputForMode_beforeDate_(NSDefaultRunLoopMode, date)
        else:
            # we're done, either because of an error or because the export is complete
            failed = status.ok is False # whereas None means successful
            self.footer.setMode_('zoom')
            self.stopScript()

    def exportProgress(self, written, total, cancelled):
        label = self.footer.progressPanel.message
        if cancelled:
            self.footer.setMessage_(u'Export terminated…')
        else:
            bar = self.footer.progressPanel.bar
            bar.setMaxValue_(total)
            bar.setDoubleValue_(written)
            if (total==written):
                self.footer.setMessage_(u'Finishing export…')        

    # 
    # Interrupting the run
    # 
    @objc.IBAction
    def stopScript_(self, sender=None):
        self.stopScript()

    def stopScript(self):
        # run stop() method if the script defines one
        result = self.vm.stop() 
        self.echo(result.output)

        self.animationSpinner.stopAnimation_(None)
        if self.animationTimer is not None:
            self.animationTimer.invalidate()
            self.animationTimer = None
        if self.fullScreen is not None:
            self.currentView = self.graphicsView
            self.fullScreen = None
            NSMenu.setMenuBarVisible_(True)
        NSCursor.unhide()
        focus = self.textView or self.graphicsView
        focus.window().makeFirstResponder_(focus)
        focus.window().makeKeyAndOrderFront_(self)

        if self.textView:
            self.textView.hideValueLadder()
        if self.vm.session:
            self.vm.session.cancel()

    #
    # Pasteboards
    #
    @objc.IBAction
    def copyImageAsPDF_(self, sender):
        pboard = NSPasteboard.generalPasteboard()
        # graphicsView implements the pboard delegate method to provide the data
        pboard.declareTypes_owner_([NSPDFPboardType,NSPostScriptPboardType,NSTIFFPboardType], self.graphicsView)


    @objc.IBAction
    def printDocument_(self, sender):
        op = NSPrintOperation.printOperationWithView_printInfo_(self.graphicsView, self.printInfo())
        op.runOperationModalForWindow_delegate_didRunSelector_contextInfo_(
            NSApp().mainWindow(), self, "printOperationDidRun:success:contextInfo:",
            0)

    def printOperationDidRun_success_contextInfo_(self, op, success, info):
        if success:
            self.setPrintInfo_(op.printInfo())
    printOperationDidRun_success_contextInfo_ = objc.selector(printOperationDidRun_success_contextInfo_,
            signature="v@:@ci")

    #
    # Zoom commands, forwarding to the graphics view.
    #
    @objc.IBAction
    def zoomIn_(self, sender):
        if self.fullScreen is not None: return
        self.graphicsView.zoomIn_(sender)

    @objc.IBAction
    def zoomOut_(self, sender):
        if self.fullScreen is not None: return
        self.graphicsView.zoomOut_(sender)

    @objc.IBAction
    def zoomToTag_(self, sender):
        if self.fullScreen is not None: return
        self.graphicsView.zoomTo_(sender.tag() / 100.0)

    @objc.IBAction
    def zoomToFit_(self, sender):
        if self.fullScreen is not None: return
        self.graphicsView.zoomToFit_(sender)

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
        self.scrollwheel = False
        self.wheeldelta = 0.0
        return self

    def setCanvas(self, canvas):
        self.canvas = canvas
        self.setNeedsDisplay_(True)
        if not hasattr(self, "screenRect"):
            self.screenRect = NSScreen.mainScreen().frame()
            cw, ch = self.canvas.size
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
            clip = NSBezierPath.bezierPathWithRect_( ((0, 0), (self.canvas.width, self.canvas.height)) )
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

def errorAlert(msgText, infoText):
    # Force NSApp initialisation.
    NSApplication.sharedApplication().activateIgnoringOtherApps_(0)
    alert = NSAlert.alloc().init()
    alert.setMessageText_(msgText)
    alert.setInformativeText_(infoText)
    alert.setAlertStyle_(NSCriticalAlertStyle)
    btn = alert.addButtonWithTitle_("OK")
    return alert.runModal()
