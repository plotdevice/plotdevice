import sys
from os.path import join, abspath, dirname, exists

# do some special-case handling when the module is imported from within the source dist
# (determined by checking the existence project files at a known path). if we're in the
# source dist, add the build dir to the path so we can pick up the .so files,
module_root = abspath(join(abspath(dirname(__file__)), '../..'))
if exists(join(module_root, 'app/PlotDevice-Info.plist')):
    so_dir = join(module_root, 'build/lib/plotdevice/lib')
    sys.path.append(so_dir)
    if not exists(so_dir):
        unbuilt = 'Build the plotdevice module with `python setup.pt build\' before attempting import it.'
        raise RuntimeError(unbuilt)

# test the sys.path by attempting to load the c-extensions
try:
    import geometry, io, pathmatics
except ImportError:
    from pprint import pformat
    notfound = "Couldn't locate C extensions (cIO.so, cGeometry.so, & cPathmatics.so).\nSearched in:\n%s\nto no avail..."%pformat(sys.path)
    raise RuntimeError(notfound)

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
