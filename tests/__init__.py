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
sdist_root = dirname(tests_root)
sys.path.append(sdist_root)
sys.path.append(join(sdist_root, 'build/lib'))

try:
  from plotdevice import _ctx

  def reference(image_path):
    """Write the canvas out to disk and compare the output with a reference image"""
    def decorator(test_item):
      @functools.wraps(test_item)
      def wrapper(*args, **kwargs):
        test_item(*args, **kwargs)
        render_images(_ctx, image_path)
      return wrapper
    return decorator

  class PlotDeviceTestCase(unittest.TestCase):
    def setUp(self):
      _ctx.clear(all)
      _ctx._resetEnvironment()
      random.seed(123456790)
except (ImportError, RuntimeError) as e:
  pass

def render_images(ctx, dst):
  """Write the current canvas image to _out/$(dst) and generate a diff image at _diff/$(dst)"""
  ref, out, diff = [join(tests_root, subdir, dst) for subdir in ('_ref','_out','_diff')]

  # make sure the diff & output dirs exist
  for subdir in out, diff:
    img_dir = dirname(subdir)
    if not isdir(img_dir): os.makedirs(img_dir)

  # write the generated image to the output dir
  bg = ctx.canvas.background
  if 'Pattern' in str(type(bg)) or getattr(bg, 'alpha', 0) > 0:
    ctx.background(bg)
  else:
    bg = ctx.background(join(tests_root, '_in/transparency-grid.png'))
  ctx.canvas.save(out)
  w, h = ctx.canvas.size

  # compare the 'out' vs 'ref' image and write a 'diff' image
  ctx.clear(all)
  ctx._resetEnvironment()
  ctx.size(w,h)
  # ctx.background(bg)
  ctx.image(ref)
  ctx.blend('difference')
  ctx.image(out)
  ctx.canvas.save(diff)

def render_diffs(multisuite):
  """Create an html document presenting all the rendered images, their references, and the diff between them"""
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

