import sys
import unittest
import importlib
from os.path import basename, dirname
from glob import glob
from pdb import set_trace as tron
from . import report, suites

try:
  import plotdevice
except (ImportError, RuntimeError) as e:
  unbuilt = 'Build the c-extensions with "python setup.py build" before running tests.'
  raise ImportError(unbuilt)

tests = suites()
verb = 2 if '-v' in sys.argv else 1
result = unittest.TextTestRunner(verbosity=verb).run(tests)
report()
sys.exit(0 if result.wasSuccessful() else 1)
