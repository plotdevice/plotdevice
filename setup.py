# encoding:utf-8

# This is your standard setup.py, so to install the module & command line tool, use:
#     python setup.py install
#
# In addition to the `install' command, there are a few other variants:
#
#    app:    builds ./dist/PlotDevice.app using Xcode
#    py2app: builds the application using py2app
#    clean:  discard anything already built and start fresh
#    build:  puts the module in a usable state. after building, you should be able
#            to run the ./app/plotdevice command line tool within the source distribution.
#            If you're having trouble building the app, this can be a good way to sanity
#            check your setup
#
# We require some dependencies:
# - Mac OS X 10.9+
# - py2app or xcode or just pip
# - PyObjC (should be in /System/Library/Frameworks/Python.framework/Versions/2.7/Extras)
# - cPathMatics, cGeo, cIO, cEvent, & polymagic (included in the "app/deps" folder)
# - Sparkle.framework (auto-downloaded only for `dist` builds)

import sys,os,json
from distutils.dir_util import remove_tree
from setuptools import setup, find_packages
from pkg_resources import DistributionNotFound
from os.path import join, exists, dirname, basename, abspath
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
CLASSIFIERS = (
    "Development Status :: 5 - Production/Stable",
    "Environment :: MacOS X :: Cocoa",
    "Intended Audience :: Developers",
    "Intended Audience :: Education",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS :: MacOS X",
    "Programming Language :: Python",
    "Topic :: Artistic Software",
    "Topic :: Multimedia :: Graphics",
    "Topic :: Multimedia :: Graphics :: Editors :: Vector-Based",
    "Topic :: Multimedia :: Video",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Software Development :: User Interfaces",
    "Topic :: Text Editors :: Integrated Development Environments (IDE)",
)
DESCRIPTION = "Create two-dimensional graphics and animations with code"
LONG_DESCRIPTION = """PlotDevice is a Macintosh application used for computational graphic design. It provides an
interactive Python environment where you can create two-dimensional graphics
and output them in a variety of vector, bitmap, and animation formats. It is
meant both as a sketch environment for exploring generative design and as a
general purpose graphics library for use in stand-alone Python programs.

PlotDevice is a fork of NodeBox 1.9.7rc1 with support for modern versions of
Python and Mac OS.

The new version features:

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

Requires:

* Mac OS X 10.9+
"""


## Basic Utils ##

# the sparkle updater framework will be fetched as needed
SPARKLE_VERSION = '1.7.0'
SPARKLE_URL = 'https://github.com/pornel/Sparkle/releases/download/%(v)s/Sparkle-%(v)s.tar.bz2'% {'v':SPARKLE_VERSION}

# helpers for dealing with plists & git (spiritual cousins if ever there were)
import plistlib
def info_plist(pth='app/PlotDevice-Info.plist'):
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

def last_commit():
    commit_count, _, _ = gosub('git log --oneline | wc -l')
    return 'r%s' % commit_count.strip()

def gosub(cmd, on_err=True):
    """Run a shell command and return the output"""
    from subprocess import Popen, PIPE
    shell = isinstance(cmd, basestring)
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=shell)
    out, err = proc.communicate()
    ret = proc.returncode
    if on_err:
        msg = '%s:\n' % on_err if isinstance(on_err, basestring) else ''
        assert ret==0, msg + (err or out)

    return out, err, ret

def timestamp():
    from datetime import datetime
    from pytz import timezone, utc
    now = utc.localize(datetime.utcnow()).astimezone(timezone('US/Eastern'))
    return now.strftime("%a, %d %b %Y %H:%M:%S %z")

## Build Commands ##

from distutils.core import Command
class CleanCommand(Command):
    description = "wipe out the ./build ./dist and app/deps/.../build dirs"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        os.system('rm -rf ./build ./dist')
        os.system('rm -rf ./app/deps/*/build')
        os.system('rm -rf plotdevice.egg-info MANIFEST.in PKG')

from setuptools.command.sdist import sdist
class BuildDistCommand(sdist):
    def finalize_options(self):
        with file('MANIFEST.in','w') as f:
            tracked, _, _ = gosub('git ls-tree --full-tree --name-only -r HEAD')
            for line in tracked.splitlines()[1:]:
                f.write("include %s\n"%line)
        sdist.finalize_options(self)

    def run(self):
        sdist.run(self)

        # it would be nice to clean up MANIFEST.in and plotdevice.egg-info here,
        # but we'll see if the upload command depends on them...
        remove_tree('plotdevice.egg-info')
        os.unlink('MANIFEST.in')

