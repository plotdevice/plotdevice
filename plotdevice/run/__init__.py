import sys, site
from os.path import abspath, dirname, relpath, exists, join

try:
    # under normal circumstances the PyObjC site-dir is in the .lib directory...
    objc_dir = abspath(join(dirname(__file__), '../lib/PyObjC'))

    # ...but if run from the sdist, the binaries will be in setup.py's build directory
    if not exists(objc_dir):
        objc_dir = abspath(join(dirname(__file__), '../../build/lib/plotdevice/lib/PyObjC'))

    # add our embedded PyObjC site-dir to the sys.path (and remove any conflicts)
    map(sys.path.remove, filter(lambda p:p.endswith('PyObjC'), sys.path))
    site.addsitedir(objc_dir)

    # test the sys.path by attempting to load a PyObjC submodule
    import objc
except ImportError:
    from pprint import pformat
    missing = "Searched for PyObjC libraries in:\n%s\nto no avail..."%pformat(sys.path)
    if exists('%s/../../app/info.plist'%dirname(__file__)):
        missing += '\n\nBuild the plotdevice module with `python setup.py build\' before attempting import it.'
    raise RuntimeError(missing)


# pull in the encoding-pragma detector
from .common import encoded

# expose the script-runner object
from .sandbox import Sandbox

__all__ = ('objc', 'encoding', 'Sandbox')