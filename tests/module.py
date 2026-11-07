import os, sys
import tempfile
import unittest
from . import PlotDeviceTestCase, reference
from subprocess import check_output, run, STDOUT
import plotdevice
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

    @unittest.skipUnless(hasattr(sys, 'orig_argv'), 'needs python 3.10')
    def test_cli_joined_flags(self):
        # -mplotdevice is the cli too
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, 'cli.pv')
            with open(script, 'w') as f:
                f.write("import plotdevice\nprint('in_cli=%s' % plotdevice.in_cli)\nsize(10, 10)\n")
            for flags in (['-m', 'plotdevice'], ['-mplotdevice']):
                out = check_output([sys.executable, *flags, '-q', script], stderr=STDOUT, cwd=sdist_path, text=True)
                self.assertIn('in_cli=True', out)

    @unittest.skipUnless(plotdevice.free_threaded, 'needs a free-threaded build')
    def test_cli_gil(self):
        # the free-threaded cli relaunches with -X gil=0
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, 'gil.pv')
            with open(script, 'w') as f:
                f.write("import sys\nprint('gil=%s xgil=%s' % (sys._is_gil_enabled(), sys._xoptions.get('gil')))\nsize(10, 10)\n")
            def gil(**env):
                env = {k: v for k, v in os.environ.items() if k != 'PYTHON_GIL'} | env
                return check_output([sys.executable, '-m', 'plotdevice', script, '--export', os.path.join(tmp, 'gil.png')],
                                    stderr=STDOUT, cwd=sdist_path, env=env, text=True)
            self.assertIn('gil=False xgil=0', gil())                     # relaunched with -X gil=0
            self.assertIn('gil=True xgil=None', gil(PYTHON_GIL='1'))     # the user's choice wins

    def test_cli_shows_deprecation_warnings(self):
        # FutureWarnings name the script's line
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, 'deprecated.pv')
            with open(script, 'w') as f:
                f.write("size(10, 10)\n"
                        "Transform().transform\n"
                        "image('%s/tests/_in/plaid.png', plot=False).image\n" % sdist_path)
            out = run([sys.executable, '-m', 'plotdevice', '-q', script], capture_output=True, text=True, cwd=sdist_path)
            self.assertIn('%s:2: FutureWarning: The \'transform\' attribute is deprecated' % script, out.stderr)
            self.assertIn('%s:3: FutureWarning: The \'image\' attribute is deprecated' % script, out.stderr)

    def test_cli_colors(self):
        # --colors sets -q exports' default colors
        with tempfile.TemporaryDirectory() as tmp:
            script = os.path.join(tmp, 'colors.pv')
            with open(script, 'w') as f:
                f.write("size(10, 10)\nfill(0, 0, 0)\nrect(0, 0, 10, 10)\n"
                        "export('%s/own.tiff')\nexport('%s/chosen.tiff', colors=P3)\n" % (tmp, tmp))
            run([sys.executable, '-m', 'plotdevice', '-q', script, '--colors', 'cmyk'], check=True, cwd=sdist_path)
            from Quartz import (CGImageSourceCreateWithURL, CGImageSourceCreateImageAtIndex, CGImageGetColorSpace,
                                CGColorSpaceGetModel, kCGColorSpaceModelCMYK)
            from Foundation import NSURL
            image = lambda name: CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(os.path.join(tmp, name)), None), 0, None)
            self.assertEqual(CGColorSpaceGetModel(CGImageGetColorSpace(image('own.tiff'))), kCGColorSpaceModelCMYK)
            self.assertNotEqual(CGColorSpaceGetModel(CGImageGetColorSpace(image('chosen.tiff'))), kCGColorSpaceModelCMYK)
            # and the press cmyk colors are read through
            reads = os.path.join(tmp, 'reads.pv')
            with open(reads, 'w') as f:
                f.write("print(color(1, 0, 0, 0, mode=CMYK).hex)\n")
            hexes = [run([sys.executable, '-m', 'plotdevice', '-q', reads] + flags, capture_output=True, text=True, cwd=sdist_path).stdout.split()
                     for flags in ([], ['--colors', 'fogra47'])]
            self.assertNotEqual(hexes[0], hexes[1])
            windowed = run([sys.executable, '-m', 'plotdevice', script, '--colors', 'cmyk'], capture_output=True, text=True, cwd=sdist_path)
            self.assertNotEqual(windowed.returncode, 0)
            self.assertIn('--colors applies only with --export or -q', windowed.stderr)

    @unittest.skipIf(plotdevice.in_bundle, 'only applies outside the app')
    def test_cli_app_only_options(self):
        # outside the app, --install points to pip/uv and -t doesn't exist
        install = run([sys.executable, '-m', 'plotdevice', '--install', 'six'], capture_output=True, text=True, cwd=sdist_path)
        self.assertEqual(install.returncode, 1)
        self.assertIn('only available in the PlotDevice app', install.stderr)
        script = '%s/tests/_in/cli.pv'%sdist_path
        free_threaded = run([sys.executable, '-m', 'plotdevice', '-t', script], capture_output=True, text=True, cwd=sdist_path)
        self.assertEqual(free_threaded.returncode, 2)
        self.assertIn('unrecognized arguments: -t', free_threaded.stderr)

    def test_rsrc_path_finds_resources_the_modules_rsrc_lacks_in_its_apps_resources(self):
        # the Xcode app keeps them in Resources
        import plotdevice.util as util
        with tempfile.TemporaryDirectory() as tmp:
            app = os.path.join(tmp, 'Fake.app/Contents')
            module = os.path.join(app, 'Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/plotdevice')
            for path in (os.path.join(module, 'rsrc/colors.json'), os.path.join(app, 'Resources/press/GRACoL2013_CRPC6.icc')):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, 'w').close()
            real = util.__file__
            util.__file__ = os.path.join(module, 'util/__init__.py')
            try:
                self.assertEqual(util.rsrc_path('colors.json'), os.path.join(module, 'rsrc/colors.json'))
                self.assertEqual(util.rsrc_path('press/GRACoL2013_CRPC6.icc'), os.path.join(app, 'Resources/press/GRACoL2013_CRPC6.icc'))
                self.assertEqual(util.rsrc_path('press/missing.icc'), os.path.join(module, 'rsrc/press/missing.icc'))
            finally:
                util.__file__ = real


def suite():
    from unittest import TestSuite, defaultTestLoader

    suite = TestSuite()
    suite.addTest(defaultTestLoader.loadTestsFromTestCase(ModuleTests))

    return suite
