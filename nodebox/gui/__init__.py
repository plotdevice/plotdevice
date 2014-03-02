def bundle_path(subpath=None):
    """Find the path to the main NSBundle (or an optional subpath within it)"""
    from os.path import join
    from Foundation import NSBundle
    bundle = NSBundle.mainBundle().bundlePath()
    if subpath:
        return join(bundle, subpath)
    return bundle

from nodebox.gui.document import NodeBoxDocument, PythonScriptDocument
from nodebox.gui.app import NodeBoxAppDelegate
from nodebox.gui.views import ZoomPanel, NodeBoxBackdrop, NodeBoxGraphicsView, FullscreenView

