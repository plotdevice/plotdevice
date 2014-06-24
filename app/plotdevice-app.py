import sys
import objc
import Foundation
import AppKit
from signal import signal, SIGINT
from os.path import dirname, abspath, join
from PyObjCTools import AppHelper

# rather than hijacking PYTHONPATH in the .m loader, add the module directory now
sys.path.append('%s/Contents/Resources/python'%abspath(Foundation.NSBundle.mainBundle().bundlePath()))

# install a signal handler to quit on ^c (should the app ever be launched from terminal)
signal(SIGINT, lambda m,n: AppKit.NSApplication.sharedApplication().terminate_(True))

# PlotDevice is a typical document-based application. We'll import the PlotDeviceDocument
# class et al from the gui module and the corresponding document-type defined in the
# info.plist will do the rest.
import plotdevice.gui

# loop forever
AppHelper.runEventLoop()
