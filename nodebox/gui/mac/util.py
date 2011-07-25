from Foundation import *
from AppKit import *

def errorAlert(msgText, infoText):
    # Force NSApp initialisation.
    NSApplication.sharedApplication().activateIgnoringOtherApps_(0)
    alert = NSAlert.alloc().init()
    alert.setMessageText_(msgText)
    alert.setInformativeText_(infoText)
    alert.setAlertStyle_(NSCriticalAlertStyle)
    btn = alert.addButtonWithTitle_("OK")
    return alert.runModal()
