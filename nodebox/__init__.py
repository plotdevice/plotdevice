__version__='1.10'
__MAGIC = "_n_o_d_e_b_o_x_"

def get_version():
    return __version__

app = None
def initialize(mode='headless'):
    """vestigial"""
    
    # make sure repeated calls don't keep running the setup routine
    global app
    if app is not None: return
    app = {'headless':False, 'gui':True}.get(mode)
    if app is None: return

class NodeBoxError(Exception): 
    pass

# add the Extras directory to sys.path since every module depends on PyObjC and friends    
import sys
try:
    import objc
except ImportError:
    extras = '/System/Library/Frameworks/Python.framework/Versions/2.7/Extras/lib/python'
    sys.path.extend([extras, '%s/PyObjC'%extras])
    import objc

# print python exceptions to the console rather than silently failing
objc.setVerbose(True) 

# create a canvas and graphics context for the draw functions to operate on
import sys
from nodebox.graphics import colors
from nodebox import graphics
from nodebox import util
ns = {}
canvas = graphics.Canvas()
context = graphics.Context(canvas, ns)
colors._ctx = context

from os import getenv
from os.path import join
sys.path.append(join(getenv('HOME'), 'Library', 'Application Support', 'NodeBox'))

# set up the standard nodebox global namespace, all tied to the module-level canvas
# (note that this means you shouldn't `import *` from this in more than one script file
# or unpredictable things may happen as you mutate global state in multiple places.)
for module in graphics, util, context:
    ns.update( (a,getattr(module,a)) for a in module.__all__  )
globals().update(ns)
__all__ = ns.keys()
