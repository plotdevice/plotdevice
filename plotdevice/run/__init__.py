import sys, site
from os.path import abspath, dirname, relpath, exists, join
from subprocess import call, getoutput

try:
    # test the sys.path by attempting to load a PyObjC submodule...
    import objc
except ImportError:
    deps_dir = join(dirname(__file__), '../../app/deps')
    if exists(deps_dir):
        # if run from the sdist, install pyobjc et al. in a venv at app/deps/local
        venv_dir = join(deps_dir, 'local')
        if not exists(venv_dir):
            import importlib.util
            spec = importlib.util.spec_from_file_location("setup", join(dirname(__file__), '../../setup.py'))
            setup = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(setup)

            import venv
            venv.create(venv_dir, symlinks=True, with_pip=True)
            PIP = '%s/bin/pip3' % venv_dir
            call([PIP, 'install', '--upgrade', 'pip'])
            call([PIP, '--isolated', 'install', *setup.config['install_requires']])

        # use the venv's site directory
        site_path = getoutput('%s/bin/python3 -c "import site; print(site.getsitepackages()[0])"' % venv_dir)
        site.addsitedir(site_path)
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