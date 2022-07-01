import sys, site
from os.path import abspath, dirname, exists, join
from subprocess import call, getoutput

try:
    # test the sys.path by attempting to load a PyObjC submodule...
    from Foundation import *
except ImportError:
    setup_py = join(dirname(__file__), '../../setup.py')
    if exists(setup_py):
        # if run from the sdist, install pyobjc et al. in a venv at app/deps/local
        site_path = getoutput('{py} {setup} -q env'.format(py=sys.executable, setup=setup_py))
        site.addsitedir(site_path)
        from Foundation import *
    else:
        from pprint import pformat
        missing = "Searched for PyObjC libraries in:\n%s\nto no avail..."%pformat(sys.path)
        raise RuntimeError(missing)

# pull in the encoding-pragma detector
from .common import encoded

# expose the script-runner object
from .sandbox import Sandbox

__all__ = ('objc', 'encoding', 'Sandbox')