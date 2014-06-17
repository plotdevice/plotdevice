import sys
import objc
import Foundation
import AppKit
from os.path import dirname, abspath, join
from PyObjCTools import AppHelper

# rather than hijacking PYTHONPATH in the .m loader, add the module + .so directory here
# (we insert rather than append to avoid getting trapped in py2app's zipfile)
sys.path.insert(0, '%s/Contents/Resources/python'%abspath(Foundation.NSBundle.mainBundle().bundlePath()))

# PlotDevice is a typical document-based application. We'll import the PlotDeviceDocument
# class et al from the gui module and the corresponding document-type defined in the
# info.plist will do the rest.
import plotdevice.gui

AppHelper.runEventLoop()
