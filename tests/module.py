import os
import unittest
from . import PlotDeviceTestCase, reference, render_images
from subprocess import check_output, STDOUT
from plotdevice import *

sdist_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestModule(PlotDeviceTestCase):
    def test_pyobjc(self):
        import objc
        self.assertIn(sdist_path, objc.__file__)

    @reference('module/nodebox-compat.png')
    def test_nodebox_compat(self):
        code = open('%s/tests/_in/compliance/nodebox.py'%sdist_path).read()
        os.chdir('%s/tests/_in/compliance'%sdist_path)
        exec code in _ctx._ns.copy()
        os.chdir(sdist_path)

    @reference('module/compliance.png')
    def test_compliance(self):
        code = open('%s/tests/_in/compliance/plotdevice.py'%sdist_path).read()
        os.chdir('%s/tests/_in/compliance'%sdist_path)
        exec code in _ctx._ns.copy()
        os.chdir(sdist_path)

    def test_cli(self):
        plod_bin = '%s/app/plotdevice'%sdist_path
        script = '%s/tests/_in/cli.pv'%sdist_path
        output = '%s/tests/_out/module/cli.png'%sdist_path
        check_output([plod_bin, script, '--export', output], stderr=STDOUT, cwd=sdist_path)
        render_images(_ctx, 'module/cli.png', save_output=False)


def suite():
    from unittest import TestSuite, makeSuite

    suite = TestSuite()
    suite.addTest(makeSuite(TestModule))

    return suite