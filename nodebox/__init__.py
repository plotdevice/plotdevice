"""
nodebox

Provides the standard drawing environment to external scripts (see README.md for details).

Begin your script with:

    from nodebox import *

and all of the familiar NodeBox drawing commands will be added to the environment. Two additional 
variables are also part of the global namespace:

    canvas (holder of the graphics context and a writer of image files)
    export (a helper function for doing batch image/animation exports)

"""

__version__='1.10'
__MAGIC = "_n_o_d_e_b_o_x_"

def get_version():
    return __version__

class NodeBoxError(Exception): 
    pass

# note whether the module is being used within the .app, via task.py, or from the repl
import sys, re
called_from = getattr(sys.modules['__main__'], '__file__', '<interactive>')
is_windowed = bool(re.search(r'nodebox(-app|/run/task)\.py$', called_from))
app = bool(called_from=='nodebox-app.py') if is_windowed else None

# add the Extras directory to sys.path since every module depends on PyObjC and friends    
try:
    import objc
except ImportError:
    extras = '/System/Library/Frameworks/Python.framework/Versions/2.7/Extras/lib/python'
    sys.path.extend([extras, '%s/PyObjC'%extras])
    import objc

# print python exceptions to the console rather than silently failing
objc.setVerbose(True) 

# add any installed Libraries to the sys path
from os import getenv
from os.path import join
sys.path.append(join(getenv('HOME'), 'Library', 'Application Support', 'NodeBox'))

# if imported from an external module, set up a drawing environment in __all__.
# (note that since this happens at the module level, the canvas will be shared
# among all the files in a given process that `import *`).
if not is_windowed:
    # create a global canvas and graphics context for the draw functions to operate on
    from nodebox import graphics
    from nodebox import util
    from nodebox.run.export import export
    ns = {"export":export}
    canvas = graphics.Canvas()
    context = graphics.Context(canvas, ns)

    # set up the standard nodebox global namespace, all tied to the module-level canvas
    for module in graphics, util, context:
        ns.update( (a,getattr(module,a)) for a in module.__all__  )
    globals().update(ns)
    __all__ = ns.keys()
else:
    __all__ = ('app',)