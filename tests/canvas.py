# encoding: utf-8
import unittest
from types import SimpleNamespace
from collections import UserDict
from . import PlotDeviceTestCase
from plotdevice import *
from plotdevice import _ctx, gfx, lib

class _Poison(object):
    def __getattr__(self, attr):
        raise AssertionError('rendering read _ctx.%s' % attr)

def _scene():
    size(80, 60)
    background(.95)
    with mask(oval(10, 10, 40, 40, plot=False)):
        fill(1, 0, 0)
        rect(0, 0, 80, 60)
    with shadow('#888', blur=3), alpha(.8):
        fill('black', 'white')
        rect(45, 5, 30, 30)
    font('Avenir', 12)
    fill(0, 0, 1)
    text('frame', 5, 55)
    return _ctx.canvas.commit()

def _png(frame):
    return bytes(frame._getImageData('png'))

class FrameTests(PlotDeviceTestCase):
    def test_frame_renders_without_the_context(self):
        frame = _scene()
        expected = _png(frame)
        gfx.bind(_Poison())
        lib.bind(_Poison())
        try:
            with self.assertRaises(AssertionError):
                Color(1, 0, 0).nsColor # the poison catches context reads outside of a render...
            rendered = _png(frame)     # ...and a render never makes one
        finally:
            _ctx._activate()
        self.assertEqual(rendered, expected)

    def test_frame_captures_the_output_mode(self):
        outputmode(CMYK)
        frame = _scene()
        expected = _png(frame)
        outputmode(RGB)
        self.assertEqual(_png(frame), expected)   # still renders as cmyk
        self.assertNotEqual(_png(_scene()), expected) # whereas a fresh frame doesn't

    def test_frame_ignores_later_edits(self):
        size(40, 40)
        with alpha(.5):
            r = rect(0, 0, 20, 20)
        frame = _ctx.canvas.commit()
        expected = _png(frame)
        clear(r) # removes it from the live canvas (reaching into its effect container)...
        rect(20, 20, 20, 20)
        self.assertNotIn(r, _ctx.canvas[0].contents)
        self.assertEqual(len(frame.grobs[0].contents), 1) # ...but not from the committed frame
        self.assertEqual(_png(frame), expected)

    def test_frame_commits_text(self):
        from plotdevice.gfx.text import Text
        size(120, 60)
        t = text('committed', 10, 40)
        outputmode(CMYK) # changed after the text was built: the commit must pick it up
        frame = _ctx.canvas.commit()
        committed = frame.grobs[0] # a copy, since `t` is still held
        self.assertEqual(committed._nsmode, CMYK)
        self.assertEqual(committed._engine.firstUnlaidCharacterIndex(), len(committed.text))
        def forbidden(text):
            raise AssertionError('rendering wrote to the text storage')
        orig, Text._colorize = Text._colorize, forbidden
        try:
            _png(frame)
        finally:
            Text._colorize = orig

    def test_frame_shares_grobs_the_script_let_go_of(self):
        size(100, 100)
        rect(0, 0, 10, 10)
        line(0, 0, 10, 10)
        arc(50, 50, 10)
        text('unheld', 10, 40)
        image('tests/_in/macpaint-tile.png', 50, 50)
        with shadow('#888', blur=2):
            oval(20, 20, 10, 10)
        frame = _ctx.canvas.commit()
        for committed, grob in zip(frame.grobs[:-1], _ctx.canvas[:-1]):
            self.assertIs(committed, grob)
        self.assertIs(frame.grobs[-1].contents[0], _ctx.canvas[-1].contents[0])

    def test_frame_copies_grobs_the_script_holds(self):
        size(100, 100)
        p = line(0, 0, 10, 10)
        t = text('held', 10, 40)
        img = image('tests/_in/macpaint-tile.png', 50, 50)
        block = text('by its block', 10, 60).blocks[0]
        word = text('by a word', 10, 80).words[0]
        with shadow('#888', blur=2):
            r = rect(20, 20, 10, 10)
        frame = _ctx.canvas.commit()
        for committed, grob in zip(frame.grobs[:-1], _ctx.canvas[:-1]):
            self.assertIsNot(committed, grob)
            self.assertIs(type(committed), type(grob))
        self.assertIsNot(frame.grobs[-1].contents[0], r)

    def test_held_grobs_can_be_edited_after_commit(self):
        size(100, 100)
        pen(2, dash=4)
        stroke(0)
        fill(.2, .5, .8)
        p = rect(10, 10, 40, 30)
        t = text('kept', 10, 80)
        frame = _ctx.canvas.commit()
        expected = _png(frame)
        p.lineto(90, 90)
        p.rotate(30)
        p.fill.alpha = .2
        p.alpha = .5
        t.append(' and edited')
        t.width = 30
        t.x += 20
        self.assertEqual(_png(frame), expected)

    def test_held_image_keeps_its_own_state(self):
        size(60, 60)
        img = image('tests/_in/macpaint-tile.png', 10, 10, width=40)
        img.alpha = .3
        img.rotate(30)
        frame = _ctx.canvas.commit()
        self.assertIsNot(frame.grobs[0], img)
        clear()
        img.draw()
        self.assertEqual(_png(frame), _png(_ctx.canvas.commit()))

    def test_plot_draws_an_image_as_is(self):
        size(60, 60)
        img = image('tests/_in/macpaint-tile.png', 10, 10, plot=False)
        img.alpha = .3
        rotate(30)
        alpha(.8)
        plotted = plot(img)
        self.assertEqual(plotted.alpha, .3)
        self.assertEqual(tuple(plotted.transform.matrix), tuple(img.transform.matrix))

    def test_copies_cover_their_state(self):
        from plotdevice.gfx.bezier import Bezier
        from plotdevice.gfx.image import Image
        p = rect(0, 0, 10, 10, plot=False)
        clone = p.copy()
        self.assertEqual(set(vars(clone)), set(Bezier._state) | {'_needs_closure'})
        for attr in ('_nsBezierPath', '_transform', '_effects', '_fillcolor'):
            self.assertIsNot(getattr(clone, attr), getattr(p, attr))
        img = image('tests/_in/macpaint-tile.png', 0, 0, plot=False)
        clone = img.copy()
        self.assertEqual(set(vars(clone)), set(Image._state))
        for attr in ('_frame', '_transform', '_effects'):
            self.assertIsNot(getattr(clone, attr), getattr(img, attr))

