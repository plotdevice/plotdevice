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
#
import os, sys, json, re, platform
from glob import glob
from shutil import rmtree
from setuptools import setup, find_packages, Command
from setuptools.extension import Extension
from setuptools.command.build_py import build_py
from setuptools.command.build_ext import build_ext
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
URL = "https://plotdevice.io/"
CLASSIFIERS = [
    "Development Status :: 5 - Production/Stable",
    "Environment :: MacOS X :: Cocoa",
    "Intended Audience :: Developers",
    "Intended Audience :: Education",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS :: MacOS X",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Topic :: Artistic Software",
    "Topic :: Multimedia :: Graphics",
    "Topic :: Multimedia :: Graphics :: Editors :: Vector-Based",
    "Topic :: Multimedia :: Video",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Software Development :: User Interfaces",
    "Topic :: Text Editors :: Integrated Development Environments (IDE)",
]
DESCRIPTION = "Create two-dimensional graphics and animations with code"
LONG_DESCRIPTION = """PlotDevice is a Macintosh application used for computational graphic design. It
provides an interactive Python environment where you can create two-dimensional
graphics and output them in a variety of vector, bitmap, and animation formats.
It is meant both as a sketch environment for exploring generative design and as
a general purpose graphics library for use in external Python programs.

PlotDevice scripts can create images from simple geometric primitives, text, and
external vector or bitmap images. Drawing commands provide a thin abstraction
over macOS's Quartz graphics engine, providing high-quality rendering
of 2D imagery and powerful compositing operations.

PlotDevice is a fork of NodeBox 1.9.7rc1 with support for modern versions of
Python and Mac OS.

The new version features:

* Runs natively on Intel and Apple Silicon and supports retina displays
* Python 3 only (including a bundled 3.10 installation in the app)
* images can now be exported in HEIC format and videos support H.265 (HEVC)
* SVG files can now be drawn to the canvas using the `image()` command (thanks to the magical [SwiftDraw](https://github.com/swhitty/SwiftDraw) library)
* image exports have a configurable `zoom` to create 2x/3x/etc ‘retina’ images
* revamped `var()` command for creating GUIs to modify values via sliders, buttons, toggles, etc.
* updated text editor with multiple tabs, new themes, and additional key-binding modes emulating Sublime Text and VS Code
* the module's command line interface is now accessible through `python3 -m plotdevice`
* the command line tool has a new `--install` option to download [PyPI](https://pypi.org) packages for use within the app
* document autosaving is now user-configurable
* Bugfixes and misc. improvements detailed in the [changelog](https://github.com/plotdevice/plotdevice/blob/main/CHANGES.md)

Version 0.9.5 added:

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
* Python 3.6+
"""

## Basic Utils ##

# the sparkle updater framework will be fetched as needed
SPARKLE_VERSION = '2.1.0'
SPARKLE_URL = 'https://github.com/sparkle-project/Sparkle/releases/download/%(v)s/Sparkle-%(v)s.tar.xz' % {'v':SPARKLE_VERSION}

# helpers for dealing with plists & git (spiritual cousins if ever there were)
import plistlib
def info_plist(pth='app/info.plist'):
    info = plistlib.load(open(pth, 'rb'))
    # overwrite the xcode placeholder vars
    info['CFBundleExecutable'] = info['CFBundleName'] = APP_NAME
    return info

def update_plist(pth, **modifications):
    info = plistlib.load(open(pth, 'rb'))
    for key, val in modifications.items():
        if val is None:
            info.pop(key)
        else:
            info[key] = val
    with open(pth, 'wb') as f:
        plistlib.dump(info, f)

def update_shebang(pth, interpreter):
    body = open(pth).readlines()[1:]
    body.insert(0,'#!%s\n'%interpreter)
    with open(pth, 'w') as f:
        f.writelines(body)

def last_commit():
    commit_count, _, _ = gosub('git log --oneline | wc -l')
    return 'r%s' % commit_count.decode('utf-8').strip()

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
    return datetime.now().strftime("%a, %d %b %Y %H:%M:%S")

def stale(dst, src):
  if exists(src):
    if not exists(dst) or getmtime(dst) < getmtime(src):
        yield dst, src

## Build Commands ##

