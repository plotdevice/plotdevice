# encoding: utf-8
import sys
import os
import re
import traceback
import random
import time
from io import open
from objc import super

from ..lib.cocoa import *

from .editor import OutputTextView, EditorView
from .widgets import DashboardController, ExportSheet
from .views import FullscreenWindow, FullscreenView
from ..run import Sandbox, encoded
from .. import DeviceError
from . import set_timeout

NSEventGestureAxisVertical = 2

class PlotDeviceDocument(NSDocument):
    def init(self):
        self.stationery = "TMPL:sketch" # untitled/example docs flag
        self.source = None # string read in from file
        self.source_enc = 'utf-8' # or the contents of a coding: comment
        self.script = None # window controller
        return super(PlotDeviceDocument,self).init()

    def makeWindowControllers(self):
        self.script = ScriptController.alloc().initWithWindowNibName_("PlotDeviceDocument")

        if self.stationery:
            self.script.setStationery_(self.stationery)
            if os.path.exists(self.stationery) and not self.stationery.startswith('TMPL:'):
                self.setDisplayName_(os.path.basename(self.stationery).replace('.pv',''))
                self.script.synchronizeWindowTitleWithDocumentName()
        elif self.source is not None:
            self.script.setPath_source_(self.path, self.source)

        self.addWindowController_(self.script)

    @property
    def path(self):
        url = self.fileURL()
        return url.path() if url else None

    #
    # Reading & writing the script file (and keeping track of its path)
    #
    def setFileURL_(self, url):
        self.stationery = None
        super(PlotDeviceDocument, self).setFileURL_(url)
        # make sure the vm knows about saved/renamed files
        if self.script and self.path:
            self.script.path = self.path

    def writeToURL_ofType_error_(self, url, tp, err):
        path = url.fileSystemRepresentation()
        # always use the same encoding we were read in with
        with open(path, 'w', encoding=self.source_enc) as f:
            f.write(self.script._get_source())
        return True, err

    def readFromURL_ofType_error_(self, url, tp, err):
        path = url.fileSystemRepresentation()
        self.source_enc = encoded(path)
        self.source = open(path, encoding=self.source_enc).read()
        if self.script:
            self.script.setPath_source_(self.path, self.source)
        return True, err

    # for debugging the editor:
    def updateChangeCount_(self, chg):
        # changes = {0:"NSChangeDone", 1:"NSChangeUndone", 2:"NSChangeCleared", 3:"NSChangeReadOtherContents", 4:"NSChangeAutosaved", 5:"NSChangeRedone", 256:"NSChangeDiscardable", }
        # print changes[chg]
        super(PlotDeviceDocument, self).updateChangeCount_(chg)

    ## Autosave & restoration on re-launch

    def autosavesInPlace(self):
        return True

    def encodeRestorableStateWithCoder_(self, coder):
        super(PlotDeviceDocument, self).encodeRestorableStateWithCoder_(coder)
        if self.stationery and not self.undoManager().canUndo():
            coder.encodeObject_forKey_(self.stationery, "plotdevice:stationery")

    def restoreStateWithCoder_(self, coder):
        super(PlotDeviceDocument, self).restoreStateWithCoder_(coder)
        self.stationery = coder.decodeObjectForKey_("plotdevice:stationery")
        if self.stationery:
            self.script.setStationery_(self.stationery)

    ## Explicit saves

    def prepareSavePanel_(self, panel):
        # saving modifications to .py files is fine, but if a Save As operation
        # happens, restrict it to .pv files
        panel.setRequiredFileType_("pv")
        panel.setAccessoryView_(None)
        return True

    def presentedItemDidChange(self):
        # reload the doc if an external editor modified the file
        self.performSelectorOnMainThread_withObject_waitUntilDone_("_refresh", None, True)

    def _refresh(self):
        doc_mtime = self.fileModificationDate().timeIntervalSince1970()
        file_mtime = os.path.getmtime(self.fileURL().fileSystemRepresentation())
        if file_mtime > doc_mtime:
            self.revertToContentsOfURL_ofType_error_(self.fileURL(), self.fileType(), None)

