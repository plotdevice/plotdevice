# This is a setup file for a command-line version of NodeBox.
# If you want to work on the Mac OS X version, go look in macsetup.py.

# This is your standard setup.py, so to install the package, use:
#     python setup.py install

# We require some dependencies:
# - PyObjC
# - psyco
# - py2app
# - cPathMatics (included in the "libs" folder)
# - polymagic (included in the "libs" folder)
# - Numeric (included in the "libs" folder)
# - Numpy (installable using "easy_install numpy")

import sys,os
from distutils.core import setup, Command
from distutils.command.build_py import build_py
from setuptools import find_packages
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
    Extension('cIO', ['libs/IO/module.m','libs/IO/Installer.m', 'libs/IO/ImageSequence.m', 'libs/IO/AnimatedGif.m', 'libs/IO/Video.m'], extra_link_args=['-framework', 'AppKit', '-framework', 'Foundation', '-framework', 'Security', '-framework', 'AVFoundation', '-framework', 'CoreMedia', '-framework', 'CoreVideo'], **quiet)
]

plist={
    'CFBundleDocumentTypes': [{
        'CFBundleTypeExtensions': [ 'py' ],
        'CFBundleTypeIconFile': 'NodeBoxFile.icns',
        'CFBundleTypeName': "Python File",
        'CFBundleTypeRole': 'Editor',
        'LSItemContentTypes':['public.python-script'],
        'LSHandlerRank':'Alternate',
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
    "Resources/English.lproj/ExportImageAccessory.xib",
    "Resources/English.lproj/ExportMovieAccessory.xib",
    "Resources/English.lproj/MainMenu.xib",
    "Resources/English.lproj/NodeBox Help",
    "Resources/English.lproj/NodeBoxDocument.xib",
    "Resources/English.lproj/NodeBoxPreferences.xib",
    "Resources/English.lproj/ProgressBarSheet.xib",
    "Resources/NodeBox.icns",
    "Resources/NodeBoxFile.icns",
]

BUILD_APP = 'py2app' in sys.argv
if BUILD_APP:
    import py2app

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

class BuildCommand(build_py):
    def run(self):

        # let the real build_py routine do its thing
        build_py.run(self)

        # include some ui resources for running a script from the command line
        if not BUILD_APP:
            rsrc_dir = '%s/nodebox/run/rsrc'%self.build_lib
            self.mkpath(rsrc_dir)
            self.spawn(['/usr/bin/ibtool','--compile', '%s/viewer.nib'%rsrc_dir, "Resources/English.lproj/NodeBoxDocument.xib"])
            self.copy_file("Resources/NodeBoxFile.icns", '%s/icon.icns'%rsrc_dir)
        
if __name__=='__main__':
    config = {}

    # app-specific config
    if BUILD_APP:
        config.update(dict(
            app = [{
                'script': "boot/nodebox-app.py",
                "plist":plist,
            }],
            data_files = rsrc,
            options = {
                "py2app": {
                    "iconfile": "Resources/NodeBox.icns",
                    "semi_standalone":True,
                    "site_packages":True,
                    "strip":False,
                    "semi_standalone":True,
                }
            },
        ))

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
        scripts = ["boot/nodebox"],
        zip_safe=False,
        cmdclass={
            'clean': CleanCommand,
            'build_py': BuildCommand,
        },
    ))

    setup(**config)
