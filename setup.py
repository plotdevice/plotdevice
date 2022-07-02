# encoding:utf-8

# To install the module & command line tool in site-packages, use:
#    python3 setup.py install
#
# In addition to the `install' command, there are a few other variants:
#    app:    builds ./dist/PlotDevice.app using Xcode
#    py2app: builds the application using py2app
#    clean:  discard anything already built and start fresh
#    test:   run unit tests and generate the file "details.html" with the test output
#    dev:    puts the module in a usable state within the source distribution. after running,
#            you should be able to run the `python3 -m plotdevice` command line interface.
#            If you're having trouble building the app, this can be a good way to sanity
#            check your setup
#
# We require some dependencies:
# - Mac OS X 11+ and Xcode command line tools (type `xcode-select --install` in the terminal)
# - the python3.8 provided by Xcode or a homebrew- or pyenv-built python3 interpreter
# - Sparkle.framework (auto-downloaded only for `dist` builds)

import os, sys, json, re, platform
from glob import glob
from setuptools import setup, find_packages
from setuptools.extension import Extension
from distutils.dir_util import remove_tree
from distutils.command.build_py import build_py
from pkg_resources import DistributionNotFound
from os.path import join, exists, dirname, basename, abspath, getmtime
from subprocess import call, getoutput
import plotdevice


## Metadata ##

# PyPI fields
APP_NAME = 'PlotDevice'
MODULE = APP_NAME.lower()
VERSION = plotdevice.__version__
AUTHOR = plotdevice.__author__
AUTHOR_EMAIL = plotdevice.__email__
LICENSE = plotdevice.__license__
URL = "http://plotdevice.io/"
CLASSIFIERS = [
    "Development Status :: 5 - Production/Stable",
    "Environment :: MacOS X :: Cocoa",
    "Intended Audience :: Developers",
    "Intended Audience :: Education",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS :: MacOS X",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Topic :: Artistic Software",
    "Topic :: Multimedia :: Graphics",
    "Topic :: Multimedia :: Graphics :: Editors :: Vector-Based",
    "Topic :: Multimedia :: Video",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Software Development :: User Interfaces",
    "Topic :: Text Editors :: Integrated Development Environments (IDE)",
]
DESCRIPTION = "Create two-dimensional graphics and animations with code"
LONG_DESCRIPTION = """PlotDevice is a Macintosh application used for computational graphic design. It provides an
interactive Python environment where you can create two-dimensional graphics
and output them in a variety of vector, bitmap, and animation formats. It is
meant both as a sketch environment for exploring generative design and as a
general purpose graphics library for use in stand-alone Python programs.

PlotDevice is a fork of NodeBox 1.9.7rc1 with support for modern versions of
Python and Mac OS.

The new version features:

* Python 3 compatible
* Can now be built with system Python or Homebrew versions of the interpreter
* Much faster import times on Yosemite thanks to a bundled copy of PyObjC 3.0.4
* HTTP is now handled by the ``requests`` module and caches responses locally
* Totally revamped typography system with support for OpenType features,
  pagination, multi-column text, character geometry, and more
* Added 130+ unit tests (run them with ``python setup.py test``) plus bugfixes for
  for ``measure()``, ``textpath()``, ``Bezier.fit()``, ``read()``, and the Preferences dialog

Version 0.9.4 added:

* Enhanced command line interface.
* New text editor with tab completion, syntax color themes, and emacs/vi bindings.
* Video export in H.264 or animated gif formats (with GCD-based i/o).
* Added support for external editors by reloading the source when changed.
* Build system now works with Xcode or ``py2app`` for the application and ``pip`` for the module.
* Virtualenv support (for both installation of the module and running scripts with dependencies).
* External scripts can use ``from plotdevice import *`` to create a drawing environment.
* Simplified bezier & affine transform api using the python ‘with’ statement
* New compositing operations for blend mode, global opacity, and dropshadows
* Simplified typography commands with stylesheet-based character styles
* Now uses the system's Python 2.7 interpreter.

Requirements:

* Mac OS X 11+
* Python 3.8+
"""

## Basic Utils ##

