__version__='0.9'

def get_version():
    return __version__

class DeviceError(Exception):
    pass

# note whether the module is being used within the .app, via console.py, or from the repl
import sys, re
called_from = getattr(sys.modules['__main__'], '__file__', '<interactive>')
is_windowed = bool(re.search(r'plotdevice(-app|/run/console)\.py$', called_from))
in_setup = bool(called_from.endswith('setup.py'))

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

# the global non-conflicting token (fingers crossed)
DEFAULT = '_p_l_o_t_d_e_v_i_c_e_'

if is_windowed or in_setup:
    # if a script imports * from within the app/tool, nothing should be (re-)added to the
    # global namespace. we'll let the Sandbox handle populating the namespace instead.
    __all__ = []
else:
    # if imported from an external module, set up a drawing environment in __all__.
    # (note that since this happens at the module level, the canvas will be shared
    # among all the files in a given process that `import *`).

    # create a global canvas and graphics context for the draw functions to operate on
    from .context import Context
    ctx = Context()

    # set up the standard plotdevice global namespace by exposing the module-level
    # context/canvas's internal ns
    globals().update(ctx._ns)
    __all__ = ctx._ns.keys()
