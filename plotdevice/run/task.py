#!/usr/bin/env python
# encoding: utf-8
"""
task.py

Simple renderer for command line scripts when run from the module rather than an app bundle.

This is the back-end of the `plotdevice` command line script in the boot subdir of the distribution
(or the bin directory once installed). It expects the parsed args from the front-end to be passed
as a json blob piped to stdin.

If an export option was specified, the output file(s) will be generated and the script will terminate
once disk i/o completes. Otherwise a window will open to display the script's output and will remain
until dismissed by quitting the app or sending a ctrl-c from the console.
"""

import sys
import os
import json
import select
import signal
from math import floor
from os.path import dirname, abspath, exists, join
from codecs import open

import plotdevice
# plotdevice.initialize('gui') # adds pyobjc to sys.path as a side effect...
import objc # ...otherwise this would fail
from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper
from plotdevice.run import Sandbox, resource_path

STDOUT = sys.stdout
STDERR = sys.stderr
ERASER = '\r%s\r'%(' '*80)

class ScriptApp(NSApplication):
    @classmethod
    def sharedApplicationForMode_(cls, mode):
        app = super(ScriptApp, cls).sharedApplication()
        if mode=='headless':
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        elif mode=='windowed':
            icon = NSImage.alloc().initWithContentsOfFile_(resource_path('icon.icns'))
            app.setApplicationIconImage_(icon)
        return app

class ScriptAppDelegate(NSObject):
    script = objc.IBOutlet()
    window = objc.IBOutlet()
    menu = objc.IBOutlet()

    def initWithOpts_forMode_(self, opts, mode):
        self.opts = opts
        self.mode = mode
        self.poll = NSFileHandle.fileHandleWithStandardInput()

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, "catchInterrupts:", "NSFileHandleDataAvailableNotification", None)
        self.poll.waitForDataInBackgroundAndNotify()
        return self

    def applicationDidFinishLaunching_(self, note):
        if self.mode=='headless':
            self.script = PlotDeviceScript.alloc().initWithOpts_forMode_(self.opts, self.mode)
            self.script.export()
        elif self.mode=='windowed':
            nib = NSData.dataWithContentsOfFile_(resource_path('PlotDeviceScript.nib'))
            ui = NSNib.alloc().initWithNibData_bundle_(nib, None)
            ok, objs = ui.instantiateNibWithOwner_topLevelObjects_(self, None)
            self.script.initWithOpts_forMode_(self.opts, self.mode)
            self.window.setTitleWithRepresentedFilename_(self.opts['file'])
            NSApp().setMainMenu_(self.menu)

            self._wc = NSWindowController.alloc().initWithWindow_(self.window)
            self._wc.setShouldCascadeWindows_(False)
            self._wc.setWindowFrameAutosaveName_('plotdevice:%s'%self.opts['file'])
            self._wc.showWindow_(self)

            self._watch = PlotDeviceScriptReloader.alloc().initWithScript_(self.script)

            if opts['activate']:
                NSApp().activateIgnoringOtherApps_(True)
            AppHelper.callAfter(self.script.runScript)

    def catchInterrupts_(self, sender):
        read, write, timeout = select.select([sys.stdin.fileno()], [], [], 0)
        for fd in read:
            if fd == sys.stdin.fileno():
                line = sys.stdin.readline().strip()
                if 'CANCEL' in line:
                    self.script.cancel()
        self.poll.waitForDataInBackgroundAndNotify()

    def done(self, quit=False):
        if self.mode=='headless' or quit:
            NSApp().terminate_(None)

# from plotdevice.lib.fsevents import Observer
from plotdevice.gui.app import PlotDeviceDocumentController
class PlotDeviceScriptReloader(PlotDeviceDocumentController):
    def initWithScript_(self, doc):
        self._script = doc
        # self._observer = Observer()
        # self._observer.start()
        self.updateWatchList_(None)
        return self

    def documents(self):
        return [self._script]