# `file's owner' in PlotDeviceDocument.xib
class ScriptController(NSWindowController):
    # main document window
    graphicsView = IBOutlet()
    outputView = IBOutlet()
    editorView = IBOutlet()
    statusView = IBOutlet()

    # auxiliary windows
    dashboardController = IBOutlet()
    exportSheet = IBOutlet()

    ## Properties

    # .path
    def _get_path(self):
        return self.vm.path
    def _set_path(self, pth):
        self.vm.path = pth
    path = property(_get_path, _set_path)

    # .source
    def _get_source(self):
        return self.editorView.source if self.editorView else self.vm.source
    def _set_source(self, src):
        self.vm.source = src
        if self.editorView:
            self.editorView.source = src
    source = property(_get_source, _set_source)

    ## Initializers

    def initWithWindowNibName_(self, nib):
        self._init_state()
        return super(ScriptController, self).initWithWindowNibName_(nib)

    def _init_state(self):
        self.vm = Sandbox(self)
        self.animationTimer = None
        self.fullScreen = None
        self.currentView = None
        self.stationery = None

    def setPath_source_(self, path, source):
        self.vm.path = path
        self.vm.source = source
        if self.editorView:
            self.editorView.source = source

    def setStationery_(self, tmpl):
        is_untitled = tmpl.startswith('TMPL:')
        is_example = os.path.exists(tmpl) and not is_untitled
        if is_example:
            # self.source = file(tmpl).read().decode("utf-8")
            self.source = open(tmpl, encoding='utf-8').read()
            if self.document():
                # when an example script is opened, setStatioenry is called before the
                # ScriptController gets a reference to the document and the doc handles
                # setting the title.
                #
                # when restored at launch, the stationery value doesn't get unpacked until
                # after an untitled doc gets created. thus we have a self.document reference
                # and should set the title to the example's name (rather than "Untitled")
                self.document().setDisplayName_(os.path.basename(tmpl).replace('.pv',''))
                self.synchronizeWindowTitleWithDocumentName()
        elif is_untitled:
            from plotdevice.util.ottobot import genTemplate
            self.source = genTemplate(tmpl.split(':',1)[1])

    def awakeFromNib(self):
        win = self.window()
        win.setPreferredBackingLocation_(NSWindowBackingLocationVideoMemory)
        win.useOptimizedDrawing_(True)

        # place the statusView in the title bar
        frame = win.frame()
        win.contentView().superview().addSubview_(self.statusView)
        self.statusView.setFrame_( ((frame.size.width-104,frame.size.height-22), (100,22)) )

        # sign up for autoresume on quit-and-relaunch (but only if this isn't console.py)
        if self.editorView:
            win.setRestorable_(True)

        # always a reference to either the in-window view or a fullscreen view
        self.currentView = self.graphicsView

    ## WindowController duties

    def windowDidLoad(self):
        # the editor might not exist if we're being opened in console.py
        if self.editorView:
            # pass the editor a reference to the undomanager so it can sync up with the
            # menus and the file's dirty-state
            self.editorView._undo_mgr = self.document().undoManager()

            # if the document was loaded from disk (rather than stationery/untitled), the
            # setPath_Source_ call came before the editorview was loaded from the nib.
            # now that the editor has woken up, we can populate it.
            if self.vm.source:
                self.editorView.source = self.vm.source


    def encodeRestorableStateWithCoder_(self, coder):
        # walk through editor's superviews to autosave the splitview positions
        if self.editorView:
            split_frames = []
            it = self.editorView
            while it.superview():
                if type(it) is NSSplitView:
                    sub_frames = [NSStringFromRect(sub.frame()) for sub in it.subviews()]
                    split_frames.append(sub_frames)
                    if len(split_frames) == 2:
                        break
                it = it.superview()
            coder.encodeObject_forKey_(split_frames, "plotdevice:split_rects")
        super(ScriptController, self).encodeRestorableStateWithCoder_(coder)


    def restoreStateWithCoder_(self, coder):
        # restore the splitview positions (if rects were autosaved)
        split_frames = coder.decodeObjectForKey_("plotdevice:split_rects")
        if split_frames:
            it = self.editorView
            while it.superview():
                if type(it) is NSSplitView:
                    first, second = [NSRectFromString(s) for s in split_frames.pop(0)]
                    for sub, rect in zip(it.subviews(), [first,second]):
                        sub.setFrame_(rect)
                    if not split_frames:
                        break
                it = it.superview()
        super(ScriptController, self).restoreStateWithCoder_(coder)

    ## Window behavior

    def windowDidResignKey_(self, note):
        if self.editorView:
            self.editorView.blur()
            self.editorView.window().makeFirstResponder_(None)

    def windowDidBecomeKey_(self, note):
        if self.editorView:
            self.editorView.window().makeFirstResponder_(self.editorView)
            set_timeout(self.editorView, 'focus', 0.1)

    def windowWillUseStandardFrame_defaultFrame_(self, win, rect):
        container = self.graphicsView.superview().superview().superview().superview() # nssplitview or nsview
        frame = win.frame()
        current = frame.size
        gworld = self.graphicsView.frame().size
        scrollview = self.graphicsView.superview().superview().superview().frame().size
        thumb_w = 1 if type(container) is NSSplitView else 0 # no thumb when running from command line

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

    def windowWillClose_(self, note):
        self.stopScript()

        # break some retain cycles on our way out
        self.vm._cleanup()
        if self.editorView:
            self.editorView._cleanup()
            self.outputView._cleanup()
        self.graphicsView = self.outputView = self.editorView = self.statusView = None
        self.dashboardController = self.exportSheet = self.vm = None

    def shouldCloseDocument(self):
        return True

    #
    # Running the script in the main window
    #

    @IBAction
    def runScript_(self, sender):
        # listens for cmd-r
        if self.vm.session:
            return NSBeep()
        self.runScript()

    @IBAction
    def runFullscreen_(self, sender):
        # listens for cmd-shift-r
        if not self.fullScreen:
            # create a full-screen window to draw in
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
        self.runScript()

    def runScript(self):
        """Compile the script and run its global scope.

        For non-animated scripts, this is a whole run since all of their drawing and control
        flow is at the module level. For animated scripts, this is just a first pass to populate
        the namespace with the script's variables and particularly the setup/draw/stop functions.

        If a draw() function is defined, we'll start the animationTimer which will repeatedly
        call self.invoke('draw') until cancelled by the user.
        """

        # halt any animation that was already running
        if self.animationTimer:
            self.animationTimer.invalidate()
            self.animationTimer = None

        # get all the output progress indicators going
        self.statusView.beginRun()
        if (self.outputView):
            self.editorView.clearErrors()
            self.outputView.clear(timestamp=True)

        # Compile the script and run its global scope
        self.vm.source = self.source
        success = self.invoke(None)

        # Display the dashboard if the var() command was called
        if self.vm.vars:
            self.dashboardController.buildInterface(self.vm.vars)

        if not success or not self.vm.animated:
            # halt the progress indicator if we crashed (or if we succeeded in a non-anim)
            self.statusView.endRun()

            # don't mess with the gui window-state if running in fullscreen until the
            # user explicitly cancels with esc or cmd-period
            if success and not self.fullScreen:
                self.stopScript()

            return # either way, the run is complete

        # Check whether we are dealing with animation
        if self.vm.animated:

            # Run setup routine
            self.invoke("setup")

            if not self.vm.crashed:
                # calling speed(0) just draws the first frame, so bail out before repeating
                if self.vm.speed<=0:
                    return self.step()

                # shift the focus so we can catch mouse events in the canvas
                window = self.currentView.window()
                window.makeFirstResponder_(self.currentView)

                # Start the timer
                self.animationTimer = set_timeout(self, 'step', 1.0/self.vm.speed, repeat=True)


    def step(self):
        """Keep calling the script's draw method until an error occurs or the animation complete."""
        ok = self.invoke("draw")
        if not ok:
            self.stopScript()

    def invoke(self, method):
        """Call a method defined in the script's global namespace and update the ui appropriately

        If `method` exists in the namespace, it is called. If it's undefined, the invocation
        is ignored and no error is raised. If the method is None, the script's global scope
        will be run, but no additional methods will be called.

        Returns a boolean flagging whether the call was successful.
        """
        # Run the script
        self.vm.state = self._ui_state()
        result = self.vm.run(method=method)
        self.echo(result.output)

        # only update the view during animations after the script's draw()
        # method is called (otherwise a blank canvas flashes on the screen
        # during the compilation and setup() calls.
        redraw = not self.vm.animated or method=='draw'

        # Display the output of the script
        if result.ok and redraw:
            try:
                self.currentView.setCanvas(self.vm.canvas)
            except DeviceError, e:
                return self.crash()
        if not result.ok and method in (None, "setup"):
            self.stopScript()
        if result.ok=='HALTED':
            self.stopScript()

        return result.ok

    def echo(self, output):
        """Pass a list of (isStdErr, txt) tuples to the output window"""
        for isErr, data in output:
            self.outputView.append(data, stream='err' if isErr else 'message')

    def _ui_state(self):
        """Collect mouse & keyboard events to be spliced into the script's namespace"""
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

    #
    # Exporting to file(s)
    #
    @IBAction
    def exportAsImage_(self, sender):
        if self.vm.session:
            return NSBeep()
        self.exportSheet.beginExport('image')

    @IBAction
    def exportAsMovie_(self, sender):
        if self.vm.session:
            return NSBeep()
        self.exportSheet.beginExport('movie')

    def exportInit(self, kind, fname, opts):
        """Begin actual export (invoked by self.exportSheet unless sheet was cancelled)"""
        if self.animationTimer is not None:
            self.stopScript()

        # if this is a single-image export and the canvas already contains some grobs,
        # write it out synchronously rather than starting up an export session
        if kind=='image' and opts['last']==opts['first'] and list(self.vm.canvas):
            img_data = self.vm.canvas._getImageData(opts['format'])
            img_data.writeToFile_atomically_(fname, True)
            self.exportStatus('complete')
            return

        # if we're exporting multiple frames, give some ui feedback
        if self.outputView:
            self.outputView.clear(timestamp=True)
        if self.statusView:
            self.statusView.beginExport()

        # let the Sandbox take over
        self.vm.source = self.source
        self.vm.export(kind, fname, opts)

    def exportFrame(self, status, canvas=None):
        """Handle a newly rendered frame (and any console output it generated)"""
        if status.output:
            # print any console messages
            self.echo(status.output)

        if canvas and self.window() and self.vm._meta.frame % 2:
            # blit the canvas to the graphics view            ^ (but only every other frame)
            self.currentView.setCanvas(canvas)

    def exportProgress(self, written, total, cancelled):
        """Update the progress meter in the StatusView (invoked by self.vm.session)"""
        if self.statusView:
            self.statusView.updateExport_total_(written, total)

    def exportStatus(self, event):
        """Handle an export-lifecycle event (invoked by self.vm.session)"""

        if self.statusView:
            # give ui feedback for export state
            if event=='cancelled': self.statusView.finishExport()
            elif event=='complete': self.statusView.endExport()

        if event=='complete':
            # shut down the export ui
            self.stopScript()

    #
    # Interrupting the run
    #
    @IBAction
    def stopScript_(self, sender=None):
        # catch command-period
        if self.vm.session:
            self.vm.session.cancel()
        else:
            self.stopScript()

    def cancelOperation_(self, sender):
        # catch the escape key
        self.stopScript_(sender)

    def stopScript(self):
        # if we're currently animating, finish up the draw loop
        if self.animationTimer:
            self.animationTimer.invalidate()
            self.animationTimer = None

            # run stop() method if the script defines one
            result = self.vm.stop()
            self.echo(result.output)

        # disable progress spinner
        if self.statusView and not self.vm.session:
            self.statusView.endRun()

        # relay any errors to the text panes (if we're in the app)
        if self.editorView:
            self.editorView.report(self.vm.crashed, self.vm.path or "<Untitled>")
            self.outputView.report(self.vm.crashed, self.vm.namespace.get('FRAME') if self.vm.animated else None)

        # return from fullscreen (if applicable)
        if self.fullScreen is not None:
            # copy the final frame back to the window's view
            self.graphicsView.setCanvas(self.vm.canvas)
            self.currentView = self.graphicsView

            # close the fullscreen window
            NSMenu.setMenuBarVisible_(True)
            self.fullScreen.performClose_(self)
            self.fullScreen = None
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


    def crash(self):
        # called by the graphicsview when a grob blows up with unexpected input
        errtxt = self.vm.die()
        self.echo([(True, errtxt)])
        self.stopScript()


    #
    # Pasteboards
    #
    @IBAction
    def copyImageAsPDF_(self, sender):
        pboard = NSPasteboard.generalPasteboard()
        # graphicsView implements the pboard delegate method to provide the data
        pboard.declareTypes_owner_([NSPDFPboardType,NSPostScriptPboardType,NSTIFFPboardType], self.graphicsView)


    #
    # Zoom commands, forwarding to the graphics view.
    #
    @IBAction
    def zoomIn_(self, sender):
        if self.fullScreen is not None: return
        self.graphicsView.zoomIn_(sender)

    @IBAction
    def zoomOut_(self, sender):
        if self.fullScreen is not None: return
        self.graphicsView.zoomOut_(sender)

    @IBAction
    def zoomToTag_(self, sender):
        if self.fullScreen is not None: return
        self.graphicsView.zoomTo_(sender.tag() / 100.0)

    @IBAction
    def zoomToFit_(self, sender):
        if self.fullScreen is not None: return
        self.graphicsView.zoomToFit_(sender)

# separate document class for public.python-source files
class PythonScriptDocument(PlotDeviceDocument):
    pass

def errorAlert(msgText, infoText):
    # Force NSApp initialisation.
    NSApplication.sharedApplication().activateIgnoringOtherApps_(0)
    alert = NSAlert.alloc().init()
    alert.setMessageText_(msgText)
    alert.setInformativeText_(infoText)
    alert.setAlertStyle_(NSCriticalAlertStyle)
    btn = alert.addButtonWithTitle_("OK")
    return alert.runModal()
