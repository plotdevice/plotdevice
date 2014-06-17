import unittest
import sys

# To run the test, make sure you have at least built the PlotDevice Extensions.
# Run the following command in the Terminal:
#   xcodebuild -target "Build Extensions"
sys.path.append('..')
sys.path.append('../build/libs')

from plotdevice.graphics import *

class GraphicsTestCase(unittest.TestCase):

    def setUp(self):
        self.ctx = Context()

    def test_arrow_type_error(self):
        """Test if passing a wrong arrow type raises an error."""
        self.assertRaises(DeviceError, self.ctx.arrow, 0, 0, 100, type=42)

    def test_too_many_pops(self):
        """Test if popping too many times raises an error."""
        self.assertRaises(DeviceError, self.ctx.pop)

    def test_font_not_found(self):
        """Test if setting an unexisting font raises an error."""
        old_font = self.ctx.font()
        self.assertRaises(DeviceError, self.ctx.font, "THIS_FONT_DOES_NOT_EXIST")
        self.assertEquals(self.ctx.font(), old_font, "Current font has not changed.")

    def test_ellipse(self):
        """Test if ellipse is an alias for oval."""
        self.assertTrue(hasattr(self.ctx, "ellipse"))
        self.assertTrue(self.ctx.ellipse == self.ctx.oval)
        p = BezierPath(self.ctx)
        self.assertTrue(hasattr(p, "ellipse"))
        self.assertTrue(p.ellipse == p.oval)

class BezierPathTestCase(unittest.TestCase):

    def setUp(self):
        self.ctx = Context()

    def test_capstyle_context(self):
        self.ctx.capstyle(SQUARE)
        p = BezierPath(self.ctx)
        self.assertEquals(p.capstyle, BUTT, "Default line cap style is butt.")
        p.inheritFromContext()
        self.assertEquals(p.capstyle, SQUARE)

    def test_capstyle_constructor(self):
        p = BezierPath(self.ctx, capstyle=ROUND)
        self.assertEquals(p.capstyle, ROUND)

    def test_capstyle_validation(self):
        self.assertRaises(DeviceError, self.ctx.capstyle, 42)
        self.assertRaises(DeviceError, BezierPath, self.ctx, capstyle=42)
        p = BezierPath(self.ctx)
        self.assertRaises(DeviceError, p._set_capstyle, 42)

    def test_joinstyle_context(self):
        self.ctx.joinstyle(ROUND)
        p = BezierPath(self.ctx)
        self.assertEquals(p.joinstyle, MITER, "Default line join style is miter.")
        p.inheritFromContext()
        self.assertEquals(p.joinstyle, ROUND)

    def test_joinstyle_constructor(self):
        p = BezierPath(self.ctx, joinstyle=ROUND)
        self.assertEquals(p.joinstyle, ROUND)

    def test_joinstyle_validation(self):
        self.assertRaises(DeviceError, self.ctx.joinstyle, 42)
        self.assertRaises(DeviceError, BezierPath, self.ctx, joinstyle=42)
        p = BezierPath(self.ctx)
        self.assertRaises(DeviceError, p._set_joinstyle, 42)

if __name__=='__main__':
    unittest.main()