class CleanCommand(Command):
    description = "wipe out the ./build & ./dist dirs and other setup-generated files"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        os.system('rm -rf ./build ./dist')
        os.system('rm -rf plotdevice.egg-info MANIFEST.in PKG')
        os.system('rm -rf ./tests/_out ./tests/_diff ./details.html')
        os.system('rm -f ./_plotdevice.*.so')
        os.system('cd deps/extensions/svg && make clean')
        os.system('find plotdevice -name .DS_Store -exec rm {} \;')
        os.system('find plotdevice -name \*.pyc -exec rm {} \;')
        os.system('find plotdevice -name __pycache__ -type d -prune -exec rmdir {} \;')

class DistCleanCommand(Command):
    description = "delete Python.framework, local pypi dependencies, and all generated files"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        self.run_command('clean')
        os.system('rm -rf ./deps/local')
        os.system('rm -rf ./deps/frameworks/*.framework')

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
            call([PIP, 'install', '-q', '--upgrade', 'pip', 'wheel', 'py2app', 'twine'])
            call([PIP, '--isolated', 'install', *config['install_requires']])

        # place the compiled c-extensions in the main repo dir
        build_ext = self.distribution.get_command_obj('build_ext')
        build_ext.inplace = 1
        self.run_command('build_ext')

        print("\nA local development environment has been set up in %s" % venv_dir)

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
                recursive-include deps/extensions/svg *.swift Makefile
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

        # make sure we have the sources for SwiftDraw
        call('cd deps/extensions/svg && make SwiftDraw', shell=True)

        # build the sdist based on our MANIFEST additions
        sdist.run(self)

        # clean up
        rmtree('plotdevice.egg-info')
        os.unlink('MANIFEST.in')

class BuildCommand(build_py):
    def run(self):

        # let the real build_py routine do its thing
        build_py.run(self)

        # include some ui resources for running a script from the command line
        rsrc_dir = '%s/plotdevice/rsrc'%self.build_lib
        self.mkpath(rsrc_dir)
        self.copy_file("app/Resources/PlotDeviceFile.icns", rsrc_dir)
        self.copy_file("app/Resources/colors.json", rsrc_dir)

        # recompile the command-line UI nib if necessary
        xib = 'app/Resources/en.lproj/PlotDeviceScript.xib'
        nib = 'app/Resources/viewer.nib'
        for dst, src in stale(nib, xib):
            self.spawn(['/usr/bin/ibtool','--compile', nib, xib])
        self.copy_file(nib, rsrc_dir)

