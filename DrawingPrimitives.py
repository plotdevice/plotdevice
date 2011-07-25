# This file is obsolete.
# NodeBox now uses a package structure.
# The drawing primitives are now in the new "nodebox.graphics" package.
# This will also ensure you get the graphics package for the correct platform.

import nodebox.graphics.cocoa
from nodebox.graphics.cocoa import *
from nodebox.util import *

__all__ = nodebox.graphics.cocoa.__all__

import warnings
warnings.warn('DrawingPrimitives is deprecated. Please use "from nodebox import graphics"', DeprecationWarning, stacklevel=2)