# the sparkle updater framework will be fetched as needed
SPARKLE_VERSION = '1.10.0'
SPARKLE_URL = 'https://github.com/sparkle-project/Sparkle/releases/download/%(v)s/Sparkle-%(v)s.tar.bz2' % {'v':SPARKLE_VERSION}

# helpers for dealing with plists & git (spiritual cousins if ever there were)
import plistlib
def info_plist(pth='app/info.plist'):
    info = plistlib.readPlist(pth)
    # overwrite the xcode placeholder vars
    info['CFBundleExecutable'] = info['CFBundleName'] = APP_NAME
    return info

def update_plist(pth, **modifications):
    info = plistlib.readPlist(pth)
    for key, val in modifications.items():
        if val is None:
            info.pop(key)
        else:
            info[key] = val
    plistlib.writePlist(info, pth)

def update_shebang(pth, interpreter):
    body = open(pth).readlines()[1:]
    body.insert(0,'#!%s\n'%interpreter)
    with open(pth, 'w') as f:
        f.writelines(body)

def last_commit():
    commit_count, _, _ = gosub('git log --oneline | wc -l')
    return 'r%s' % commit_count.strip()

def gosub(cmd, on_err=True):
    """Run a shell command and return the output"""
    from subprocess import Popen, PIPE
    shell = isinstance(cmd, str)
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=shell)
    out, err = proc.communicate()
    ret = proc.returncode
    if on_err:
        msg = '%s:\n' % on_err if isinstance(on_err, str) else ''
        if ret != 0:
            print(msg + out.decode('utf8') + err.decode('utf8'))
    return out, err, ret

def timestamp():
    from datetime import datetime
    from pytz import timezone, utc
    now = utc.localize(datetime.utcnow()).astimezone(timezone('US/Eastern'))
    return now.strftime("%a, %d %b %Y %H:%M:%S %z")

def stale(dst, src):
  if exists(src):
    if not exists(dst) or getmtime(dst) < getmtime(src):
        yield dst, src

## Build Commands ##

from distutils.core import Command
class CleanCommand(Command):
    description = "wipe out the ./build ./dist and deps/local dirs"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        os.system('rm -rf ./build ./dist')
        os.system('rm -rf ./deps/local')
        os.system('rm -rf plotdevice.egg-info MANIFEST.in PKG')
        os.system('rm -rf ./tests/_out ./tests/_diff ./details.html')
        os.system('rm -f ./_plotdevice.*.so')
        os.system('find plotdevice -name .DS_Store -exec rm {} \;')
        os.system('find plotdevice -name \*.pyc -exec rm {} \;')
        os.system('find plotdevice -name __pycache__ -type d -prune -exec rmdir {} \;')

class LocalDevCommand(Command):
    description = "set up environment to allow for running `python -m plotdevice` within the repo"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        # install pyobjc, requests and the other pypi dependencies in deps/local
        import platform
        venv_dir = join('deps/local', platform.python_version())
        if not exists(venv_dir):
            import venv
            venv.create(venv_dir, symlinks=True, with_pip=True)
            PIP = '%s/bin/pip3' % venv_dir
            call([PIP, 'install', '-q', '--upgrade', 'pip', 'wheel'])
            call([PIP, '--isolated', 'install', '--target', join(venv_dir, 'libs'), *config['install_requires']])

        # place the compiled c-extensions in the main repo dir
        build_ext = self.distribution.get_command_obj('build_ext')
        build_ext.inplace = 1
        self.run_command('build_ext')

        # build the sdist (primarily for access to its rsrc subdir)
        self.run_command('build_py')


from setuptools.command.sdist import sdist
class BuildDistCommand(sdist):
    def finalize_options(self):
        with open('MANIFEST.in','w') as f:
            f.write("""
                graft app/Resources
                prune app/Resources/en.lproj
                prune app/Resources/ui
                include app/plotdevice
                include deps/extensions/*/*.h
                include tests/*.py
                graft tests/_in
                graft examples
                include *.md
                include *.url
            """)
        sdist.finalize_options(self)

    def run(self):
        # include a compiled nib in the sdist so ibtool (and thus Xcode.app) isn't required to install
        for dst, src in stale('app/Resources/viewer.nib', "app/Resources/en.lproj/PlotDeviceScript.xib"):
            self.spawn(['/usr/bin/ibtool','--compile', dst, src])

        # build the sdist based on our MANIFEST additions
        sdist.run(self)

        # clean up
        remove_tree('plotdevice.egg-info')
        os.unlink('MANIFEST.in')

