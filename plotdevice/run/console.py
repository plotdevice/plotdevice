#!/usr/bin/env python
# encoding: utf-8
"""
console.py

Simple renderer for `.pv' scripts when run from the console rather than in-app.

This is the back-end of the `plotdevice` command line script in the 'app' subdir of the source
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
from PyObjCTools import AppHelper
from plotdevice.lib.cocoa import *
from plotdevice.gui import ScriptController
from plotdevice.util import rsrc_path
from plotdevice.run import encoding

STDOUT = sys.stdout
STDERR = sys.stderr
ERASER = '\r%s\r'%(' '*80)

class ScriptApp(NSApplication):
    @classmethod
    def sharedApplicationForMode_(cls, mode):
        app = cls.sharedApplication()
        if mode=='headless':
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        elif mode=='windowed':
            icon = NSImage.alloc().initWithContentsOfFile_(rsrc_path('viewer.icns'))
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

        if self.mode=='windowed':
            # load the viewer ui from the nib in plotdevice/rsrc
            nib = NSData.dataWithContentsOfFile_(rsrc_path('viewer.nib'))
            ui = NSNib.alloc().initWithNibData_bundle_(nib, None)
            ok, objs = ui.instantiateNibWithOwner_topLevelObjects_(self, None)
            NSApp().setMainMenu_(self.menu)

            # configure the window script-controller, and update-watcher
            self.script.setScript_options_(pth, self.opts)
            self.window.setTitleWithRepresentedFilename_(pth)
            # self.script.setWindowFrameAutosaveName_('plotdevice:%s'%self.opts['file'])

            # foreground the window (if -b wasn't passed) and run the script
            if self.opts['activate']:
                NSApp().activateIgnoringOtherApps_(True)
            self.script.showWindow_(self)
            AppHelper.callAfter(self.script.scriptedRun)
        elif self.mode=='headless':
            # create a window-less WindowController
            self.script = ConsoleScript.alloc().init()
            self.script.setScript_options_(pth, self.opts)

            # BUG? FEATURE? (it's a mystery!)
            # exports will stall if `last` isn't an int. this should probably
            # be handled by the command line arg-parser though, no?
            if not opts.get('last',None):
                opts['last'] = opts.get('first', 1)

            # kick off an export session
            format = self.opts['export'].rsplit('.',1)[1]
            kind = 'movie' if format in ('mov','gif') else 'image'
            self.script.exportInit(kind, self.opts['export'], self.opts)

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

    @objc.IBAction
    def openLink_(self, sender):
        link = 'http://plotdevice.io'
        if sender.tag() > 0:
            link += '/doc'
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(link))


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
        if not self.stale():
            return
        # call the script's _refresh handler if the change-event wasn't spurious
        self.script.performSelectorOnMainThread_withObject_waitUntilDone_("_refresh", None, True)

    def stale(self):
        file_mtime = os.path.getmtime(self.script.path)
        if file_mtime > self.mtime:
            self.mtime = file_mtime
            return True

class ConsoleScript(ScriptController):

    def init(self):
        self._init_state()
        self._buf = '' # cache the export progress message between stdout writes
        return objc.super(ScriptController, self).init()

    def setScript_options_(self, path, opts):
        self.vm.path = path
        self.vm.source = self.unicode_src
        self.vm.metadata.update(opts)
        self.opts = opts
        self.watcher = ScriptWatcher.alloc().initWithScript_(self)

    @property
    def unicode_src(self):
        """Read in our script file's contents (honoring its `# encoding: ...` if present)"""
        if sys.version_info >= (3, 0):
            src = open(self.path, encoding = 'utf-8').read()
            enc = encoding(src) or 'utf-8'
            if enc != 'utf-8':
                src = open(self.path, encoding = enc).read()
            return src
        else:
            src = open(self.path).read()
            enc = encoding(src) or 'utf-8'
            return src.decode(enc)

    def scriptedRun(self):
        # this is the first run that gets triggered at invocation
        # afterward any menu commands will go to runScript and runFullscreen
        if self.opts['fullscreen']:
            self.runFullscreen_(None)
        else:
            self.runScript()

    def _refresh(self):
        # file changed: reread the script (and potentially run it)
        self.vm.source = self.unicode_src
        if self.opts['live']:
            self.scriptedRun()

    def runScript(self):
        if self.watcher.stale():
            self.vm.source = self.unicode_src
        objc.super(ConsoleScript, self).runScript()

    def runFullscreen_(self, sender):
        if self.watcher.stale():
            self.vm.source = self.unicode_src
        objc.super(ConsoleScript, self).runFullscreen_(sender)

    def windowWillClose_(self, note):
        NSApp().terminate_(self)

    def echo(self, output):
        STDERR.write(ERASER)
        for isErr, data in output:
            stream = STDERR if isErr else STDOUT
            stream.write(data)
            stream.flush()
        if self._buf:
            STDERR.write(self._buf)
            STDERR.flush()

    def exportFrame(self, status, canvas=None):
        objc.super(ConsoleScript, self).exportFrame(status, canvas)
        if not status.ok:
            NSApp().delegate().done()

    def exportStatus(self, event):
        objc.super(ConsoleScript, self).exportStatus(event)

        if event == 'cancelled':
            msg = 'Halted after %i frames. Finishing file I/O...\n' % self.vm.session.added
        else:
            msg = ''
        STDOUT.flush()
        STDERR.write(ERASER + msg)
        STDERR.flush()

        if event=='complete':
            self._buf = ''
            NSApp().delegate().done()

    def exportProgress(self, written, total, cancelled):
        objc.super(ConsoleScript, self).exportProgress(written, total, cancelled)

        if cancelled:
            msg = "%i frames to go..."%(total-written)
        else:
            padding = len(str(total)) - len(str(written))
            msg = "%s%i/%i frames written"%(' '*padding, written, total)

        dots = progress(written, total)
        self._buf = '\r%s %s\r%s'%(dots, msg, dots[:1+dots.count('#')])
        STDERR.write(ERASER + self._buf)
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
