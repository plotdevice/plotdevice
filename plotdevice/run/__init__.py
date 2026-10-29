import sys, site
from glob import glob
from importlib.machinery import PathFinder
from os.path import abspath, dirname, exists, expanduser, join
from subprocess import call
from sysconfig import get_path
from .. import in_bundle

# the per-interpreter subdirectories used by `plotdevice --install`
lib_dir = expanduser('~/Library/Application Support/PlotDevice')
interpreter_lib_dir = join(lib_dir, 'python%d.%d%s' % (*sys.version_info[:2], sys.abiflags))

class BundledFinder:
    """Imports PyObjC and PlotDevice from the app's own site-packages"""
    def __init__(self, site_dir):
        self.site_dir = site_dir
        self.names = {'plotdevice', '_plotdevice'}
        for top_level in glob(join(site_dir, 'pyobjc*.dist-info', 'top_level.txt')):
            with open(top_level) as f:
                self.names.update(f.read().split())

    def find_spec(self, name, path=None, target=None):
        if path is None and name in self.names:
            return PathFinder.find_spec(name, [self.site_dir])

if in_bundle:
    # let the packages the user installed take precedence over the app's, except for PyObjC and PlotDevice
    site_dir = get_path('purelib')
    site_index = sys.path.index(site_dir) if site_dir in sys.path else len(sys.path)
    sys.path[site_index:site_index] = [interpreter_lib_dir, lib_dir]
    sys.meta_path.insert(0, BundledFinder(site_dir))

try:
    # test the sys.path by attempting to load a PyObjC submodule...
    import Foundation
    import objc
except ImportError:
    # detect whether we're being run from the repository and set up a local env if so
    repo = abspath(join(dirname(__file__), '../..'))
    make_py = '%s/make.py' % repo
    if exists(make_py):
        from platform import python_version
        from sysconfig import get_config_var
        # the `make.py dev`-created venv for whichever interpreter called it
        local_libs = '%s/deps/local/%s%s/lib/python%s%s/site-packages' % (repo, python_version(), sys.abiflags, get_config_var('py_version_short'), sys.abiflags)
        if not exists(local_libs):
            call([sys.executable, make_py, 'dev'])
        site.addsitedir(local_libs)
        import Foundation
        import objc
    else:
        from pprint import pformat
        missing = "Searched for PyObjC libraries in:\n%s\nto no avail..."%pformat(sys.path)
        raise RuntimeError(missing)

# pull in the encoding-pragma detector
from .common import encoded

# expose the script-runner object
from .sandbox import Sandbox

__all__ = ('objc', 'encoded', 'Sandbox')