from distutils.command.build_py import build_py
class BuildCommand(build_py):
    def run(self):
        # first let the real build_py routine do its thing
        build_py.run(self)

        # then compile the extensions into the just-built module
        self.spawn(['/usr/bin/python', 'app/deps/build.py', abspath(self.build_lib)])

        # include some ui resources for running a script from the command line
        rsrc_dir = '%s/plotdevice/rsrc'%self.build_lib
        self.mkpath(rsrc_dir)
        self.copy_file("app/Resources/colors.json", '%s/colors.json'%rsrc_dir)
        self.spawn(['/usr/bin/ibtool','--compile', '%s/viewer.nib'%rsrc_dir, "app/Resources/English.lproj/PlotDeviceScript.xib"])
        self.copy_file("app/Resources/PlotDeviceFile.icns", '%s/viewer.icns'%rsrc_dir)

class BuildAppCommand(Command):
    description = "Build PlotDevice.app with xcode"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        self.spawn(['xcodebuild'])
        remove_tree('dist/PlotDevice.app.dSYM')
        print "done building PlotDevice.app in ./dist"

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
            assert os.getcwd() == self.cwd, 'Must be in package root: %s' % self.cwd
            build_py2app.run(self)
            if self.dry_run:
                return

            # undo py2app's weird treatment of the config.version value
            info_pth = 'dist/PlotDevice.app/Contents/Info.plist'
            update_plist(info_pth, CFBundleShortVersionString=None)

            # set up internal paths and ensure destination dirs exist
            RSRC = self.resdir
            BIN = join(dirname(RSRC), 'SharedSupport')
            MODULE = join(self.bdist_base, 'lib/plotdevice')
            PY = join(RSRC, 'python')
            for pth in BIN, PY:
                self.mkpath(pth)

            # install the module in Resources/python
            self.spawn(['/usr/bin/ditto', MODULE, join(PY, 'plotdevice')])

            # discard the eggery-pokery
            remove_tree(join(RSRC,'lib'), dry_run=self.dry_run)
            os.unlink(join(RSRC,'include'))
            os.unlink(join(RSRC,'site.pyc'))

            # place the command line tool in SharedSupport
            self.copy_file("app/plotdevice", BIN)

            # success!
            print "done building PlotDevice.app in ./dist"

except DistributionNotFound:
    # virtualenv doesn't include pyobjc, py2app, etc. in the sys.path for some reason.
    # not being able to access py2app isn't a big deal for 'build', 'app', 'dist', or 'clean'
    # so only abort the build if the 'py2app' command was given
    if 'py2app' in sys.argv:
        print """setup.py: py2app build failed
          Couldn't find the py2app module (perhaps because you've called setup.py from a virtualenv).
          Make sure you're using the system's /usr/bin/python interpreter for py2app builds."""
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
        ORIG = 'app/deps/Sparkle-%s/Sparkle.framework'%SPARKLE_VERSION
        SPARKLE = join(APP,'Contents/Frameworks/Sparkle.framework')
        if not exists(ORIG):
            print "Downloading Sparkle.framework"
            self.mkpath('app/deps')
            os.system('curl -L %s | bunzip2 -c | tar xf - -C app/deps'%SPARKLE_URL)
        self.mkpath(dirname(SPARKLE))
        self.spawn(['ditto', ORIG, SPARKLE])

        # code-sign the app and sparkle bundles, then verify
        self.spawn(['codesign', '-f', '-v', '-s', "Developer ID Application", SPARKLE])
        self.spawn(['codesign', '-f', '-v', '-s', "Developer ID Application", APP])
        self.spawn(['spctl', '--assess', '-v', 'dist/PlotDevice.app'])

        # create versioned zipfile of the app
        self.spawn(['ditto','-ck', '--keepParent', APP, ZIP])

        # write out the release metadata for plotdevice-site to consume/merge
        with file('dist/release.json','w') as f:
            release = dict(zipfile=basename(ZIP), bytes=os.path.getsize(ZIP),
                           version=VERSION, revision=last_commit(),
                           timestamp=timestamp())
            json.dump(release, f)

        print "\nBuilt PlotDevice.app, %s, and release.json in ./dist" % basename(ZIP)

## Run Build ##

if __name__=='__main__':
    # make sure we're at the project root regardless of the cwd
    # (this means the various commands don't have to play path games)
    os.chdir(dirname(abspath(__file__)))

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
        packages = find_packages(),
        scripts = ["app/plotdevice"],
        zip_safe=False,
        cmdclass={
            'app': BuildAppCommand,
            'clean': CleanCommand,
            'build_py': BuildCommand,
            'dist': DistCommand,
            'sdist': BuildDistCommand,
        },
    )

    # py2app-specific config
    if 'py2app' in sys.argv:
        config.update(dict(
            app = [{
                'script': "app/plotdevice-app.py",
                "plist":info_plist(),
            }],
            data_files = [
                "app/Resources/ui",
                "app/Resources/English.lproj",
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

    # begin the build process
    setup(**config)
