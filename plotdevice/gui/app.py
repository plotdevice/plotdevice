# encoding: utf-8
import sys
import os
import objc
from glob import glob
import plotdevice
from Foundation import *
from AppKit import *
from plotdevice.gui.preferences import get_default
from plotdevice.run import CommandListener
from plotdevice.gui import bundle_path, set_timeout
from plotdevice import util

LIB_DIR_README = """"You can put PlotDevice libraries In this directory to make them available to your scripts.
"""

class PlotDeviceAppDelegate(NSObject):
    examplesMenu = None

    def awakeFromNib(self):
        self._prefsController = None
        self._docsController = NSDocumentController.sharedDocumentController()
        self._listener = CommandListener(port=get_default('remote-port'))
        libDir = os.path.join(os.getenv("HOME"), "Library", "Application Support", "PlotDevice")
        try:
            if not os.path.exists(libDir):
                os.mkdir(libDir)
                f = open(os.path.join(libDir, "README.txt"), "w")
                f.write(LIB_DIR_README)
                f.close()
            self._listener.start()
        except OSError: pass
        except IOError: pass
        self.examplesMenu = NSApp().mainMenu().itemWithTitle_('Examples')

    def applicationDidFinishLaunching_(self, note):
        mm=NSApp().mainMenu()

        # disable the start-dictation item in the edit menu
        edmenu = mm.itemAtIndex_(2).submenu()
        for it in edmenu.itemArray():
            action = it.action()
            if action in (NSSelectorFromString("startDictation:"), ):
                edmenu.removeItem_(it)

        # add a hidden item to the menus that can be triggered internally by the editor
        for menu in mm.itemArray()[2:5]:
            flicker = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_('Flash This Menu', None, '')
            flicker.setEnabled_(True)
            flicker.setHidden_(True)
            menu.submenu().insertItem_atIndex_(flicker,0)

    def applicationWillBecomeActive_(self, note):
        # rescan the examples dir every time?
        self.updateExamples()

    def updateExamples(self):
        examples_folder = bundle_path(rsrc="examples")
        pyfiles = glob('%s/*/*.pv'%examples_folder)
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

    @objc.IBAction
    def newSketch_(self, sender):
        kind = ['sketch','anim','ottobot'][sender.tag()]
        self.docFromTemplate_('TMPL:'+kind)
        if kind=='ottobot':
            doc.runScript()

    @objc.IBAction
    def openExample_(self, sender):
        tmpl = sender.representedObject()
        self.docFromTemplate_(tmpl)

    def docFromTemplate_(self, tmpl):
        """Open a doc with no undo state which contains either an example, or a new-sketch template"""
        doc, err = self._docsController.makeUntitledDocumentOfType_error_("io.plotdevice.document", None)
        doc.stationery = tmpl
        self._docsController.addDocument_(doc)
        doc.makeWindowControllers()
        doc.showWindows()
        return doc

    @objc.IBAction
    def showPreferencesPanel_(self, sender):
        if self._prefsController is None:
            from plotdevice.gui.preferences import PlotDevicePreferencesController
            self._prefsController = PlotDevicePreferencesController.alloc().init()
        self._prefsController.showWindow_(sender)

    @objc.IBAction
    def showHelp_(self, sender):
        url = NSURL.fileURLWithPath_(bundle_path(rsrc='doc/manual.html'))
        opened = NSWorkspace.sharedWorkspace().openURL_(url)

    @objc.IBAction
    def showSite_(self, sender):
        url = NSURL.URLWithString_("http://nodebox.net/")
        NSWorkspace.sharedWorkspace().openURL_(url)

    def listenOnPort_(self, port):
        if self._listener and self._listener.port == port:
            return
        newlistener = CommandListener(port=port)
        if self._listener:
            self._listener.join()
        self._listener = newlistener
        newlistener.start()
        return newlistener.active

    def applicationWillTerminate_(self, note):
        self._listener.join()
        import atexit
        atexit._run_exitfuncs()
