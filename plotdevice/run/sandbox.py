import os, sys, re
from os.path import dirname, basename, abspath, relpath, isdir
from functools import partial
from inspect import getargspec
from collections import namedtuple
from PyObjCTools import AppHelper
from Foundation import *
from AppKit import *
from ..lib.io import MovieExportSession, ImageExportSession
from .common import stacktrace, coredump, uncoded
from plotdevice import util, context, gfx, Halted, DeviceError

__all__ = ['Sandbox']

Outcome = namedtuple('Outcome', ['ok', 'output'])
Output = namedtuple('Output', ['isErr', 'data'])

class Metadata(object):
    __slots__ = 'args', 'virtualenv', 'first', 'frame', 'last', 'loop'
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
    def exportFrame(self, status, canvas=None):
        pass
    def exportStatus(self, status):
        pass
    def exportProgress(self, written, total):
        pass

class Sandbox(object):

    def __init__(self, delegate=None):
        self._meta = None       # runtime opts for the script
        self._path = None       # file path to the active script
        self._source = None     # unicode contents of script
        self._code = None       # byte-compiled source
        self._anim = None       # persistent dict passed to animation functions in script
        self.canvas = None      # can be handed off to views or exporters to access the image
        self.context = None     # quartz playground
        self.namespace = {}     # a reference to the script's namespace (managed by self.context)
        self.crashed = False    # flag whether the script exited abnormally
        self.live = False       # whether to keep the output pipe open between runs
        self.session = None     # the image/movie export session (if any)
        self.delegate = None    # object with exportFrame and exportProgress methods


        # set up the graphics plumbing
        self.canvas = context.Canvas()
        self.context = context.Context(self.canvas, self.namespace)
        self.delegate = delegate or Delegate()

        # control params used during exports and console-based runs
        self._meta = Metadata(args=[], virtualenv=None, # environmant
                              first=1, frame=1, last=None, # runtime
                              loop=False) # export opts

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
        return self._anim is not None or callable(self.namespace.get('draw',None))

    @property
    def tty(self):
        """Whether the script's output is being redirected to a pipe (r)"""
        return getattr(self.delegate, 'graphicsView', None) is None

    def _preflight(self):
        """Set up a namespace for the script and prepare it for rendering"""

        # Initialize the namespace
        self.context._resetEnvironment()

        # add a pathname (if the script exists on the filesystem)
        if self._path:
            self.namespace['__file__'] = self._path

        # start off with all systems nominal (fingers crossed)
        self.crashed = False
        result = Outcome(True, [])
        self._meta.frame = self._meta.first
        self._anim = None

        # if our .source attr has been changed since the last run, compile it now
        if not self._code:
            def compileScript():
                # _source is already unicode so strip out the `encoding:` comment
                src = uncoded(self._source)
                scriptname = self._path or "<Untitled>"
                fname = scriptname.encode('ascii', 'ignore')
                self._code = compile(src, fname, "exec")
            result = self.call(compileScript)
            if not result.ok:
                return result

        return result

    def run(self, method=None, cmyk=False):
        """Clear the context and run either the entire script or a specific method."""

        # if this is the initial pass, reset the namespace and canvas state
        if method is None:
            check = self._preflight() # compile the script
            self.context._outputmode = 'cmyk' if cmyk else 'rgb'
            if not check.ok:
                return check

        # Clear the canvas
        self.canvas.clear()

        # Reset the context state (and bind the .gfx objects as a side-effect)
        self.context._resetContext()

        # Set the frame/pagenum
        self.namespace['PAGENUM'] = self.namespace['FRAME'] = self._meta.frame

        # Run the specified method (or script's top-level if None)
        result = self.call(method)

        # (non-animation scripts are now complete (as are anims that just crashed))

        if self.animated and result.ok:
            # animations require special bookkeeping depending on which routine is being run
            if method is None:
                # we're in the initial pass through the script so flag the run as ongoing
                self._anim = util.adict()

                # default to 30fps if speed() wasn't called in the script
                if self.speed is None:
                    self.canvas.speed = 30

                # determine which of the script's routines accept an argument
                for routine in 'setup','draw','stop':
                    func = self.namespace.get(routine)
                    # replace each such routine with a partial application passing
                    # the dict. this means we can .call() it without any explicit args
                    if callable(func) and getargspec(func).args:
                        self.namespace[routine] = partial(self.namespace[routine], self._anim)

            elif method=='draw':
                # tick the frame ahead after each draw call
                self._meta.frame+=1
                if self._meta.frame > self._meta.last and self._meta.loop:
                    self._meta.frame = self._meta.first

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
        elif callable(self.namespace.get(method, None)):
            method = self.namespace[method]
        elif not callable(method):
            # silently skip over undefined methods (convenient if a script lacks 'setup' or 'draw')
            return Outcome(True, [])

        # find the script name and directory (or substitute placeholder values)
        if not self._path:
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
        output = StdIO()
        sys.stdout, sys.stderr = output.pipes
        if self._meta.virtualenv:
            sys.path.insert(0, self._meta.virtualenv)
        sys.path.insert(0, scriptDir)
        os.chdir(scriptDir)

        try:
            # run the code object we were passed
            method()
        except Halted:
            return Outcome('HALTED', output.data)
        except:
            # print the stacktrace and quit
            sys.stderr.write(self.die())
            return Outcome(False, output.data)
        finally:
            # restore the environment
            sys.stdout, sys.stderr = pipes
            os.chdir(cwd)
            sys.path = syspath
            sys.argv = argv
        return Outcome(True, output.data)

    def stop(self):
        """Called when an animated run is halted (voluntarily or otherwise)"""
        # print "stopping at", self._meta.frame-1, "of", self._meta.last
        result = Outcome(True, [])
        if not self.crashed:
            result = self.call("stop")
        return result

    def die(self):
        """Triggered by self.call() if the script raised an exception or by
        the ScriptController if the view bombed during canvas.draw()"""
        self.crashed = coredump(self._path, self._source)
        return stacktrace(self._path, self._source)

    def export(self, kind, fname, opts):
        """Export graphics and animations to image and movie files.

        args:
            kind - 'image' or 'movie'
            fname - path to outputfile
            opts - dictionary with required keys:
                     first, last, format
                   for a movie export also include:
                     bitrate, fps, loop
                   and for an image sequence:
                     cmyk, single
        """

        # pull off the file extension and use that as the format
        opts.setdefault('format', fname.lower().rsplit('.',1)[-1])

        # set the in/out frames for the export
        self._meta.first, self._meta.last = opts['first'], opts['last']

        # compile & evaluate the script once
        firstpass = self.run(cmyk=opts.get('cmyk',False))
        self.delegate.exportFrame(firstpass, canvas=None)
        if not firstpass.ok:
            return

        # call the script's setup() routine and pass the output along to the delegate
        if self.animated:
            setup = self.run("setup")
            self.delegate.exportFrame(setup)
            if not setup.ok:
                return

        # set up an export manager and attach the delegate's callbacks
        ExportSession = ImageExportSession if kind=='image' else MovieExportSession
        self.session = ExportSession(fname, **opts)
        self.session.on(progress=self.delegate.exportProgress,
                        status=self.delegate.exportStatus,
                        complete=self._exportComplete)

        # start looping through frames, calling draw() and adding the canvas
        # to the export-session on each iteration
        self._exportFrame()

    def _exportFrame(self):
        if self.session.next():
            # step to the proper FRAME value
            self._meta.frame = self.session.next()

            # run the draw() function if it exists (or the whole top-level if not)
            result = self.run(method="draw" if self.animated else None)

            # let the delegate draw to the screen
            self.delegate.exportFrame(result, self.canvas)

            # pass the frame content to the file-writer
            if result.ok:
                self.session.add(self.canvas)

            # know when to fold 'em
            if result.ok in (False, 'HALTED'):
                self.session.cancel()

            # give the runloop a chance to collect events between frames
            AppHelper.callLater(0.001, self._exportFrame)
        else:
            # we've drawn the final frame in the export
            result = self.call("stop")
            self.delegate.exportFrame(result, canvas=None)
            self.session.done()

    def _exportComplete(self):
        self.session = None

    def _cleanup(self):
        # self.session = None
        self.delegate = None

PY2 = sys.version_info[0] == 2
if not PY2:
    char_type = bytes
else:
    char_type = str

class StdIO(object):
    class OutputFile(object):
        def __init__(self, stream, streamname):
            self.stream = stream
            self.isErr = streamname=='stderr'

        def write(self, data):
            if isinstance(data, char_type):
                try:
                    data = unicode(data, "utf_8", "replace")
                except UnicodeDecodeError:
                    data = "XXX " + repr(data)
            self.stream.write(Output(self.isErr, data))

    def __init__(self):
        self.data = [] # the list of (isErr, txt) tuples .write calls go to

    @property
    def pipes(self):
        return self.OutputFile(self, 'stdout'), self.OutputFile(self, 'stderr')

    def write(self, output):
        self.data.append(output)
