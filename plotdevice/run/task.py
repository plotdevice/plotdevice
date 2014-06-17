#!/usr/bin/env python
# encoding: utf-8
"""
task.py

Simple renderer for command line scripts when run from the module rather than an app bundle.

This is the back-end of the `plotdevice` command line script in the 'etc' subdir of the source
distribution (or the bin directory of your virtualenv once installed). It expects the parsed args
from the front-end to be passed as a json blob piped to stdin.

If an export option was specified, the output file(s) will be generated and the script will terminate
once disk i/o completes. Otherwise a window will open to display the script's output and will remain
until dismissed by quitting the app or sending a ctrl-c from the console.
"""

import sys
import os
import json
import select
import signal
from math import floor, ceil
from os.path import dirname, abspath, exists, join
from codecs import open

import plotdevice # adds pyobjc to sys.path as a side effect...
import objc # ...otherwise this would fail
from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper
from plotdevice.run import resource_path
from plotdevice.gui import ScriptController

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
            icon = NSImage.alloc().initWithContentsOfFile_(resource_path('viewer.icns'))
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
        pth = self.opts['file']
        src = file(pth).read()

        if self.mode=='windowed':
            # load the viewer ui from the nib in plotdevice/rsrc
            nib = NSData.dataWithContentsOfFile_(resource_path('viewer.nib'))
            ui = NSNib.alloc().initWithNibData_bundle_(nib, None)
            ok, objs = ui.instantiateNibWithOwner_topLevelObjects_(self, None)
            NSApp().setMainMenu_(self.menu)

            # configure the window script-controller, and update-watcher
            self.script.setPath_source_options_(pth, src, self.opts)
            self.window.setTitleWithRepresentedFilename_(pth)
            # self.script.setWindowFrameAutosaveName_('plotdevice:%s'%self.opts['file'])

            # foreground the window (if -b wasn't passed) and run the script
            if opts['activate']:
                NSApp().activateIgnoringOtherApps_(True)
            self.script.showWindow_(self)
            AppHelper.callAfter(self.script.runScript)
        elif self.mode=='headless':
            # create a window-less WindowController
            self.script = ConsoleScript.alloc().init()
            self.script.setPath_source_options_(pth, src, self.opts)

            # BUG? FEATURE? (it's a mystery!)
            # not sure why this is necessary. does this not get validated by the
            # front end? should it be happening with every export session? maybe
            # interacts with the sandbox's zeroing out the --frames arg after
            # the first run?
            opts.setdefault('last', opts.get('first', 1))

            # kick off an export session
            format = self.opts['export'].rsplit('.',1)[1]
            kind = 'movie' if format in ('mov','gif') else 'image'
            self.script.exportConfig(kind, self.opts['export'], self.opts)

    def catchInterrupts_(self, sender):
        read, write, timeout = select.select([sys.stdin.fileno()], [], [], 0)
        for fd in read:
            if fd == sys.stdin.fileno():
                line = sys.stdin.readline().strip()
                if 'CANCEL' in line:
                    script = self.script
                    if script.vm.session:
                        script.vm.session.cancel()

                    if getattr(script,'animationTimer',None) is not None:
                        script.stopScript()
                    elif self.mode == 'windowed':
                        NSApp().delegate().done(quit=True)
        self.poll.waitForDataInBackgroundAndNotify()

    def done(self, quit=False):
        if self.mode=='headless' or quit:
            NSApp().terminate_(None)

class ScriptWatcher(NSObject):
    def initWithScript_(self, script):
        self.script = script
        self.mtime = os.path.getmtime(script.path)
        self._queue = NSOperationQueue.mainQueue()
        NSFileCoordinator.addFilePresenter_(self)
        return self

    def presentedItemURL(self):
        return NSURL.fileURLWithPath_(self.script.path)

    def presentedItemOperationQueue(self):
        return self._queue

    def presentedItemDidChange(self):
        # reload the doc if an external editor modified the file
        if self.stale():
            self.script.performSelectorOnMainThread_withObject_waitUntilDone_("_refresh", None, True)

    def stale(self):
        file_mtime = os.path.getmtime(self.script.path)
        if file_mtime > self.mtime:
            self.mtime = file_mtime
            return True

class ConsoleScript(ScriptController):

    def init(self):
        print "- init"
        self._init_state()
        return super(ScriptController, self).init()

    def setPath_source_options_(self, path, source, opts):
        self.vm.path = path
        self.vm.source = source
        self.vm.metadata = self.opts = opts
        self.watcher = ScriptWatcher.alloc().initWithScript_(self)

    def _refresh(self):
        self.vm.source = file(self.path).read()
        if self.opts['live']:
            self.runScript()

    def runScript(self):
        if self.watcher.stale():
            self.vm.source = file(self.path).read()
        super(ConsoleScript, self).runScript()

    def windowWillClose_(self, note):
        NSApp().terminate_(self)

    def echo(self, output):
        STDERR.write(ERASER)
        for isErr, data in output:
            stream = STDERR if isErr else STDOUT
            stream.write(data)
            stream.flush()

    def exportStatus(self, status, canvas=None):
        super(ConsoleScript, self).exportStatus(status, canvas)
        if not status.ok:
            NSApp().delegate().done()

    def exportProgress(self, written, total, cancelled):
        super(ConsoleScript, self).exportProgress(written, total, cancelled)
        if cancelled:
            msg = u'Cancelling export…'
        elif total==written:
            msg = u'Finishing export…'
        else:
            msg = "\rGenerating %i frames %s"%(total, progress(written, total))
        STDERR.write(ERASER + msg)
        STDERR.flush()

def progress(written, total, width=20):
    pct = int(ceil(width*written/float(total)))
    dots = "".join(['#'*pct]+['.']*(width-pct))
    return '[%s]' % dots

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
