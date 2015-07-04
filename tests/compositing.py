# encoding: utf-8
import unittest
from . import PlotDeviceTestCase, reference
from plotdevice import *

class CompositingTests(PlotDeviceTestCase):
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
  suite.addTest(unittest.makeSuite(CompositingTests))
  return suite
