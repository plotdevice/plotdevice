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

from distutils.core import setup, Extension
import nodebox

NAME = 'NodeBox'
VERSION = nodebox.__version__

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
* PDF export for graphics
* QuickTime export for animations
* Manipulate every numeric variable in a script by command-dragging it, even during animation
* Creating simple user interfaces using text fields, sliders, and buttons
* Stop a running script by typing command-period
* Universal Binary
* Integrated bezier mathematics and boolean operations
* Command-line interface
* Zooming
"""

ext_modules = [
    Extension('cGeo', ['nodebox/ext/cGeo.c']),
    Extension('cPathmatics', ['nodebox/ext/cPathmatics.c']),
    Extension('cPolymagic', ['nodebox/ext/gpc.c', 'nodebox/ext/cPolymagic.m'], extra_link_args=['-framework', 'AppKit', '-framework', 'Foundation'])
    ]

packages = ['nodebox', 'nodebox.graphics', 'nodebox.util', 'nodebox.geo']

if __name__=='__main__':

    setup(name = NAME,
        version = VERSION,
        description = DESCRIPTION,
        long_description = LONG_DESCRIPTION,
        author = AUTHOR,
        author_email = AUTHOR_EMAIL,
        url = URL,
        classifiers = CLASSIFIERS,
        ext_modules = ext_modules,
        packages = packages
    )

