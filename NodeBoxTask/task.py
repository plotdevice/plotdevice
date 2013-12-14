#!/usr/bin/env python
# encoding: utf-8
"""
NodeBoxTask.py

Headless renderer for command line export tasks
"""

import sys
import os
import json
import objc
import traceback
from AppKit import NSApplication
from Foundation import *
from PyObjCTools import AppHelper
nodebox_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append("%s/python"%nodebox_dir)

import nodebox
from nodebox.export import MovieExportSession, ImageExportSession
from nodebox import graphics
from nodebox import util

objc.setVerbose(True)

class NodeBoxRunner(object):
    
    def __init__(self, src_or_path):
        src, fname = src_or_path, '<Untitled>'
        if os.path.exists(src_or_path):
            src = file(src_or_path).read().decode('utf-8')
            fname = src_or_path
        self._code = compile(src+"\n\n", fname, 'exec')
        self.namespace = {}
        self.canvas = graphics.Canvas()
        self.context = graphics.Context(self.canvas, self.namespace)
        self.__doc__ = {}
        self._pageNumber = 1
        self.frame = 1
        self.session = None

    def _check_animation(self):
        """Returns False if this is not an animation, True otherwise.
        Throws an expection if the animation is not correct (missing a draw method)."""
        if self.canvas.speed is not None:
            if not self.namespace.has_key('draw'):
                raise graphics.NodeBoxError('Not a correct animation: No draw() method.')
            return True
        return False

    def run(self):
        self._initNamespace()
        exec self._code in self.namespace
        if self._check_animation():
            if self.namespace.has_key('setup'):
                self.namespace['setup']()
            self.namespace['draw']()

    def run_multiple(self, frames, first=1):
        # First frame is special:
        self.run()
        yield first
        animation = self._check_animation()
            
        for i in range(first, frames):
            self.canvas.clear()
            self.context._resetContext()
            self.frame = i + 1
            self.namespace["PAGENUM"] = self.namespace["FRAME"] = self.frame
            if animation:
                self.namespace['draw']()
            else:
                exec self._code in self.namespace
            sys.stdout.flush()
            yield self.frame
    
    def _initNamespace(self, frame=1):
        self.canvas.clear()
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
        # Add the frame
        self.frame = frame
        self.namespace["PAGENUM"] = self.namespace["FRAME"] = self.frame

    def export(self, **opts):
        fn, first, last, fps = opts['export'], opts['first'], opts['last'], opts['fps']
        format = fn.rsplit('.',1)[1]
        if last:
            # pick the right kind of output (single movie vs multiple docs)
            if format in ('mov','gif'):
                self.session = MovieExportSession(fname=fn, frames=last, fps=fps, first=first, console=True)
                self.session.bitrate = opts['rate']
            else:
                self.session = ImageExportSession(fname=fn, pages=last, format=format, first=first, console=True)
            self._run_session(last, first)
        else:
            self._run_single()

    def _run_single(self, fn):
        self.run()
        self.canvas.save(fn)
        quit()

    def _run_session(self, frames, first):
        try:
            for frame in self.run_multiple(frames, first=first):
                self.session.add(self.canvas, frame)
                date = NSDate.dateWithTimeIntervalSinceNow_(0.05);
                NSRunLoop.currentRunLoop().acceptInputForMode_beforeDate_(NSDefaultRunLoopMode, date)
        except KeyboardInterrupt:
            print "\rWrote %i/%i"%(frame, frames)
        except:
            etype, value, tb = sys.exc_info()
            while tb and 'NodeBoxTask.app' in tb.tb_frame.f_code.co_filename:
                tb = tb.tb_next
            errtxt = "".join(traceback.format_exception(etype, value, tb))
            sys.stdout.write(errtxt)
            self.session._shutdown()
            AppHelper.callAfter(quit)            
        else:
            self.session.on_complete(quit)
            self.session.done()

def quit():
    NSApplication.sharedApplication().terminate_(None)

def main():
    opts = json.loads(sys.stdin.readline())
    runner = NodeBoxRunner(opts['file'])
    runner.export(**opts)

if __name__ == '__main__':
    main()
