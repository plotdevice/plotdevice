import sys, site
from os.path import abspath, dirname, exists, join
from subprocess import call

try:
    # test the sys.path by attempting to load a PyObjC submodule...
    from Foundation import *
except ImportError:
    # detect whether we're being run from the repository and set up a local env if so
    repo = abspath(join(dirname(__file__), '../..'))
    setup_py = '%s/setup.py' % repo
    if exists(setup_py):
        from platform import python_version
        from sysconfig import get_config_var
        local_libs = '%s/deps/local/%s/lib/python%s/site-packages' % (repo, python_version(), get_config_var('py_version_short'))
        if not exists(local_libs):
            call([sys.executable, setup_py, 'dev'])
        site.addsitedir(local_libs)
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