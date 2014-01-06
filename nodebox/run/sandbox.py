import os, sys, re
import traceback
import random
from os.path import dirname, basename, abspath, relpath, isdir
from hashlib import md5
from codecs import open
from collections import namedtuple
from PyObjCTools import AppHelper
from Foundation import *
from AppKit import *
from nodebox.graphics import NodeBoxError
# from nodebox.gui.widgets import MAGICVAR
from nodebox import util
from nodebox import graphics
from nodebox.run.export import MovieExportSession, ImageExportSession
from nodebox.run import stacktrace

__all__ = ['Sandbox']

Outcome = namedtuple('Outcome', ['ok', 'output'])
Output = namedtuple('Output', ['isErr', 'data'])
PLUGIN_DIR = os.path.join(os.getenv("HOME"), "Library", "Application Support", "NodeBox")

class Metadata(object):
    __slots__ = 'args', 'virtualenv', 'first', 'next', 'last', 'console', 'running', 'loop'
    def __init__(self, **opts):
        for k,v in opts.items(): setattr(self,k,v)
    def update(self, changes):
        for k,v in changes.items(): 
            try: setattr(self,k,v)
            except AttributeError: pass
    def items(self):
        for k in self.__slots__:
            yield k, getattr(self, k)

class Sandbox(object):

    def __init__(self, delegate=None):
        self._env = {}          # the base namespace for the script (with all the gfx routines)
        self._meta = None       # runtime opts for the script
        self._script = None     # file path to the active script
        self._source = None     # unicode contents of script
        self._code = None       # byte-compiled source
        self.canvas = None      # can be handed off to views or exporters to access the image
        self.context = None     # quartz playground
        self.namespace = {}     # a mutable copy of _env with the user script's functions mixed in
        self.session = None     # the image/movie export session (if any)
        self.stationery = False # whether the script is from the examples folder
        self.delegate = None    # object with exportStatus and exportProgress methods

        # set up the graphics plumbing
        self.canvas = graphics.Canvas()
        self.context = graphics.Context(self.canvas, self.namespace)
        self.delegate = delegate

        # create a clean env to use as a template during runs
        re_private = re.compile(r'^_|_$')
        self._env.update( (a,getattr(graphics,a)) for a in graphics.__all__  )
        self._env.update( (a,getattr(util,a)) for a in util.__all__  )
        self._env.update( (a,getattr(self.context,a)) for a in dir(self.context) if not re_private.search(a) )
        self._env["_ctx"] = self.context
        self._meta = Metadata(args=[], virtualenv=None, first=1, next=1, last=None, running=False, console=None, loop=False)

    # .script
    def _get_script(self):
        """Path to the current python script (r/w)"""
        return self._script
    def _set_script(self, pth):
        if pth==self._script: return
        self._script = pth
    script = property(_get_script, _set_script)

    # .source
    def _get_source(self):
        """Contents of the current python script (r/w)"""
        return self._source
    def _set_source(self, src):
        if src==self._source: return
        self._source = src
        self._code = None
    source = property(_get_source, _set_source)

    # .state
    def _set_state(self, ui_state):
        """Update the mouse and keyboard globals in the namespace (w)"""
        # Update keyboard/mouse event globals
        self.namespace.update(ui_state)
    state = property(fset=_set_state)

    # .metadata
    def _get_meta(self):
        """Runtime parameters corresponding to the console.py command line switches (r/w)"""
        return dict(self._meta.items())
    def _set_meta(self, metadict):
        self._meta.update(metadict)
    metadata = property(_get_meta, _set_meta)

    @property
    def vars(self):
        """Script variables being tracked through the vars() method (r)"""
        return self.context._vars

    @property
    def speed(self):
        """Frames per second if an animation, None if not (r)"""
        return self.canvas.speed

    @property
    def animated(self):
        """Whether the script has multiple frames (r)"""
        return bool(self.canvas.speed)

    @property
    def running(self):
        """Whether the script still has frames to be rendered (r)"""
        if self._meta.running and self.canvas.speed and 'draw' in self.namespace:
            return self._meta.last is None or self._meta.next <= self._meta.last
        return self._meta.running

    @property
    def tty(self):
        """Whether the script's output is being redirected to a pipe (r)"""
        return getattr(self.delegate, 'graphicsView', None) is None
        # return self._meta.console is not None

    def compile(self, src=None):
        """Set up a namespace for the script (or src if specified) and prepare it for rendering"""
        if src:
            self.source = src

        # Initialize the namespace
        self.namespace.clear()
        self.namespace.update(dict(self._env))
        # self.namespace.update(dict( __doc__=self.__doc__, ))
        # self.namespace[MAGICVAR] = self.magicvar # Add the magic var

        result = Outcome(True, [])
        if not self._code:
            # Compile the script
            def compileScript():
                self._code = compile("%s\n\n"%self._source, self._script.encode('ascii', 'ignore'), "exec")
            result = self.call(compileScript)
            if not result.ok:
                return result
        
        # Reset the frame / animation status
        self._meta.running = False
        self._meta.next = self._meta.first
        self.canvas.speed = None
        return result

    def stop(self):
        """Called once the script has stop running (voluntarily or otherwise)"""
        # print "stopping at", self._meta.next-1, "of", self._meta.last
        result = Outcome(True, [])
        # if not self._meta.last or self._meta.next-1 == self._meta.last:
        if self._meta.running:
            result = self.call("stop")
            self._meta.running = False
        self._meta.first, self._meta.last = (1,None)
        if self._meta.console:
            self._meta.console.put(None)
            self._meta.console = None
        return result

    def render(self, method=None):
        """Run either the entire script or call a specific method"""
        # Check if there is code to run
        if self._code is None:
            self.compile()

        # Clear the canvas
        self.canvas.clear()

        # Reset the context
        self.context._resetContext()

        # Initalize the magicvar
        # self.namespace[MAGICVAR] = self.magicvar
        # print "render frame %i (%s)" % (self._meta.next, method)

        # Set the frame/pagenum
        self.namespace['PAGENUM'] = self.namespace['FRAME'] = self._meta.next
        
        # Run the script
        result = self.call(method)

        if self.animated:
            # flag that we're starting a new animation
            if method==None:
                self._meta.running = True                 
            # tick the frame ahead after each draw call
            elif method=='draw':
                self._meta.next+=1
                if self._meta.next > self._meta.last and self._meta.loop:
                    self._meta.next = self._meta.first

        return result

    def call(self, method=None):
        """
        Runs the given method in a boxed environment.
        Boxed environments:
         - Have their current directory set to the directory of the file
         - Have their argument set to the filename
         - Have their outputs redirect to an output stream.
        Returns:
           An namedtuple containing two fields:
             - "ok": A boolean indicating whether the run was successful
             - "output": The OutputFile
        """

        # default to running the script itself if a method (e.g., compile) isn't specified.
        if not method:
            def execScript():
                exec self._code in self.namespace
            method = execScript
        elif method in self.namespace:
            method = self.namespace[method]
        elif not callable(method):
            # silently skip over undefined methods (convenient if a script lacks 'setup' or 'draw')
            return Outcome(True, [])

        # find the script name and directory (or substitute placeholder values)
        if self.stationery:
            scriptDir = dirname(self.stationery)
            scriptName = basename(self.stationery)
        elif not self._script:
            scriptDir = os.getenv("HOME")
            scriptName = "<untitled>"
        else:
            scriptName = self._script
            scriptDir = dirname(scriptName)

        # save the external runtime environment
        pipes = sys.stdout, sys.stderr
        cwd = os.getcwd()
        argv = sys.argv
        syspath = list(sys.path)
        sys.argv = [scriptName] + self._meta.args

        # set up environment for script
        output = StdIO(pipe=self._meta.console)
        sys.stdout, sys.stderr = output.pipes
        if isdir(PLUGIN_DIR):
            sys.path.insert(0, PLUGIN_DIR)
        if self._meta.virtualenv:
            sys.path.insert(0, self._meta.virtualenv)
        sys.path.insert(0, scriptDir)
        os.chdir(scriptDir)

        try:
            # run the code object we were passed
            method()
        except:
            # print the stacktrace and quit
            errtxt = stacktrace(self._script)
            sys.stderr.write(errtxt)
            return Outcome(False, output.data)
        finally:
            # restore the environment
            sys.stdout, sys.stderr = pipes
            os.chdir(cwd)
            sys.path = syspath
            sys.argv = argv
        return Outcome(True, output.data)

    def export(self, kind, fname, opts):
        """Export graphics and animations to image and movie files.

        args:
            kind - 'image' or 'movie'
            fname - path to outputfile
            opts - dictionary with required keys:
                     first, last, format
                   and for a movie export, also include:
                     bitrate, fps, loop
        """
        compilation = self.compile() # compile the script
        self.delegate.exportStatus(compilation)
        if not compilation.ok:
            return

        firstpass = self.call() # evaluate the script once
        self.delegate.exportStatus(firstpass)
        if not firstpass.ok:
            return

        if self.animated:
            setup = self.call("setup")
            self.delegate.exportStatus(setup)
            if not setup.ok:
                return

        opts.setdefault('console', self.tty)
        opts.setdefault('first', 1)
        ExportSession = ImageExportSession if kind=='image' else MovieExportSession
        self.session = ExportSession(fname, **opts)
        self.session.on_progress(self.delegate.exportProgress)

        self._meta.first, self._meta.last = opts['first'], opts['last']
        self._runExportBatch()

    def _finishExport(self):
        self.session.done()
        if self.session.running:
            self.session.on_complete(self._exportComplete)
        else:
            self._exportComplete()

    def _exportComplete(self):
        self.session = None
        self.delegate.exportStatus(status=Outcome(None, [])) # the delegate should run vm.stop() on its own

    def _runExportBatch(self):
        if self.session.batches:
            first, last = self.session.batches.pop(0)

            method = "draw" if self.animated else None
            for i in range(first, last+1):
                if self.session.cancelled: 
                    break

                self._meta.next = i
                result = self.render(method)
                self.delegate.exportStatus(result, self.canvas)
                self.delegate.exportProgress(self.session.written, self.session.total, self.session.cancelled)
                if not result.ok:
                    self.session._shutdown()
                    return self._finishExport()
                self.session.add(self.canvas, i)

                # give the runloop a chance to collect events (rather than just beachballing)
                date = NSDate.dateWithTimeIntervalSinceNow_(0.05);
                NSRunLoop.currentRunLoop().acceptInputForMode_beforeDate_(NSDefaultRunLoopMode, date)

        if self.session.batches:
            # keep running _runExportBatch until we run out of batches
            AppHelper.callLater(0.1, self._runExportBatch)
        else:
            self._finishExport()
    
    def _cleanup(self):
        # self.session = None
        self.delegate = None


class StdIO(object):
    class OutputFile(object):
        def __init__(self, stream, streamname):
            self.stream = stream
            self.isErr = streamname=='stderr'

        def write(self, data):
            if isinstance(data, str):
                try:
                    data = unicode(data, "utf_8", "replace")
                except UnicodeDecodeError:
                    data = "XXX " + repr(data)
            self.stream.write(Output(self.isErr, data))

    def __init__(self, pipe=None):
        self.pipe = pipe # the console (if we were called outside of the app)
        self.data = [] # the list of (isErr, txt) tuples .write calls go to

    @property
    def pipes(self):
        return self.OutputFile(self, 'stdout'), self.OutputFile(self, 'stderr')

    def write(self, output):
        self.data.append(output)

        # and echo to console if we were passed a pipe
        if self.pipe:
            self.pipe.put(output.data.encode('utf8'))