class BuildCommand(build_py):
    def run(self):
        # let the real build_py routine do its thing
        build_py.run(self)

        # include some ui resources for running a script from the command line
        rsrc_dir = '%s/plotdevice/rsrc'%self.build_lib
        self.mkpath(rsrc_dir)
        self.copy_file("app/Resources/PlotDeviceFile.icns", '%s/viewer.icns'%rsrc_dir)
        self.copy_file("app/Resources/colors.json", rsrc_dir)

        # recompile the command-line UI nib if necessary
        xib = 'app/Resources/en.lproj/PlotDeviceScript.xib'
        nib = 'app/Resources/viewer.nib'
        for dst, src in stale(nib, xib):
            self.spawn(['/usr/bin/ibtool','--compile', nib, xib])
        self.copy_file(nib, rsrc_dir)


class TestCommand(Command):
    description = "Run unit tests"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        from subprocess import call
        test_cmd = [sys.executable, '-m', 'tests'] + sys.argv[2:]
        print(" ".join(test_cmd))
        call(test_cmd)

class BuildAppCommand(Command):
    description = "Build PlotDevice.app with xcode"
    user_options = []
    def initialize_options(self):
        pass

    def finalize_options(self):
        # make sure the embedded framework exists (and has updated app/python.xcconfig)
        print("Set up Python.framework for app build")
        call('cd deps/embed && make', shell=True)

    def run(self):
        self.spawn(['xcodebuild'])
        remove_tree('dist/PlotDevice.app.dSYM')
        print("done building PlotDevice.app in ./dist")

try:
    import py2app
    from py2app.build_app import py2app as build_py2app
    class BuildPy2AppCommand(build_py2app):
        description = """Build PlotDevice.app with py2app (then undo some of its questionable layout defaults)"""
        def initialize_options(self):
            build_py2app.initialize_options(self)
        def finalize_options(self):
            self.verbose=0
            build_py2app.finalize_options(self)
            os.environ['ACTION'] = 'build' # flag for deps/build.py

        def run(self):
            build_py2app.run(self)
            if self.dry_run:
                return

            # undo py2app's weird treatment of the config.version value
            info_pth = 'dist/PlotDevice.app/Contents/Info.plist'
            update_plist(info_pth, CFBundleShortVersionString=None)

            # set up internal paths and ensure destination dirs exist
            RSRC = self.resdir
            BIN = join(dirname(RSRC), 'SharedSupport')
            LIB = join(RSRC, 'python')
            MODULES = join(self.bdist_base, 'lib')

            # install the module in Resources/python
            self.spawn(['/usr/bin/ditto', MODULES, LIB])

            # discard the eggery-pokery
            remove_tree(join(RSRC,'lib'), dry_run=self.dry_run)
            os.unlink(join(RSRC,'include'))
            os.unlink(join(RSRC,'site.pyc'))

            # place the command line tool in SharedSupport
            self.mkpath(BIN)
            self.copy_file("app/plotdevice", BIN)

            # success!
            print("done building PlotDevice.app in ./dist")

except (DistributionNotFound, ImportError):
    # virtualenv doesn't include pyobjc, py2app, etc. in the sys.path for some reason.
    # not being able to access py2app isn't a big deal for 'build', 'app', 'dist', or 'clean'
    # so only abort the build if the 'py2app' command was given
    if 'py2app' in sys.argv:
        print("""setup.py: py2app build failed
          Couldn't find the py2app module (perhaps because you've called setup.py from a virtualenv).
          Make sure you're using the system's /usr/bin/python interpreter for py2app builds.""")
        sys.exit(1)


## Packaging Commands (really only useful to the maintainer) ##

