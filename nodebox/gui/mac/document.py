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
from nodebox.gui.mac import PyDETextView
from nodebox.gui.mac.ValueLadder import MAGICVAR
from nodebox.gui.mac.export import MovieExportSession, ImageExportSession
from nodebox.gui.mac.dashboard import *
from nodebox.gui.mac.util import errorAlert
from nodebox import util
from nodebox import graphics



# class defined in NodeBoxDocument.xib
class NodeBoxDocument(NSDocument):
    graphicsView = objc.IBOutlet()
    outputView = objc.IBOutlet()
    textView = objc.IBOutlet()
    window = objc.IBOutlet()
    variablesController = objc.IBOutlet()
    dashboardController = objc.IBOutlet()
    animationSpinner = objc.IBOutlet()
    # The ExportImageAccessory adds:
    exportImageAccessory = objc.IBOutlet()
    exportImageFormat = objc.IBOutlet()
    exportImagePageCount = objc.IBOutlet()
    # The ExportMovieAccessory adds:
    exportMovieAccessory = objc.IBOutlet()
    exportMovieFormat = objc.IBOutlet()
    exportMovieFrames = objc.IBOutlet()
    exportMovieFps = objc.IBOutlet()
    exportMovieLoop = objc.IBOutlet()
    # When the PageCount accessory is loaded, we also add:
    pageCount = objc.IBOutlet()
    pageCountAccessory = objc.IBOutlet()
    # When the ExportSheet is loaded, we also add:
    exportSheet = objc.IBOutlet()
    exportSheetIndicator = objc.IBOutlet()

    magicvar = None # Used for value ladders.
    _code = None
    vars = []
    path = None
    # file export config & state
    export = dict(formats=dict(image=('pdf', 'eps', 'png', 'tiff', 'jpg', 'gif'), movie=('mov', 'gif')),
                  movie=dict(format='mov', frames=150, fps=30, loop=0),
                  image=dict(format='png', pages=10),
                  dir=None, session=None)
    # run/export-related state
    _meta = dict(args=[], virtualenv=None, live=False,
                 export=None, first=1, last=None, stdout=None )    

    def windowNibName(self):
        return "NodeBoxDocument"

    def init(self):
        self = super(NodeBoxDocument, self).init()
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "textFontChanged:", "PyDETextFontChanged", None)
        self.namespace = {}
        self.canvas = graphics.Canvas()
        self.context = graphics.Context(self.canvas, self.namespace)
        self.animationTimer = None
        self.fullScreen = None
        self.currentView = None
        self.__doc__ = {}
        self._pageNumber = 1
        self._frame = 150
        self._seed = time.time()
        self._fileMD5 = None
        return self

    def windowControllerDidLoadNib_(self, controller):
        if self.path:
            self.readFromUTF8(self.path)
        font = PyDETextView.getBasicTextAttributes()[NSFontAttributeName]
        self.outputView.setFont_(font)
        self.textView.window().makeFirstResponder_(self.textView)
        self.textView.window().setPreferredBackingLocation_(NSWindowBackingLocationVideoMemory)
        self.currentView = self.graphicsView

        # disable system's auto-smartquotes (10.9+) in the editor pane
        try:
            self.textView.setAutomaticQuoteSubstitutionEnabled_(False)
            self.textView.setEnabledTextCheckingTypes_(0)
        except AttributeError:
            pass

    def autosavesInPlace(self):
        return True

    def close(self):
        self.stopScript()
        super(NodeBoxDocument, self).close()

    def refresh(self):
        """Reload source from file if it has been modified while the app was inactive"""
        url = self.fileURL()
        pth = url.fileSystemRepresentation()
        if os.path.exists(pth):
            try:
                filehash = md5(file(pth).read()).digest()
                if filehash != self._fileMD5:
                    self.revertToContentsOfURL_ofType_error_(url, self.fileType(), None)
                    if self._meta['live']:
                        self.runScript()
            except IOError:
                pass

    def __del__(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self, "PyDETextFontChanged", None)
        # text view has a couple of circular refs, it can let go of them now
        self.textView._cleanup()

    def textFontChanged_(self, notification):
        font = PyDETextView.getBasicTextAttributes()[NSFontAttributeName]
        self.outputView.setFont_(font)

    def readFromFile_ofType_(self, path, tp):
        if self.textView is None:
            # we're not yet fully loaded
            self.path = path
        else:
            # "revert"
            self.readFromUTF8(path)
        return True

    def _updateWindowAutosave(self):
        url = self.fileURL()
        if url:
            name = 'nodebox:%s'%url.fileSystemRepresentation()
            lower_splitview = self.textView.superview().superview().superview()
            upper_splitview = lower_splitview.superview()
            window_ctl = self.windowControllers()[0]

            window_ctl.setShouldCascadeWindows_(False)
            window_ctl.setWindowFrameAutosaveName_(name)
            lower_splitview.setAutosaveName_('%s - lower'%name)
            upper_splitview.setAutosaveName_('%s - upper'%name)

    def writeToFile_ofType_(self, path, tp):
        f = file(path, "w")
        text = self.source().encode("utf8")
        self._fileMD5 = md5(text).digest()
        self._updateWindowAutosave()
        f.write(text)
        f.close()
        return True

    def readFromUTF8(self, path):
        with file(path) as f:
            text = f.read()
            self._fileMD5 = md5(text).digest()
            self._updateWindowAutosave()
            self.setSource_(text.decode("utf-8"))
            self.textView.usesTabs = "\t" in text

    def cleanRun(self, fn, newSeed = True, buildInterface=True):
        self.animationSpinner.startAnimation_(None)

        # Prepare everything for running the script
        self.prepareRun()

        # Run the actual script
        success = self.fastRun(fn, newSeed)
        self.animationSpinner.stopAnimation_(None)

        if success and buildInterface:

            # Build the interface
            self.vars = self.namespace["_ctx"]._vars
            if len(self.vars) > 0:
                self.buildInterface_(None)

        return success

    def prepareRun(self):

        # Compile the script
        success, output = self._boxedRun(self._compileScript)
        self.outputView.clear(timestamp=True)
        self._flushOutput(output)
        if not success:
            return False

        # Initialize the namespace
        self._initNamespace()

        # Reset the pagenum
        self._pageNum = 1

        # Reset the frame
        self._frame = self._meta['first']

        self.speed = self.canvas.speed = None

    def fastRun(self, fn, newSeed = False):
        # Check if there is code to run
        if self._code is None:
            return False

        # Clear the canvas
        self.canvas.clear()

        # Generate a new seed, if needed
        if newSeed:
            self._seed = time.time()
        random.seed(self._seed)

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
        self.namespace["MOUSEX"], self.namespace["MOUSEY"] = mx, my
        self.namespace["mousedown"] = self.currentView.mousedown
        self.namespace["keydown"] = self.currentView.keydown
        self.namespace["key"] = self.currentView.key
        self.namespace["keycode"] = self.currentView.keycode
        self.namespace["scrollwheel"] = self.currentView.scrollwheel
        self.namespace["wheeldelta"] = self.currentView.wheeldelta

        # Reset the context
        self.context._resetContext()

        # Initalize the magicvar
        self.namespace[MAGICVAR] = self.magicvar

        # Set the pagenum
        self.namespace['PAGENUM'] = self._pageNumber

        # Set the frame
        self.namespace['FRAME'] = self._frame

        # Run the script
        success, output = self._boxedRun(fn)
        self._flushOutput(output)
        if not success:
            return False

        # Display the output of the script
        self.currentView.setCanvas(self.canvas)

        return True

    def scriptedRun(self, opts, stdout=None):
        meta = dict( (k, opts[k]) for k in ['args', 'virtualenv', 'live', 'first', 'last', 'stdout'] )
        self._meta = meta
        self.refresh()

        if opts['export']:
            fn = opts['export']
            if fn.endswith('mov') or fn.endswith('gif') and opts['last']:
                self.doExportAsMovie(fn, fps=opts['fps'],
                                         frames=opts['last'],
                                         first=opts['first'],
                                         loop=opts['loop'])
            else:
                self.doExportAsImage(fn, format=fn.rsplit('.',1)[1],
                                         pages=opts['last'] or 1,
                                         first=opts['first'])
        elif opts['fullscreen']:
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

    def runScript(self, compile=True, newSeed=True):
        if self.fullScreen is not None: return
        self.currentView = self.graphicsView
        self._runScript(compile, newSeed)

    def _runScript(self, compile=True, newSeed=True):
        # execute the script
        if not self.cleanRun(self._execScript):
            # syntax error. bail out before looping
            self._finishOutput()
        elif self.canvas.speed is not None:
            # Check whether we are dealing with animation
            if not self.namespace.has_key("draw"):
                errorAlert("Not a proper NodeBox animation",
                    "NodeBox animations should have at least a draw() method.")
                return

            # Check if animationTimer is already running
            if self.animationTimer is not None:
                self.stopScript()

            self.speed = self.canvas.speed

            # Run setup routine
            if self.namespace.has_key("setup"):
                self.fastRun(self.namespace["setup"])
            window = self.currentView.window()
            window.makeFirstResponder_(self.currentView)

            # Start the timer
            self.animationTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0 / self.speed, self, objc.selector(self.doFrame, signature="v@:@"), None, True)

            # Start the spinner
            self.animationSpinner.startAnimation_(None)
        else:
            self._finishOutput()

    def runScriptFast(self):
        if self.animationTimer is None:
            self.fastRun(self._execScript)
        else:
            # XXX: This can be sped up. We just run _execScript to get the
            # method with __MAGICVAR__ into the namespace, and execute
            # that, so it should only be called once for animations.
            self.fastRun(self._execScript)
            self.fastRun(self.namespace["draw"])

    def doFrame(self):
        ok = self.fastRun(self.namespace["draw"], newSeed=True)
        if not ok or self._frame==self._meta['last']:
            self.stopScript()
        else:
            self._frame += 1

    def source(self):
        return self.textView.string()

    def setSource_(self, source):
        self.textView.setString_(source)

    def cancelOperation_(self, sender):
        self.stopScript()

    @objc.IBAction
    def stopScript_(self, sender=None):
        self.stopScript()

    def stopScript(self):
        if self.namespace.has_key("stop"):
            success, output = self._boxedRun(self.namespace["stop"])
            self._flushOutput(output)
        self.animationSpinner.stopAnimation_(None)
        if self.animationTimer is not None:
            self.animationTimer.invalidate()
            self.animationTimer = None
        if self.fullScreen is not None:
            self.currentView = self.graphicsView
            self.fullScreen = None
            NSMenu.setMenuBarVisible_(True)
        NSCursor.unhide()
        self.textView.hideValueLadder()
        window = self.textView.window()
        window.makeFirstResponder_(self.textView)
        if self.export['session']:
            self.export['session'].status(cancel=True)
        self._finishOutput()

    def _compileScript(self, source=None):
        if source is None:
            source = self.source()
        self._code = None
        self._code = compile(source + "\n\n", self.scriptName.encode('ascii', 'ignore'), "exec")

    def _initNamespace(self):
        self.namespace.clear()
        # Add everything from the namespace
        for name in graphics.__all__:
            self.namespace[name] = getattr(graphics, name)
        for name in util.__all__:
            self.namespace[name] = getattr(util, name)
        # Add everything from the context object
        self.namespace["_ctx"] = self.context
        for attrName in dir(self.context):
            self.namespace[attrName] = getattr(self.context, attrName)
        # Add the document global
        self.namespace["__doc__"] = self.__doc__
        # Add the page number
        self.namespace["PAGENUM"] = self._pageNumber
        # Add the frame number
        self.namespace["FRAME"] = self._frame
        # Add the magic var
        self.namespace[MAGICVAR] = self.magicvar
        # XXX: will be empty after reset.
        #for var in self.vars:
        #    self.namespace[var.name] = var.value

    def _execScript(self):
        exec self._code in self.namespace
        self.__doc__ = self.namespace.get("__doc__", self.__doc__)

    def _boxedRun(self, method, args=[]):
        """
        Runs the given method in a boxed environment.
        Boxed environments:
         - Have their current directory set to the directory of the file
         - Have their argument set to the filename
         - Have their outputs redirect to an output stream.
        Returns:
           A tuple containing:
             - A boolean indicating whether the run was successful
             - The OutputFile
        """

        self.scriptName = self.fileName()
        libDir = os.path.join(os.getenv("HOME"), "Library", "Application Support", "NodeBox")
        if not self.scriptName:
            curDir = os.getenv("HOME")
            self.scriptName = "<untitled>"
        else:
            curDir = os.path.dirname(self.scriptName)
        save = sys.stdout, sys.stderr
        saveDir = os.getcwd()
        saveArgv = sys.argv
        savePath = list(sys.path)
        sys.argv = [self.scriptName] + self._meta.get('args',[])
        if os.path.exists(libDir):
            sys.path.insert(0, libDir)
        if self._meta['virtualenv']:
            sys.path.insert(0, self._meta['virtualenv'])
        os.chdir(curDir)
        sys.path.insert(0, curDir)
        output = []
        sys.stdout = OutputFile(output, False)
        sys.stderr = OutputFile(output, True)
        self._scriptDone = False
        try:
            if self.animationTimer is None:
                pass
                # Creating a thread is a heavy operation,
                # don't install it when animating, where speed is crucial
                #t = Thread(target=self._userCancelledMonitor, name="UserCancelledMonitor")
                #t.start()
            try:
                method(*args)
            except KeyboardInterrupt:
                self.stopScript()
            except:
                etype, value, tb = sys.exc_info()
                tb = self._prettifyStacktrace(etype, value, tb)
                etype = value = tb = None
                return False, output
        finally:
            self._scriptDone = True
            sys.stdout, sys.stderr = save
            os.chdir(saveDir)
            sys.path = savePath
            sys.argv = saveArgv
            #self._flushOutput()
        return True, output

    def _prettifyStacktrace(self, etype, value, tb):
        # remove the internal nodebox frames from the stacktrace
        while tb and 'nodebox/gui' in tb.tb_frame.f_code.co_filename:
            tb = tb.tb_next

        # make filenames relative to the script's dir
        errtxt = "".join(traceback.format_exception(etype, value, tb))
        if self.fileName():
            basedir = os.path.dirname(self.fileName())
            def relativize(m):
                abspath = m.group(2)
                relpath = os.path.relpath(m.group(2), basedir)
                pth = relpath if len(relpath)<len(abspath) else abspath
                return '%sFile "%s"'%(m.group(1), pth)
            errtxt = re.sub(r'( +)File "([^"]+)"', relativize, errtxt)
        sys.stderr.write(errtxt)

    # from Mac/Tools/IDE/PyEdit.py
    def _userCancelledMonitor(self):
        import time
        from signal import SIGINT
        from Carbon import Evt
        while not self._scriptDone:
            if Evt.CheckEventQueueForUserCancel():
                # Send a SIGINT signal to ourselves.
                # This gets delivered to the main thread,
                # cancelling the running script.
                os.kill(os.getpid(), SIGINT)
                break
            time.sleep(0.25)

    def _flushOutput(self, output):
        outAttrs = PyDETextView.getBasicTextAttributes()
        errAttrs = outAttrs.copy()
        # XXX err color from user defaults...
        errAttrs[NSForegroundColorAttributeName] = NSColor.redColor()

        outputView = self.outputView
        outputView.setSelectedRange_((outputView.textStorage().length(), 0))
        for isErr, data in output:
            outputView.append(data, stream='err' if isErr else 'message')
            if self._meta['stdout']:
                self._meta['stdout'].put(data.encode('utf8'))

        # del self.output

    def _finishOutput(self):
        if not self._meta['live']:
            self._meta['first'], self._meta['last'] = (1,None)
            if self._meta['stdout']:
                self._meta['stdout'].put(None)
                self._meta['stdout'] = None

    @objc.IBAction
    def copyImageAsPDF_(self, sender):
        pboard = NSPasteboard.generalPasteboard()
        # graphicsView implements the pboard delegate method to provide the data
        pboard.declareTypes_owner_([NSPDFPboardType,NSPostScriptPboardType,NSTIFFPboardType], self.graphicsView)

    @objc.IBAction
    def exportAsImage_(self, sender):
        exportPanel = self.imageExportPanel()
        path = self.fileName()
        if path:
            dirName, fileName = os.path.split(path)
            fileName, ext = os.path.splitext(fileName)
            fileName += "." + self.export['image']['format']
        else:
            dirName, fileName = None, "Untitled.%s"%self.export['image']['format']
        # If a file was already exported, use that folder as the default.
        if self.export['dir'] is not None:
            dirName = self.export['dir']

        exportPanel.beginSheetForDirectory_file_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            dirName, fileName, NSApp().mainWindow(), self,
            "imageExportPanelDidEnd:returnCode:contextInfo:", 0)

    def imageExportPanel(self):
        exportPanel = NSSavePanel.savePanel()

        # set defaults
        format_idx = self.export['formats']['image'].index(self.export['image']['format'])
        exportPanel.setNameFieldLabel_("Export To:")
        exportPanel.setPrompt_("Export")
        exportPanel.setCanSelectHiddenExtension_(True)
        if not NSBundle.loadNibNamed_owner_("ExportImageAccessory", self):
            NSLog("Error -- could not load ExportImageAccessory.")
        self.exportImagePageCount.setIntValue_(self.export['image']['pages'])
        self.exportImageFormat.selectItemAtIndex_(format_idx)
        exportPanel.setRequiredFileType_(self.export['image']['format'])
        exportPanel.setAccessoryView_(self.exportImageAccessory)
        return exportPanel

    def imageExportPanelDidEnd_returnCode_contextInfo_(self, panel, returnCode, context):
        if returnCode:
            fname = panel.filename()
            self.export['dir'] = os.path.split(fname)[0] # Save the directory we exported to.
            pages = self.exportImagePageCount.intValue()
            format = panel.requiredFileType()
            panel.close()
            self.export['image'] = dict(format=format, pages=pages)
            self.doExportAsImage(fname, format, pages)
    imageExportPanelDidEnd_returnCode_contextInfo_ = objc.selector(imageExportPanelDidEnd_returnCode_contextInfo_,
            signature="v@:@ii")

    @objc.IBAction
    def exportImageFormatChanged_(self, sender):
        panel = sender.window()
        format = self.export['formats']['image'][sender.indexOfSelectedItem()]
        panel.setRequiredFileType_(format)

    def doExportAsImage(self, fname, format, pages=1, first=1):
        if self.animationTimer is not None:
            self.stopScript()
        # When saving one page (the default), just save the current graphics
        # context. When generating multiple pages, we run the script again
        # (so we don't use the current displayed view) for the first page,
        # and then for every next page.
        if pages == 1:
            if self.graphicsView.canvas is None:
                self.runScript()
            self.canvas.save(fname, format)
        elif pages > 1:
            self.export['session'] = ImageExportSession(fname, pages, format, first=first)

            if not self.cleanRun(self._execScript): return
            self._pageNumber = first
            self._frame = first

            # # If the speed is set, we are dealing with animation
            if self.canvas.speed is not None and self.namespace.has_key("setup"):
                if self.namespace.has_key("setup"):
                    self.fastRun(self.namespace["setup"])
            AppHelper.callAfter(self._runExportBatch)

    def _runExportBatch(self):
        if self.export['session'].batches:
            first, last = self.export['session'].batches.pop(0)
            self._pageNumber = first
            self._frame = first

            # If the speed is set, we are dealing with animation
            if self.canvas.speed is None:
                for i in range(first, last+1):
                    if i > 0: # Run has already happened first time
                        self.fastRun(self._execScript, newSeed=True)
                    self.export['session'].add(self.canvas, self._frame)
                    self.graphicsView.setNeedsDisplay_(True)
                    self._pageNumber += 1
                    self._frame += 1
                    self.shareThread()
            else:
                for i in range(first, last+1):
                    self.fastRun(self.namespace["draw"], newSeed=True)
                    self.export['session'].add(self.canvas, self._frame)
                    self.graphicsView.setNeedsDisplay_(True)
                    self._pageNumber += 1
                    self._frame += 1
                    self.shareThread()

        if self.export['session'].batches:
            # keep running _runExportBatch until we run out of batches
            AppHelper.callLater(0.1, self._runExportBatch)
        else:
            # clean up after script and finish any sessions
            if self.canvas.speed is not None and self.namespace.has_key("stop"):
                # only run the stop() function in the user script is an animation
                success, output = self._boxedRun(self.namespace["stop"])
                self._flushOutput(output)
            self.export['session'].done()
            self._pageNumber = 1
            self._frame = 1
            if self.export['session'].running:
                self.export['session'].on_complete(self._finishOutput)
            else:
                self._finishOutput()

    @objc.IBAction
    def exportAsMovie_(self, sender):
        exportPanel = self.movieExportPanel()
        path = self.fileName()
        if path:
            dirName, fileName = os.path.split(path)
            fileName, ext = os.path.splitext(fileName)
            fileName += "." + self.export['movie']['format']
        else:
            dirName, fileName = None, "Untitled.%s" % self.export['movie']['format']
        # If a file was already exported, use that folder as the default.
        if self.export['dir'] is not None:
            dirName = self.export['dir']

        exportPanel.beginSheetForDirectory_file_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            dirName, fileName, NSApp().mainWindow(), self,
            "moviePanelDidEnd:returnCode:contextInfo:", 0)

    def movieExportPanel(self):
        exportPanel = NSSavePanel.savePanel()

        # set defaults
        format_idx = self.export['formats']['movie'].index(self.export['movie']['format'])
        should_loop = self.export['movie']['format']=='gif' and self.export['movie']['loop']==-1
        exportPanel.setNameFieldLabel_("Export To:")
        exportPanel.setPrompt_("Export")
        exportPanel.setCanSelectHiddenExtension_(True)
        exportPanel.setAllowedFileTypes_(self.export['formats']['movie'])
        if not NSBundle.loadNibNamed_owner_("ExportMovieAccessory", self):
            NSLog("Error -- could not load ExportMovieAccessory.")
        self.exportMovieFrames.setIntValue_(self.export['movie']['frames'])
        self.exportMovieFps.setIntValue_(self.export['movie']['fps'])
        exportPanel.setAccessoryView_(self.exportMovieAccessory)
        self.exportMovieFormat.selectItemAtIndex_(format_idx)
        exportPanel.setRequiredFileType_(self.export['movie']['format'])
        self.exportMovieLoop.setEnabled_(self.export['movie']['format']=='gif')
        self.exportMovieLoop.setState_(NSOnState if should_loop else NSOffState)
        return exportPanel

    def moviePanelDidEnd_returnCode_contextInfo_(self, panel, returnCode, context):
        if returnCode:
            fname = panel.filename()
            self.export['dir'] = os.path.split(fname)[0] # Save the directory we exported to.
            frames = self.exportMovieFrames.intValue()
            fps = self.exportMovieFps.floatValue()
            format_idx = self.exportMovieFormat.indexOfSelectedItem()
            format = self.export['formats']['movie'][format_idx]
            loop = -1 if self.exportMovieLoop.state()==NSOnState else 0
            self.export['movie'] = dict(format=format, frames=frames, fps=fps, loop=loop)
            panel.close()

            if frames <= 0 or fps <= 0: return
            self.doExportAsMovie(fname, frames, fps, loop=loop)
    moviePanelDidEnd_returnCode_contextInfo_ = objc.selector(moviePanelDidEnd_returnCode_contextInfo_,
            signature="v@:@ii")

    @objc.IBAction
    def exportMovieFormatChanged_(self, sender):
        panel = sender.window()
        format = self.export['formats']['movie'][sender.indexOfSelectedItem()]
        panel.setRequiredFileType_(format)
        self.exportMovieLoop.setEnabled_(format=='gif') # only gifs can loop
        self.exportMovieLoop.setState_(NSOnState if format=='gif' else NSOffState)

    def doExportAsMovie(self, fname, frames=60, fps=30, first=1, loop=0):
        if self.animationTimer is not None:
            self.stopScript()
        if not self.cleanRun(self._execScript): return
        self._pageNumber = first
        self._frame = first
        
        self.export['session'] = MovieExportSession(fname, frames, fps, loop, first=first)

        if self.canvas.speed is not None and self.namespace.has_key("setup"):
            self.fastRun(self.namespace["setup"])
            self.shareThread()
        AppHelper.callAfter(self._runExportBatch)

    def shareThread(self):
        # give the runloop a chance to collect events (rather than just beachballing)
        date = NSDate.dateWithTimeIntervalSinceNow_(0.05);
        NSRunLoop.currentRunLoop().acceptInputForMode_beforeDate_(NSDefaultRunLoopMode, date)

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

    @objc.IBAction
    def buildInterface_(self, sender):
        self.dashboardController.buildInterface(self.vars)

    def validateMenuItem_(self, menuItem):
        if menuItem.action() in ("exportAsImage:", "exportAsMovie:"):
            return self.canvas is not None
        return True

    # Zoom commands, forwarding to the graphics view.

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

class OutputFile(object):

    def __init__(self, data, isErr=False):
        self.data = data
        self.isErr = isErr

    def write(self, data):
        if isinstance(data, str):
            try:
                data = unicode(data, "utf_8", "replace")
            except UnicodeDecodeError:
                data = "XXX " + repr(data)
        self.data.append((self.isErr, data))

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
            NSApp.sendAction_to_from_('stopScript:', None, self)

    def keyUp_(self, event):
        self.keydown = False
        self.key = event.characters()
        self.keycode = event.keyCode()

    def scrollWheel_(self, event):
        self.scrollwheel = True
        self.wheeldelta = event.deltaY()

    def canBecomeKeyView(self):
        return True

    def acceptsFirstResponder(self):
        return True

def calc_scaling_factor(width, height, maxwidth, maxheight):
    return min(float(maxwidth) / width, float(maxheight) / height)
