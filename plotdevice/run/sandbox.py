import os, sys, re
from os.path import dirname, basename, abspath, relpath, isdir
from functools import partial
from inspect import getargspec
from collections import namedtuple
from PyObjCTools import AppHelper
from Foundation import *
from AppKit import *
from ..run import stacktrace, coredump, encoding
from ..lib.io import MovieExportSession, ImageExportSession
from plotdevice import util, context, gfx, DeviceError

__all__ = ['Sandbox']

Outcome = namedtuple('Outcome', ['ok', 'output'])
Output = namedtuple('Output', ['isErr', 'data'])

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

class Delegate(object):
    """No-op sandbox delegate that will be used by default if a delegate isn't specified"""
    def exportStatus(self, status, canvas=None):
        pass
    def exportProgress(self, written, total, cancelled):
        pass

class Sandbox(object):

    def __init__(self, delegate=None):
        self._meta = None       # runtime opts for the script
        self._path = None       # file path to the active script
        self._source = None     # unicode contents of script
        self._code = None       # byte-compiled source
        self._stateful = []     # list of script functions that expect a state variable
        self._statevar = None   # persistent dict passed to animation functions in script
        self.canvas = None      # can be handed off to views or exporters to access the image
        self.context = None     # quartz playground
        self.namespace = {}     # a reference to the script's namespace (managed by self.context)
        self.crashed = False    # flag whether the script exited abnormally
        self.live = False       # whether to keep the output pipe open between runs
        self.session = None     # the image/movie export session (if any)
        self.stationery = False # whether the script is from the examples folder
        self.delegate = None    # object with exportStatus and exportProgress methods

        # set up the graphics plumbing
        self.canvas = context.Canvas()
        self.context = context.Context(self.canvas, self.namespace)
        self.delegate = delegate or Delegate()

        # control params used during exports and console-based runs
        self._meta = Metadata(args=[], virtualenv=None, first=1, next=1, last=None, running=False, console=None, loop=False)

    # .script
    def _get_path(self):
        """Path to the current python script (r/w)"""
        return self._path
    def _set_path(self, pth):
        if pth==self._path: return
        self._path = pth
    path = property(_get_path, _set_path)

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
        self.live = metadict.get('live', self.live)
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

    def _preflight(self):
        """Set up a namespace for the script and prepare it for rendering"""

        # Initialize the namespace
        self.context._resetEnvironment()

        # start off with all systems nominal (fingers crossed)
        self.crashed = False
        result = Outcome(True, [])
        self._meta.running = False
        self._meta.next = self._meta.first

        # if our .source attr has been changed since the last run, compile it now
        if not self._code:
            def compileScript():
                scriptname = self._path or "<Untitled>"
                # src needs to be a bytestring if the script defines its encoding in an
                # `encoding: ...` comment. otherwise just pass the unicode to compile()
                enc = encoding(self._source)
                src = self._source.encode(enc) if enc else self._source
                fname = scriptname.encode('ascii', 'ignore')
                self._code = compile(src, fname, "exec")
            result = self.call(compileScript)
            if not result.ok:
                return result

        return result

    def render(self, method=None):
        """Clear the context and run either the entire script or a specific method."""

        # if this is the initial pass, reset the namespace and canvas state
        if method is None:
            check = self._preflight() # compile the script
            if not check.ok:
                return check

        # Clear the canvas
        self.canvas.clear()

        # Reset the context state (and bind the .gfx objects as a side-effect)
        self.context._resetContext()

        # Set the frame/pagenum
        self.namespace['PAGENUM'] = self.namespace['FRAME'] = self._meta.next

        # Run the script's top-level
        result = self.call(method)

        # bail out if we crashed or we're a non-anim and are thus `done'
        if not result.ok or not self.animated:
            return result

        # if we're still here, deal with some special-handling for animations
        if method is None:
            # we're in the initial pass through the script so flag the run as ongoing
            self._meta.running = True

            # determine which of the script's routines expect a state varaiable
            self._stateful = []
            for routine in 'setup','draw','stop':
                func = self.namespace.get(routine)
                if func and getargspec(func).args:
                    self._stateful.append(routine)

            # allocate a fresh state var if any routines are using it
            self._statevar = util.adict() if self._stateful else None

        elif method=='draw':
            # tick the frame ahead after each draw call
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
            if method in self._stateful:
                method = partial(self.namespace[method], self._statevar)
            else:
                method = self.namespace[method]
        elif not callable(method):
            # silently skip over undefined methods (convenient if a script lacks 'setup' or 'draw')
            return Outcome(True, [])

        # find the script name and directory (or substitute placeholder values)
        if self.stationery:
            scriptDir = dirname(self.stationery)
            scriptName = basename(self.stationery)
        elif not self._path:
            scriptDir = os.getenv("HOME")
            scriptName = "<untitled>"
        else:
            scriptName = self._path
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
        if self._meta.virtualenv:
            sys.path.insert(0, self._meta.virtualenv)
        sys.path.insert(0, scriptDir)
        os.chdir(scriptDir)

        try:
            # run the code object we were passed
            method()
        except:
            # print the stacktrace and quit
            self.crashed = coredump(self._path, self._source)
            errtxt = stacktrace(self._path, self._source)
            sys.stderr.write(errtxt)
            return Outcome(False, output.data)
        finally:
            # restore the environment
            sys.stdout, sys.stderr = pipes
            os.chdir(cwd)
            sys.path = syspath
            sys.argv = argv
        return Outcome(True, output.data)

    def crash(self):
        self.crashed = coredump(self._path, self._source)
        return stacktrace(self._path, self._source)

    def stop(self):
        """Called once the script has stopped running (voluntarily or otherwise)"""
        # print "stopping at", self._meta.next-1, "of", self._meta.last
        result = Outcome(True, [])
        if self._meta.running:
            if not self.crashed:
                result = self.call("stop")
            self._meta.running = False
        self._meta.first, self._meta.last = (1,None)
        if self._meta.console and not self.live:
            self._meta.console.put(None)
            self._meta.console = None
        return result

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

        # compile & evaluate the script once
        firstpass = self.render()
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



