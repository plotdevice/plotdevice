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

    def test_dimension_range(self):
        # reproduces https://github.com/plotdevice/plotdevice/issues/67
        size(300, 200)
        self.assertEqual(list(range(0, WIDTH)), list(range(0, 300)))
        self.assertEqual(list(range(0, HEIGHT)), list(range(0, 200)))

    def test_magicnumber_protocol(self):
        # exercise the dunder methods on MagicNumber that make it behave like a real float
        size(300, 200)
        for magic in (WIDTH, HEIGHT, px, inch, pica, cm, mm):
            expected = float(magic)
            with self.subTest(magic=magic):
                self.assertEqual(list(range(0, magic)), list(range(0, int(expected))))
                self.assertEqual(round(magic), round(expected))
                self.assertEqual(hash(magic), hash(expected))
                self.assertTrue(magic <= expected)
                self.assertTrue(magic >= expected)
                self.assertEqual(format(magic, '.2f'), format(expected, '.2f'))
                self.assertEqual(144 / magic, 144 / expected)

    def test_magicnumber_cross_comparisons(self):
        # confirm dimension-to-unit comparisons work
        size(10 * cm, 20 * cm)
        self.assertEqual(WIDTH / cm, 10)
        self.assertEqual(HEIGHT / cm, 20)
        for a, b in [(inch, pica), (cm, mm), (WIDTH, cm), (HEIGHT, inch), (WIDTH, HEIGHT)]:
            with self.subTest(a=a, b=b):
                self.assertEqual(a <= b, float(a) <= float(b))
                self.assertEqual(a >= b, float(a) >= float(b))

    def test_magicnumber_unsupported_operators(self):
        # confirm errors blame the actual type (Dimension or Unit) rather than
        # the spurious 'float' comparison from earlier releases
        size(300, 200)
        for magic in (WIDTH, HEIGHT, px, inch, pica, cm, mm):
            typename = type(magic).__name__
            ops = [
                lambda m: m << 2,
                lambda m: m >> 2,
                lambda m: 2 << m,
                lambda m: 2 >> m,
                lambda m: ~m,
            ]
            for op in ops:
                with self.subTest(magic=magic, op=op):
                    with self.assertRaises(TypeError) as exc:
                        op(magic)
                    self.assertIn(typename, str(exc.exception))
                    self.assertNotIn('float', str(exc.exception))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(CanvasTests))
    return suite
