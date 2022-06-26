import sys, site
from os.path import abspath, dirname, relpath, exists, join

try:
    # test the sys.path by attempting to load a PyObjC submodule...
    import objc
except ImportError:
    # ...but if run from the sdist, the PyObjC site-dir will be in setup.py's build directory
    objc_dir = abspath(join(dirname(__file__), '../../build/lib/plotdevice/lib/PyObjC'))
    if exists(objc_dir):
        site.addsitedir(objc_dir)
        import objc
    else:
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