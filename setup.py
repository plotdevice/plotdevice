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
VERSION = '1.0'
CREATOR = 'Plod'
BUNDLE_ID = "io.plotdevice.PlotDevice"

AUTHOR = "Frederik De Bleser",
AUTHOR_EMAIL = "frederik@pandora.be",
URL = "http://nodebox.net/",
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

# quiet = {"extra_compile_args":['-Qunused-arguments']}

# ext_modules = [
#     Extension('cGeo', ['libs/cGeo/cGeo.c'], **quiet),
#     Extension('cPathmatics', ['libs/pathmatics/pathmatics.c'], **quiet),
#     Extension('cPolymagic', ['libs/polymagic/gpc.c', 'libs/polymagic/polymagic.m'], extra_link_args=['-framework', 'AppKit', '-framework', 'Foundation'], **quiet),
#     Extension('cIO', ['libs/IO/module.m','libs/IO/SysAdmin.m', 'libs/IO/ImageSequence.m', 'libs/IO/AnimatedGif.m', 'libs/IO/Video.m'], extra_link_args=['-framework', 'AppKit', '-framework', 'Foundation', '-framework', 'Security', '-framework', 'AVFoundation', '-framework', 'CoreMedia', '-framework', 'CoreVideo'], **quiet),
#     Extension('cEvents', ['libs/macfsevents/_fsevents.c', 'libs/macfsevents/compat.c'], extra_link_args = ["-framework","CoreFoundation", "-framework","CoreServices"], **quiet),
# ]

plist={
    'CFBundleDocumentTypes': [{
        'CFBundleTypeExtensions': [ 'py' ],
        'CFBundleTypeIconFile': 'PlotDeviceFile.icns',
        'CFBundleTypeName': "Python File",
        'CFBundleTypeRole': 'Editor',
        'LSItemContentTypes':['public.python-script'],
        'LSHandlerRank':'Owner',
        'NSDocumentClass': 'PlotDeviceDocument',
    }],
    "CFBundleIdentifier": BUNDLE_ID,
    "CFBundleName": NAME,
    "CFBundleSignature": CREATOR,
    "CFBundleShortVersionString": VERSION,
    "CFBundleGetInfoString": DESCRIPTION,
    "LSMinimumSystemVersion":"10.9",
    "NSMainNibFile":"MainMenu",
    "NSPrincipalClass": 'NSApplication',
}


rsrc = [
    "Resources/English.lproj/AskString.xib",
    "Resources/English.lproj/Credits.rtf",
    "Resources/English.lproj/MainMenu.xib",
    "Resources/English.lproj/PlotDeviceDocument.xib",
    "Resources/English.lproj/PlotDevicePreferences.xib",
    "Resources/ui",
    "Resources/PlotDevice.icns",
    "Resources/PlotDeviceFile.icns",
]

BUILD_APP = any(v in ('py2app','dist') for v in sys.argv)

from distutils.core import Command
class CleanCommand(Command):
    description = "wipe out the ./build ./dist and libs/.../build dirs"
    user_options = []
    def initialize_options(self):
        self.cwd = None
    def finalize_options(self):
        self.cwd = os.getcwd()
    def run(self):
        assert os.getcwd() == self.cwd, 'Must be in package root: %s' % self.cwd
        os.system('rm -rf ./build ./dist')
        os.system('rm -rf ./libs/*/build')

# from distutils.command.build_ext import build_ext
# class BuildExtCommand(build_ext):
#     def run(self):
#         # c-extensions post-build hook:
#         #   - move all the .so files out of the top-level directory

#         if BUILD_APP:
#             build_ext.run(self) # first let the real build_ext routine do its thing
#             return # py2app moves the libraries to lib-dynload instead

#         self.spawn(['/usr/bin/python', 'libs/buildlibs.py'])
#         print "built libs from", os.getcwd()
#         self.spawn(['/usr/bin/ditto', 'build/libs', '%s/plotdevice/lib'%self.build_lib])

#         # build_ext.run(self) # first let the real build_ext routine do its thing
#         # if BUILD_APP: return # py2app moves the libraries to lib-dynload instead
#         # self.mkpath('%s/plotdevice/ext'%self.build_lib)

#         # for ext in self.extensions:
#         #     print "each", self.build_lib, ext.name
#         #     src = "%s/%s.so"%(self.build_lib, ext.name)
#         #     dst = "%s/plotdevice/libs/%s.so"%(self.build_lib, ext.name)
#         #     self.move_file(src, dst)
#             # self.spawn(['/usr/bin/touch',"%s/plotdevice/ext/__init__.py"%self.build_lib])

