# encoding:utf-8

# This is your standard setup.py, so to install the module & command line tool, use:
#     python setup.py install
#
# To build an application in the dist subdirectory, use:
#     python setup.py py2app
#
# To build a distribution-friendly dmg & zip, use:
#     python setup.py dist
#
# We require some dependencies:
# - Mac OS X 10.9+
# - py2app or xcode or just pip
# - PyObjC (should be in /System/Library/Frameworks/Python.framework/Versions/2.7/Extras)
# - cPathMatics, cGeo, cIO, cEvent, & polymagic (included in the "libs" folder)

import sys,os
from distutils.dir_util import remove_tree
from setuptools import setup, find_packages
from setuptools.extension import Extension

NAME = 'PlotDevice'
VERSION = '0.9'
CREATOR = 'Plod'
BUNDLE_ID = "io.plotdevice.PlotDevice"
COPYRIGHT = u"© 2014 Samizdat Drafting Co."

AUTHOR = "Christian Swinehart",
AUTHOR_EMAIL = "drafting@samizdat.cc",
URL = "http://plotdevice.io/",
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

DESCRIPTION = "Create 2-dimensional graphics and animation using Python code"
LONG_DESCRIPTION = """PlotDevice is a Macintosh application used in graphic design research. It provides an
interactive Python environment where you can create two-dimensional graphics
and output them in a variety of vector, bitmap, and animation formats. It is
meant both as a sketch environment for exploring generative design and as a
general purpose graphics library for use in external Python programs.

PlotDevice is a fork of NodeBox 1.9.7rc1 with support for modern versions of
Python and Mac OS.

The new version features:
* Enhanced command line interface.
* New text editor with tab completion, syntax color themes, and emacs/vi bindings.
* Video export in H.264 or animated gif formats (with [GCD](http://en.wikipedia.org/wiki/Grand_Central_Dispatch)-based i/o).
* Added support for external editors by reloading the source when changed.
* Build system now works with Xcode or `py2app` for the application and `pip` for the module.
* Virtualenv support (for both installation of the module and running scripts with dependencies).
* External scripts can use `from plotdevice.script import *` to create a drawing environment.
* Simplified bezier & affine transform api using the python ‘with’ statement
* Now uses the system's Python 2.7 interpreter.
* Includes refreshed offline docs.

Requires:
* Mac OS X 10.9+
"""

plist={
   "UTExportedTypeDeclarations":[
      {
         "UTTypeConformsTo":[
            "public.data"
         ],
         "UTTypeIconFile":"PlotDeviceFile",
         "UTTypeIdentifier":"io.plotdevice.document",
         "UTTypeDescription":"PlotDevice Document",
         "UTTypeTagSpecification":{
            "com.apple.ostype":[
               "TEXT"
            ],
            "public.mime-type":[
               "text\/plain"
            ],
            "public.filename-extension":[
               "pv"
            ]
         }
      }
   ],
   "CFBundleDocumentTypes":[
      {
        "CFBundleTypeExtensions":[
          "pv"
        ],
        "LSTypeIsPackage":0,
        "NSDocumentClass":"PlotDeviceDocument",
        "CFBundleTypeName":"PlotDevice Document",
        "CFBundleTypeIconFile":"PlotDeviceFile.icns",
        "LSItemContentTypes":[
          "io.plotdevice.document"
        ],
        "CFBundleTypeRole":"Editor",
        "LSHandlerRank":"Owner"
      },
      {
        "CFBundleTypeExtensions":[
          "py"
        ],
        "LSTypeIsPackage":0,
        "NSDocumentClass":"PythonScriptDocument",
        "CFBundleTypeName":"Python Script",
        "CFBundleTypeIconFile":"PlotDeviceFile.icns",
        "LSItemContentTypes":[
          "public.python-script"
        ],
        "CFBundleTypeRole":"Editor",
        "LSHandlerRank":"Alternate"
      }
    ],
    "CFBundleIdentifier": BUNDLE_ID,
    "CFBundleName": NAME,
    "CFBundleSignature": CREATOR,
    "CFBundleShortVersionString": VERSION,
    "NSHumanReadableCopyright":COPYRIGHT,

    "LSMinimumSystemVersion":"10.9",
    "NSMainNibFile":"MainMenu",
    "NSPrincipalClass": 'NSApplication',
}

BUILD_APP = any(v in ('py2app','dist') for v in sys.argv)

from distutils.core import Command
class CleanCommand(Command):
    description = "wipe out the ./build ./dist and app/deps/.../build dirs"
    user_options = []
    def initialize_options(self):
        self.cwd = None
    def finalize_options(self):
        self.cwd = os.getcwd()
    def run(self):
        assert os.getcwd() == self.cwd, 'Must be in package root: %s' % self.cwd
        os.system('rm -rf ./build ./dist')
        os.system('rm -rf ./app/deps/*/build')

