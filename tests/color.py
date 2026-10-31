# encoding: utf-8
import os
import re
import unittest
import tempfile
from os.path import join
from . import PlotDeviceTestCase
from plotdevice import *
from plotdevice import _ctx, DeviceError

# P3 red and sRGB red, each in the other space
P3_RED_IN_SRGB = (1.0930908918380737, -0.22684034705162048, -0.15007957816123962)
SRGB_RED_IN_P3 = (0.9174699187278748, 0.2003689408302307, 0.13852068781852722)

# P3 red and sRGB greys per LittleCMS 2.19, in percent
GRACOL_RED = (0, .937, 1, 0)
DARK_GREYS = {GRACOL: ((83, 74, 61, 100), (82, 73, 62, 95), (80, 72, 62, 91), (78, 70, 63, 84), (0, 0, 0, 0)),
              FOGRA47: ((77, 60, 56, 95), (77, 58, 54, 94), (76, 56, 52, 93), (75, 53, 49, 89), (0, 0, 0, 0))}

def _image(path):
    """An image file's color space name and its pixels as written"""
    from Foundation import NSURL
    from Quartz import (CGImageSourceCreateWithURL, CGImageSourceCreateImageAtIndex, CGImageGetColorSpace,
                        CGColorSpaceCopyName, CGImageGetDataProvider, CGDataProviderCopyData, CGImageGetBytesPerRow,
                        CGImageGetBitsPerPixel)
    img = CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(path), None), 0, None)
    data = bytes(CGDataProviderCopyData(CGImageGetDataProvider(img)))
    return CGColorSpaceCopyName(CGImageGetColorSpace(img)), data, CGImageGetBytesPerRow(img), CGImageGetBitsPerPixel(img) // 8

