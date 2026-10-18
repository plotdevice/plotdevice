# encoding: utf-8
import unittest
from types import SimpleNamespace
from collections import UserDict
from . import PlotDeviceTestCase
from plotdevice import *
from plotdevice import _ctx, gfx, lib
import objc

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

def _pixels(cgimage):
    from Quartz import CGImageGetDataProvider, CGDataProviderCopyData, CGImageGetBytesPerRow, CGImageGetWidth, CGImageGetHeight
    raw = bytes(CGDataProviderCopyData(CGImageGetDataProvider(cgimage)))
    stride, width = CGImageGetBytesPerRow(cgimage), CGImageGetWidth(cgimage) * 4
    return b''.join(raw[row * stride:row * stride + width] for row in range(CGImageGetHeight(cgimage)))

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

    def test_frame_renders_to_a_surface_identically(self):
        from Quartz import CGBitmapContextCreateImage
        frame = _scene()
        width, height = [max(int(dim * 2.0), 1) for dim in frame.pagesize]
        surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(width, height)
        for _ in range(2): # a surface is drawn into repeatedly, so the second frame matters too
            frame._render_to_surface(surface, 2.0)
        self.assertEqual(_pixels(CGBitmapContextCreateImage(surface.context())),
                         _pixels(frame._render_to_cgimage(1.0, 2.0)))

def _pump(until, timeout=5.0):
    from Foundation import NSRunLoop, NSDate, NSDefaultRunLoopMode
    import time
    deadline = time.time() + timeout
    while not until() and time.time() < deadline:
        NSRunLoop.currentRunLoop().runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.01))
    return until()

