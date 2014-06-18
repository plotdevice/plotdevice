import sys
from os.path import join, abspath, dirname, exists

# do some special-case handling when the module is imported from within the source dist.
# if the libraries build dir exists, add it to the path so we can pick up the .so files,
# otherwise leave the path as it is and bomb on failure to find the libraries.
lib_root = abspath(dirname(__file__))
inplace = exists(join(lib_root, '../../app/main.m'))
if inplace:
    sys.path.append(join(lib_root, '../../build/ext'))

# test the sys.path by attempting to load the c-extensions
try:
    import geometry, io, pathmatics
except ImportError:
    print "failed with path", sys.path
    suggest = ' (try running `python setup.py build` before using the module from within the repository)'
    notfound = "Couldn't locate C extensions%s." % (suggest if inplace else '')
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
