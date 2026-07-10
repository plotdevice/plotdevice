# encoding: utf-8
import unittest
from types import SimpleNamespace
from collections import UserDict
from . import PlotDeviceTestCase
from plotdevice import *

class CanvasTests(PlotDeviceTestCase):
    def test_ordered_by_dotted_attr(self):
        size(100, 100)
        positions = [80, 20, 50]
        for y in positions:
            rect(10, y, 10, 10)

        sorted_grobs = ordered(canvas, 'bounds.y')
        self.assertEqual([g.bounds.y for g in sorted_grobs], sorted(positions))

    def test_ordered_by_dict_like_non_dict(self):
        items = [UserDict({'y': 80}), UserDict({'y': 20}), UserDict({'y': 50})]
        sorted_items = ordered(items, 'y')
        self.assertEqual([d['y'] for d in sorted_items], [20, 50, 80])

    def test_ordered_heterogeneous_items(self):
        items = [{'y': 80}, SimpleNamespace(y=20), {'y': 50}]
        sorted_items = ordered(items, 'y')
        ys = [it['y'] if isinstance(it, dict) else it.y for it in sorted_items]
        self.assertEqual(ys, [20, 50, 80])

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(CanvasTests))
    return suite
