# encoding: utf-8
import sys
import os
import objc
from glob import glob
from ..lib.cocoa import *
from PyObjCTools import AppHelper
from .preferences import PlotDevicePreferencesController, get_default
from . import bundle_path, set_timeout

LIB_DIR_README = """"You can put PlotDevice libraries In this directory to make them available to your scripts.
"""

class PlotDeviceAppDelegate(NSObject):
    examplesMenu = IBOutlet()
    updatesMenu = IBOutlet()

    def awakeFromNib(self):
        self._prefsController = None
        self._docsController = NSDocumentController.sharedDocumentController()
        libDir = os.path.join(os.getenv("HOME"), "Library", "Application Support", "PlotDevice")
        try:
            if not os.path.exists(libDir):
                os.mkdir(libDir)
                f = open(os.path.join(libDir, "README.txt"), "w")
                f.write(LIB_DIR_README)
                f.close()
        except OSError: pass
        except IOError: pass

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

        # If the sparkle framework was installed in our bundle, init an updater
        self.sparkle = None
        sparkle_path = bundle_path(fmwk='Sparkle')
        if os.path.exists(sparkle_path):
            objc.loadBundle('Sparkle', globals(), bundle_path=sparkle_path)
            self.sparkle = objc.lookUpClass('SUUpdater').sharedUpdater()
            self.updatesMenu.setTarget_(self.sparkle)
            self.updatesMenu.setAction_("checkForUpdates:")
            self.updatesMenu.setHidden_(False)


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

    @IBAction
    def newSketch_(self, sender):
        kind = ['sketch','anim','ottobot'][sender.tag()]
        doc = self.docFromTemplate_('TMPL:'+kind)
        if kind=='ottobot':
            AppHelper.callLater(0.1, doc.script.runScript)

    @IBAction
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

    @IBAction
    def showPreferencesPanel_(self, sender):
        if self._prefsController is None:
            self._prefsController = PlotDevicePreferencesController.alloc().init()
        self._prefsController.showWindow_(sender)

    @IBAction
    def showHelp_(self, sender):
        url = NSURL.URLWithString_("http://plotdevice.io/manual")
        NSWorkspace.sharedWorkspace().openURL_(url)

    @IBAction
    def showSite_(self, sender):
        url = NSURL.URLWithString_("http://plotdevice.io/")
        NSWorkspace.sharedWorkspace().openURL_(url)

    def applicationWillTerminate_(self, note):
        import atexit
        atexit._run_exitfuncs()
