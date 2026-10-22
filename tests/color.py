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

def _image(path):
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

    def test_gradient_keeps_the_space_its_made_in(self):
        with color(space=SRGB):
            g = Gradient(color(1, 0, 0), '#00f')
        self.assertEqual(g._space, SRGB)
        self.assertEqual(Gradient(g)._space, SRGB)
        self.assertEqual(Gradient('#f00', '#00f')._space, P3)

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
        outputmode(CMYK)
        self._swatch(color(.6, .4, .4, 1, mode=CMYK))
        space, data, row, bpp = _image(self._save('swatch.tiff', cmyk=True))
        outputmode(RGB)
        self.assertEqual(bpp, 4)
        self.assertEqual(tuple(data[10 * row + 10 * bpp:][:4]), (153, 102, 102, 255))

    def test_placed_cmyk_images_keep_their_numbers(self):
        import zlib
        from Quartz import (CGBitmapContextCreate, CGBitmapContextCreateImage, CGColorSpaceCreateWithName, kCGColorSpaceGenericCMYK,
                            CGContextSetFillColorWithColor, CGColorCreate, CGContextFillRect, CGImageDestinationCreateWithURL,
                            CGImageDestinationAddImage, CGImageDestinationFinalize, kCGImageAlphaNone)
        from Foundation import NSURL
        generic = CGColorSpaceCreateWithName(kCGColorSpaceGenericCMYK)
        ctx = CGBitmapContextCreate(None, 20, 20, 8, 80, generic, kCGImageAlphaNone)
        CGContextSetFillColorWithColor(ctx, CGColorCreate(generic, (0, 0, 0, 1, 1)))
        CGContextFillRect(ctx, ((0, 10), (20, 10))) # (the top half: K)
        CGContextSetFillColorWithColor(ctx, CGColorCreate(generic, (1, 0, 0, 0, 1)))
        CGContextFillRect(ctx, ((0, 0), (20, 10)))  # (the bottom: C)
        src = join(self.tmp, 'tagged.tiff')
        dest = CGImageDestinationCreateWithURL(NSURL.fileURLWithPath_(src), 'public.tiff', 1, None)
        CGImageDestinationAddImage(dest, CGBitmapContextCreateImage(ctx), None)
        CGImageDestinationFinalize(dest)
        size(20, 20)
        image(src, 0, 0)
        space, data, row, bpp = _image(self._save('placed.tiff', colors=CMYK))
        self.assertEqual((tuple(data[5 * row + 5 * bpp:][:4]), tuple(data[15 * row + 5 * bpp:][:4])), ((0, 0, 0, 255), (255, 0, 0, 0)))
        pdf = open(self._save('placed.pdf', colors=CMYK), 'rb').read()
        self.assertTrue(re.search(rb'/Subtype /Image[^>]*/ColorSpace\s+/DeviceCMYK', pdf)) # (not printing the pdf if it fails)

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
        self.assertNotIn(p3, streams) # (the fills are in srgb, and the groups are relabelled to it)
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
        for colors, primaries in ((P3, 12), (SRGB, 1)): # (the colr atom's codes for P3-D65 and Rec.709)
            path = join(self.tmp, colors + '.mov')
            with export(path, colors=colors) as movie:
                for i in range(2):
                    with movie.frame:
                        self._two_swatches()
            mov = open(path, 'rb').read()
            at = re.search(rb'colrncl[cx]', mov).end()
            self.assertEqual(int.from_bytes(mov[at:at + 2], 'big'), primaries, colors)

    def test_each_format_takes_the_colors_it_can_hold(self):
        from plotdevice.gfx.colors import _output_colors
        profile = '/System/Library/ColorSync/Profiles/AdobeRGB1998.icc'
        accepts = dict(png='P3 SRGB icc', heic='P3 SRGB icc', mov='P3 SRGB', gif='SRGB', eps='SRGB CMYK',
                       pdf='P3 SRGB icc CMYK', tiff='P3 SRGB icc CMYK', jpg='P3 SRGB icc CMYK')
        for format, ok in accepts.items():
            for name, val in (('P3', P3), ('SRGB', SRGB), ('icc', profile), ('CMYK', CMYK)):
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
                       dict(colors=CMYK, cmyk=True), dict(colours=CMYK)):
            self.assertRaises(DeviceError, export, path, **kwargs)
        self.assertRaises(DeviceError, export, join(self.tmp, 'bad.png'), colors=CMYK)
        self.assertFalse(os.path.exists(path))

    def test_exports_follow_outputmode_unless_they_choose(self):
        outputmode(CMYK)
        self._swatch(color(0, 0, 0, 1, mode=CMYK))
        export(join(self.tmp, 'mode.tiff'))
        export(join(self.tmp, 'chosen.tiff'), colors=P3)
        export(join(self.tmp, 'mode.png')) # (a format that can't hold cmyk takes its default)
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
        self.assertEqual(caught[0].filename, __file__) # (pointing at the export() call)
        export(join(self.tmp, 'new.tiff'), colors=CMYK)
        self.assertEqual(open(join(self.tmp, 'old.tiff'), 'rb').read(), open(join(self.tmp, 'new.tiff'), 'rb').read())

    def _pdf_pixels(self, path):
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
            self.assertLessEqual(max(abs(a - b) for a, b in zip(pdf, png)), 2, n) # (the small image is scaled up)

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
