# Startup file for the NodeBox OS X application
# PyObjC requires the startup file to be in the root folder.
# This just imports everything from the nodebox.gui module
# and works from there

import objc
import Foundation
import AppKit

from PyObjCTools import AppHelper

import nodebox.gui

AppHelper.runEventLoop()
