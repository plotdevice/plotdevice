# Setup file for the NodeBox OS X application.
#
# You can create the application by running:
#
#     python macsetup.py py2app -A
#
# This creates a linked distribution, so changes to the python files only require you to restart the application.
# This is the preferred way to develop.
# To create a full distribution, use the macbuild.sh shell script to pull in all the right files.

#from distutils.core import setup, Extension

import py2app
from distutils.core import setup, Extension

from setup import VERSION, NAME, packages, ext_modules
packages.extend(['nodebox.gui', 'nodebox.gui.mac'])

# Useful site packages
includes = ['Image', 'numpy', 'psyco']

plist = dict(
    CFBundleDocumentTypes = [
        dict(
            CFBundleTypeExtensions = ["py"],
            CFBundleTypeName = "Python Source File",
            CFBundleTypeRole = "Editor",
            NSDocumentClass = "NodeBoxDocument",
            CFBundleTypeIconFile = "NodeBoxFile.icns",
        ),
    ],
    CFBundleIconFile = NAME + '.icns',
    CFBundleName = NAME,
    CFBundleShortVersionString = VERSION,
    CFBundleVersion='',
    CFBundleGetInfoString= VERSION,
    CFBundleExecutable = NAME,
    LSMinimumSystemVersion = "10.5.0",
    CFBundleIdentifier = 'net.nodebox.NodeBox',
    CFBundleSignature = 'NdBx',
    CFBundleInfoDictionaryVersion=VERSION,
    NSHumanReadableCopyright= u'Copyright © 2003-2009 NodeBox. All Rights Reserved.',
    CFBundleHelpBookFolder='NodeBox Help',
    CFBundleHelpBookName='NodeBox Help',
)
py2app_options = {
    'optimize': 2,
    'iconfile': 'Resources/NodeBox.icns',
    'site_packages': True,
    'includes': includes,
}

if __name__=='__main__':

    setup(name = NAME,
        version = VERSION,
        data_files = [
            'Resources/English.lproj',
            'Resources/Credits.rtf',
            'Resources/NodeBox.icns',
            'Resources/NodeBoxFile.icns',
            'Resources/zoombig.png',
            'Resources/zoomsmall.png',
        ],
        app = [dict(script='macboot.py', plist=plist)],
        packages = packages,
        ext_modules = ext_modules,
        options = {'py2app':py2app_options},
        ),