class ColorTests(PlotDeviceTestCase):
    def setUp(self):
        super(ColorTests, self).setUp()
        _ctx._resetContext()
        self.tmp = tempfile.mkdtemp()

    def assertComponents(self, actual, expected, places=5):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertAlmostEqual(a, e, places=places)

    # spaces

    def test_colors_are_p3_by_default(self):
        c = color(1, 0, 0)
        self.assertEqual(c.space, P3)
        self.assertEqual(c.rgba, (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(color('#f00').space, P3)
        self.assertEqual(color(.5).space, P3)
        self.assertEqual(color(.6, .7, .8, mode=HSV).space, P3)

    def test_space_keyword_makes_a_one_off_color(self):
        c = color('#f00', space=SRGB)
        self.assertEqual(c.space, SRGB)
        self.assertEqual(c.rgba, (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(color(1, 0, 0).space, P3) # the active space is unchanged

    def test_with_color_space_scopes_the_active_space(self):
        with color(space=SRGB):
            self.assertEqual(color(1, 0, 0).space, SRGB)
            self.assertEqual(color('#f00').space, SRGB)
        self.assertEqual(color(1, 0, 0).space, P3)
        color(space=SRGB)
        self.assertEqual(color(1, 0, 0).space, SRGB)

    def test_converting_reexpresses_the_components(self):
        p3_red = color(1, 0, 0)
        srgb = color(p3_red, space=SRGB)
        self.assertEqual(srgb.space, SRGB)
        self.assertComponents(srgb.rgba, P3_RED_IN_SRGB + (1,))
        self.assertComponents(color(color('#f00', space=SRGB), space=P3).rgba, SRGB_RED_IN_P3 + (1,))
        self.assertEqual(color(srgb, space=P3), p3_red) # (lossless, out of gamut too)
        self.assertEqual(p3_red.space, P3) # the original is untouched

    def test_copying_keeps_the_space(self):
        c = color('#f00', space=SRGB)
        self.assertEqual(color(c).space, SRGB)
        self.assertEqual(c.copy().space, SRGB)
        self.assertEqual(color(c), c)

    def test_components_stay_in_the_colors_own_space(self):
        c = color(.2, .4, .6)
        with color(space=SRGB):
            self.assertEqual(c.rgba, (.2, .4, .6, 1.0))
            self.assertEqual(c.space, P3)

    def test_hex_is_in_the_active_space(self):
        srgb_red = color('#f00', space=SRGB)
        self.assertEqual(srgb_red.hex, '#ea3323')
        with color(space=SRGB):
            self.assertEqual(srgb_red.hex, '#f00')
            self.assertEqual(color(1, 0, 0).hex, '#f00') # p3 red, clipped to srgb
        c = color(.2, .4, .6, space=SRGB)
        with color(space=SRGB):
            self.assertEqual(color(c.hex), c)

    def test_hex_rounds(self):
        self.assertEqual(color(.5).hex, '#808080')
        self.assertEqual(color('#7f7f7f').hex, '#7f7f7f')
        self.assertEqual(color(color(1, 1, 1), space=SRGB).hex, '#fff') # despite conversion noise

    def test_repr_names_the_space_when_it_isnt_the_active_one(self):
        self.assertEqual(repr(color(1, 0, 0)), "Color('#f00')")
        self.assertEqual(repr(color(1, 0, 0, .5)), "Color('#f00', 0.5)")
        srgb_red = color('#f00', space=SRGB)
        self.assertEqual(repr(srgb_red), "Color('#f00', space=SRGB)")
        with color(space=SRGB):
            self.assertEqual(repr(srgb_red), "Color('#f00')")
            self.assertEqual(repr(color(1, 0, 0, space=P3)), "Color('#f00', space=P3)")

    # mode & space names

    def test_mode_and_space_are_case_insensitive(self):
        self.assertComponents(color(0, 1, 1, mode='HSV').rgba, (1, 0, 0, 1))
        self.assertEqual(color(1, 0, 0, space='SRGB').space, SRGB)
        with color(mode='HSV', space='sRGB'):
            self.assertComponents(color(0, 1, 1).rgba, (1, 0, 0, 1))
            self.assertEqual(color(0, 1, 1).space, SRGB)

    def test_unknown_mode_or_space_raises(self):
        for kwargs in (dict(mode='hsl'), dict(space='adobe-rgb')):
            with self.assertRaises(DeviceError):
                color(**kwargs)
            with self.assertRaises(DeviceError):
                color(1, 0, 0, **kwargs)
        with self.assertRaises(DeviceError):
            colormode('lab')

    # component values

    def test_out_of_range_rgb_is_kept(self):
        self.assertEqual(color(300, 0, 0, range=255).r, 300/255)
        self.assertEqual(color(1.4, -.2, 0).rgba, (1.4, -.2, 0.0, 1.0))
        self.assertEqual(color(1.5).rgba, (1.5, 1.5, 1.5, 1.0))
        c = color(.5, .5, .5)
        c.r = 1.4
        self.assertEqual(c.r, 1.4)

    def test_alpha_and_cmyk_are_clamped(self):
        self.assertEqual(color(1, 0, 0, 2).a, 1.0)
        self.assertEqual(color(1, 0, 0, -1).a, 0.0)
        self.assertEqual(color(2, -1, .5, 0, mode=CMYK).cmyka, (1.0, 0.0, .5, 0.0, 1.0))

    def test_hsv_comes_from_unclamped_components(self):
        c = color(1.2, .6, .6)
        h, s, v, a = c.hsba
        self.assertAlmostEqual(v, 1.2)
        self.assertAlmostEqual(s, .5)
        self.assertComponents(color(.6, .5, 1.2, mode=HSV).hsba, (.6, .5, 1.2, 1))

    def test_cmyk_colors_keep_their_components(self):
        cyan = color(1, 0, 0, 0, mode=CMYK)
        self.assertEqual(cyan.cmyka, (1.0, 0.0, 0.0, 0.0, 1.0))
        self.assertComponents(cyan.rgba, (-0.2703114, 0.6267204, 0.8346672, 1), places=4) # unclipped
        self.assertEqual(color(cyan, space=SRGB).cmyka, cyan.cmyka)

    def test_setting_alpha_keeps_cmyk_components(self):
        black = color(0, 0, 0, 1, mode=CMYK)
        black.alpha = .25
        self.assertEqual(black.cmyka, (0.0, 0.0, 0.0, 1.0, .25))
        self.assertEqual(black.a, .25)

    def test_setters_keep_the_space(self):
        c = color(.2, .4, .6, space=SRGB)
        for attr, val in (('red', .9), ('hue', .3), ('alpha', .5), ('cyan', .1), ('hex', '#f80')):
            setattr(c, attr, val)
            self.assertEqual(c.space, SRGB, attr)

    def test_component_setters(self):
        c = color(.2, .4, .6)
        c.green = .8
        self.assertEqual(c.rgba, (.2, .8, .6, 1.0))
        c.rgba = (.1, .2, .3, .4)
        self.assertEqual(c.rgba, (.1, .2, .3, .4))
        c.hsba = (.5, .5, .5, .5)
        self.assertComponents(c.hsba, (.5, .5, .5, .5))
        c.magenta = .25
        self.assertAlmostEqual(c.magenta, .25)

    def test_hex_setters(self):
        c = color(.2, .4, .6, .5)
        c.hex = '#f80'
        self.assertEqual(repr(c), "Color('#f80', 0.5)")
        c.hexa = ('#08f', .25)
        self.assertEqual(repr(c), "Color('#08f', 0.25)")

    def test_setting_a_copy_leaves_the_original(self):
        c = color(.2, .4, .6)
        d = c.copy()
        d.red = 1
        d.alpha = .5
        self.assertEqual(c.rgba, (.2, .4, .6, 1.0))

    # equality

    def test_colors_compare_by_value(self):
        self.assertEqual(color(1, 0, 0), color('#f00'))
        self.assertEqual(color(.5), color(.5, .5, .5))
        self.assertNotEqual(color(1, 0, 0), color(1, 0, 0, .5))
        self.assertNotEqual(color(1, 0, 0), color('#f00', space=SRGB)) # same numbers, other space
        self.assertNotEqual(color(1, 0, 0), color(color(1, 0, 0), space=SRGB)) # same color, other space
        self.assertNotEqual(color(.6, .4, .4, 1, mode=CMYK), color(0, 0, 0, 1, mode=CMYK))
        self.assertNotEqual(color(1, 0, 0), (1, 0, 0))

    def test_colors_hash_by_value(self):
        self.assertEqual(len({color(1, 0, 0), color('#ff0000'), color(1, 0, 0, 1)}), 1)
        self.assertEqual({color(.2, .4, .6): 'x'}[color(.2, .4, .6)], 'x')
        self.assertEqual(hash(color(1, 0, 0)), hash(color(color(color(1, 0, 0), space=SRGB), space=P3)))

    # blending

    def test_blend_is_in_the_active_space(self):
        mid = color(1, 0, 0).blend(color(0, 0, 1), .5)
        self.assertEqual(mid.space, P3)
        self.assertComponents(mid.rgba, (.5, 0, .5, 1))
        with color(space=SRGB):
            mid = color(1, 0, 0, space=P3).blend('#00f', .5)
        self.assertEqual(mid.space, SRGB)
        self.assertComponents(mid.rgba, ((P3_RED_IN_SRGB[0]) / 2, P3_RED_IN_SRGB[1] / 2, (1 + P3_RED_IN_SRGB[2]) / 2, 1))

    def test_cmyk_colors_blend_in_cmyk(self):
        k50 = color(0, 0, 0, 1, mode=CMYK).blend(color(0, 0, 0, 0, mode=CMYK), .5)
        self.assertComponents(k50.cmyka, (0, 0, 0, .5, 1))
        self.assertComponents(color(1, 0, 0, 0, mode=CMYK).blend(color(0, 1, 0, 0, mode=CMYK), .25).cmyka, (.75, .25, 0, 0, 1))

    def test_reads_of_cmyk_colors_go_through_the_export_blocks_press(self):
        from Quartz import CGColorCreate
        from plotdevice.gfx.colors import Press, _components, _matched, _SPACES
        cyan, white = color(1, 0, 0, 0, mode=CMYK), color(1)
        outside = (cyan.rgba, cyan.hex, cyan.blend(white, .5).rgba, hash(cyan))
        size(10, 10)
        with export(join(self.tmp, 'press.pdf'), colors=FOGRA47):
            inside = (cyan.rgba, cyan.hex, cyan.blend(white, .5).rgba, hash(cyan))
            self.assertEqual(cyan, color(1, 0, 0, 0, mode=CMYK)) # equality ignores the press
        direct = _components(_matched(CGColorCreate(Press.named[FOGRA47].space, (1, 0, 0, 0, 1)), _SPACES[P3]))
        self.assertComponents(inside[0], direct)
        self.assertComponents(inside[2], [v + (1 - v) * .5 for v in direct])
        self.assertNotEqual(inside[1], outside[1])
        self.assertGreater(abs(inside[0][0] - outside[0][0]), .05)
        self.assertEqual(inside[3], outside[3])
        self.assertEqual((cyan.rgba, cyan.hex), outside[:2]) # generic cmyk after the block

    def test_gradient_keeps_the_space_its_made_in(self):
        with color(space=SRGB):
            g = Gradient(color(1, 0, 0), '#00f')
        self.assertEqual(g._space, SRGB)
        self.assertEqual(Gradient(g)._space, SRGB)
        self.assertEqual(Gradient('#f00', '#00f')._space, P3)

    def test_gradient_objects_fill_stroke_and_background(self):
        # a Gradient works wherever a color does
        g = Gradient(color(1, 0, 0), color(0, 0, 1), angle=0)
        fill(g)
        self.assertIsInstance(rect(0, 0, 10, 10)._fillcolor, Gradient)
        self.assertFalse(hasattr(g, '_rollback')) # fill() installs a copy
        self.assertIsInstance(rect(0, 0, 10, 10, fill=g)._fillcolor, Gradient)
        self.assertIsInstance(rect(0, 0, 10, 10, stroke=g)._strokecolor, Gradient)
        path = bezier(plot=False)
        path.fill, path.stroke = g, g
        self.assertIsInstance(path._fillcolor, Gradient)
        self.assertIsInstance(path._strokecolor, Gradient)
        saved = fill(color(1, 0, 0), color(0, 0, 1), angle=0)
        fill(0)
        fill(saved)
        self.assertIsInstance(rect(0, 0, 10, 10)._fillcolor, Gradient)
        stroke(g)
        self.assertIsInstance(rect(0, 0, 10, 10)._strokecolor, Gradient)
        stroke(color(1, 0, 0), color(0, 0, 1), angle=90)
        self.assertIsInstance(rect(0, 0, 10, 10)._strokecolor, Gradient)
        background(g)
        self.assertIsInstance(_ctx.canvas.background, Gradient)
        for command in (fill, stroke, background):
            with self.assertRaisesRegex(DeviceError, 'only argument'):
                command(g, angle=90)
        with stroke(color(0, 1, 0), color(0, 0, 1)):
            self.assertIsInstance(rect(0, 0, 10, 10)._strokecolor, Gradient)
        self.assertIsInstance(rect(0, 0, 10, 10)._strokecolor, Gradient) # rolled back to the earlier one

    def test_fill_stroke_and_background_take_colors_arguments(self):
        # colors take color()'s args, gradients their own
        for command in (fill, stroke, background):
            name = command.__name__
            self.assertEqual(command(.5, 1, 1, mode=HSV), color(.5, 1, 1, mode=HSV))
            self.assertEqual(command(HSV, .5, 1, 1), color(.5, 1, 1, mode=HSV))
            self.assertEqual(command(255, 0, 0, range=255), color(1, 0, 0))
            self.assertEqual(command(1, 0, 0, space=SRGB), color(1, 0, 0, space=SRGB))
            self.assertIsInstance(command('red', 'blue', angle=0, steps=[0, 1]), Gradient)
            with self.assertRaisesRegex(DeviceError, "Unknown Color argument 'alpha'"):
                command(1, 0, 0, alpha=.5)
            with self.assertRaisesRegex(DeviceError, "Unknown Color arguments 'alpha', 'colour'"):
                command(1, 0, 0, alpha=.5, colour=1)
            with self.assertRaisesRegex(DeviceError, "Unknown Gradient argument 'mode'"):
                command('red', 'blue', angle=0, mode=HSV)
            with self.assertRaisesRegex(DeviceError, "%s\\(\\) takes 'angle' only with two or more colors" % name):
                command('red', angle=0)
            with self.assertRaisesRegex(DeviceError, "%s\\(\\) takes 'mode' only with a color" % name):
                command(mode=HSV)
            with self.assertRaisesRegex(DeviceError, "Unknown Color argument 'alpha'"):
                command(alpha=.5)
        # color() rejects the same
        for call in (lambda: color(1, 0, 0, alpha=.5), lambda: color(alpha=.5), lambda: color(mode=HSV, alpha=.5)):
            with self.assertRaisesRegex(DeviceError, "Unknown Color argument 'alpha'"):
                call()

    def test_images_take_no_other_arguments(self):
        # an image's tiles can't take colors or gradient keywords
        tile = 'tests/_in/plaid.png'
        for command in (fill, background):
            for args, kwargs in (((tile, 'red'), {}), ((tile,), dict(angle=45)), ((image(tile),), dict(alpha=.5))):
                with self.assertRaisesRegex(DeviceError, "takes an image as its only argument"):
                    command(*args, **kwargs)

    def test_gradient_strokes_draw_within_the_stroke(self):
        from Foundation import NSURL
        from Quartz import (CGImageSourceCreateWithURL, CGImageSourceCreateImageAtIndex, CGBitmapContextCreate,
                            CGContextDrawImage, CGBitmapContextCreateImage, CGDataProviderCopyData, CGImageGetDataProvider,
                            CGColorSpaceCreateWithName, kCGColorSpaceDisplayP3, kCGImageAlphaPremultipliedLast)
        def pixels(path, w, h):
            img = CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(path), None), 0, None)
            ctx = CGBitmapContextCreate(None, w, h, 8, w * 4, CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3), kCGImageAlphaPremultipliedLast)
            CGContextDrawImage(ctx, ((0, 0), (w, h)), img)
            data = bytes(CGDataProviderCopyData(CGImageGetDataProvider(CGBitmapContextCreateImage(ctx))))
            return lambda x, y: tuple(data[(y * w + x) * 4:][:3])
        size(200, 100)
        background(1)
        nofill()
        stroke(color(1, 0, 0), color(0, 0, 1), angle=0)
        pen(10)
        rect(10, 10, 180, 40)
        pen(10, dash=10)
        line(10, 80, 190, 80)
        export(join(self.tmp, 'stroke.png'))
        px = pixels(join(self.tmp, 'stroke.png'), 200, 100)
        left, right, inside = px(10, 30), px(189, 30), px(100, 30)
        self.assertGreater(left[0], 200)
        self.assertLess(left[2], 60)
        self.assertGreater(right[2], 200)
        self.assertLess(right[0], 60)
        self.assertEqual(inside, (255, 255, 255))
        self.assertNotEqual(px(14, 80), (255, 255, 255)) # a dash
        self.assertEqual(px(25, 80), (255, 255, 255))    # and the gap after it
        # in a cmyk export the gradient's stops keep their numbers
        clear(all)
        size(200, 100)
        background(None)
        nofill()
        stroke(color(1, 0, 0, 0, mode=CMYK), color(0, 0, 0, 1, mode=CMYK), angle=0)
        pen(10)
        rect(10, 10, 180, 40)
        export(join(self.tmp, 'stroke.tiff'), colors=CMYK)
        name, data, row, depth = _image(join(self.tmp, 'stroke.tiff'))
        ink = lambda x, y: tuple(round(v / 2.55) for v in data[y * row + x * depth:][:4])
        self.assertEqual(ink(5, 30)[1:3], (0, 0))
        self.assertGreater(ink(5, 30)[0], 95)
        self.assertGreater(ink(194, 30)[3], 95)
        self.assertLess(ink(194, 30)[0], 5)

    def test_pattern_filled_text_exports_in_cmyk(self):
        # text filled with a pattern exports as it does when drawn inside the export block
        def scene():
            clear(all)
            size(100, 100)
            background('white')
            text('Hm', 10, 60, size=48, fill=Pattern('tests/_in/macpaint-thatch.png'))
        for colors in (CMYK, FOGRA39):
            scene()
            export(join(self.tmp, colors + '-after.tiff'), colors=colors)
            with export(join(self.tmp, colors + '-inside.tiff'), colors=colors):
                scene()
            self.assertEqual(_image(join(self.tmp, colors + '-after.tiff')), _image(join(self.tmp, colors + '-inside.tiff')), colors)

    def test_pattern_objects_draw_in_cmyk(self):
        # an explicit Pattern draws as the image/path shorthand does, in a cmyk export too
        def exported(name, paint):
            clear(all)
            size(100, 100)
            background('white')
            fill(paint)
            stroke(paint)
            pen(12)
            rect(20, 20, 60, 60)
            export(join(self.tmp, name), colors=CMYK)
            return _image(join(self.tmp, name))[1]
        tile = 'tests/_in/macpaint-thatch.png'
        made = exported('object.tiff', Pattern(tile))
        self.assertEqual(made, exported('shorthand.tiff', tile))
        self.assertNotEqual(made, exported('blank.tiff', 'white'))

    def test_canvas_patterns_draw_in_the_exports_colors(self):
        # a snapshot made outside the export resolves its colors as the export does
        def scene():
            rect(0, 0, 40, 20, fill='red')
            rect(0, 20, 40, 20, fill=Color('cmyk', 0, 1, 1, 0))
            text('Hi', 4, 34, size=18, fill='blue')
        size(40, 40)
        scene()
        tile = Pattern(_ctx.canvas)
        for colors in (CMYK, FOGRA39):
            clear(all)
            scene()
            export(join(self.tmp, 'direct.tiff'), colors=colors)
            clear(all)
            rect(0, 0, 40, 40, fill=tile)
            export(join(self.tmp, 'pattern.tiff'), colors=colors)
            self.assertEqual(_image(join(self.tmp, 'pattern.tiff')), _image(join(self.tmp, 'direct.tiff')), colors)

    def test_canvas_pattern_text_draws_in_the_exports_colors(self):
        # text filled with a canvas tile resolves its colors as the export does
        size(20, 20)
        rect(0, 0, 20, 20, fill=Color('cmyk', 0, 1, 1, 0))
        tile = Pattern(_ctx.canvas)
        for colors in (CMYK, FOGRA39):
            for paint, name in ((tile, 'tiled.tiff'), (Color('cmyk', 0, 1, 1, 0), 'direct.tiff')):
                clear(all)
                size(220, 120)
                text('Hm', 10, 90, size=96, font='Helvetica', weight='bold', fill=paint)
                export(join(self.tmp, name), colors=colors)
            self.assertEqual(_image(join(self.tmp, 'tiled.tiff')), _image(join(self.tmp, 'direct.tiff')), colors)

    def test_plotted_canvases_draw_in_the_exports_colors(self):
        # a canvas plotted before the export resolves its colors as the export does
        def scene():
            rect(0, 0, 40, 20, fill='red')
            rect(0, 20, 40, 20, fill=Color('cmyk', 0, 1, 1, 0))
            text('Hi', 4, 34, size=18, fill='blue')
        size(40, 40)
        scene()
        snapshot = plot(_ctx.canvas, 0, 0)
        for colors in (CMYK, FOGRA39):
            clear(all)
            scene()
            export(join(self.tmp, 'direct.tiff'), colors=colors)
            clear(all)
            plot(snapshot)
            export(join(self.tmp, 'plotted.tiff'), colors=colors)
            self.assertEqual(_image(join(self.tmp, 'plotted.tiff')), _image(join(self.tmp, 'direct.tiff')), colors)

    # outputs

    def _save(self, name, **kwargs):
        path = join(self.tmp, name)
        _ctx.canvas.save(path, **kwargs)
        return path

    def _swatch(self, *clr, **kwargs):
        size(20, 20)
        background(None)
        fill(*clr)
        rect(0, 0, 20, 20)

    def test_bitmaps_are_tagged_p3_with_the_scripts_numbers(self):
        self._swatch(.8, .4, .2)
        for ext in ('png', 'tiff', 'jpg', 'heic'):
            space, data, row, bpp = _image(self._save('swatch.' + ext))
            self.assertEqual(space, 'kCGColorSpaceDisplayP3', ext)
        space, data, row, bpp = _image(self._save('swatch.png'))
        self.assertEqual(tuple(data[10 * row + 10 * bpp:][:3]), (204, 102, 51))

    def test_srgb_colors_are_converted_into_p3_bitmaps(self):
        self._swatch(color('#f00', space=SRGB))
        space, data, row, bpp = _image(self._save('swatch.png'))
        self.assertEqual(tuple(data[10 * row + 10 * bpp:][:3]), (234, 51, 35))

    def test_gifs_are_converted_to_srgb(self):
        self._swatch(.8, .4, .2)
        space, data, row, bpp = _image(self._save('swatch.gif'))
        r, g, b = data[10 * row + 10 * bpp:][:3]
        for got, want in zip((r, g, b), (219, 94, 32)):
            self.assertLessEqual(abs(got - want), 2)

    def test_eps_is_converted_to_srgb(self):
        size(100, 40)
        fill(.24, .464, .8)
        rect(0, 0, 20, 20)
        fill(.6, .3, .9)
        text('Ink', 30, 30)
        eps = open(self._save('out.eps'), 'rb').read().decode('latin-1')
        fills = re.findall(r'^([-\d. ]+) sc$', eps, re.M)
        self.assertIn('0.1358774 0.4707064 0.82546824', fills)             # the rect, in srgb
        self.assertNotIn('0.23999999 0.46399999 0.80000001', fills)
        text_srgb = color(color(.6, .3, .9), space=SRGB).rgba[:3]
        self.assertTrue(any(all(abs(float(v) - w) < 1e-4 for v, w in zip(f.split(), text_srgb)) for f in fills), fills)

    def test_cmyk_exports_keep_cmyk_numbers(self):
        # in cmyk output mode
        outputmode(CMYK)
        self._swatch(color(.6, .4, .4, 1, mode=CMYK))
        space, data, row, bpp = _image(self._save('swatch.tiff', cmyk=True))
        outputmode(RGB)
        self.assertEqual(bpp, 4)
        self.assertEqual(tuple(data[10 * row + 10 * bpp:][:4]), (153, 102, 102, 255))

    def test_placed_cmyk_images_keep_their_numbers(self):
        # a tagged cmyk image is relabeled, not converted
        import zlib
        from Quartz import (CGBitmapContextCreate, CGBitmapContextCreateImage, CGColorSpaceCreateWithName, kCGColorSpaceGenericCMYK,
                            CGContextSetFillColorWithColor, CGColorCreate, CGContextFillRect, CGImageDestinationCreateWithURL,
                            CGImageDestinationAddImage, CGImageDestinationFinalize, kCGImageAlphaNone)
        from Foundation import NSURL
        generic = CGColorSpaceCreateWithName(kCGColorSpaceGenericCMYK)
        ctx = CGBitmapContextCreate(None, 20, 20, 8, 80, generic, kCGImageAlphaNone)
        CGContextSetFillColorWithColor(ctx, CGColorCreate(generic, (0, 0, 0, 1, 1)))
        CGContextFillRect(ctx, ((0, 10), (20, 10))) # top half K
        CGContextSetFillColorWithColor(ctx, CGColorCreate(generic, (1, 0, 0, 0, 1)))
        CGContextFillRect(ctx, ((0, 0), (20, 10)))  # bottom half C
        src = join(self.tmp, 'tagged.tiff')
        dest = CGImageDestinationCreateWithURL(NSURL.fileURLWithPath_(src), 'public.tiff', 1, None)
        CGImageDestinationAddImage(dest, CGBitmapContextCreateImage(ctx), None)
        CGImageDestinationFinalize(dest)
        size(20, 20)
        image(src, 0, 0)
        space, data, row, bpp = _image(self._save('placed.tiff', colors=CMYK))
        self.assertEqual((tuple(data[5 * row + 5 * bpp:][:4]), tuple(data[15 * row + 5 * bpp:][:4])), ((0, 0, 0, 255), (255, 0, 0, 0)))
        pdf = open(self._save('placed.pdf', colors=CMYK), 'rb').read()
        self.assertTrue(re.search(rb'/Subtype /Image[^>]*/ColorSpace\s+/DeviceCMYK', pdf)) # never prints the pdf

    def test_rgb_export_after_a_cmyk_one_is_rgb(self):
        import zlib
        self._swatch(0, 1, 0)
        export(join(self.tmp, 'b.pdf'), colors=CMYK)
        self.assertEqual(outputmode(), RGB)
        export(join(self.tmp, 'c.pdf'))
        export(join(self.tmp, 'c.png'))
        pdf = open(join(self.tmp, 'c.pdf'), 'rb').read()
        content = b''.join(zlib.decompress(s) for s in re.findall(rb'stream\r?\n(.*?)endstream', pdf, re.S))
        self.assertIn(b'0 1 0 sc', content)
        self.assertNotRegex(content, rb' k\b')
        space, data, row, bpp = _image(join(self.tmp, 'c.png'))
        self.assertEqual(tuple(data[10 * row + 10 * bpp:][:3]), (0, 255, 0))

    # export(colors=...)

    def _two_swatches(self):
        size(20, 10)
        background(None)
        fill(color('#3c8', space=SRGB))
        rect(0, 0, 10, 10)
        fill(1, 0, 0) # (P3 red, outside srgb)
        rect(10, 0, 10, 10)

    def test_srgb_exports_are_tagged_srgb_with_p3_colors_clipped(self):
        self._two_swatches()
        for ext in ('png', 'tiff', 'heic'):
            path = join(self.tmp, 'srgb.' + ext)
            export(path, colors=SRGB)
            space, data, row, bpp = _image(path)
            self.assertEqual(space, 'kCGColorSpaceSRGB', ext)
            off = 3 if ext == 'heic' else 0 # (lossy)
            for x, want in ((5, (0x33, 0xcc, 0x88)), (15, (255, 0, 0))):
                got = data[5 * row + x * bpp:][:3]
                self.assertLessEqual(max(abs(g - w) for g, w in zip(got, want)), off, (ext, tuple(got), want))

    def test_srgb_pdfs_fill_and_blend_in_srgb(self):
        import zlib
        self._two_swatches()
        with blend('multiply'):
            rect(0, 0, 20, 10)
        export(join(self.tmp, 'srgb.pdf'), colors=SRGB)
        pdf = open(join(self.tmp, 'srgb.pdf'), 'rb').read()
        streams = [zlib.decompress(s) for s in re.findall(rb'stream\r?\n(.*?)endstream', pdf, re.S)]
        from Quartz import CGColorSpaceCopyICCData, CGColorSpaceCreateWithName, kCGColorSpaceSRGB, kCGColorSpaceDisplayP3
        srgb, p3 = [bytes(CGColorSpaceCopyICCData(CGColorSpaceCreateWithName(name))) for name in (kCGColorSpaceSRGB, kCGColorSpaceDisplayP3)]
        self.assertIn(srgb, streams)
        self.assertNotIn(p3, streams) # fills in srgb, groups relabeled
        self.assertIn(b'1 0 0 sc', b''.join(streams))

    def test_icc_exports_are_in_the_profile(self):
        from Quartz import (CGColorSpaceCreateWithICCData, CGColorSpaceCreateWithName, kCGColorSpaceSRGB, CGColorCreate,
                            CGColorCreateCopyByMatchingToColorSpace, kCGRenderingIntentDefault, CGColorGetComponents)
        profile = '/System/Library/ColorSync/Profiles/AdobeRGB1998.icc'
        self._two_swatches()
        path = join(self.tmp, 'adobe.png')
        export(path, colors=profile)
        space, data, row, bpp = _image(path)
        self.assertEqual(space, 'kCGColorSpaceAdobeRGB1998')
        green = CGColorCreate(CGColorSpaceCreateWithName(kCGColorSpaceSRGB), (0x33 / 255, 0xcc / 255, 0x88 / 255, 1))
        adobe = CGColorCreateCopyByMatchingToColorSpace(CGColorSpaceCreateWithICCData(open(profile, 'rb').read()), kCGRenderingIntentDefault, green, None)
        want = tuple(round(v * 255) for v in CGColorGetComponents(adobe).as_tuple(4)[:3])
        self.assertEqual(tuple(data[5 * row + 5 * bpp:][:3]), want)

    def test_srgb_movies_are_tagged_rec709(self):
        # the colr atom's primaries, transfer, and matrix codes, whichever codec
        for codec in (HEVC, PRORES):
            for colors, primaries, transfer, matrix in ((P3, 12, None, 1), (SRGB, 1, None, 1), (REC709, 1, 1, 1), (REC2020, 9, 1, 9)):
                path = join(self.tmp, '%s-%s.mov' % (codec, colors))
                with export(path, codec=codec, colors=colors) as movie:
                    for i in range(2):
                        with movie.frame:
                            self._two_swatches()
                mov = open(path, 'rb').read()
                at = re.search(rb'colrncl[cx]', mov).end()
                tags = [int.from_bytes(mov[at + i:at + i + 2], 'big') for i in (0, 2, 4)]
                self.assertEqual(tags[0], primaries, (codec, colors))
                self.assertEqual(tags[2], matrix, (codec, colors))
                if transfer is not None:
                    self.assertEqual(tags[1], transfer, (codec, colors))

    def test_each_format_takes_the_colors_it_can_hold(self):
        from plotdevice.gfx.colors import _output_colors
        profile = '/System/Library/ColorSync/Profiles/AdobeRGB1998.icc'
        accepts = dict(png='P3 SRGB icc rec', heic='P3 SRGB icc rec', mov='P3 SRGB rec', gif='SRGB', eps='SRGB CMYK',
                       pdf='P3 SRGB icc rec CMYK', tiff='P3 SRGB icc rec CMYK', jpg='P3 SRGB icc rec CMYK')
        for format, ok in accepts.items():
            for name, val in (('P3', P3), ('SRGB', SRGB), ('icc', profile), ('rec', 'ITU-709'), ('rec', 'ITU-2020'), ('CMYK', CMYK)):
                if name in ok.split():
                    _output_colors(val, format)
                else:
                    self.assertRaises(DeviceError, _output_colors, val, format)
        self.assertEqual([_output_colors(None, f) for f in ('png', 'pdf', 'mov', 'gif', 'eps')], [P3, P3, P3, SRGB, SRGB])
        self.assertEqual(_output_colors('CMYK', 'pdf'), CMYK)
        self.assertEqual(_output_colors(profile, 'pdf'), profile)

    def test_export_rejects_bad_colors_and_arguments(self):
        self._two_swatches()
        path = join(self.tmp, 'bad.pdf')
        for kwargs in (dict(colors=64), dict(colors='adobe'), dict(colors='/nonexistent.icc'), dict(colors=__file__),
                       dict(colors=CMYK, cmyk=True)):
            self.assertRaises(DeviceError, export, path, **kwargs)
        self.assertRaises(TypeError, export, path, colours=CMYK) # a misspelled keyword
        self.assertRaises(DeviceError, export, join(self.tmp, 'bad.png'), colors=CMYK)
        self.assertFalse(os.path.exists(path))

    def test_exports_follow_outputmode_unless_they_choose(self):
        outputmode(CMYK)
        self._swatch(color(0, 0, 0, 1, mode=CMYK))
        export(join(self.tmp, 'mode.tiff'))
        export(join(self.tmp, 'chosen.tiff'), colors=P3)
        export(join(self.tmp, 'mode.png')) # no cmyk, so the default
        outputmode(RGB)
        from Quartz import CGImageSourceCreateWithURL, CGImageSourceCreateImageAtIndex, CGImageGetColorSpace, CGColorSpaceGetModel, kCGColorSpaceModelCMYK
        from Foundation import NSURL
        tiff = CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(join(self.tmp, 'mode.tiff')), None), 0, None)
        self.assertEqual(CGColorSpaceGetModel(CGImageGetColorSpace(tiff)), kCGColorSpaceModelCMYK)
        self.assertEqual(_image(join(self.tmp, 'chosen.tiff'))[0], 'kCGColorSpaceDisplayP3')
        self.assertEqual(_image(join(self.tmp, 'mode.png'))[0], 'kCGColorSpaceDisplayP3')

    def test_cmyk_argument_is_deprecated_for_colors(self):
        import warnings
        self._swatch(color(0, 0, 0, 1, mode=CMYK))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            export(join(self.tmp, 'old.tiff'), cmyk=True)
        self.assertEqual([w.category for w in caught], [FutureWarning])
        self.assertEqual(caught[0].filename, __file__) # the export() call
        export(join(self.tmp, 'new.tiff'), colors=CMYK)
        self.assertEqual(open(join(self.tmp, 'old.tiff'), 'rb').read(), open(join(self.tmp, 'new.tiff'), 'rb').read())

    def test_bundled_presses_are_the_profiles_the_readme_lists(self):
        import hashlib
        from plotdevice.gfx.colors import Press, _PRESSES
        from plotdevice.util import rsrc_path
        readme = open(rsrc_path('press/README.md')).read()
        sums = dict((name, digest) for digest, name in re.findall(r'^([0-9a-f]{64})  (\S+)$', readme, re.M))
        presses = dict(GRACOL='gracol', GRACOL_UNCOATED='gracol_uncoated', SWOP='swop', FOGRA39='fogra39', FOGRA47='fogra47')
        for name, value in presses.items():
            self.assertEqual(globals()[name], value)
            profile = Press(value).profile # decompressed from rsrc/press
            self.assertEqual(hashlib.sha256(profile).hexdigest(), sums[_PRESSES[value]], name)
            self.assertEqual((profile[12:16], profile[16:20]), (b'prtr', b'CMYK'), name)
        self.assertEqual(len(sums), len(presses))

    def test_installed_profiles_by_file_name(self):
        # names match in folder order, after a path
        from Quartz import CGColorSpaceCopyICCData, CGColorSpaceCreateWithName, kCGColorSpaceSRGB
        from plotdevice.gfx import colors
        from plotdevice.gfx.colors import _output_colors, Press
        cmyk, rgb = Press(FOGRA47).profile, bytes(CGColorSpaceCopyICCData(CGColorSpaceCreateWithName(kCGColorSpaceSRGB)))
        user, other = join(self.tmp, 'user'), join(self.tmp, 'other')
        os.makedirs(user)
        os.makedirs(other)
        for folder, name, icc in ((user, 'My Press.icc', cmyk), (other, 'My Press.icc', cmyk), (other, 'Lab Proof.ICM', rgb),
                                  (user, 'Shadowed.icc', rgb), (other, 'Shadowed.icc', cmyk)):
            open(join(folder, name), 'wb').write(icc)
        saved = colors._PROFILE_FOLDERS
        colors._PROFILE_FOLDERS = [user, other]
        try:
            for name in ('My Press', 'my press.icc', 'MY PRESS'):
                self.assertEqual(_output_colors(name, 'pdf'), os.path.realpath(join(user, 'My Press.icc')))
            self.assertEqual(_output_colors('lab proof', 'png'), os.path.realpath(join(other, 'Lab Proof.ICM')))
            # the menus skip truncated profiles
            open(join(user, 'Cut Off.icc'), 'wb').write(cmyk[:4000])
            self.assertIsNone(colors._profile_header(join(user, 'Cut Off.icc')))
            self.assertIsNotNone(colors._profile_header(join(user, 'My Press.icc')))
            with self.assertRaisesRegex(DeviceError, "can't be exported"):
                _output_colors('My Press', 'png')
            with self.assertRaisesRegex(DeviceError, "'Nothing Here' isn't a built-in color space or ICC profile filename"):
                _output_colors('Nothing Here', 'pdf')
            # an existing path wins over a name
            here = os.getcwd()
            os.chdir(other)
            try:
                self.assertEqual(_output_colors('Shadowed.icc', 'pdf'), join(os.path.realpath(other), 'Shadowed.icc'))
                self.assertEqual(_output_colors('Shadowed', 'png'), os.path.realpath(join(user, 'Shadowed.icc')))
            finally:
                os.chdir(here)
            # system profiles, offered or not
            if os.path.exists('/System/Library/ColorSync/Profiles/ITU-2020.icc'):
                self.assertEqual(_output_colors('ITU-2020', 'png'), '/System/Library/ColorSync/Profiles/ITU-2020.icc')
                self.assertEqual(_output_colors(REC2020, 'png'), _output_colors('ITU-2020', 'png'))
                self.assertEqual(_output_colors('REC709', 'mov'), '/System/Library/ColorSync/Profiles/ITU-709.icc')
                self.assertEqual(_output_colors('generic rgb profile', 'png'), '/System/Library/ColorSync/Profiles/Generic RGB Profile.icc')
                # Generic CMYK in any form means CMYK
                generic = '/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc'
                copy = join(user, 'Copy.icc')
                open(copy, 'wb').write(open(generic, 'rb').read())
                for val in ('Generic CMYK Profile', generic, copy):
                    self.assertEqual(_output_colors(val, 'pdf'), CMYK, val)
                with self.assertRaisesRegex(DeviceError, "can't be exported"):
                    _output_colors('Generic CMYK Profile', 'png')
        finally:
            colors._PROFILE_FOLDERS = saved
            colors._PROFILE_LISTS.clear()

    def test_presses_resolve_where_cmyk_fits(self):
        from plotdevice.gfx.colors import _output_colors, _output_mode, Press
        path = join(self.tmp, 'press.icc')
        open(path, 'wb').write(Press(FOGRA47).profile)
        for val, format, key in ((GRACOL, 'pdf', GRACOL), ('FOGRA39', 'tiff', FOGRA39), ('swop', 'eps', SWOP), ('Gracol-Uncoated', 'jpg', GRACOL_UNCOATED), (path, 'jpg', path)):
            self.assertEqual(_output_colors(val, format), key)
            self.assertEqual(_output_mode(key), CMYK)
        for format in ('png', 'heic', 'gif', 'mov'):
            with self.assertRaisesRegex(DeviceError, "can't be exported"):
                _output_colors(GRACOL, format)

    def _press_swatches(self):
        size(40, 20)
        background(1)
        fill(color(0, 0, 0, 1, mode=CMYK))
        rect(0, 0, 10, 10)
        fill(color(.6, .4, .4, 1, mode=CMYK))
        rect(10, 0, 10, 10)
        fill(1, 0, 0)
        rect(20, 0, 10, 10)
        with blend('multiply'):
            fill(color(0, 0, 1, 0, mode=CMYK))
            rect(30, 0, 10, 10)

    def test_rgb_colors_keep_their_shadows_in_a_press(self):
        # dark greys stay distinct, white is the paper
        from plotdevice.gfx.colors import _output_colors
        for press, greys in DARK_GREYS.items():
            _output_colors(press, 'pdf') # loads the press
            inks = [color(g / 255, g / 255, g / 255, space=SRGB)._press_values(press) for g in (0, 8, 16, 26, 255)]
            for got, want in zip(inks, greys):
                self.assertLessEqual(max(abs(g * 100 - w) for g, w in zip(got, want)), 1, (press, got, want))
            self.assertEqual(len(set(inks)), 5, press)
            self.assertEqual(inks[-1], (0, 0, 0, 0, 1))

    def test_press_bitmaps_keep_cmyk_numbers_in_the_press(self):
        from Quartz import (CGImageSourceCreateWithURL, CGImageSourceCreateImageAtIndex, CGImageGetColorSpace, CGColorSpaceCopyICCData,
                            CGBitmapContextCreate, CGContextDrawImage, CGBitmapContextCreateImage, CGDataProviderCopyData,
                            CGImageGetDataProvider, kCGImageAlphaNone)
        from Foundation import NSURL
        from plotdevice.gfx.colors import Press
        self._press_swatches()
        red = tuple(round(v * 255) for v in GRACOL_RED)
        for ext in ('tiff', 'jpg'):
            path = join(self.tmp, 'press.' + ext)
            export(path, colors=GRACOL)
            img = CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(path), None), 0, None)
            space = CGImageGetColorSpace(img)
            self.assertEqual(bytes(CGColorSpaceCopyICCData(space)), Press(GRACOL).profile, ext)
            # drawn in its own space, unconverted
            ctx = CGBitmapContextCreate(None, 40, 20, 8, 160, space, kCGImageAlphaNone)
            CGContextDrawImage(ctx, ((0, 0), (40, 20)), img)
            data = bytes(CGDataProviderCopyData(CGImageGetDataProvider(CGBitmapContextCreateImage(ctx))))
            pixel = lambda x, y: tuple(data[(y * 40 + x) * 4:][:4])
            off = 0 if ext == 'tiff' else 4
            for (x, y), want in (((5, 5), (0, 0, 0, 255)), ((15, 5), (153, 102, 102, 255)), ((25, 5), red), ((5, 15), (0, 0, 0, 0))):
                self.assertLessEqual(max(abs(g - w) for g, w in zip(pixel(x, y), want)), max(off, 1), (ext, x, y, pixel(x, y), want))

    def test_press_pdfs_are_pdfx4(self):
        import zlib
        from plotdevice.gfx.colors import Press
        self._press_swatches()
        path = join(self.tmp, 'press.pdf')
        export(path, colors=GRACOL)
        pdf = open(path, 'rb').read()
        streams = []
        for data in re.findall(rb'stream\r?\n(.*?)endstream', pdf, re.S):
            try:
                streams.append(zlib.decompress(data))
            except zlib.error:
                streams.append(data.strip()) # the XMP packet, uncompressed
        icc = Press(GRACOL).profile
        self.assertEqual(streams.count(icc), 1) # the output intent's
        drawn = b''.join(s for s in streams if s != icc and not s.startswith(b'<?xpacket'))
        fills = set(re.sub(rb'\s+', b' ', k) for k in re.findall(rb'[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+(?=\s+k\b)', drawn))
        self.assertTrue({b'0 0 0 1', b'0.6 0.4 0.4 1', b'0 0 1 0', b'0 0 0 0'} <= fills, fills)
        self.assertTrue(any(all(abs(float(a) - b) < .01 for a, b in zip(f.split(), GRACOL_RED)) for f in fills), (fills, GRACOL_RED))
        # assertIn would print the 2.7 MB file
        for expected in (rb'/OutputIntents (\d+) 0 R', rb'/Version /1.6 /OutputIntents \d+ 0 R /Metadata', rb'/OutputConditionIdentifier \(CGATS21-2-CRPC6\)',
                         rb'<pdfxid:GTS_PDFXVersion>PDF/X-4</pdfxid:GTS_PDFXVersion>', rb'/Trapped /False /GTS_PDFXVersion \(PDF/X-4\)',
                         rb'/TrimBox \[0 0 40 20\]'):
            self.assertTrue(re.search(expected, pdf), expected)
        groups = re.findall(rb'/Group\s*<<[^>]*/CS\s+(\d+) 0 R', pdf)
        self.assertTrue(groups)
        # PDF/X-4 needs DeviceCMYK blending
        self.assertTrue(re.search(rb'\n%s 0 obj\n/DeviceCMYK\s*endobj' % groups[-1], pdf), groups)

    def test_placed_images_in_a_press(self):
        # cmyk images keep their numbers, rgb ones convert
        from Quartz import (CGBitmapContextCreate, CGBitmapContextCreateImage, CGColorSpaceCreateWithICCData, CGColorSpaceCreateDeviceCMYK,
                            CGColorSpaceCreateWithName, kCGColorSpaceSRGB, kCGImageAlphaPremultipliedLast, CGContextSetFillColorWithColor,
                            CGColorCreate, CGContextFillRect, CGImageCreateCopyWithColorSpace, CGImageDestinationCreateWithURL,
                            CGImageDestinationAddImage, CGImageDestinationFinalize, kCGImageAlphaNone, CGImageSourceCreateWithURL,
                            CGImageSourceCreateImageAtIndex, CGImageGetColorSpace, CGContextDrawImage, CGDataProviderCopyData, CGImageGetDataProvider)
        from Foundation import NSURL
        from plotdevice.gfx.colors import Press
        def write(name, space, comps, alpha=kCGImageAlphaNone, relabel=None):
            ctx = CGBitmapContextCreate(None, 10, 10, 8, 40, space, alpha)
            CGContextSetFillColorWithColor(ctx, CGColorCreate(space, comps + (1,)))
            CGContextFillRect(ctx, ((0, 0), (10, 10)))
            img = CGBitmapContextCreateImage(ctx)
            path = join(self.tmp, name)
            dest = CGImageDestinationCreateWithURL(NSURL.fileURLWithPath_(path), 'public.tiff', 1, None)
            CGImageDestinationAddImage(dest, CGImageCreateCopyWithColorSpace(img, relabel) if relabel else img, None)
            CGImageDestinationFinalize(dest)
            return path
        def pixel(path):
            img = CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(path), None), 0, None)
            ctx = CGBitmapContextCreate(None, 30, 10, 8, 120, CGImageGetColorSpace(img), kCGImageAlphaNone)
            CGContextDrawImage(ctx, ((0, 0), (30, 10)), img)
            data = bytes(CGDataProviderCopyData(CGImageGetDataProvider(CGBitmapContextCreateImage(ctx))))
            return [tuple(round(v / 2.55) for v in data[(5 * 30 + x) * 4:][:4]) for x in (5, 15, 25)]
        gracol = CGColorSpaceCreateWithICCData(Press(GRACOL).profile)
        tagged = write('gracol.tiff', gracol, (.6, .4, .4, 1))
        untagged = write('untagged.tiff', gracol, (0, 0, 0, 1), relabel=CGColorSpaceCreateDeviceCMYK())
        orange = write('orange.tiff', CGColorSpaceCreateWithName(kCGColorSpaceSRGB), (1, .5, 0), kCGImageAlphaPremultipliedLast)
        size(30, 10)
        for i, path in enumerate((tagged, untagged, orange)):
            image(path, i * 10, 0)
        for colors in (FOGRA39, CMYK):
            export(join(self.tmp, 'placed.tiff'), colors=colors)
            got = pixel(join(self.tmp, 'placed.tiff'))
            self.assertEqual(got[:2], [(60, 40, 40, 100), (0, 0, 0, 100)], colors)
        export(join(self.tmp, 'placed.tiff'), colors=GRACOL)
        self.assertEqual(pixel(join(self.tmp, 'placed.tiff'))[2], (0, 60, 96, 0)) # relative intent would give Y 100
        export(join(self.tmp, 'placed.pdf'), colors=FOGRA39)
        pdf = open(join(self.tmp, 'placed.pdf'), 'rb').read()
        spaces = re.findall(rb'/Subtype /Image[^>]*?/ColorSpace\s+(/\w+|\d+ 0 R)', pdf)
        self.assertEqual(spaces.count(b'/DeviceCMYK'), 2, spaces) # the orange stays rgb

    def test_press_eps_keeps_the_numbers(self):
        self._press_swatches()
        export(join(self.tmp, 'press.eps'), colors=GRACOL)
        eps = open(join(self.tmp, 'press.eps'), 'rb').read().decode('latin-1')
        inks = set(tuple(round(float(v), 4) for v in m.split()) for m in re.findall(r'([-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+) (?:setcmykcolor|k)\b', eps))
        self.assertIn((0, 0, 0, 1), inks)
        self.assertIn((.6, .4, .4, 1), inks)

    def _pdf_pixels(self, path):
        """A PDF's first page and its PNG, drawn into P3 over white"""
        from Quartz import (CGPDFDocumentCreateWithURL, CGPDFDocumentGetPage, CGContextDrawPDFPage, CGBitmapContextCreate,
                            CGBitmapContextCreateImage, CGColorSpaceCreateWithName, kCGColorSpaceDisplayP3, CGContextDrawImage,
                            CGImageSourceCreateWithURL, CGImageSourceCreateImageAtIndex, CGContextSetRGBFillColor, CGContextFillRect,
                            CGDataProviderCopyData, CGImageGetDataProvider, kCGImageAlphaPremultipliedLast)
        from Foundation import NSURL
        def draw(paint):
            ctx = CGBitmapContextCreate(None, 20, 20, 8, 80, CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3), kCGImageAlphaPremultipliedLast)
            CGContextSetRGBFillColor(ctx, 1, 1, 1, 1)
            CGContextFillRect(ctx, ((0, 0), (20, 20)))
            paint(ctx)
            return bytes(CGDataProviderCopyData(CGImageGetDataProvider(CGBitmapContextCreateImage(ctx))))
        url = lambda ext: NSURL.fileURLWithPath_(path[:-3] + ext)
        pdf = draw(lambda ctx: CGContextDrawPDFPage(ctx, CGPDFDocumentGetPage(CGPDFDocumentCreateWithURL(url('pdf')), 1)))
        png = draw(lambda ctx: CGContextDrawImage(ctx, ((0, 0), (20, 20)), CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(url('png'), None), 0, None)))
        return pdf, png

    def _generic_png(self, n):
        """An n x n image tagged Generic RGB"""
        from Quartz import (CGBitmapContextCreate, CGBitmapContextCreateImage, CGColorSpaceCreateWithName, kCGColorSpaceGenericRGB,
                            CGContextSetRGBFillColor, CGContextFillRect, CGImageDestinationCreateWithURL, CGImageDestinationAddImage,
                            CGImageDestinationFinalize, kCGImageAlphaPremultipliedLast)
        from Foundation import NSURL
        import random as r
        ctx = CGBitmapContextCreate(None, n, n, 8, n * 4, CGColorSpaceCreateWithName(kCGColorSpaceGenericRGB), kCGImageAlphaPremultipliedLast)
        for i in range(n):
            CGContextSetRGBFillColor(ctx, r.random(), r.random(), 0, 1)
            CGContextFillRect(ctx, ((r.random() * n, r.random() * n), (n / 10, n / 10)))
        path = join(self.tmp, 'generic%d.png' % n)
        dest = CGImageDestinationCreateWithURL(NSURL.fileURLWithPath_(path), 'public.png', 1, None)
        CGImageDestinationAddImage(dest, CGBitmapContextCreateImage(ctx), None)
        CGImageDestinationFinalize(dest)
        return path

    def test_pdf_groups_blend_in_p3(self):
        # quartz's generic rgb groups clip P3 colors
        self._swatch(1, .8, 0)
        with blend('multiply'):
            fill(1, .8, 0)
            rect(0, 0, 20, 20)
        export(join(self.tmp, 'groups.png'))
        export(join(self.tmp, 'groups.pdf'))
        pdf, png = self._pdf_pixels(join(self.tmp, 'groups.pdf'))
        self.assertEqual(tuple(png[:3]), (255, 163, 0))
        self.assertEqual(pdf, png)

    def test_pdf_groups_leave_generic_rgb_images_alone(self):
        # images sharing the groups' space aren't relabeled
        for n in (4, 400):
            clear(all)
            size(20, 20)
            background(None)
            image(self._generic_png(n), 0, 0, width=20)
            with blend('multiply'):
                fill(1, .8, 0)
                rect(10, 10, 10, 10)
            export(join(self.tmp, 'generic.png'))
            export(join(self.tmp, 'generic.pdf'))
            pdf, png = self._pdf_pixels(join(self.tmp, 'generic.pdf'))
            self.assertLessEqual(max(abs(a - b) for a, b in zip(pdf, png)), 2, n) # the small image is scaled up

    def test_pdfs_without_groups_or_in_cmyk_are_left_as_quartz_writes_them(self):
        def draw(groups=True):
            self._swatch(1, .8, 0)
            if groups:
                with blend('multiply'):
                    rect(0, 0, 10, 10)
        def updates(name):
            return open(join(self.tmp, name + '.pdf'), 'rb').read().count(b'%%EOF') - 1
        draw(groups=False)
        export(join(self.tmp, 'plain.pdf'))
        draw()
        export(join(self.tmp, 'rgb.pdf'))
        export(join(self.tmp, 'cmyk.pdf'), colors=CMYK)
        for name, colors in (('rgb_book', P3), ('cmyk_book', CMYK)):
            with export(join(self.tmp, name + '.pdf'), colors=colors) as book:
                with book.page:
                    draw()
        self.assertEqual([updates(name) for name in ('plain', 'cmyk', 'cmyk_book', 'rgb', 'rgb_book')], [0, 0, 0, 1, 1])

    def test_proofs_render_through_the_press_or_srgb(self):
        # proofs show as their exports do, tiles too
        import objc
        from Quartz import (CGBitmapContextCreate, CGBitmapContextCreateImage, CGContextDrawImage, CGDataProviderCopyData,
                            CGImageGetDataProvider, CGColorSpaceCreateWithName, kCGColorSpaceDisplayP3, kCGColorSpaceSRGB,
                            kCGImageAlphaPremultipliedLast, CGContextSetRenderingIntent, kCGRenderingIntentRelativeColorimetric,
                            CGImageSourceCreateWithURL, CGImageSourceCreateImageAtIndex)
        from Foundation import NSURL
        from plotdevice.gfx.colors import _output_colors
        def pixels(img, w=40, h=20):
            # drawn into p3, as the window is
            ctx = CGBitmapContextCreate(None, w, h, 8, w * 4, CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3), kCGImageAlphaPremultipliedLast)
            CGContextSetRenderingIntent(ctx, kCGRenderingIntentRelativeColorimetric)
            CGContextDrawImage(ctx, ((0, 0), (w, h)), img)
            data = bytes(CGDataProviderCopyData(CGImageGetDataProvider(CGBitmapContextCreateImage(ctx))))
            return [tuple(data[(y * w + x) * 4:][:3]) for y in range(h) for x in range(w)]
        def shown(frame, w=40, h=20, origin=None):
            surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(w, h)
            frame._render_to_surface(surface, 1.0, origin=origin)
            return pixels(CGBitmapContextCreateImage(surface.context()), w, h)
        def close(a, b, what):
            worst = max(max(abs(x - y) for x, y in zip(p, q)) for p, q in zip(a, b))
            self.assertLessEqual(worst, 1, what)
        self._press_swatches()
        press = _output_colors(GRACOL, 'tiff')
        export(join(self.tmp, 'press.tiff'), colors=GRACOL)
        tiff = CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(join(self.tmp, 'press.tiff')), None), 0, None)
        proofed = shown(_ctx.canvas.commit(press, 'tiff', proofed=True))
        close(proofed, pixels(tiff), 'a press proof shows the press tiff')
        self.assertNotEqual(proofed[5 * 40 + 25], shown(_ctx.canvas.commit())[5 * 40 + 25]) # p3 red, out of gamut
        tile = shown(_ctx.canvas.commit(press, 'tiff', proofed=True), 20, 10, origin=(20, 10))
        close(tile, [proofed[y * 40 + x] for y in range(10, 20) for x in range(20, 40)], "a tile shows its part of the raster")
        # a frame proofed through sRGB clips p3 red to sRGB's
        frame = _ctx.canvas.commit()
        frame.proof = CGColorSpaceCreateWithName(kCGColorSpaceSRGB)
        red = tuple(round(v * 255) for v in SRGB_RED_IN_P3)
        close([shown(frame)[5 * 40 + 25]], [red], 'p3 red through sRGB')
        close([shown(frame)[15 * 40 + 5]], [(255, 255, 255)], 'the background stays white')
        # an sRGB proof matches a colors=SRGB png
        export(join(self.tmp, 'srgb.png'), colors=SRGB)
        png = CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(join(self.tmp, 'srgb.png')), None), 0, None)
        proofed = shown(_ctx.canvas.commit(SRGB, 'png', proofed=True))
        close(proofed, pixels(png), 'an sRGB proof shows the sRGB png')
        close([proofed[5 * 40 + 25]], [red], 'p3 red clipped to sRGB')
        # as does a system rgb space's proof
        from plotdevice.gfx.colors import _output_colors
        adobe = '/System/Library/ColorSync/Profiles/AdobeRGB1998.icc'
        if os.path.exists(adobe):
            export(join(self.tmp, 'adobe.png'), colors=adobe)
            png = CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(join(self.tmp, 'adobe.png')), None), 0, None)
            frame = _ctx.canvas.commit(_output_colors(adobe, 'png'), 'png', proofed=True)
            close(shown(frame), pixels(png), 'an Adobe RGB proof shows the Adobe RGB png')

    def test_run_fullscreen_keeps_the_proof(self):
        # Run Fullscreen keeps the window's proof
        from plotdevice.gui.views import FullscreenView
        from plotdevice.gfx.colors import _output_colors, _output_space
        from plotdevice.gfx.vision import _vision_space
        class Presenter(object):
            def render(self, frame, *args, **kwargs):
                self.frame = frame
        self._press_swatches()
        press = _output_colors(GRACOL, 'tiff')
        proofs = dict(press={'colors': press, 'format': 'tiff', 'proofed': True},
                      rgb={'colors': SRGB, 'format': 'png', 'proofed': True},
                      vision={'vision': _vision_space('protanopia')}, screen={})
        for name, proofArgs in proofs.items():
            view = FullscreenView.alloc().init()
            view._presenter = Presenter()
            view.proofArgs = proofArgs
            view.render(_ctx.canvas)
            frame = view._presenter.frame
            self.assertEqual(frame.press, press if name == 'press' else None, name)
            self.assertIs(frame.proof, _output_space(proofArgs['colors']) if 'proofed' in proofArgs else None, name)
            self.assertIs(frame.vision, proofArgs.get('vision'), name)

    def test_vision_proofs_show_the_simulation(self):
        # simulated frames match DaltonLens's math
        import objc
        from Quartz import (CGBitmapContextCreate, CGBitmapContextCreateImage, CGContextDrawImage, CGDataProviderCopyData,
                            CGImageGetDataProvider, CGColorSpaceCreateWithName, kCGColorSpaceDisplayP3, kCGImageAlphaPremultipliedLast)
        from plotdevice.gfx.vision import _vision_space, _simulate, _decode
        encode = lambda v: 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        swatches = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (0, 1, 1), (1, 0, 1), (.5, .5, .5), (1, 1, 1), (.8, .4, .1), (.2, .7, .4)]
        size(10 * len(swatches), 10)
        for i, c in enumerate(swatches):
            fill(*c)
            rect(10 * i, 0, 10, 10)
        for deficiency in ('protanopia', 'protanomaly', 'deuteranopia', 'deuteranomaly', 'tritanopia', 'tritanomaly'):
            frame = _ctx.canvas.commit(vision=_vision_space(deficiency))
            surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(10 * len(swatches), 10)
            frame._render_to_surface(surface, 1.0)
            w = 10 * len(swatches)
            ctx = CGBitmapContextCreate(None, w, 10, 8, w * 4, CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3), kCGImageAlphaPremultipliedLast)
            CGContextDrawImage(ctx, ((0, 0), (w, 10)), CGBitmapContextCreateImage(surface.context()))
            data = bytes(CGDataProviderCopyData(CGImageGetDataProvider(CGBitmapContextCreateImage(ctx))))
            for i, c in enumerate(swatches):
                r, g, b = data[(5 * w + 10 * i + 5) * 4:][:3]
                want = [round(255 * encode(min(max(v, 0), 1))) for v in _simulate(deficiency, [_decode(v) for v in c])]
                self.assertLessEqual(max(abs(x - y) for x, y in zip((r, g, b), want)), 3, (deficiency, c, (r, g, b), want))
        # proofs keep transparency and alpha
        clear(all)
        size(30, 10)
        background(None)
        fill(1, 0, 0)
        rect(0, 0, 10, 10)
        fill(1, 0, 0, .5)
        rect(10, 0, 10, 10)
        red = [round(255 * encode(min(max(v, 0), 1))) for v in _simulate('protanopia', (1, 0, 0))]
        for kind in ('protanopia', 'srgb'):
            if kind == 'srgb':
                frame = _ctx.canvas.commit(SRGB, 'png', proofed=True)
            else:
                frame = _ctx.canvas.commit(vision=_vision_space('protanopia'))
            surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(30, 10)
            frame._render_to_surface(surface, 1.0)
            ctx = CGBitmapContextCreate(None, 30, 10, 8, 120, CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3), kCGImageAlphaPremultipliedLast)
            CGContextDrawImage(ctx, ((0, 0), (30, 10)), CGBitmapContextCreateImage(surface.context()))
            data = bytes(CGDataProviderCopyData(CGImageGetDataProvider(CGBitmapContextCreateImage(ctx))))
            opaque, half, empty = [tuple(data[(5 * 30 + x) * 4:][:4]) for x in (5, 15, 25)]
            self.assertEqual(empty, (0, 0, 0, 0), kind)
            self.assertEqual(half[3], 128, kind)
            self.assertLessEqual(max(abs(2 * h - o) for h, o in zip(half[:3], opaque[:3])), 3, (kind, half, opaque))
            if kind == 'protanopia':
                self.assertLessEqual(max(abs(o - r) for o, r in zip(opaque[:3], red)), 3, (opaque, red))
        # white & grey stay put, red goes dark yellow-green
        self.assertEqual([round(v, 3) for v in _simulate('protanopia', (1, 1, 1))], [1.0, 1.0, 1.0])
        red = _simulate('protanopia', (1, 0, 0))
        self.assertAlmostEqual(red[0], red[1], places=2)
        self.assertLess(red[2], .01)
        # anomalies lie between normal and dichromat
        for full, partial, color, channel in (('protanopia', 'protanomaly', (1, 0, 0), 1), ('deuteranopia', 'deuteranomaly', (1, 0, 0), 1),
                                              ('tritanopia', 'tritanomaly', (0, 0, 1), 0)):
            normal, between, extreme = color[channel], _simulate(partial, color)[channel], _simulate(full, color)[channel]
            self.assertLess(min(normal, extreme), between, partial)
            self.assertLess(between, max(normal, extreme), partial)
        for deficiency in ('protanomaly', 'deuteranomaly', 'tritanomaly'):
            self.assertEqual([round(v, 2) for v in _simulate(deficiency, (1, 1, 1))], [1.0, 1.0, 1.0], deficiency)

    def test_window_surfaces_are_tagged_p3(self):
        import objc
        from Quartz import CGColorSpaceCreateWithPropertyList, CGColorSpaceCopyName, CGBitmapContextGetColorSpace
        surface = objc.lookUpClass('PDSurface').surfaceWithWidth_height_(4, 4)
        tag = surface.surface().attachmentForKey_('IOSurfaceColorSpace')
        self.assertEqual(CGColorSpaceCopyName(CGColorSpaceCreateWithPropertyList(tag)), 'kCGColorSpaceDisplayP3')
        self.assertEqual(CGColorSpaceCopyName(CGBitmapContextGetColorSpace(surface.context())), 'kCGColorSpaceDisplayP3')

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(ColorTests))
    return suite
