#!/usr/bin/env python
# encoding: utf-8
"""
task.py

Headless renderer for command line export tasks. 

This is the back-end of the console.py arg parser -- presuming an export option was specified.
Otherwise the command is handled by the nodebox.run.listener module.
"""

import sys
import os
import json
import objc
import select
import signal
from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper

lib_dir = os.path.abspath('%s/../..'%os.path.dirname(__file__))
sys.path.append(lib_dir)
from nodebox.run import Sandbox

objc.setVerbose(True)

def console_export(opts):
    STDOUT = sys.stdout
    STDERR = sys.stderr
    ERASER = '\r%s\r'%(' '*80)

    class QuietApplication(NSApplication):
        def sharedApplication(self):
            app = super(QuietApplication, self).sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory);
            return app

    class AppDelegate(NSObject):
        def initWithOpts_(self, opts):
            self.opts = opts
            return self
      
        def applicationDidFinishLaunching_(self, note):
            runner = NodeBoxRunner(self.opts['file'])
            runner.export(**self.opts)

    class NodeBoxRunner(object):
        def __init__(self, src_or_path):
            src, fname = src_or_path, '<Untitled>'
            if os.path.exists(src_or_path):
                src = file(src_or_path).read().decode('utf-8')
                fname = src_or_path

            self.vm = Sandbox(self)
            self.vm.source = src
            self.vm.script = fname

            signal.signal(signal.SIGINT, signal.SIG_IGN)

        def export(self, **opts):
            fn, first, last, fps, mbps, loop = [opts[k] for k in ('export','first','last','fps','rate','loop')]
            format = fn.rsplit('.',1)[1]
            self.vm.metadata = opts

            # pick the right kind of output (single movie vs multiple docs)
            if format in ('mov','gif'):
                self.vm.export('movie', fn, first, last, fps, loop, mbps)
            else:
                self.vm.export('image', fn, first, last, format)

        def echo(self, output):
            STDERR.write(ERASER)
            for o in output:
                pipe = STDERR if o.isErr else STDOUT
                pipe.write(o.data)
                pipe.flush()
        
        def exportMessage(self, output):
            self.echo(output)        

        def exportProgress(self, progressBar):
            STDERR.write(ERASER+progressBar)
            STDERR.flush()

            read, write, timeout = select.select([sys.stdin.fileno()], [], [], 0)
            for fd in read:
                if fd == sys.stdin.fileno():
                    line = sys.stdin.readline().strip()
                    if 'CANCEL' in line:
                        self.vm.session.cancel()

        def exportFrame(self, frameNum, canvas, result):
            self.echo(result.output)

        def exportFailed(self, output):
            STDERR.write('\r')
            STDERR.flush()
            self.echo(output)
            self.quit()

        def exportComplete(self):
            STDERR.write('\r')
            STDERR.flush()
            self.quit()

        def quit(self):
            NSApplication.sharedApplication().terminate_(None)


    app = QuietApplication.sharedApplication()
    delegate = AppDelegate.alloc().initWithOpts_(opts)
    app.setDelegate_(delegate)
    AppHelper.runEventLoop(installInterrupt=False)


if __name__ == '__main__':
    try:
        opts = json.loads(sys.stdin.readline())
    except ValueError:
        print "bad args"
        sys.exit(1)
    console_export(opts)