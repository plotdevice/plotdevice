def bundle_path(subpath=None, rsrc=None, fmwk=None):
    """Find the path to the main NSBundle (or an optional subpath within it)"""
    from os.path import join
    from Foundation import NSBundle
    bundle = NSBundle.mainBundle().bundlePath()
    if rsrc:
      return join(bundle, "Contents", "Resources", rsrc)
    if fmwk:
      return join(bundle, "Contents", "Frameworks", '%s.framework' % fmwk)
    if subpath:
        return join(bundle, subpath)
    return bundle

from Foundation import NSTimer
def set_timeout(target, sel, delay, info=None, repeat=False):
    return NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(delay, target, sel, info, repeat)

from .document import PlotDeviceDocument, PythonScriptDocument, ScriptController
from .app import PlotDeviceAppDelegate
from .views import GraphicsBackdrop, GraphicsView, FullscreenView
from .widgets import StatusView, DashboardController, ExportSheet