class BuildExtCommand(build_ext):
    def run(self):
        call('cd deps/extensions/svg && make', shell=True)
        build_ext.run(self)

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
        call('cd deps/frameworks && make', shell=True)

    def run(self):
        self.spawn(['xcodebuild', '-configuration', 'Release'])
        rmtree('dist/PlotDevice.app.dSYM')
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
        def run(self):
            build_py2app.run(self)
            if self.dry_run:
                return

            # undo py2app's weird treatment of the config.version value
            info_pth = 'dist/PlotDevice.app/Contents/Info.plist'
            update_plist(info_pth, CFBundleShortVersionString=None)

            # place the command line tool in SharedSupport
            BIN = join(dirname(self.resdir), 'SharedSupport')
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
          Couldn't find the py2app module. To set up a virtualenv that contains all the necessary
          dependencies in the deps/local directory, call the `dev` command first:
          > python3 setup.py dev
          > ./deps/local/<python-version>/bin/python3 setup.py py2app""")
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

        # run the Xcode build
        self.run_command('app')

        # set the bundle version to the current commit number and prime the updater
        info_pth = 'dist/PlotDevice.app/Contents/Info.plist'
        update_plist(info_pth,
            CFBundleVersion = last_commit(),
            CFBundleShortVersionString = VERSION,
            SUFeedURL = 'https://plotdevice.io/app.xml',
            SUEnableSystemProfiling = 'YES'
        )

        # Download Sparkle (if necessary) and copy it into the bundle
        ORIG = 'deps/frameworks/Sparkle.framework'
        SPARKLE = join(APP,'Contents/Frameworks/Sparkle.framework')
        if not exists(ORIG):
            self.mkpath(dirname(ORIG))
            print("Downloading Sparkle.framework")
            os.system('curl -L -# %s | xz -dc | tar xf - -C %s %s'%(SPARKLE_URL, dirname(ORIG), basename(ORIG)))
        self.mkpath(dirname(SPARKLE))
        self.spawn(['ditto', ORIG, SPARKLE])

        # code-sign the app and embedded frameworks, then verify
        def codesign(root, name=None, exec=False, entitlement=False):
            test = []
            if name:
                test += ['-name', name]
            if exec:
                test += ['-perm', '-u=x']

            codesign = ['codesign', '--deep', '--strict', '--timestamp', '-o', 'runtime', '-f', '-v', '-s', 'Developer ID Application']
            if entitlement:
                codesign += ['--entitlements', 'app/PlotDevice.entitlements']

            if test:
                self.spawn(['find', root, '-type', 'f', *test, '-exec', *codesign, "{}", ";"])
            else:
                self.spawn([*codesign, root])

        PYTHON = join(APP,'Contents/Frameworks/Python.framework')
        codesign('%s/Versions/Current/lib'%PYTHON, name="*.dylib")
        codesign('%s/Versions/Current/lib'%PYTHON, name="*.o")
        codesign('%s/Versions/Current/lib'%PYTHON, name="*.a")
        codesign('%s/Versions/Current/lib'%PYTHON, exec=True)
        codesign('%s/Versions/Current/bin'%PYTHON, exec=True)
        codesign('%s/Versions/Current/bin'%PYTHON, name="python3.*", entitlement=True)
        codesign('%s/Versions/Current/Resources/Python.app'%PYTHON, entitlement=True)
        codesign(PYTHON)

        codesign('%s/Versions/Current/Updater.app'%SPARKLE)
        codesign(SPARKLE)

        codesign(APP, entitlement=True)
        self.spawn(['codesign', '--verify', '--deep', '-vv', APP])

        # create versioned zipfile of the app & notarize it
        self.spawn(['ditto', '-ck', '--keepParent', APP, ZIP])
        self.spawn(['xcrun', 'notarytool', 'submit', ZIP, '--keychain-profile', 'AC_NOTARY', '--wait'])

        # staple notarization ticket and regenerate zip
        self.spawn(['xcrun', 'stapler', 'staple', APP])
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
    long_description_content_type = 'text/markdown',
    author = AUTHOR,
    author_email = AUTHOR_EMAIL,
    url = URL,
    license = LICENSE,
    classifiers = CLASSIFIERS,
    packages = find_packages(exclude=['tests']),
    ext_modules = [Extension(
        '_plotdevice',
        sources = ['deps/extensions/module.m', *glob('deps/extensions/*/*.[cm]')],
        extra_objects=['deps/extensions/svg/SwiftDraw.o'],
        extra_link_args=sum((['-framework', fmwk] for fmwk in
            ['AppKit', 'Foundation', 'Quartz', 'Security', 'AVFoundation', 'CoreMedia', 'CoreVideo', 'CoreText']
        ), [])
    )],
    install_requires = [
        'requests',
        'cachecontrol',
        'lockfile',
        'pyobjc-core==8.5',
        'pyobjc-framework-Quartz==8.5',
        'pyobjc-framework-LaunchServices==8.5',
        'pyobjc-framework-WebKit==8.5',
    ],
    scripts = ["app/plotdevice"],
    zip_safe=False,
    cmdclass={
        'app': BuildAppCommand,
        'build_py': BuildCommand,
        'build_ext': BuildExtCommand,
        'clean': CleanCommand,
        'distclean': DistCleanCommand,
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

    # clear away any finder droppings that may have accumulated
    call('find . -name .DS_Store -delete', shell=True)

    # py2app-specific config
    if 'py2app' in sys.argv:
        config.update(dict(
            app = [{
                'script': "app/plotdevice-app.py",
                "plist":info_plist(),
            }],
            data_files = [
                "app/Resources/ui",
                "app/Resources/colors.json",
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
            }
        ))

    # include a backport of dataclasses on 3.6
    if sys.version_info < (3,7):
        config['install_requires'].append('dataclasses')

    # begin the build process
    setup(**config)
