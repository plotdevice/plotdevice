# encoding: utf-8

#
#          888             d8        888                   ,e,
# 888 88e  888  e88 88e   d88    e88 888  ,e e,  Y8b Y888P  "   e88'888  ,e e,
# 888 888b 888 d888 888b d88888 d888 888 d88 88b  Y8b Y8P  888 d888  '8 d88 88b
# 888 888P 888 Y888 888P  888   Y888 888 888   ,   Y8b "   888 Y888   , 888   ,
# 888 88"  888  "88 88"   888    "88 888  "YeeP"    Y8P    888  "88,e8'  "YeeP"
# 888
# 888
#

"""Quartz-powered vector machine

Copyright (C) 2014 Samizdat Drafting Co.
A derivative of http://nodebox.net/code by Frederik De Bleser & Tom De Smedt

All rights reserved.
MIT Licensed (see README file for details)
"""
import sys, re, os

__version__ = '0.9.4'
__author__  = 'Christian Swinehart'
__email__   = 'drafting@samizdat.cc'
__credits__ = 'Frederik De Bleser, Tom De Smedt, Just van Rossum, & Marcos Ojeda'
__license__ = 'MIT'

INTERNAL = '_p_l_o_t_d_e_v_i_c_e_' # the global non-conflicting token (fingers crossed)
class DeviceError(Exception): pass # please excuse our technical difficulties
class Halted(Exception): pass      # special exception to cleanly exit animations

# note whether the module is being used within the .app, via console.py, or from the repl
called_from = getattr(sys.modules['__main__'], '__file__', '<interactive>')
is_windowed = bool(re.search(r'plotdevice(-app|/run/console)\.py$', called_from))
in_setup = bool(called_from.endswith('setup.py')) # (for builds)

# don't mess with sys.path during builds
if not in_setup:
    # add the shared directory (for Libraries) to the path
    sys.path.append(os.path.join(os.getenv('HOME'), 'Library', 'Application Support', 'PlotDevice'))

    # use the bundled copy of PyObjC rather than the system version
    from .run import objc

    # print python exceptions to the console rather than silently failing
    objc.setVerbose(True)

# populate the namespace (or don't) depending on the context
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