class CanvasTests(PlotDeviceTestCase):
    def test_rendering_does_not_leak(self):
        import sys, gc, objc
        if objc.__version__.startswith('11.'):
            self.skipTest('PyObjC 11 (the last release supporting Python 3.9) leaks on struct- and object-returning calls')
        size(100, 100)
        for i in range(200):
            fill(i / 200.0, .2, .4); rect(i % 10 * 10, i // 10 * 5, 8, 4)
        canvas = _ctx.canvas
        canvas._getImageData('png')
        gc.collect(); before = sys.getallocatedblocks()
        for _ in range(30):
            canvas._getImageData('png')
        gc.collect(); grown = sys.getallocatedblocks() - before
        self.assertLess(grown, 1000, 'rendering grew the heap by %d blocks over 30 frames' % grown)

    def test_text_does_not_leak_colors(self):
        import gc
        from plotdevice.gfx.colors import Color
        size(100, 100); font('Avenir', 12); fill(.2, .3, .4)
        text('warm up', 10, 50); clear()
        gc.collect(); before = sum(1 for o in gc.get_objects() if isinstance(o, Color))
        for i in range(50):
            text('line %d' % i, 10, 50)
        _ctx.canvas._getImageData('png'); clear()
        gc.collect(); retained = sum(1 for o in gc.get_objects() if isinstance(o, Color)) - before
        self.assertEqual(retained, 0, '%d Colors survived their texts' % retained)

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
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(FrameTests))
    return suite