from plotdevice.gui.document import PlotDeviceDocument
class PlotDeviceScript(PlotDeviceDocument):
    def initWithOpts_forMode_(self, opts, mode):
        self.opts = opts
        self.windowed = mode=='windowed'
        self.vm = Sandbox(self)
        self.vm.path = opts['file']
        self.vm.source = self.source
        # self.fullScreen = False
        return self

    def awakeFromNib(self):
        self._showFooter = True
        self.currentView = self.graphicsView
        win = self.graphicsView.window()
        win.setAutorecalculatesContentBorderThickness_forEdge_(True,NSMinYEdge)
        win.setContentBorderThickness_forEdge_(22.0,NSMinYEdge)
        self.toggleStatusBar_(self) # hide status bar by default
        win.makeFirstResponder_(self.graphicsView)

    def windowWillClose_(self, note):
        NSApp().terminate_(self)

    def fileName(self):
        return self.vm.path

    @property
    def source(self):
        return open(self.opts['file'], encoding='utf-8').read()

    def refresh(self):
        if self.opts.get('live'):
            self.runScript()

    def runScript(self):
        self.vm.source = self.source
        self.vm.metadata = self.opts
        super(PlotDeviceScript, self).runScript()

        # hrm, the existence of w/h no longer proves anything. need to find another predicate
        # for autosizing the window...

        # resize the window to fit
        # first_run = not(hasattr(self.vm.namespace,'WIDTH') or hasattr(self.vm.namespace,'HEIGHT'))
        # if first_run and self.graphicsView:
        #     win = self.graphicsView.window()
        #     cw,ch = self.vm.namespace['WIDTH'], self.vm.namespace['HEIGHT']
        #     ch += 22 if self._showFooter else 0
        #     self.graphicsView.window().setContentSize_( (cw, ch) )

    def echo(self, output):
        STDERR.write(ERASER)
        for isErr, data in output:
            stream = STDERR if isErr else STDOUT
            stream.write(data)
            stream.flush()

    def export(self):
        opts = dict(self.opts)
        fname = opts['export']
        opts['format'] = fname.rsplit('.',1)[1]
        opts.setdefault('last', opts.get('first', 1))
        self.vm.metadata = opts

        # pick the right kind of output (single movie vs multiple docs)
        kind = 'movie' if opts['format'] in ('mov','gif') else 'image'
        self.vm.export(kind, fname, opts)

    def exportConfig(self, kind, fname, opts):
        """Override PlotDeviceDocument's behavior for windowed mode"""
        if self.animationTimer is not None:
            self.stopScript()
        self.opts.update(opts)
        self.opts['export'] = fname
        self.export()

    def exportStatus(self, status, canvas=None):
        # print "stat", status
        if status.ok:
            self.echo(status.output)
        else:
            STDERR.write('\r')
            STDERR.flush()
            self.echo(status.output)
            NSApp().delegate().done()

    def exportProgress(self, written, total, cancelled):
        # print "progress", written, total, cancelled
        if cancelled:
            msg = u'Cancelling export…'
        else:
            width = 20
            pct = int(floor(width*written/total))
            dots = "".join(['#'*pct]+['.']*(width-pct))
            msg = "\rGenerating %i frames [%s]"%(total, dots)

            if (total==written):
                msg = u'Finishing export…'
        STDERR.write(ERASER+msg)
        STDERR.flush()

    def cancel(self):
        if self.vm.session:
            self.vm.session.cancel()

        if getattr(self,'animationTimer',None) is not None:
            self.stopScript()
        elif self.windowed:
            NSApp().delegate().done(quit=True)

if __name__ == '__main__':
    try:
        opts = json.loads(sys.stdin.readline())
        mode = 'headless' if opts['export'] else 'windowed'
    except ValueError:
        print "bad args"
        sys.exit(1)

    app = ScriptApp.sharedApplicationForMode_(mode)
    delegate = ScriptAppDelegate.alloc().initWithOpts_forMode_(opts, mode)
    app.setDelegate_(delegate)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    AppHelper.runEventLoop(installInterrupt=False)
