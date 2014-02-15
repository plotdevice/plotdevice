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
import nodebox

NAME = 'NodeBox'
VERSION = nodebox.__version__
CREATOR = 'NdBx'
BUNDLE_ID = "net.nodebox.NodeBox"
HELP = "NodeBox Help"

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

DESCRIPTION = "Simple application for creating 2-dimensional graphics and animation using Python code"
LONG_DESCRIPTION = """NodeBox is a Mac OS X application that allows you to create visual output
with programming code. The application targets an audience of designers, with an easy set of state 
commands that is both intuitive and creative. It is essentially a learning environment and an automation tool.

The current version features:
* State-based graphics context
* Extensive reference documentation and tutorials
* Vector (pdf/eps) or raster (png/jpg/gif/tiff) export for graphics
* H.264 or Gif export for animations
* Manipulate every numeric variable in a script by command-dragging it, even during animation
* Creating simple user interfaces using text fields, sliders, and buttons
* Stop a running script by typing command-period
* Integrated bezier mathematics and boolean operations
* Command-line interface
* Zooming

Requires:
* Mac OS X 10.9+
"""

quiet = {"extra_compile_args":['-Qunused-arguments']}

ext_modules = [
    Extension('cGeo', ['libs/cGeo/cGeo.c'], **quiet),
    Extension('cPathmatics', ['libs/pathmatics/pathmatics.c'], **quiet),
    Extension('cPolymagic', ['libs/polymagic/gpc.c', 'libs/polymagic/polymagic.m'], extra_link_args=['-framework', 'AppKit', '-framework', 'Foundation'], **quiet),
    Extension('cIO', ['libs/IO/module.m','libs/IO/Installer.m', 'libs/IO/ImageSequence.m', 'libs/IO/AnimatedGif.m', 'libs/IO/Video.m'], extra_link_args=['-framework', 'AppKit', '-framework', 'Foundation', '-framework', 'Security', '-framework', 'AVFoundation', '-framework', 'CoreMedia', '-framework', 'CoreVideo'], **quiet),
    Extension('cEvents', ['libs/macfsevents/_fsevents.c', 'libs/macfsevents/compat.c'], extra_link_args = ["-framework","CoreFoundation", "-framework","CoreServices"], **quiet),
]

plist={
    'CFBundleDocumentTypes': [{
        'CFBundleTypeExtensions': [ 'py' ],
        'CFBundleTypeIconFile': 'NodeBoxFile.icns',
        'CFBundleTypeName': "Python File",
        'CFBundleTypeRole': 'Editor',
        'LSItemContentTypes':['public.python-script'],
        'LSHandlerRank':'Owner',
        'NSDocumentClass': 'NodeBoxDocument',
    }],
    "CFBundleIdentifier": BUNDLE_ID,
    "CFBundleName": NAME,
    "CFBundleSignature": CREATOR,
    "CFBundleShortVersionString": VERSION,
    "CFBundleGetInfoString": DESCRIPTION,
    "CFBundleHelpBookFolder":HELP,
    "CFBundleHelpBookName":HELP,
    "LSMinimumSystemVersion":"10.9",
    "NSMainNibFile":"MainMenu",
    "NSPrincipalClass": 'NSApplication',
}

