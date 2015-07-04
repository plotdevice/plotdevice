import os
import unittest

sdist_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestModule(unittest.TestCase):
    def test_module_import(self):
        import plotdevice
        self.assertTrue(hasattr(plotdevice,'_ctx'))

    def test_pyobjc(self):
        import plotdevice
        import objc
        self.assertIn(sdist_path, objc.__file__)

    def test_c_extensions(self):
        from plotdevice.lib import io, pathmatics, foundry
        self.assertIn('io', locals())

def suite():
    from unittest import TestSuite, makeSuite

    suite = TestSuite()
    suite.addTest(makeSuite(TestModule))

    return suite