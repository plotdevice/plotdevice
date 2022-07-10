import os, sys
import functools
import unittest
import random
from distutils.spawn import find_executable
from subprocess import check_output, PIPE
from os.path import dirname, abspath, isdir, join, basename, splitext, relpath
from glob import glob
from pdb import set_trace as tron

tests_root = dirname(abspath(__file__))
sdist_root = dirname(tests_root)
sys.path.append(sdist_root)
sys.path.append(join(sdist_root, 'build/lib'))

try:
  from plotdevice import _ctx, measure

  def reference(image_path):
    """Write the canvas out to disk and compare the output with a reference image"""
    def decorator(test_method):
      @functools.wraps(test_method)
      def wrapper(*args, **kwargs):
        obj = args[0]
        obj._image = image_path
        test_method(*args, **kwargs)
        obj.render()
      return wrapper
    return decorator

  class PlotDeviceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
      # make sure the diff & output dirs exist
      cat = cls.__name__.replace('Tests','').lower()
      for subdir in ('_out', '_diff'):
        img_dir = join(tests_root, subdir, cat)
        if not isdir(img_dir):
          os.makedirs(img_dir)

    def setUp(self):
      # zap any previous state
      _ctx.clear(all)
      _ctx._resetEnvironment()
      random.seed(123456790)

    def render(self, save_output=True):
      """Write the current canvas image to _out/ and generate a diff image in _diff/"""
      ref, out, diff = [join(tests_root, subdir, self._image) for subdir in ('_ref','_out','_diff')]

      # write the generated image to the output dir
      if save_output:
        bg = _ctx.canvas.background
        if 'Pattern' in str(type(bg)) or getattr(bg, 'alpha', 0) > 0:
          _ctx.background(bg)
        else:
          _ctx.background(join(tests_root, '_in/transparency-grid.png'))
        _ctx.canvas.save(out)

      # compare the 'out' vs 'ref' image and write a 'diff' image
      _ctx.clear(all)
      _ctx._resetEnvironment()
      _ctx.size(*measure(image=ref))
      _ctx.image(ref)
      _ctx.blend('difference')
      _ctx.image(out)
      _ctx.canvas.save(diff)

except (ImportError, RuntimeError) as e:
  pass

def suites():
  from . import typography, primitives, drawing, compositing, geometry, module

  suite = unittest.TestSuite()
  for mod in (typography, primitives, drawing, compositing, geometry, module):
    suite.addTest(mod.suite())
  return suite

def report():
  """Create an html document presenting all the rendered images, their references, and the diff between them"""
  with open('details.html', 'w') as f:
    f.write(html_head)
    for pth in glob('tests/_out/*/*'):
      img = relpath(pth, 'tests/_out')
      name = splitext(img)[0]
      f.write(result_div % {"name":name, "img":img})
    f.write(html_foot)
  print("See details.html for case-by-case test comparisons")

html_head = """
<!DOCTYPE html>
<html>
<head>
  <style>
  body{color:white; background:black;}
  h1{font-family:Avenir;}
  h2{font:14px/18px Courier;}
  .test-case{overflow:auto;}
  .result{
    float:left;
    margin-right:1em;
    border:1px solid #444;
    max-width:30%;
    position:relative;
  }
  .result img{
    display:block;
    background:white;
    max-width:100%;
  }
  </style>
</head>
<body>
"""

result_div = """<h2>%(name)s</h2>
<div class="test-case">
  <div class="result"><img title="goal" src="tests/_ref/%(img)s"></div>
  <div class="result"><img title="test result" src="tests/_out/%(img)s"></div>
  <div class="result"><img title="difference" src="tests/_diff/%(img)s"></div>
</div>
"""

html_foot = """
</body>
</html>
"""

