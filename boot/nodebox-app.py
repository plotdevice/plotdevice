import sys
import objc
import Foundation
import AppKit
from os.path import dirname, abspath, join
from PyObjCTools import AppHelper

# can't really see a downside to directly printing exceptions to the console (vs having main.m try
# to catch and echo them)
objc.setVerbose(1)


# rather than hijacking PYTHONPATH in the .m loader, add the module + .so directory here
sys.path.append('%s/Contents/Resources/python'%abspath(Foundation.NSBundle.mainBundle().bundlePath()))

# NodeBox is a typical document-based application. We'll import the NodeBoxDocument
# class et al from the gui module and the corresponding document-type defined in the
# info.plist will do the rest.
import nodebox.gui

AppHelper.runEventLoop()