class RendererTests(PlotDeviceTestCase):
    def test_queue_delivers_in_order_and_drops_cancelled_jobs(self):
        from plotdevice.gui import FrameQueue
        import threading
        queue = FrameQueue()
        try:
            delivered, gate = [], threading.Event()
            def job(n):
                def work(cancelled):
                    gate.wait(2.0)   # hold the first job so the rest queue up behind it
                    return n
                return work
            for n in range(4):
                queue.submit(job(n), lambda result, err, n=n: delivered.append((n, result, err)))
            self.assertFalse(queue.ready)  # one in flight is the limit with the GIL
            queue.cancel()                 # ...so cancelling now drops all four
            gate.set()
            self.assertTrue(_pump(lambda: queue.idle))
            self.assertEqual(delivered, [])
            gate.clear()
            for n in range(4, 7):
                queue.submit(job(n), lambda result, err, n=n: delivered.append((n, result, err)))
            gate.set()
            self.assertTrue(_pump(lambda: queue.idle))
            self.assertEqual(delivered, [(4, 4, None), (5, 5, None), (6, 6, None)])
            self.assertTrue(queue.ready)
        finally:
            queue.shutdown()

    def test_queue_delivers_errors(self):
        from plotdevice.gui import FrameQueue
        queue = FrameQueue()
        try:
            got = []
            def work(cancelled):
                raise ValueError('bad grob')
            queue.submit(work, lambda result, err: got.append((result, err)))
            self.assertTrue(_pump(lambda: got))
            self.assertIsNone(got[0][0])
            self.assertIsInstance(got[0][1], ValueError)
        finally:
            queue.shutdown()

    def test_frame_draw_stops_when_cancelled(self):
        size(40, 40)
        background(None)
        fill(1, 0, 0); rect(0, 0, 20, 20)
        fill(0, 0, 1); rect(20, 20, 20, 20)
        frame = _ctx.canvas.commit()
        calls = [0]
        def cancelled():
            calls[0] += 1
            return calls[0] > 1   # true from the second grob on
        from Quartz import CGBitmapContextCreateImage
        surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(40, 40)
        frame._render_to_surface(surface, 1.0, cancelled)
        partial = _pixels(CGBitmapContextCreateImage(surface.context()))
        clear()
        size(40, 40); background(None); fill(1, 0, 0); rect(0, 0, 20, 20)
        surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(40, 40)
        _ctx.canvas.commit()._render_to_surface(surface, 1.0)
        self.assertEqual(partial, _pixels(CGBitmapContextCreateImage(surface.context())))

    def test_culled_render_matches_unculled(self):
        from Quartz import CGBitmapContextCreateImage
        from plotdevice import context
        size(400, 300)
        background('white')
        with shadow('black', blur=10, offset=(20, 0)):
            rect(170, 100, 10, 40, fill='red')
            with clip(oval(20, 20, 100, 100, plot=False)):
                for x in range(0, 400, 20):
                    rect(x, 0, 10, 300, fill='green')
        rect(170, 200, 20, 20, fill='blue', shadow=Shadow('black', blur=4, offset=(25, 0)))
        with transform(CENTER), rotate(60):
            text('rotated text', 120, 280, font='Avenir', size=30)
        oval(20, 250, 30, 30, fill=(0, 0, 0, .8), blend='destinationin')
        rect(20, 150, 30, 30, fill='orange')
        frame = _ctx.canvas.commit()

        def render(cull):
            within = context.Frame._within
            if not cull:
                context.Frame._within = lambda self, rect, grobs: grobs
            try:
                surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(400, 600)
                frame._render_to_surface(surface, 2.0, origin=(400, 0))
                return _pixels(CGBitmapContextCreateImage(surface.context()))
            finally:
                context.Frame._within = within
        self.assertEqual(render(True), render(False))

        group = frame.grobs[0]
        self.assertEqual(frame._within((200, 0, 200, 300), group.contents), [group.contents[0]])
        self.assertLess(len(frame._within((200, 0, 200, 300), frame.grobs)), len(frame.grobs))

    def test_layers_sized_to_their_contents_match_full_ones(self):
        from Quartz import CGBitmapContextCreateImage
        from plotdevice.gfx import effects
        size(500, 400)
        background('white')
        text('Zapfino', 40, 120, font='Zapfino', size=40, fill='purple', alpha=.6)
        text('ƒjord', 300, 120, font='Avenir', size=48, italic=True, shadow=Shadow('black', blur=5, offset=8))
        with transform(CENTER), rotate(30), shadow('red', blur=8, offset=(10, -5)):
            rect(100, 250, 120, 60, fill='orange')
            image('tests/_in/plaid.png', 250, 240, width=80)
        with alpha(.5), blend('multiply'):
            oval(320, 260, 120, 120, fill='teal')
        frame = _ctx.canvas.commit()

        def render(sized):
            layer_box = effects._layer_box
            if not sized:
                effects._layer_box = lambda grob: None
            try:
                frame._layers = {}
                return _pixels(frame._render_to_cgimage(1.0, 2.0))
            finally:
                effects._layer_box = layer_box
        self.assertEqual(render(True), render(False))
        render(True)
        self.assertTrue(any(box is not None for box in frame._layers.values()))

    def test_one_paint_alpha_skips_its_layer(self):
        from plotdevice.gfx.bezier import Bezier
        size(200, 200)
        background(.9)
        for i in range(4):
            oval(20 + i * 30, 20, 80, 80, fill=(.2, .3, .7), alpha=.5, blend='multiply')
        star(100, 140, 7, 50, 20, fill=None, stroke='black', strokewidth=6, dash=[9, 4], alpha=.5)
        oval(120, 120, 60, 60, fill='teal', stroke='black', strokewidth=10, alpha=.5)
        frame = _ctx.canvas.commit()
        self.assertEqual([g._one_paint for g in frame.grobs], [True] * 5 + [False])

        direct = _pixels(frame._render_to_cgimage(1.0, 2.0))
        one_paint = Bezier._one_paint
        Bezier._one_paint = property(lambda self: False)
        try:
            layered = _pixels(frame._render_to_cgimage(1.0, 2.0))
        finally:
            Bezier._one_paint = one_paint
        self.assertLessEqual(max(abs(a - b) for a, b in zip(direct, layered)), 3)

    def test_wide_shadow_blurs_match_core_graphics(self):
        from plotdevice.gfx import effects
        size(400, 300)
        background('white')
        rect(40, 40, 120, 90, fill='crimson', shadow=Shadow('black', blur=60, offset=(20, 15)))
        with shadow(('navy', .6), blur=40, offset=(-10, 25)):
            star(280, 120, 6, 70, 30, fill='orange')
            oval(220, 180, 80, 60, fill='teal')
        with clip(rect(40, 170, 150, 110, plot=False)):
            oval(60, 180, 100, 80, fill='plum', shadow=Shadow('black', blur=50, offset=30))
        text('Shadowed', 220, 285, font='Avenir', size=30, shadow=Shadow('purple', blur=40, offset=(10, -15)))
        with transform(CENTER), rotate(25):
            image('tests/_in/plaid.png', 300, 200, width=60, shadow=Shadow('black', blur=35, offset=12))
        frame = _ctx.canvas.commit()

        def render(downsampled):
            quick = effects._QUICK_BLUR
            if not downsampled:
                effects._QUICK_BLUR = float('inf')
            try:
                return _pixels(frame._render_to_cgimage(1.0, 2.0))
            finally:
                effects._QUICK_BLUR = quick
        cg, ours = render(False), render(True)
        self.assertNotEqual(cg, ours)
        diffs = [abs(a - b) for a, b in zip(cg, ours)]
        self.assertLessEqual(max(diffs), 8)
        self.assertGreater(sum(d <= 3 for d in diffs) / len(diffs), .995)

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

    def test_state_does_not_chain_across_frames(self):
        def depth(obj):
            n = 0
            while hasattr(obj, '_rollback'):
                obj = obj._rollback
                obj = next(iter(obj.values())) if isinstance(obj, dict) else obj
                n += 1
            return n
        size(100, 100)
        for frame in range(10):
            clear()
            for i in range(10):
                fill(i / 10.0); stroke(0); font('Avenir', 10 + i); rect(0, 0, 10, 10)
        self.assertEqual([depth(_ctx._fillcolor), depth(_ctx._strokecolor), depth(_ctx._font)], [0, 0, 0])

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
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(RendererTests))
    return suite