from distutils.command.build_py import build_py
class BuildCommand(build_py):
    def run(self):
        # first let the real build_py routine do its thing
        build_py.run(self)

        # then build the extensions
        self.spawn(['/usr/bin/python', 'app/deps/build.py', os.path.abspath(self.build_lib)])

        # include some ui resources for running a script from the command line
        rsrc_dir = '%s/plotdevice/rsrc'%self.build_lib
        self.mkpath(rsrc_dir)
        self.copy_file("app/Resources/colors.json", '%s/colors.json'%rsrc_dir)
        self.spawn(['/usr/bin/ibtool','--compile', '%s/viewer.nib'%rsrc_dir, "app/Resources/English.lproj/PlotDeviceScript.xib"])
        self.copy_file("app/Resources/PlotDeviceFile.icns", '%s/viewer.icns'%rsrc_dir)


if BUILD_APP:
    # virtualenv doesn't include pyobjc, py2app, etc. in the sys.path for some reason, so make sure
    # we only try to import them if an app (or dist) build was explicitly requested (implying we're using
    # the system's python interpreter rather than pip+virtualenv)
    import py2app
    from py2app.build_app import py2app as build_app
    class BuildAppCommand(build_app):
        description = """Build PlotDevice.app with py2app (then undo some of its questionable layout defaults)"""
        def initialize_options(self):
            self.cwd = None
            build_app.initialize_options(self)
        def finalize_options(self):
            self.cwd = os.getcwd()
            self.verbose=0
            build_app.finalize_options(self)
        def run(self):
            TOP=self.cwd
            assert os.getcwd() == self.cwd, 'Must be in package root: %s' % self.cwd
            build_app.run(self)
            if self.dry_run:
                return

            # set up internal paths and ensure destination dirs exist
            from os.path import join, dirname
            RSRC = self.resdir
            BIN = join(dirname(RSRC), 'SharedSupport')
            MODULE = join(self.bdist_base, 'lib/plotdevice')
            PY = join(RSRC, 'python')
            for pth in BIN, PY:
                self.mkpath(pth)

            # unpack the zipped up pyc files and merge with the module sources
            self.spawn(['/usr/bin/ditto', MODULE, join(PY, 'plotdevice')])

            # discard the eggery-pokery
            remove_tree(join(RSRC,'lib'), dry_run=self.dry_run)
            os.unlink(join(RSRC,'include'))
            os.unlink(join(RSRC,'site.pyc'))

            # place the command line tool in SharedSupport
            self.copy_file("%s/app/plotdevice"%TOP, BIN)

            # install the documentation
            self.spawn(['/usr/bin/ditto', join(TOP, 'doc'), join(RSRC, 'doc')])
            self.spawn(['/usr/bin/ditto', join(TOP, 'app/Resources/examples'), join(RSRC, 'examples')])

            print "done building PlotDevice.app in ./dist"

    class DistCommand(Command):
        description = "Create distributable zip and dmg files containing the app + documentation"
        user_options = []
        def initialize_options(self):
            self.cwd = None
        def finalize_options(self):
            self.cwd = os.getcwd()
        def run(self):
            TOP = self.cwd
            APP = '%s/dist/PlotDevice.app'%TOP
            ZIP = APP.replace('.app', '-%s.zip'%VERSION)

            # build the app
            self.spawn(['xcodebuild'])
            remove_tree(APP+'.dSYM')

            # codesign using the most generic identity name possible
            self.spawn(['codesign', '-f', '-s', "Developer ID Application", APP])
            self.spawn(['spctl', '--assess', '-v', 'dist/PlotDevice.app'])

            # create a versioned zip file
            self.spawn(['ditto','-ck', '--keepParent', APP, ZIP])


if __name__=='__main__':
    config = {}

    # common config between module and app builds
    config.update(dict(
        name = NAME,
        version = VERSION,
        description = DESCRIPTION,
        long_description = LONG_DESCRIPTION,
        author = AUTHOR,
        author_email = AUTHOR_EMAIL,
        url = URL,
        classifiers = CLASSIFIERS,
        packages = find_packages(),
        scripts = ["app/plotdevice"],
        zip_safe=False,
        cmdclass={
            'clean': CleanCommand,
            'build_py': BuildCommand
        },
    ))


    # app-specific config
    if BUILD_APP:
        config.update(dict(
            app = [{
                'script': "app/plotdevice-app.py",
                "plist":plist,
            }],
            data_files = [
                "app/Resources/ui",
                "app/Resources/English.lproj",
                "app/Resources/PlotDevice.icns",
                "app/Resources/PlotDeviceFile.icns",
            ],
            options = {
                "py2app": {
                    "iconfile": "app/Resources/PlotDevice.icns",
                    "semi_standalone":True,
                    "site_packages":True,
                    "strip":False,
                }
            },
        ))
        config['cmdclass'].update({
            'py2app': BuildAppCommand,
            'dist': DistCommand,
        })
    setup(**config)