from distutils.command.build_py import build_py
class BuildCommand(build_py):
    def run(self):
        # plotdevice module post-build hook:
        #   - include some ui resources for running a script from the command line

        build_py.run(self) # first let the real build_py routine do its thing
        self.spawn(['/usr/bin/python', 'libs/buildlibs.py']) # then build the extensions
        print "built libs from", os.getcwd()

        if BUILD_APP: return # the app bundle doesn't need the PlotDeviceScript nib
        rsrc_dir = '%s/plotdevice/rsrc'%self.build_lib
        self.mkpath(rsrc_dir)
        self.spawn(['/usr/bin/ibtool','--compile', '%s/PlotDeviceScript.nib'%rsrc_dir, "Resources/English.lproj/PlotDeviceScript.xib"])
        self.copy_file("Resources/PlotDeviceFile.icns", '%s/icon.icns'%rsrc_dir)
        self.spawn(['/usr/bin/ditto', 'build/ext', '%s/plotdevice/lib'%self.build_lib])


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
            build_app.finalize_options(self)
        def run(self):
            TOP=self.cwd
            assert os.getcwd() == self.cwd, 'Must be in package root: %s' % self.cwd
            build_app.run(self)

            # Do some py2app `configuration' to make the bundle layout more
            # like what xcode produces
            RSRC="%s/dist/PlotDevice.app/Contents/Resources"%self.cwd
            BIN="%s/dist/PlotDevice.app/Contents/SharedSupport"%self.cwd
            self.mkpath(BIN)
            self.mkpath("%s/python"%RSRC)
            self.mkpath("%s/English.lproj"%RSRC)
            remove_tree("%s/../Frameworks"%RSRC, dry_run=self.dry_run)

            # place the command line tool in SharedSupport
            self.copy_file("%s/etc/plotdevice"%TOP, BIN)

            # put the module and .so files in a known location (primarily so the
            # tool can find task.py)
            self.copy_tree('%s/plotdevice'%TOP, '%s/python/plotdevice'%RSRC)
            # self.copy_tree('%s/lib/python2.7/lib-dynload'%RSRC, '%s/python/plotdevice/ext'%RSRC)
            self.spawn(['/usr/bin/ditto', '%s/build/ext'%TOP, '%s/python/plotdevice/lib'%RSRC])
            self.spawn(['/usr/bin/ditto', '%s/build/ext'%TOP, '%s/lib/python2.7/lib-dynload'%RSRC])

            # find $TOP/plotdevice -name \*pyc -exec rm {} \;

            # install the documentation
            self.copy_tree('%s/doc/examples'%TOP, '%s/examples'%RSRC)

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
            DEST = "%s/dist/PlotDevice/PlotDevice"%self.cwd
            DMG = 'PlotDevice-%s.dmg'%VERSION
            ZIP = 'PlotDevice-%s.zip'%VERSION

            # build the app
            self.run_command('py2app')

            # Make a staging area for the disk image
            self.mkpath(DEST)

            # Copy the current PlotDevice application.
            self.copy_tree("dist/PlotDevice.app", "%s/PlotDevice.app"%DEST)

            # Copy changes and readme
            self.copy_file('CHANGES.md', '%s/Changes.txt'%DEST)
            self.copy_file('README.md', '%s/Readme.txt'%DEST)

            # Copy examples
            self.copy_tree('%s/doc/examples'%TOP, '%s/Examples'%DEST)
            # chmod 755 Examples/*/*.py

            # Make DMG
            os.chdir('dist')
            self.spawn(['hdiutil','create',DMG,'-srcfolder','PlotDevice'])
            self.spawn(['hdiutil','internet-enable',DMG])

            # Make Zip
            os.chdir('PlotDevice')
            self.spawn(['zip','-r','-q',ZIP,'PlotDevice'])
            self.move_file(ZIP, '%s/dist'%TOP)

            # clean up the staging area
            remove_tree('%s/dist/PlotDevice'%TOP, verbose=False)

            print "done building PlotDevice.app, %s, and %s in ./dist"%(ZIP,DMG)


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
        # ext_modules = ext_modules,
        packages = find_packages(),
        package_data = {'plotdevice.graphics':['colors.json']},
        scripts = ["etc/plotdevice"],
        zip_safe=False,
        cmdclass={
            'clean': CleanCommand,
            'build_py': BuildCommand,
            # 'build_ext': BuildExtCommand,
        },
    ))


    # app-specific config
    if BUILD_APP:
        config.update(dict(
            app = [{
                'script': "etc/plotdevice-app.py",
                "plist":plist,
            }],
            data_files = rsrc,
            options = {
                "py2app": {
                    "iconfile": "Resources/PlotDevice.icns",
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
