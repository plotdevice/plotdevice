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
    # configure the module for non-gui use
    nodebox.initialize('headless')

    import time, sys, re
    from contextlib import contextmanager
    from Quartz.PDFKit import *
    from nodebox import graphics
    from nodebox import util

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

            For example, to create a quicktime movie and write a single frame to it you could write:

                with export("anim.mov") as movie:
                    canvas.clear()
                    ... # draw the frame
                    movie.add()

            With the `frame` context manager, this simplifies to:

                with export("anim.mov") as movie:
                    with movie.frame:
                        ... # draw the frame
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
    class ImageSequence(object):
        """Write a single image, or a numbered sequence of them.

        To save a single image:

            with export('output.png') as image:
                ... # draw something

        To draw a sequence of images, you can either handle the naming yourself:

            for i in xrange(100):
                with export('output-%03i.pdf'%i) as image:
                    ... # draw the next image in the sequence

        Or you can let the `sequence` context manager number them for you:

            with export('output.jpg') as image:
                for i in xrange(100):
                    with image.sequence:
                        ... # draw the next image in the sequence                    

        """
        def __init__(self, fname, format):
            self.fname = fname
            self.format = format
            self.idx = None
            if '#' in fname:
                head, tail = re.split(r'#+', fname, maxsplit=1)
                counter = '%%0%ii' % (len(fname) - len(head) - len(tail))
                self.tmpl = "".join([head,counter,tail.replace('#','')])
            else:
                self.tmpl = re.sub(r'^(.*)(\.[a-z]{3,4})$', r'\1-%04i\2', fname)
        def __enter__(self):
            canvas.clear()
            return self
        def __exit__(self, type, value, tb):
            if self.idx is None:
                canvas.save(self.fname, self.format)
        @property
        @contextmanager
        def sequence(self):
            """Clears the canvas, runs the code in the `with` block, then saves a numbered output file.

            For example, to a sequence of 10 images:
                with export('output.png') as image:
                    for i in xrange(100):
                        with image.sequence:
                            ... # draw the next image in the sequence
            """
            canvas.clear()
            yield
            if self.idx is None:
                self.idx = 1
            canvas.save(self.tmpl%self.idx, self.format)
            self.idx += 1

    # Context manager returned by `export` for PDF files (allowing single or multi-page docs)
    class PDF(object):
        """Represents a PDF document in the process of being assembled one page at a time.

        The class can be used procedurally to add frames and finish writing the output file:

            pdf = export('multipage.pdf')
            for i in xrange(5):
                canvas.clear() # erase the previous page's graphics from the canvas
                ...            # (do some drawing)
                pdf.add()      # add the canvas to the pdf as a new page
            pdf.finish()       # write the pdf document to disk

        It can be used more simply as a context manager:

            with export('multipage.pdf') as pdf:
                for i in xrange(5):
                    with pdf.page:
                        ... # draw the next page

            with export('singlepage.pdf') as pdf:
                ... # draw the one and only page
        """
        def __init__(self, fname):
            self.fname = fname
            self.doc = None
        def __enter__(self):
            canvas.clear()
            return self
        def __exit__(self, type, value, tb):
            self.finish() or canvas.save(self.fname, 'pdf')                

        @property
        @contextmanager
        def page(self):
            """Clears the canvas, runs the code in the `with` block, then adds the canvas as a new pdf page.

            For example, to create a pdf with two pages, you could write:

                with export("multipage.pdf") as pdf:
                    canvas.clear()
                    ... # draw first page
                    pdf.add()
                    canvas.clear()
                    ... # draw the next page
                    pdf.add()

            With the `page` context manager it simplifies to:

                with export("multipage.pdf") as pdf:
                    with pdf.page:
                        ... # draw first page
                    with pdf.page:
                        ... # draw the next page
            """
            canvas.clear()
            yield
            self.add()            

        def add(self):
            """Add a new page to the PDF with the current contents of the canvas."""
            pagedoc = PDFDocument.alloc().initWithData_(canvas._getImageData('pdf'))
            if not self.doc:
                self.doc = pagedoc
            else:
                self.doc.insertPage_atIndex_(pagedoc.pageAtIndex_(0), self.doc.pageCount())

        def finish(self):
            """Writes the fully-assembled PDF to disk"""
            if self.doc:
                self.doc.writeToFile_(self.fname)
            return self.doc

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

        For implementational details, inspect the format-specific exporters in the repl:
            help(export.PDF)
            help(export.Movie)
            help(export.ImageSequence)
        """
        format = fname.rsplit('.',1)[1]
        if format=='mov' or (format=='gif' and fps or loop is not None):
            fps = fps or 30 # set a default for .mov exports
            loop = {True:-1, False:0, None:0}.get(loop, loop) # convert bool args to int
            return Movie(fname, format, fps=fps, bitrate=bitrate, loop=loop)
        elif format=='pdf':
            return PDF(fname)
        elif format in ('eps','png','jpg','gif','tiff'):
            return ImageSequence(fname, format)
        else:
            unknown = 'Unknown export format "%s"'%format
            raise RuntimeError(unknown)

    # add references to the export context managers (so users can call help() on them)
    export.PDF = PDF
    export.Movie = Movie
    export.ImageSequence = ImageSequence

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
