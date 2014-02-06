# encoding: utf-8
import sys
import os
import re
import traceback
import random
import time
import objc

from Foundation import *
from AppKit import *
from nodebox.run import Sandbox
from nodebox.gui.editor import OutputTextView, EditorView
from nodebox.gui.widgets import DashboardController, ExportSheet
from nodebox.gui.views import FullscreenWindow, FullscreenView
from nodebox import util, graphics

NSEventGestureAxisVertical = 2

# class defined in NodeBoxDocument.xib
class NodeBoxDocument(NSDocument):
    graphicsView = objc.IBOutlet()
    outputView = objc.IBOutlet()
    editorView = objc.IBOutlet()
    textView = objc.IBOutlet() # ye olde PyDETextView
    window = objc.IBOutlet()
    dashboardController = objc.IBOutlet()
    animationSpinner = objc.IBOutlet()
    footer = objc.IBOutlet()
    mainView = objc.IBOutlet()
    exportSheet = objc.IBOutlet()

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
        self.mtime = None
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
        win = self.editorView.window()
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

        # win.makeFirstResponder_(self.editorView)
        self.currentView = self.graphicsView

        win.setAutorecalculatesContentBorderThickness_forEdge_(True,NSMinYEdge)
        win.setContentBorderThickness_forEdge_(22.0,NSMinYEdge)

        self.outputView.superview().superview().addFloatingSubview_forAxis_(self.animationSpinner,NSEventGestureAxisVertical)
        x = self.outputView.frame().size.width - 17
        self.animationSpinner.setFrame_(((x,3),(16,16)))
        self.toggleStatusBar_(self)

    def windowDidResignKey_(self, note):
        self.editorView.window().makeFirstResponder_(None)

    def windowDidBecomeKey_(self, note):
        self.editorView.window().makeFirstResponder_(self.editorView)
        self.editorView.focus()

    def windowWillUseStandardFrame_defaultFrame_(self, win, rect):
        container = self.graphicsView.superview().superview().superview().superview() # nssplitview or nsview
        frame = win.frame()
        current = frame.size
        gworld = self.graphicsView.frame().size
        scrollview = self.graphicsView.superview().superview().superview().frame().size
        thumb_w = 9 if type(container) is NSSplitView else 0 # no thumb when running from command line

        gfx_share = scrollview.width / (current.width-thumb_w)
        best_w = round(gworld.width/gfx_share) + thumb_w
        best_h = gworld.height + 22
        merged = NSIntersectionRect(rect, (rect.origin, (best_w, best_h)))

        if merged.size.width<300 or merged.size.height<222:
            # whatever appkit code makes the decision to zoom does crazy stuff if you pass it a
            # standard-frame of a fixed min size. no clue why it bobbles the height. the real ‘solution’
            # is to shim into the nswindow zoom: method. might also be the only place to disable animated
            # frame resize (which doesn't really fit with the graphicsview resize behavior)
            return frame

        center = dict(x=NSMidX(frame), y=NSMidY(frame))
        merged.origin.x = round(center['x'] - merged.size.width/2.0)
        merged.origin.y = round(center['y'] - merged.size.height/2.0)
        return merged

    def windowShouldZoom_toFrame_(self, win, rect):
        # catch the occasions where we don't modify the size and cancel the zoom
        return win.frame().size != rect.size

    def autosavesInPlace(self):
        return True

    def close(self):
        self.graphicsView = None
        self.stopScript()
        super(NodeBoxDocument, self).close()

    def source(self):
        return self.editorView.source

    def setSource_(self, source):
        self.editorView.source = source

    def cancelOperation_(self, sender):
        self.stopScript()        

    def _updateWindowAutosave(self):
        if self.path and self.editorView: # don't try to access views until fully loaded
            name = 'nodebox:%s'%self.path

            # walk through superviews to set the autosave id for the splitters
            splits = {"lower":None, "upper":None}
            it = self.editorView
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

    @objc.IBAction
    def toggleStatusBar_(self, sender):
        win = self.graphicsView.window()
        self._showFooter = not self._showFooter
        thickness = 22 if self._showFooter else 0

        content = win.contentView().frame()
        content.size.height -= thickness
        content.origin.y += thickness
        
        self.mainView.setFrame_(content)
        win.setContentBorderThickness_forEdge_(thickness, NSMinYEdge)
        self.footer.setHidden_(not self._showFooter)

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
            # scrollwheel=self.currentView.scrollwheel,
            # wheeldelta=self.currentView.wheeldelta,
        )

    def refresh(self):
        """Reload source from file if it has been modified while the app was inactive"""
        if os.path.exists(self.path):
            try:
                mtime = os.path.getmtime(self.path)
                if mtime != self.mtime:
                    print "reload", self.path
                    url = NSURL.fileURLWithPath_(self.path)
                    self.revertToContentsOfURL_ofType_error_(url, self.fileType(), None)
                    if self.vm.live:
                        self.runScript()
                else:
                    print "unchanged"
            except IOError:
                pass

    def __del__(self):
        # remove the circular references in our helper objects
        self.vm._cleanup()

    # 
    # Reading & writing the script file (and keeping track of its path)
    # 
    def setFileURL_(self, url):
        super(NodeBoxDocument, self).setFileURL_(url)

        if not url: 
            self.path = None
            return
        pth = url.fileSystemRepresentation()
        if self.path != pth:
            nc = NSNotificationCenter.defaultCenter()
            nc.postNotificationName_object_("watch", None)
        self.path = pth
        self._updateWindowAutosave()
        if self.vm:
            self.vm.path = self.path

    def readFromFile_ofType_(self, path, tp):
        if self.editorView is None:
            # we're not yet fully loaded
            self.path = path
        else:
            # "revert"
            self.readFromUTF8(path)
        return True

    def writeToFile_ofType_(self, path, tp):
        text = self.source().encode("utf8")
        with file(path, 'w', 0) as f:
            f.write(text)
        return True

    def readFromUTF8(self, path):
        with file(path) as f:
            text = f.read()
            self.mtime = os.path.getmtime(path)
            self._updateWindowAutosave()
            self.setSource_(text.decode("utf-8"))
            self.vm.path = path
            self.vm.source = text.decode("utf-8")

    def saveToURL_ofType_forSaveOperation_error_(self, url, type, op, err):
        ok = super(NodeBoxDocument, self).saveToURL_ofType_forSaveOperation_error_(url, type, op, err)
        if self.path and os.path.exists(self.path):
            self.mtime = os.path.getmtime(self.path)

        # if the save operation left a backup file around (why!), rm it here...
        bak = self.backupFileURL().fileSystemRepresentation() if self.backupFileURL() else None
        if ok and bak and os.path.exists(bak) and os.path.basename(bak).startswith('.'):
            os.unlink(bak)

        return ok

    def prepareSavePanel_(self, panel):
        # saving modifications to .py files is fine, but if a Save As operation happens, restrict it to .nb files
        panel.setRequiredFileType_("nb")
        panel.setAccessoryView_(None)
        return True

    def backupFileURL(self):
        # by default a backup file is left in the original file's directory with a tilde appended to
        # the filename (before the extension). since for some reason the NSDocument infrastructure isn't
        # clearing it away after a save, we'll prepend a dot to the name so the user doesn't see the 
        # backup file appearing on save. then in saveToURL, we clean out the backup file
        pth = super(NodeBoxDocument, self).backupFileURL()
        if not pth:
            return None
        pth = pth.fileSystemRepresentation()
        tmp = os.path.join(os.path.dirname(pth), '.'+os.path.basename(pth))
        return NSURL.fileURLWithPath_(tmp)

    # 
    # Running the script in the main window
    # 
    def scriptedRun(self, opts):
        self.vm.metadata = opts
        self.refresh()

        if opts['fullscreen']:
            self.runFullscreen_(None)
        else:
            self.runScript()

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

        # disable double buffering during the run (stopScript reënables it)
        self.graphicsView.volatile = True

        # execute the script
        if not self.eval():
            # syntax error. bail out before looping
            self.vm.stop()
        elif self.vm.animated:
            # Check whether we are dealing with animation
            if 'draw' not in self.vm.namespace:
                errorAlert("Not a proper NodeBox animation",
                    "NodeBox animations should have at least a draw() method.")
                return

            # Run setup routine
            self.invoke("setup")
            window = self.currentView.window()
            window.makeFirstResponder_(self.currentView)

            # Start the timer
            self.animationTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0 / self.vm.speed, self, objc.selector(self.step, signature="v@:@"), None, True)
            
            # Start the spinner
            self.animationSpinner.startAnimation_(None)
        else:
            # clean up after successful non-animated run
            self.stopScript()

    def step(self):
        """Keep calling the script's draw method until an error occurs or the animation complete."""
        ok = self.invoke("draw")
        if not ok or not self.vm.running:
            self.stopScript()

    def eval(self):
        """Compile the script and run its global scope.

        For non-animated scripts, this is a whole run since all of their drawing and control
        flow is at the module level. For animated scripts, this is just a first pass to populate
        the namespace with the script's variables and particularly the setup/draw/stop functions.
        """
        self.animationSpinner.startAnimation_(None)
        if (self.outputView):
            self.outputView.clear(timestamp=True)

        # Compile the script
        compilation = self.vm.compile(self.source())
        self.echo(compilation.output)
        if not compilation.ok:
            return False

        # Run the actual script
        success = self.invoke(None)
        self.animationSpinner.stopAnimation_(None)

        if success and self.vm.vars:
            # Build the interface
            self.dashboardController.buildInterface(self.vm.vars)

        return success

    def invoke(self, method):
        """Call a method defined in the script's global namespace.

        If `method` exists in the namespace, it is called. If it's undefined, the invocation
        is ignored and no error is raised. If the method is None, the script's global scope 
        will be run, but no additional methods will be called.
        """
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
        if not result.ok and method is None:
            self.stopScript()

        return result.ok

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

    def exportConfig(self, kind, fname, opts):
        """Begin actual export (invoked by self.exportSheet unless sheet was cancelled)"""
        self.vm.source = self.source()
        if self.animationTimer is not None:
            self.stopScript()
        if not self._showFooter:
            self.toggleStatusBar_(self)

        if kind=='image' and opts['last'] == opts['first']:
            self.runScript()
            self.vm.canvas.save(fname, opts.get('format'))
        else:
            msg = u"Generating %s %s…"%(opts['last']-opts['first']+1, 'pages' if kind=='image' else 'frames')
            self.footer.setMode_('export')
            self.footer.setMessage_(msg)

            self.vm.export(kind, fname, opts)

    def exportStatus(self, status, canvas=None):
        """Handle export-related events (invoked by self.vm)

        Called with either a status flag + output text, a rendered canvas, or both."""
        if status.output:
            # print any console messages
            self.echo(status.output)

        if status.ok:
            # display the canvas
            self.currentView.setCanvas(canvas)
        else:
            # we're done, either because of an error or because the export is complete
            failed = status.ok is False # whereas None means successful
            self.footer.setMode_('zoom')
            self.stopScript()

    def exportProgress(self, written, total, cancelled):
        """Update the export progress bar (invoked by self.vm.session)"""
        label = self.footer.progressPanel.message
        if cancelled:
            self.footer.setMessage_(u'Cancelling export…')
            self.footer.wait()
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

        # disable ui feedback and return from fullscreen (if applicable)
        self.animationSpinner.stopAnimation_(None)
        if self.animationTimer is not None:
            self.animationTimer.invalidate()
            self.animationTimer = None
        if self.fullScreen is not None:
            self.currentView = self.graphicsView
            self.fullScreen = None
            NSMenu.setMenuBarVisible_(True)
        NSCursor.unhide()

        # try to send the cursor to the editor
        if self.editorView:
            self.editorView.focus()
        elif self.graphicsView:
            self.graphicsView.window().makeFirstResponder_(self.graphicsView)

        # bring the window forward (to recover from fullscreen mode) and re-cache the graphics
        if self.graphicsView:
            # note that graphicsView is nulled out in self.close_ before we're called.
            # otherwise the makeKey will cause a double-flicker before the window disappears
            focus = self.editorView or self.graphicsView
            focus.window().makeKeyAndOrderFront_(self)
            self.graphicsView.volatile = False

        # end any ongoing export cleanly
        if self.vm.session:
            self.vm.session.cancel()

        self.outputView.report(self.vm.crashed, self.vm.namespace['FRAME'] if self.vm.animated else None)

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


def errorAlert(msgText, infoText):
    # Force NSApp initialisation.
    NSApplication.sharedApplication().activateIgnoringOtherApps_(0)
    alert = NSAlert.alloc().init()
    alert.setMessageText_(msgText)
    alert.setInformativeText_(infoText)
    alert.setAlertStyle_(NSCriticalAlertStyle)
    btn = alert.addButtonWithTitle_("OK")
    return alert.runModal()
