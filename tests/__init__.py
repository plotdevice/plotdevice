import os, sys
import functools
import unittest
import random
from distutils.spawn import find_executable
from subprocess import check_output, PIPE
from os.path import dirname, abspath, isdir, join, basename, splitext
from glob import glob
from pdb import set_trace as tron

tests_root = dirname(abspath(__file__))
sys.path.append(dirname(tests_root))
from plotdevice import _ctx

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
  }
  .result img{
    display:block;
    background:white;
  }
  </style>
</head>
<body>
"""

result_div = """<div class="test-case">
<div class="result"><img title="goal" src="tests/_ref/%(cat)s/%(img)s"></div>
<div class="result"><img title="test result" src="tests/_out/%(cat)s/%(img)s"></div>
<div class="result"><img title="difference" src="tests/_diff/%(cat)s/%(img)s"></div>
</div>
"""

html_foot = """
</body>
</html>
"""

def render_diffs(multisuite):
  with open('details.html', 'w') as f:
    f.write(html_head)

    for suite in [s._tests[0]._tests for s in multisuite._tests]:
      cat = suite[0].__module__.split('.')[-1]
      img_fnames = {'test_'+splitext(basename(f))[0].replace('-','_'):basename(f) for f in glob('tests/_out/%s/*'%cat)}

      if img_fnames:
        # print cat
        f.write('<h1>%s</h1>\n' % cat.title())
        for test in suite:
          name = test._testMethodName
          img = img_fnames.get(name)
          if img:
            # print "-", test._testMethodName
            f.write('<h2>%s</h2>\n' % name)
            f.write(result_div % dict(cat=cat, img=img))
    f.write(html_foot)

  print "See details.html for case-by-case test comparisons"


def compute_diff(output_file):
  cmd = [
    find_executable('gm'),
    'compare',
    '-metric', 'rmse',
    '-matte',
    '-highlight-style', 'assign',
    # '-highlight-color', 'red',
    '-file', join(tests_root, '_diff', output_file),
    join(tests_root, '_ref', output_file),
    join(tests_root, '_out', output_file)
  ]
  stdout = check_output(cmd, stderr=PIPE)

def reference(known_good_image):
  """Write the canvas out to disk and compare the output with a reference image"""
  def decorator(test_item):
    @functools.wraps(test_item)
    def wrapper(*args, **kwargs):
      test_item(*args, **kwargs)
      out = '%s/_out/%s'%(tests_root, known_good_image)
      ref = '%s/_ref/%s'%(tests_root, known_good_image)
      diff = '%s/_diff/%s'%(tests_root, known_good_image)
      for subdir in '_out', '_diff':
        img_dir = join(tests_root, subdir, dirname(known_good_image))
        if not isdir(img_dir): os.makedirs(img_dir)

      _ctx.canvas.save(join(tests_root, '_out', known_good_image))
      w, h = _ctx.canvas.size
      bg = _ctx.canvas.background

      _ctx.clear(all)
      _ctx._resetEnvironment()
      _ctx.size(w,h)
      _ctx.background(bg)
      _ctx.image(join(tests_root, '_ref', known_good_image))
      _ctx.blend('difference')
      _ctx.image(join(tests_root, '_out', known_good_image))
      _ctx.canvas.save(join(tests_root, '_diff', known_good_image))
      # compute_diff(known_good_image)
    return wrapper
  return decorator

class PlotDeviceTestCase(unittest.TestCase):
  def setUp(self):
    _ctx.clear(all)
    _ctx._resetEnvironment()
    random.seed(123456)