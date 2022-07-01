import sys
from os.path import abspath, dirname, exists, join
from glob import glob

try:
    import _plotdevice # make sure the c-extensions are accessible
except ImportError:
    setup_py = join(dirname(__file__), '../../setup.py')
    if exists(setup_py):
        from subprocess import call
        # call('{py} {setup} build_ext --inplace'.format(py=sys.executable, setup=setup_py))
        call([sys.executable, setup_py, 'build_ext', '--inplace'])
    import _plotdevice

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
