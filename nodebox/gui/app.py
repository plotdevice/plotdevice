import sys
import os
import objc
from glob import glob

from Foundation import *
from AppKit import *
from nodebox.gui.preferences import get_default
from nodebox.run import CommandListener
from nodebox import util

class NodeBoxAppDelegate(NSObject):
    examplesMenu = None

    def awakeFromNib(self):
        self._prefsController = None
        self._docsController = NSDocumentController.sharedDocumentController()
        self._listener = CommandListener(port=get_default('remote-port'))
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
        self.examplesMenu = NSApp().mainMenu().itemWithTitle_('Examples')

    def listenOnPort_(self, port):
        if self._listener and self._listener.port == port:
            return
        newlistener = CommandListener(port=port)
        if self._listener:
            self._listener.join()
        self._listener = newlistener
        newlistener.start()
        return newlistener.active

    def updateExamples(self):
        examples_folder = os.path.join(NSBundle.mainBundle().bundlePath(), "Contents/Resources/examples")
        pyfiles = glob('%s/*/*.py'%examples_folder)
        categories = self.examplesMenu.submenu()
        folders = {}
        for item in categories.itemArray():
            item.submenu().removeAllItems()
            folders[item.title()] = item.submenu()
        for fn in sorted(pyfiles):
            cat = os.path.basename(os.path.dirname(fn))
            example = os.path.basename(fn)
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(example[:-3], "openExample:", "")
            item.setRepresentedObject_(fn)
            folders[cat].addItem_(item)
        self.examplesMenu.setHidden_(not pyfiles)

    def openExample_(self, sender):
        pth = sender.representedObject()
        doc, err = self._docsController.makeUntitledDocumentOfType_error_("public.python-script", None)
        doc.stationery = pth
        self._docsController.addDocument_(doc)
        doc.makeWindowControllers()
        doc.showWindows()

    def applicationWillBecomeActive_(self, note):
        # check for filesystem changes while the app was inactive
        for doc in self._docsController.documents():
            url = doc.fileURL()
            if url and os.path.exists(url.fileSystemRepresentation()):
                doc.refresh()
        self.updateExamples()

    @objc.IBAction
    def showPreferencesPanel_(self, sender):
        if self._prefsController is None:
            from nodebox.gui.preferences import NodeBoxPreferencesController
            self._prefsController = NodeBoxPreferencesController.alloc().init()
        self._prefsController.showWindow_(sender)

    @objc.IBAction
    def generateCode_(self, sender):
        """Generate a piece of NodeBox code using OttoBot"""
        from util.ottobot import genProgram
        controller = NSDocumentController.sharedDocumentController()
        doc = controller.newDocument_(sender)
        doc = controller.currentDocument()
        doc.setSource_(genProgram())
        doc.runScript()

    # @objc.IBAction
    # def showHelp_(self, sender):
    #     url = NSURL.URLWithString_("http://nodebox.net/code/index.php/Reference")
    #     NSWorkspace.sharedWorkspace().openURL_(url)

    @objc.IBAction
    def showSite_(self, sender):
        url = NSURL.URLWithString_("http://nodebox.net/")
        NSWorkspace.sharedWorkspace().openURL_(url)

    def applicationWillTerminate_(self, note):
        self._listener.join()
        import atexit
        atexit._run_exitfuncs()
