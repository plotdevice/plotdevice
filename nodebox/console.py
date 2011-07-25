from AppKit import NSApplication

try:
    import nodebox
except ImportError:
    import sys, os
    nodebox_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(os.path.dirname(nodebox_dir))

from nodebox import graphics
from nodebox import util

class NodeBoxRunner(object):
    
    def __init__(self):
        # Force NSApp initialisation.
        NSApplication.sharedApplication().activateIgnoringOtherApps_(0)
        self.namespace = {}
        self.canvas = graphics.Canvas()
        self.context = graphics.Context(self.canvas, self.namespace)
        self.__doc__ = {}
        self._pageNumber = 1
        self.frame = 1
        
    def _check_animation(self):
        """Returns False if this is not an animation, True otherwise.
        Throws an expection if the animation is not correct (missing a draw method)."""
        if self.canvas.speed is not None:
            if not self.namespace.has_key('draw'):
                raise graphics.NodeBoxError('Not a correct animation: No draw() method.')
            return True
        return False

    def run(self, source_or_code):
        self._initNamespace()
        if isinstance(source_or_code, basestring):
            source_or_code = compile(source_or_code + "\n\n", "<Untitled>", "exec")
        exec source_or_code in self.namespace
        if self._check_animation():
            if self.namespace.has_key('setup'):
                self.namespace['setup']()
            self.namespace['draw']()
        
    def run_multiple(self, source_or_code, frames):
        if isinstance(source_or_code, basestring):
            source_or_code = compile(source_or_code + "\n\n", "<Untitled>", "exec")
            
        # First frame is special:
        self.run(source_or_code)
        yield 1
        animation = self._check_animation()
            
        for i in range(frames-1):
            self.canvas.clear()
            self.frame = i + 2
            self.namespace["PAGENUM"] = self.namespace["FRAME"] = self.frame
            if animation:
                self.namespace['draw']()
            else:
                exec source_or_code in self.namespace
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
        
def make_image(source_or_code, outputfile):
    
    """Given a source string or code object, executes the scripts and saves the result as an image.
    Supported image extensions: pdf, tiff, png, jpg, gif"""
    
    runner = NodeBoxRunner()
    runner.run(source_or_code)
    runner.canvas.save(outputfile)
    
def make_movie(source_or_code, outputfile, frames, fps=30):

    """Given a source string or code object, executes the scripts and saves the result as a movie.
    You also have to specify the number of frames to render.
    Supported movie extension: mov"""

    from nodebox.util import QTSupport
    runner = NodeBoxRunner()
    movie = QTSupport.Movie(outputfile, fps)
    for frame in runner.run_multiple(source_or_code, frames):
        movie.add(runner.canvas)
    movie.save()

def usage(err=""):
    if len(err) > 0:
        err = '\n\nError: ' + str(err)
    print """NodeBox console runner
Usage: console.py sourcefile imagefile
   or: console.py sourcefile moviefile number_of_frames [fps]
Supported image extensions: pdf, tiff, png, jpg, gif
Supported movie extension:  mov""" + err

def main():
    import sys, os
    if len(sys.argv) < 2:
        usage()
    elif len(sys.argv) == 3: # Should be an image
        basename, ext = os.path.splitext(sys.argv[2])
        if ext not in ('.pdf', '.gif', '.jpg', '.jpeg', '.png', '.tiff'):
            return usage('This is not a supported image format.')
        make_image(open(sys.argv[1]).read(), sys.argv[2])
    elif len(sys.argv) == 4 or len(sys.argv) == 5: # Should be a movie
        basename, ext = os.path.splitext(sys.argv[2])
        if ext != '.mov':
            return usage('This is not a supported movie format.')
        if len(sys.argv) == 5:
            try:
                fps = int(sys.argv[4])
            except ValueError:
                return usage()
        else:
            fps = 30
        make_movie(open(sys.argv[1]).read(), sys.argv[2], int(sys.argv[3]), fps)

def test():
    # Creating the NodeBoxRunner class directly:
    runner = NodeBoxRunner()
    runner.run('size(500,500)\nfor i in range(400):\n  oval(random(WIDTH),random(HEIGHT),50,50, fill=(random(), 0,0,random()))')
    runner.canvas.save('console-test.pdf')
    runner.canvas.save('console-test.png')
    
    # Using the runner for animations:
    runner = NodeBoxRunner()
    for frame in runner.run_multiple('size(300, 300)\ntext(FRAME, 100, 100)', 10):
        runner.canvas.save('console-test-frame%02i.png' % frame)

    # Using the shortcut functions:
    make_image('size(200,200)\ntext(FRAME, 100, 100)', 'console-test.gif')
    make_movie('size(200,200)\ntext(FRAME, 100, 100)', 'console-test.mov', 10)

if __name__=='__main__':
    main()