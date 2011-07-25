import unittest
import sys

# To run the test, make sure you have at least built the NodeBox Extensions.
# Run the following command in the Terminal:
#   xcodebuild -target "Build Extensions"
sys.path.append('..')
sys.path.append('../build/libs')

from nodebox.graphics import *

class GraphicsTestCase(unittest.TestCase):
    
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