rsrc = [
    "Resources/English.lproj/AskString.xib",
    "Resources/English.lproj/Credits.rtf",
    "Resources/English.lproj/MainMenu.xib",
    "Resources/English.lproj/NodeBoxDocument.xib",
    "Resources/English.lproj/NodeBoxPreferences.xib",
    "Resources/NodeBox.icns",
    "Resources/NodeBoxFile.icns",
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

from distutils.command.build_ext import build_ext
class BuildExtCommand(build_ext):
    def run(self):
        # c-extensions post-build hook:
        #   - move all the .so files out of the top-level directory

        build_ext.run(self) # first let the real build_ext routine do its thing
        if BUILD_APP: return # py2app moves the libraries to lib-dynload instead
        self.mkpath('%s/nodebox/ext'%self.build_lib)
        for ext in self.extensions:
            src = "%s/%s.so"%(self.build_lib, ext.name)
            dst = "%s/nodebox/ext/%s.so"%(self.build_lib, ext.name)
            self.move_file(src, dst)

from distutils.command.build_py import build_py
class BuildCommand(build_py):
    def run(self):
        # nodebox module post-build hook:
        #   - include some ui resources for running a script from the command line
        
        build_py.run(self) # first let the real build_py routine do its thing
        if BUILD_APP: return # the app bundle doesn't need the NodeBoxScript nib
        rsrc_dir = '%s/nodebox/rsrc'%self.build_lib
        self.mkpath(rsrc_dir)
        self.spawn(['/usr/bin/ibtool','--compile', '%s/NodeBoxScript.nib'%rsrc_dir, "Resources/English.lproj/NodeBoxScript.xib"])
        self.copy_file("Resources/NodeBoxFile.icns", '%s/icon.icns'%rsrc_dir)
        
if BUILD_APP:
    # virtualenv doesn't include pyobjc, py2app, etc. in the sys.path for some reason, so make sure 
    # we only try to import them if an app (or dist) build was explicitly requested (implying we're using
    # the system's python interpreter rather than pip+virtualenv)
    import py2app
    from py2app.build_app import py2app as build_app
    class BuildAppCommand(build_app):
        description = """Build NodeBox.app with py2app (then undo some of its questionable layout defaults)"""
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
            RSRC="%s/dist/NodeBox.app/Contents/Resources"%self.cwd
            BIN="%s/dist/NodeBox.app/Contents/SharedSupport"%self.cwd
            self.mkpath(BIN)
            self.mkpath("%s/python"%RSRC)
            self.mkpath("%s/English.lproj"%RSRC)
            remove_tree("%s/../Frameworks"%RSRC, dry_run=self.dry_run)

            # place the command line tool in SharedSupport
            self.copy_file("%s/etc/nodebox"%TOP, BIN)

            # put the module and .so files in a known location (primarily so the
            # tool can find task.py)
            self.copy_tree('%s/nodebox'%TOP, '%s/python/nodebox'%RSRC)
            self.copy_tree('%s/lib/python2.7/lib-dynload'%RSRC, '%s/python/nodebox/ext'%RSRC)
            # find $TOP/nodebox -name \*pyc -exec rm {} \;

            # install the documentation
            self.copy_tree('%s/doc/examples'%TOP, '%s/examples'%RSRC)

            print "done building NodeBox.app in ./dist"

    class DistCommand(Command):
        description = "Create distributable zip and dmg files containing the app + documentation"
        user_options = []
        def initialize_options(self):
            self.cwd = None
        def finalize_options(self):
            self.cwd = os.getcwd()
        def run(self):
            TOP = self.cwd
            DEST = "%s/dist/NodeBox/NodeBox"%self.cwd
            DMG = 'NodeBox-%s.dmg'%VERSION
            ZIP = 'NodeBox-%s.zip'%VERSION

            # build the app
            self.run_command('py2app')

            # Make a staging area for the disk image
            self.mkpath(DEST)

            # Copy the current NodeBox application.
            self.copy_tree("dist/NodeBox.app", "%s/NodeBox.app"%DEST)

            # Copy changes and readme
            self.copy_file('CHANGES.md', '%s/Changes.txt'%DEST)
            self.copy_file('README.md', '%s/Readme.txt'%DEST)

            # Copy examples
            self.copy_tree('%s/doc/examples'%TOP, '%s/Examples'%DEST)
            # chmod 755 Examples/*/*.py

            # Make DMG
            os.chdir('dist')
            self.spawn(['hdiutil','create',DMG,'-srcfolder','NodeBox'])
            self.spawn(['hdiutil','internet-enable',DMG])

            # Make Zip
            os.chdir('NodeBox')
            self.spawn(['zip','-r','-q',ZIP,'NodeBox'])
            self.move_file(ZIP, '%s/dist'%TOP)

            # clean up the staging area
            remove_tree('%s/dist/NodeBox'%TOP, verbose=False)

            print "done building NodeBox.app, %s, and %s in ./dist"%(ZIP,DMG)


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
        ext_modules = ext_modules,
        packages = find_packages(),
        scripts = ["etc/nodebox"],
        zip_safe=False,
        cmdclass={
            'clean': CleanCommand,
            'build_py': BuildCommand,
            'build_ext': BuildExtCommand,
        },
    ))


    # app-specific config
    if BUILD_APP:
        config.update(dict(
            app = [{
                'script': "etc/nodebox-app.py",
                "plist":plist,
            }],
            data_files = rsrc,
            options = {
                "py2app": {
                    "iconfile": "Resources/NodeBox.icns",
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
