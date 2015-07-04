import sys
from os.path import abspath, dirname, exists
from glob import glob

try:
    # if the lib files are missing, presume we're in the source dist and look in its build dir
    if not glob('%s/*.so'%dirname(__file__)):
        sys.path.append(abspath('%s/../../build/lib/'%dirname(__file__)))
        sys.path.append(abspath('%s/plotdevice/lib'%sys.path[-1]))
    import io, pathmatics, foundry # make sure the c-extensions are accessible
except ImportError:
    missing = "Missing C extensions (cPathmatics.so & friends) in %s" % abspath(dirname(__file__))
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
