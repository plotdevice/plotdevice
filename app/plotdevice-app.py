import sys
from os.path import dirname, abspath, join

# rather than hijacking PYTHONPATH in the .m loader, add the module directory now
sys.path.append(join(dirname(abspath(__file__)), 'python'))

# PlotDevice is a typical document-based application. We'll import the PlotDeviceDocument
# class et al from the gui module and the corresponding document-type defined in the
# info.plist will do the rest.
import plotdevice.gui

# install a signal handler to quit on ^c (should the app ever be launched from terminal)
import AppKit
from signal import signal, SIGINT
signal(SIGINT, lambda m,n: AppKit.NSApplication.sharedApplication().terminate_(True))

# loop forever
from PyObjCTools import AppHelper
AppHelper.runEventLoop()
