import unittest
import sys

# To run the test, make sure you have at least built the NodeBox Extensions.
# Run the following command in the Terminal:
#   xcodebuild -target "Build Extensions"
sys.path.append('..')
sys.path.append('../build/libs')

from nodebox.graphics import *

class GraphicsTestCase(unittest.TestCase):
    
    def test_arrow_type_error(self):
        """Test if passing a wrong arrow type raises an error."""
        ctx = Context()
        self.assertRaises(NodeBoxError, ctx.arrow, 0, 0, 100, type=42)

    def test_too_many_pops(self):
        """Test if popping too many times raises an error."""
        ctx = Context()
        self.assertRaises(NodeBoxError, ctx.pop)
        
    def test_font_not_found(self):
        """Test if setting an unexisting font raises an error."""
        ctx = Context()
        old_font = ctx.font()
        self.assertRaises(NodeBoxError, ctx.font, "THIS_FONT_DOES_NOT_EXIST")
        self.assertEquals(ctx.font(), old_font, "Current font has not changed.")
    
    def test_ellipse(self):
        """Test if ellipse is an alias for oval."""
        ctx = Context()
        self.assertTrue(hasattr(ctx, "ellipse"))
        self.assertTrue(ctx.ellipse == ctx.oval)
        p = BezierPath(ctx)
        self.assertTrue(hasattr(p, "ellipse"))
        self.assertTrue(p.ellipse == p.oval)

if __name__=='__main__':
    unittest.main()