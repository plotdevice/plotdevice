# encoding: utf-8
import unittest
from . import PlotDeviceTestCase, reference
from plotdevice import *

class CompositingTests(PlotDeviceTestCase):
    def test_effects_restore_to_unset(self):
        from plotdevice import _ctx
        with alpha(.5), blend('multiply'), shadow('red'):
            pass
        self.assertEqual(_ctx._effects._fx, {})

    @reference('compositing/alpha.png')
    def test_alpha(self):
        # ref/Compositing/commands/alpha()
        size(125, 125)
        rect(10,10, 50,50, fill='red') # at full opacity
        alpha(.5)
        rect(35,35, 50,50, fill='black') # half opacity

    @reference('compositing/alpha-layer.png')
    def test_alpha_layer(self):
        # ref/Compositing/commands/alpha()
        size(125, 125)
        with alpha(.5): # entire layer at half opacity
            rect(10,10, 50,50, fill='red')
            rect(35,35, 50,50, fill='black')

    @reference('compositing/clip.png')
    def test_clip(self):
        # ref/Compositing/commands/clip()
        size(125, 125)
        with clip(poly(64,64, 50, sides=5)):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-image.png')
    def test_clip_image(self):
        # ref/Compositing/commands/clip()
        size(125, 125)
        with clip(image('tests/_in/logo-stencil.png')):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-text.png')
    def test_clip_text(self):
        # ref/Compositing/commands/clip()
        size(125, 125)
        font("Avenir", "bold", 112)
        with clip(text('Hi', 5, 100)):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-vector-image.png')
    def test_clip_image_vector(self):
        size(125, 125)
        # ensure tiny PDF is scaled up before rasterizing into a larger mask
        with clip(image('tests/_in/tiny-triangle.pdf', width=125, height=125)):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-vector-image-scale.png')
    def test_clip_image_vector_scale(self):
        size(125, 125)
        scale(2)
        with clip(image('tests/_in/tiny-triangle.pdf', width=62, height=62)):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-vector-image-rotate.png')
    def test_clip_image_vector_rotate(self):
        size(125, 125)
        rotate(30)
        with clip(image('tests/_in/tiny-triangle.pdf', width=125, height=125)):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-vector-image-transform.png')
    def test_clip_image_vector_transform(self):
        size(125, 125)
        scale(1.5)
        rotate(20)
        with clip(image('tests/_in/tiny-triangle.pdf', width=83, height=83)):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-outline-pdf.png')
    def test_clip_image_outline_pdf(self):
        # channel='outline' traces the pdf's vector shapes into a Bezier and
        # clips against that directly, rather than rasterizing a bitmap mask
        size(125, 125)
        with clip(image('tests/_in/tiny-triangle.pdf', width=125, height=125), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-outline-pdf-transform.png')
    def test_clip_image_outline_pdf_transform(self):
        # same as test_clip_image_outline_pdf but under canvas transforms, to
        # confirm the traced path is positioned via the image's _screen_transform
        size(125, 125)
        translate(20, 40)
        scale(1.3)
        rotate(20)
        with clip(image('tests/_in/tiny-triangle.pdf', width=83, height=83), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-outline-svg.png')
    def test_clip_image_outline_svg(self):
        # vector-fill.svg has two overlapping shapes (a circle and a rect) --
        # the outline should be their union, not two independently-clipped shapes
        size(125, 125)
        with clip(image('tests/_in/vector-fill.svg', width=125, height=125), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-outline-svg-stroke.png')
    def test_clip_image_outline_svg_stroke(self):
        # vector-stroke.svg is a stroke-only (unfilled) ring -- without
        # converting the stroke to its equivalent fill outline, this shape
        # would contribute a zero-width centerline (i.e. no clippable area)
        size(125, 125)
        with clip(image('tests/_in/vector-stroke.svg', width=125, height=125), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-outline-pdf-stroke.png')
    def test_clip_image_outline_pdf_stroke(self):
        # skewed-stroke.pdf is a stroke-only (unfilled) ring drawn under a
        # rotated, non-uniformly-scaled `cm` in its own content stream --
        # exercises stroke-to-fill conversion under an anisotropic transform,
        # not just the identity/uniform-scale case the _transform test covers
        size(125, 125)
        with clip(image('tests/_in/skewed-stroke.pdf', width=125, height=125), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-outline-pdf-xobject.png')
    def test_clip_image_outline_pdf_xobject(self):
        # xobject.pdf's only geometry is a filled square inside a Form
        # XObject, invoked via `Do` from the page's content stream (which
        # itself draws nothing directly) -- without recursing into Form
        # XObjects, the traced outline would be empty
        size(125, 125)
        with clip(image('tests/_in/xobject.pdf', width=125, height=125), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-outline-pdf-xobject-transform.png')
    def test_clip_image_outline_pdf_xobject_transform(self):
        # the Form XObject here has its own /Matrix (a 90-degree rotation)
        # and is also invoked under a non-trivial `cm` at the `Do` call site --
        # exercises the concatenation order (Matrix applied first, then the
        # invoking CTM)
        size(125, 125)
        with clip(image('tests/_in/xobject-transform.pdf', width=125, height=125), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-outline-pdf-xobject-nested.png')
    def test_clip_image_outline_pdf_xobject_nested(self):
        # the page's Form XObject itself invokes a second, nested Form XObject
        # via its own `Do` -- exercises formDepth > 1 and a Form resolving
        # `Do` against its own /Resources dict rather than the page's
        size(125, 125)
        with clip(image('tests/_in/xobject-nested.pdf', width=125, height=125), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/clip-outline-raster.png')
    def test_clip_image_outline_raster(self):
        # channel='outline' on a raster (non-vector) image just falls back to
        # a rect the size of the image, since there's no vector geometry to trace
        size(125, 125)
        with clip(image('tests/_in/plaid.png', 10, 10, 80, 80), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/mask-outline-pdf.png')
    def test_mask_image_outline_pdf(self):
        size(125, 125)
        with mask(image('tests/_in/tiny-triangle.pdf', width=125, height=125), channel='outline'):
            image('tests/_in/plaid.png')

    @reference('compositing/mask.png')
    def test_mask(self):
        # ref/Compositing/commands/mask()
        size(125, 125)
        with mask(poly(64,64, 50, sides=5)):
            image('tests/_in/plaid.png')

    @reference('compositing/mask-image.png')
    def test_mask_image(self):
        # ref/Compositing/commands/mask()
        size(125, 125)
        with mask(image('tests/_in/logo-stencil.png')):
            image('tests/_in/plaid.png')

    @reference('compositing/mask-text.png')
    def test_mask_text(self):
        # ref/Compositing/commands/mask()
        size(125, 125)
        font("Avenir", "bold", 112)
        with mask(text('Hi', 5, 100)):
            image('tests/_in/plaid.png')

    @reference('compositing/mask-vector-image.png')
    def test_mask_image_vector(self):
        size(125, 125)
        # ensure tiny PDF is scaled up before rasterizing into a larger mask
        with mask(image('tests/_in/tiny-triangle.pdf', width=125, height=125)):
            image('tests/_in/plaid.png')

    @reference('compositing/shadow-multi.png')
    def test_shadow_multi(self):
        # ref/Compositing/commands/shadow()
        size(125, 125)
        # draw each rect with its own dropshadow
        pen(5, fill='#08a', stroke='#eee')
        shadow('#999', blur=6, offset=4)
        rect(60,10, 50,50)
        rect(10,10, 50,50)
        rect(35,35, 50,50, fill=None)

    @reference('compositing/shadow-layer.png')
    def test_shadow_layer(self):
        # ref/Compositing/commands/shadow()
        size(125, 125)
        # draw a single dropshadow for the entire layer
        pen(5, fill='#08a', stroke='#eee')
        with shadow('#999', blur=6, offset=4):
            rect(60,10, 50,50)
            rect(10,10, 50,50)
            rect(35,35, 50,50, fill=None)

    @reference('compositing/shadow.png')
    def test_shadow(self):
        # ref/Compositing/commands/shadow()
        size(125, 125)
        with shadow('green'):
            poly(30,30, 15)
        with shadow(('black',.5), blur=5):
            poly(90,30, 15)
        with shadow('red', blur=0, offset=(5,10)):
            poly(30,90, 15)
        with shadow('blue', blur=20, offset=0):
            poly(90,90, 15)

    @reference('compositing/beginclip.jpg')
    def test_beginclip(self):
        # ref/Compositing/compat/beginclip()
        size(125, 125)
        p = oval(20, 20, 80, 80, plot=False)
        beginclip(p)
        image("tests/_in/header.jpg", -130, 0)
        endclip()


def suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(CompositingTests))
  return suite
