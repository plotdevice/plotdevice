import unittest
from os.path import basename, dirname
from glob import glob
from pdb import set_trace as tron
from . import render_diffs

try:
  import plotdevice.lib
except (ImportError, RuntimeError) as e:
    unbuilt = 'Build the c-extensions with "python setup.py build" before running tests.'
    raise ImportError(unbuilt)


cats = [basename(m).replace('.py','') for m in glob('%s/[a-ln-z]*.py'%dirname(__file__))]
cats += [basename(m).replace('.py','') for m in glob('%s/m*.py'%dirname(__file__))]
mods = [__import__(c, globals(), locals(), ['suite']) for c in cats]

suite = unittest.TestSuite()
for category, mod in zip(cats, mods):
  suitefn = getattr(mod, 'suite')
  suite.addTest(suitefn())
unittest.TextTestRunner(verbosity=1).run(suite)
render_diffs(suite)