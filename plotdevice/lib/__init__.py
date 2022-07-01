import sys
from os.path import abspath, dirname, exists
from glob import glob

_libdir = abspath(dirname(__file__))
try:
    # if the lib files are missing, presume we're in the source dist and look in its build dir
    if not glob('%s/*.so' % _libdir):
        build_dir = '%s/../../build/lib/plotdevice/lib' % _libdir
        if exists(build_dir): sys.path.append(abspath(build_dir))
    else:
        sys.path.append(_libdir)
    from . import io, pathmatics, foundry # make sure the c-extensions are accessible
except ImportError:
    missing = "Missing C extensions (cPathmatics.so & friends) in %s" % _libdir
    if exists('%s/../../setup.py' % _libdir):
        missing += "\nBuild the plotdevice module with `python3 setup.py build` before attempting import it."
    raise ImportError(missing)

# allow Libraries to request a _ctx reference
def register(module):
    """When called within a library's __init__.py, returns the currently bound context.
    After having registered, the module's _ctx variable will be updated whenever the
    context changes. Libraries should register themselves using the following snippet:

    from plotdevice.lib import register
    _ctx = register(__name__)
    """
    _bound['modules'].append(module)
    return _bound['ctx']

# keep registered libraries up-to-date when the context is re-bound
def bind(ctx):
    _bound['ctx'] = ctx
    for module in _bound['modules']:
        setattr(sys.modules[module], '_ctx', ctx)

_bound = {"ctx":None, "modules":[]}
