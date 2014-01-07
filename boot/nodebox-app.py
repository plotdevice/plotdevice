import sys
import objc
import Foundation
import AppKit
from os.path import dirname, abspath, join
from PyObjCTools import AppHelper

# rather than hijacking PYTHONPATH in the .m loader, add the module + .so directory here
sys.path.append('%s/Contents/Resources/python'%abspath(Foundation.NSBundle.mainBundle().bundlePath()))

# NodeBox is a typical document-based application. We'll import the NodeBoxDocument
# class et al from the gui module and the corresponding document-type defined in the
# info.plist will do the rest.
import nodebox.gui

AppHelper.runEventLoop()
