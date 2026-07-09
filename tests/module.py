import os, sys
import unittest
from . import PlotDeviceTestCase, reference
from subprocess import check_output, STDOUT
from plotdevice import *

sdist_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class ModuleTests(PlotDeviceTestCase):
    def test_pyobjc(self):
        import objc
        self.assertIsNotNone(objc.lookUpClass('Vandercook'))

    @reference('module/nodebox-compat.png')
    def test_nodebox_compat(self):
        code = open('%s/tests/_in/compliance/nodebox.py'%sdist_path).read()
        os.chdir('%s/tests/_in/compliance'%sdist_path)
        exec(code, _ctx._ns.copy())
        os.chdir(sdist_path)

    @reference('module/compliance.png')
    def test_compliance(self):
        code = open('%s/tests/_in/compliance/plotdevice.py'%sdist_path).read()
        os.chdir('%s/tests/_in/compliance'%sdist_path)
        exec(code, _ctx._ns.copy())
        os.chdir(sdist_path)

    def test_cli(self):
        self._image = 'module/cli.png'
        script = '%s/tests/_in/cli.pv'%sdist_path
        output = '%s/tests/_out/%s'%(sdist_path, self._image)
        check_output([sys.executable, '-m', 'plotdevice', script, '--export', output], stderr=STDOUT, cwd=sdist_path)
        self.render(save_output=False)


def suite():
    from unittest import TestSuite, defaultTestLoader

    suite = TestSuite()
    suite.addTest(defaultTestLoader.loadTestsFromTestCase(ModuleTests))

    return suite
