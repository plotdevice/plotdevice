# encoding: utf-8
"""
console.py

Simple renderer for `.pv' scripts when run from the console rather than in-app.

This is the back-end of the module's __main__.py command line interface. It expects the parsed args
from the front-end to be passed as a dict to its run() method

If an export option was specified, the output file(s) will be generated and the script will terminate
once disk i/o completes. Otherwise a window will open to display the script's output and will remain
until dismissed by quitting the app or sending a ctrl-c from the console.
"""

import os
import sys
import json
import select
import signal
from math import floor, ceil
from os.path import dirname, abspath, exists, join
from io import open

from ..run import objc, encoded
from ..lib.cocoa import *
from ..lib.io import SysAdmin
from ..util import rsrc_path
from ..gui import ScriptController, next_tick

from PyObjCTools import AppHelper
from AppKit import NSRunningApplication

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
            icon = NSImage.alloc().initWithContentsOfFile_(rsrc_path('PlotDeviceFile.icns'))
            app.setApplicationIconImage_(icon)
        return app

class ScriptAppDelegate(NSObject):
    script = objc.IBOutlet()
    window = objc.IBOutlet()
    menu = objc.IBOutlet()

    def initWithOpts_(self, opts):
        self.opts = opts
        return self

    def applicationDidFinishLaunching_(self, note):
        opts = self.opts
        pth = opts['script']

        if self.opts['mode']=='windowed':
            # load the viewer ui from the nib in plotdevice/rsrc
            nib = NSData.dataWithContentsOfFile_(rsrc_path('viewer.nib'))
            ui = NSNib.alloc().initWithNibData_bundle_(nib, None)
            ok, objs = ui.instantiateNibWithOwner_topLevelObjects_(self, None)

            NSApp().setMainMenu_(self.menu)

            # configure the window script-controller, and update-watcher
            self.script.setScript_options_(pth, opts)
            self.window.setTitleWithRepresentedFilename_(pth)
            # self.script.setWindowFrameAutosaveName_('plotdevice:%s'%opts['file'])

            # foreground the window (if -b wasn't passed) and run the script
            if opts['activate']:
                NSApp().activateIgnoringOtherApps_(True)
            self.script.showWindow_(self)
            AppHelper.callAfter(self.script.scriptedRun)
        elif self.opts['mode']=='headless':
            # create a window-less WindowController
            self.script = ConsoleScript.alloc().init()
            self.script.setScript_options_(pth, opts)

            # make sure the frame count is finite
            if not opts.get('last', None):
                opts['last'] = opts.get('first', 1)

            if opts['export']:
                # kick off an export session
                format = opts['export'].rsplit('.',1)[1]
                kind = 'movie' if format in ('mov','gif') else 'image'
                self.script.exportInit(kind, opts['export'], opts)
            else:
                self.script.runHeadless()

    @objc.IBAction
    def openLink_(self, sender):
        link = 'http://plotdevice.io'
        if sender.tag() > 0:
            link += '/doc'
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(link))

    def done(self, quit=False):
        if self.opts['mode']=='headless' or quit:
            NSApp().terminate_(None)

class ScriptWatcher(NSObject):
    def initWithScript_(self, script):
        self.script = script
        self.mtime = os.path.getmtime(script.path)
        SysAdmin.watchFile_for_onUpdate_(script.path, script, '_refresh')
        return self

    def stale(self):
        file_mtime = os.path.getmtime(self.script.path)
        if file_mtime > self.mtime:
            self.mtime = file_mtime
            return True

class ConsoleScript(ScriptController):

    def init(self):
        self._init_state()
        self._buf = '' # cache the export progress message between stdout writes
        return super(ScriptController, self).init()

    def setScript_options_(self, path, opts):
        self.vm.path = path
        self.vm.source = self.unicode_src
        self.vm.metadata = opts
        self.opts = opts
        self.watcher = ScriptWatcher.alloc().initWithScript_(self)

    @property
    def unicode_src(self):
        """Read in our script file's contents (honoring its `# encoding: ...` if present)"""
        enc = encoded(self.path)
        return open(self.path, encoding=enc).read()

    def scriptedRun(self):
        # this is the first run that gets triggered at invocation
        # afterward any menu commands will go to runScript and runFullscreen
        if self.opts['fullscreen']:
            self.runFullscreen_(None)
        else:
            self.runScript()

    def _refresh(self):
        # file changed: reread the script (and potentially run it)
        if not self.watcher.stale():
            return # file was re-saved but not changed
        self.vm.source = self.unicode_src
        if self.opts['live']:
            self.scriptedRun()

    def runScript(self):
        if self.watcher.stale():
            self.vm.source = self.unicode_src
        super(ConsoleScript, self).runScript()

    def runFullscreen_(self, sender):
        if self.watcher.stale():
            self.vm.source = self.unicode_src
        super(ConsoleScript, self).runFullscreen_(sender)

    def windowWillClose_(self, note):
        NSApp().terminate_(self)

    @objc.python_method
    def invokeHeadless(self, method):
        result = self.vm.run(method)
        self.echo(result.output)
        if not result.ok:
            NSApp().terminate_(None)

    def runHeadless(self):
        self.vm.source = self.unicode_src
        self.invokeHeadless(None)
        self.invokeHeadless('setup')

        if self.vm.animated:
            self.redrawHeadless()
        else:
            NSApp().terminate_(None)

    def redrawHeadless(self):
        self.invokeHeadless('draw')
        self.loop = next_tick(self, 'redrawHeadless')

    @objc.python_method
    def echo(self, output):
        STDERR.write(ERASER)
        for isErr, data in output:
            stream = STDERR if isErr else STDOUT
            stream.write(data)
            stream.flush()
        if self._buf:
            STDERR.write(self._buf)
            STDERR.flush()

    @objc.python_method
    def exportFrame(self, status, canvas=None):
        super(ConsoleScript, self).exportFrame(status, canvas)
        if not status.ok:
            NSApp().delegate().done()

    @objc.python_method
    def exportStatus(self, event):
        super(ConsoleScript, self).exportStatus(event)

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

    @objc.python_method
    def exportProgress(self, written, total, cancelled):
        super(ConsoleScript, self).exportProgress(written, total, cancelled)

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



def run(opts):
    # install a signal handler to catch ^c
    SysAdmin.handleInterrupt()

    app = ScriptApp.sharedApplicationForMode_(opts['mode'])
    delegate = ScriptAppDelegate.alloc().initWithOpts_(opts)
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()