class DistCommand(Command):
    description = "Create distributable zip of the app and release metadata"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        APP = 'dist/PlotDevice.app'
        ZIP = 'dist/PlotDevice_app-%s.zip' % VERSION

        # build the app
        self.spawn(['xcodebuild'])

        # we don't need no stinking core dumps
        remove_tree(APP+'.dSYM')

        # set the bundle version to the current commit number and prime the updater
        info_pth = 'dist/PlotDevice.app/Contents/Info.plist'
        update_plist(info_pth,
            CFBundleVersion = last_commit(),
            CFBundleShortVersionString = VERSION,
            SUFeedURL = 'http://plotdevice.io/app.xml',
            SUEnableSystemProfiling = 'YES'
        )

        # Download Sparkle (if necessary) and copy it into the bundle
        ORIG = 'deps/vendor/Sparkle-%s/Sparkle.framework'%SPARKLE_VERSION
        SPARKLE = join(APP,'Contents/Frameworks/Sparkle.framework')
        if not exists(ORIG):
            self.mkpath(dirname(ORIG))
            print("Downloading Sparkle.framework")
            os.system('curl -L -# %s | bunzip2 -c | tar xf - -C %s'%(SPARKLE_URL, dirname(ORIG)))
        self.mkpath(dirname(SPARKLE))
        self.spawn(['ditto', ORIG, SPARKLE])

        # code-sign the app and sparkle bundles, then verify
        self.spawn(['codesign', '-f', '-v', '-s', "Developer ID Application", SPARKLE])
        self.spawn(['codesign', '-f', '-v', '-s', "Developer ID Application", APP])
        self.spawn(['spctl', '--assess', '-v', 'dist/PlotDevice.app'])

        # create versioned zipfile of the app
        self.spawn(['ditto','-ck', '--keepParent', APP, ZIP])

        # write out the release metadata for plotdevice-site to consume/merge
        with open('dist/release.json','w') as f:
            release = dict(zipfile=basename(ZIP), bytes=os.path.getsize(ZIP),
                           version=VERSION, revision=last_commit(),
                           timestamp=timestamp())
            json.dump(release, f)

        print("\nBuilt PlotDevice.app, %s, and release.json in ./dist" % basename(ZIP))

# common config between module and app builds
config = dict(
    name = MODULE,
    version = VERSION,
    description = DESCRIPTION,
    long_description = LONG_DESCRIPTION,
    author = AUTHOR,
    author_email = AUTHOR_EMAIL,
    url = URL,
    license = LICENSE,
    classifiers = CLASSIFIERS,
    packages = find_packages(exclude=['tests']),
    ext_modules = [Extension(
        '_plotdevice',
        sources = ['deps/extensions/module.m', *glob('deps/extensions/*/*.[cm]')],
        extra_link_args=sum((['-framework', fmwk] for fmwk in
            ['AppKit', 'Foundation', 'Quartz', 'Security', 'AVFoundation', 'CoreMedia', 'CoreVideo', 'CoreText']
        ), [])
    )],
    install_requires = [
        'requests',
        'cachecontrol',
        'lockfile',
        'pyobjc-core==8.5',
        'pyobjc-framework-Cocoa==8.5',
        'pyobjc-framework-Quartz==8.5',
        'pyobjc-framework-LaunchServices==8.5',
        'pyobjc-framework-WebKit==8.5',
    ],
    scripts = ["app/plotdevice"],
    zip_safe=False,
    cmdclass={
        'app': BuildAppCommand,
        'clean': CleanCommand,
        'build_py': BuildCommand,
        'dist': DistCommand,
        'sdist': BuildDistCommand,
        'test': TestCommand,
        'dev': LocalDevCommand,
    },
)

## Run Build ##

if __name__=='__main__':
    # make sure we're at the project root regardless of the cwd
    # (this means the various commands don't have to play path games)
    os.chdir(dirname(abspath(__file__)))

    # py2app-specific config
    if 'py2app' in sys.argv:
        config.update(dict(
            app = [{
                'script': "app/plotdevice-app.py",
                "plist":info_plist(),
            }],
            data_files = [
                "app/Resources/ui",
                "app/Resources/en.lproj",
                "app/Resources/PlotDevice.icns",
                "app/Resources/PlotDeviceFile.icns",
                "examples",
            ],
            options = {
                "py2app": {
                    "iconfile": "app/Resources/PlotDevice.icns",
                    "semi_standalone":True,
                    "site_packages":True,
                    "strip":False,
                }
            },
            cmdclass={
                'build_py': BuildCommand,
                'py2app': BuildPy2AppCommand,
            },
            install_requires=[]
        ))

    # begin the build process
    setup(**config)
