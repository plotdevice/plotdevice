__version__='1.0'
__MAGIC = '_p_l_o_t_d_e_v_i_c_e_'

def get_version():
    return __version__

class DeviceError(Exception):
    pass

# note whether the module is being used within the .app, via task.py, or from the repl
import sys, re
called_from = getattr(sys.modules['__main__'], '__file__', '<interactive>')
is_windowed = bool(re.search(r'plotdevice(-app|/run/task)\.py$', called_from))
app = bool(called_from=='plotdevice-app.py') if is_windowed else None

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
sys.path.append(join(getenv('HOME'), 'Library', 'Application Support', 'PlotDevice'))

if is_windowed:
    # if imported from within the app/tool, all we need is the path-manipulation side
    # effects and a flag to our gui/headless status in the `app` variable
    __all__ = ('app',)
else:
    # if imported from an external module, set up a drawing environment in __all__.
    # (note that since this happens at the module level, the canvas will be shared
    # among all the files in a given process that `import *`).
    from . import graphics, grobs, util

    # create a global canvas and graphics context for the draw functions to operate on
    context = graphics.Context()
    ns = context._ns

    # set up the standard plotdevice global namespace, all tied to the module-level context/canvas
    for module in util, context:
        ns.update( (a,getattr(module,a)) for a in module.__all__  )
    ns.update(grobs.ns)
    globals().update(ns)
    __all__ = ns.keys()
