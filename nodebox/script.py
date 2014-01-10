"""
nodebox.script

Provides the standard NodeBox drawing environment to external scripts (see README.md for details).

Begin your script with:

    from nodebox.script import *

and all of the familiar NodeBox drawing commands will be added to the environment. Two additional 
variables have also been added to the global namespace:

    canvas (holder of the graphics context and a writer of image files)
    export (a helper function for doing batch image/animation exports)

"""

import nodebox
if nodebox.app:
    # become a no-op if imported inside the NodeBox app or command line tool
    __all__ = [] 
else:
    import time, sys
    from nodebox import graphics
    from nodebox import util
    from contextlib import contextmanager

    # Trivial subclass of graphics.Canvas that also resets the context when `clear` is called
    class Canvas(graphics.Canvas):
        """Holds the accumulated set of graphic objects drawn by the script (and can write them).

        When drawing commands are called by your script, the result is the addition of new graphics
        to the canvas. Once your drawing code has run, you can write the resulting graphic to a file
        by calling:

            canvas.save('output.pdf')

        to erase the canvas and start drawing something else, call:

            canvas.clear()
        """
        def clear(self):
            """Erase all graphics objects and reset the graphics context state"""
            super(Canvas, self).clear()
            if 'context' in globals():
                context._resetContext()

    # Context manager returned by `export` when an animation file extension is provided
    class Movie(object):
        """Represents a movie in the process of being assembled one frame at a time.

        The class can be used procedurally, but you need to be careful to call its methods
        in the correct order or a corrupt file may result:

            movie = export('anim.mov')
            for i in xrange(100):
                canvas.clear() # erase the previous frame from the canvas
                ...            # (do some drawing)
                movie.add()    # add the canvas to the movie
            movie.finish()     # wait for i/o to complete

        It can be used more simply as a context manager:

            with export('anim.mov') as movie:
                for i in xrange(100):
                    with movie.frame:
                        ... # draw the next frame
        """
        def __init__(self, *args, **opts):
            from nodebox.run.export import MovieExportSession
            self.session = MovieExportSession(*args, **opts)

        def __enter__(self):
            return self

        def __exit__(self, type, value, tb):
            self.finish()

        @property
        @contextmanager
        def frame(self):
            """Clears the canvas, runs the code in the `with` block, then adds the canvas to the movie.

            For example, to create a quicktime movie and write a single frame to it:
                with export("anim.mov") as movie:
                    with movie.frame:
                        rect(10,10,100,100)
            """
            canvas.clear()
            yield
            self.add()

        def add(self):
            """Add a new frame to the movie with the current contents of the canvas."""
            self.session.add(canvas)
            self._progress()

        def _progress(self):
            sys.stderr.write("\rExporting frame %i/%i"%self.session.count())

        def finish(self):
            """Finish writing the movie file.

            Signal that there are no more frames to be added and print progress messages until 
            the background thread has finished encoding the movie.
            """
            self.session.done()
            while True:
                self._progress()
                if self.session.writer.doneWriting():
                    break
                time.sleep(0.1)
            sys.stderr.write('\r%s\r'%(' '*80))
            sys.stderr.flush()

    # Context manager returned by `export` when an image-type file extension is provided
    class Image(object):
        def __init__(self, fname, format):
            self.fname = fname
        def __enter__(self):
          canvas.clear()
        def __exit__(self, type, value, tb):
          canvas.save(fname, format)

    def export(fname, fps=None, loop=None, bitrate=1.0):
        """Context manager for image/animation batch exports.

        When writing multiple images or frames of animation, the export manager keeps track of when
        the canvas needs to be cleared, when to write the graphics to file, and preventing the python
        script from exiting before the background thread has completed writing the file.

        To export an image:
            with export('output.pdf') as image:
                ... # (do some drawing)

        To export a movie:
            with export('anim.mov', fps=30, bitrate=1.8) as movie:
                for i in xrange(100):
                    with movie.frame:
                        ... # draw the next frame

        The file format is selected based on the file extension of the fname argument. If the format 
        is `gif`, an image will be exported unless an `fps` or `loop` argument (of any value) is
        also provided, in which case an animated gif will be created. Otherwise all arguments aside
        from the fname are optional and default to:
            fps: 30      (relevant for both gif and mov exports)
            loop: False  (set to True to loop forever or an integer for a fixed number of repetitions)
            bitrate: 1.0 (in megabits per second)

        Note that the `loop` argument only applies to animated gifs and `bitrate` is used in the H.264 
        encoding of `mov` files.
        """
        format = fname.rsplit('.',1)[1]
        if format=='mov' or (format=='gif' and fps or loop is not None):
            fps = fps or 30 # set a default for .mov exports
            loop = {True:-1, False:0, None:0}.get(loop, loop) # convert bool args to int
            return Movie(fname, format, fps=fps, bitrate=bitrate, loop=loop)
        elif format in ('pdf','eps','png','jpg','gif','tiff'):
            return Image(fname, format)
        else:
            unknown = 'Unknown export format "%s"'%format
            raise RuntimeError(unknown)

    # create a canvas and graphics context for the draw functions to operate on
    ns = {"export":export}
    canvas = Canvas()
    context = graphics.Context(canvas, ns)

    # set up the standard nodebox global namespace, all tied to the module-level canvas
    # (note that this means you shouldn't `import *` from this in more than one acript file
    # or unpredictable things may happen as you mutate global state in multiple places.)
    for module in graphics, util, context:
        ns.update( (a,getattr(module,a)) for a in module.__all__  )
    globals().update(ns)
    __all__ = ns.keys()
