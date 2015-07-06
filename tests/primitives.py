# encoding: utf-8
import unittest
from . import PlotDeviceTestCase, reference
from plotdevice import *

class PrimitivesTests(PlotDeviceTestCase):
    @reference('primitives/primitives-arc.png')
    def test_primitives_arc(self):
        # tut/Primitives (1)
        size(150, 75)
        arc(75,25, 25)

    @reference('primitives/primitives-square.png')
    def test_primitives_square(self):
        # tut/Primitives (2)
        size(150, 75)
        poly(75,25, 25)

    @reference('primitives/primitives-poly.png')
    def test_primitives_poly(self):
        # tut/Primitives (3)
        size(150, 75)
        poly(75,25, 25, sides=6)

    @reference('primitives/primitives-star.png')
    def test_primitives_star(self):
        # tut/Primitives (4)
        size(150, 75)
        poly(75,25, 25, points=5)

    @reference('primitives/primitives-arrow.png')
    def test_primitives_arrow(self):
        # tut/Primitives (5)
        size(150, 75)
        arrow(75,25, 50)

    @reference('primitives/primitives-oval.png')
    def test_primitives_oval(self):
        # tut/Primitives (6)
        size(150, 75)
        oval(75,25, 50,50)

    @reference('primitives/primitives-rect.png')
    def test_primitives_rect(self):
        # tut/Primitives (7)
        size(150, 75)
        rect(75,25, 50,50)

    @reference('primitives/primitives-image.png')
    def test_primitives_image(self):
        # tut/Primitives (8)
        size(150, 77)
        image("tests/_in/triforce.png", 75,25)

    @reference('primitives/primitives-text.png')
    def test_primitives_text(self):
        # tut/Primitives (9)
        size(150, 75)
        text("xyzzy", 75,25)

    @reference('primitives/arc-simple.png')
    def test_arc_simple(self):
        # ref/Primitives/commands/arc()
        size(125, 125)
        fill(.9)
        arc(125,125, 125)
        
        fill(.2)
        arc(40,40, 20)

    @reference('primitives/arc.png')
    def test_arc(self):
        # ref/Primitives/commands/arc()
        size(125, 125)
        nofill()
        stroke(.2)
        arc(60,60, 40, range=180)
        arc(60,60, 30, range=90, ccw=True)
        stroke('red')
        arc(60,60, 20, range=270, close=True)

    @reference('primitives/superfolia.jpg')
    def test_superfolia(self):
        # ref/Primitives/commands/image()
        size(135, 135)
        image("tests/_in/superfolia.jpg", 0, 0)

    @reference('primitives/line.jpg')
    def test_line(self):
        # ref/Primitives/commands/line()
        size(125, 125)
        pen(2)
        stroke(0.2)
        line(10, 20, 80, 80)

    @reference('primitives/oval.jpg')
    def test_oval(self):
        # ref/Primitives/commands/oval()
        size(125, 125)
        fill(0.2)
        oval(10,20, 40,40)

    @reference('primitives/poly-sides.png')
    def test_poly_sides(self):
        # ref/Primitives/commands/poly()
        size(125, 125)
        fill(.2)
        poly(30,30, 20)
        poly(80,30, 20, sides=5)
        poly(30,80, 20, sides=6)
        poly(80,80, 20, sides=8)

    @reference('primitives/poly-points.png')
    def test_poly_points(self):
        # ref/Primitives/commands/poly()
        size(125, 125)
        fill(.2)
        poly(30,30, 20, points=5)
        poly(80,30, 20, points=6)
        poly(30,80, 20, points=8)
        poly(80,80, 20, points=12)

    @reference('primitives/rect.jpg')
    def test_rect(self):
        # ref/Primitives/commands/rect()
        size(125, 125)
        fill(0.2)
        rect(10, 20, 60, 40)

    @reference('primitives/text.png')
    def test_text(self):
        # ref/Primitives/commands/text()
        size(125, 125)
        fill(0.2)
        font("Helvetica", 20)
        text("hello", 10,50)
        text("goodbye", 10,70, italic=True)

    @reference('primitives/arrow.jpg')
    def test_arrow(self):
        # ref/Primitives/compat/arrow()
        size(125, 125)
        fill(0.2)
        arrow(50, 50, 50)
        
        rotate(180)
        fill('red')
        arrow(50, 50, 50)

    @reference('primitives/star.png')
    def test_star(self):
        # ref/Primitives/compat/star()
        size(125, 125)
        fill(.75)
        star(50,50, 16, 50,25)
        
        fill(0.2)
        star(50,50, 8, 50)


def suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(PrimitivesTests))
  return suite
