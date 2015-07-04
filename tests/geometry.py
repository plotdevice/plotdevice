# encoding: utf-8
import unittest
from . import PlotDeviceTestCase, reference
from plotdevice import *

class GeometryTests(PlotDeviceTestCase):
    @reference('geometry/graphics_state7.png')
    def test_graphics_state7(self):
        # tut/Geometry (1)
        size(280, 80)
        rect(20, 20, 40, 40)
        with transform():
            rotate(45)
            rect(120, 20, 40, 40)
        rect(220, 20, 40, 40)

    @reference('geometry/math-angle.png')
    def test_math_angle(self):
        # tut/Geometry (2)
        size(194, 194)
        r = 2.0
        origin = Point(WIDTH/2, HEIGHT/2)
        
        for i in range(5):
            pt = Point(random(WIDTH), random(HEIGHT))
            arc(pt, r)
        
            a = origin.angle(pt)
            with transform(CORNER):
                translate(origin.x, origin.y)
                rotate(-a)
                arrow(30, 0, 10)

    @reference('geometry/math-coordinates.png')
    def test_math_coordinates(self):
        # tut/Geometry (3)
        size(194, 194)
        r = 2.0
        origin = Point(WIDTH/2, HEIGHT/2)
        arc(origin, r) # a.k.a. arc(origin.x, origin.y, r)
        
        for i in range(10):
            a = 36*i
            pt = origin.coordinates(85, a)
            arc(pt, r)
            line(origin, pt)

    @reference('geometry/math-perpendicular.png')
    def test_math_perpendicular(self):
        # tut/Geometry (4)
        size(194, 194)
        stroke(0.5) and nofill()
        path = oval(45, 45, 105, 105)
        for t in range(50):
            curve = path.point(t/50.0)
            a = curve.angle(curve.ctrl2)
            with transform(CORNER):
                translate(curve.x, curve.y)
                rotate(-a+90) # rotate by 90°
                line(0, 0, 35, 0)

    @reference('geometry/math-angles.png')
    def test_math_angles(self):
        # tut/Geometry (5)
        size(109, 177)
        with stroke(0), nofill():
            arc(50,25, 25, range=180)
        
            geometry(RADIANS)
            arc(50,75, 25, range=pi)
        
            geometry(PERCENT)
            arc(50,125, 25, range=.5)

    @reference('geometry/math-trig7.jpg')
    def test_math_trig7(self):
        # tut/Geometry (6)
        size(260, 260)
        def coordinates(x0, y0, distance, angle):
            from math import radians, sin, cos
            angle = radians(angle)
            x1 = x0 + cos(angle) * distance
            y1 = y0 + sin(angle) * distance
            return x1, y1

    @reference('geometry/reset.jpg')
    def test_reset(self):
        # ref/Transform/commands/reset()
        size(125, 125)
        font(14), fill(0.2)
        
        rotate(90)
        text("one", 30, 80)
        text("two", 45, 80)
        
        reset()
        text("three", 70, 80)

    @reference('geometry/rotate.jpg')
    def test_rotate(self):
        # ref/Transform/commands/rotate()
        size(125, 125)
        fill(0.2)
        rotate(-45)
        rect(30, 30, 40, 40)

    @reference('geometry/scale.png')
    def test_scale(self):
        # ref/Transform/commands/scale()
        size(125, 125)
        fill(0.2)
        poly(30,30, 20)
        scale(0.5)
        poly(70,30, 20)

    @reference('geometry/skew.jpg')
    def test_skew(self):
        # ref/Transform/commands/skew()
        size(125, 125)
        fill(0.2)
        skew(10.0)
        rect(20, 10, 40, 40)

    @reference('geometry/pop.jpg')
    def test_pop(self):
        # ref/Transform/commands/transform()
        size(125, 125)
        fill(0.2)
        fontsize(14)
        rotate(90)
        text("one", 40, 80)
        
        with transform():
            rotate(-90)
            text("two", 40, 40)
        
        text("three", 50, 80)

    @reference('geometry/translate.jpg')
    def test_translate(self):
        # ref/Transform/commands/translate()
        size(125, 125)
        fill(0.2)
        arc(10,10, 20)
        translate(50, 50)
        arc(10,10, 20)

    @reference('geometry/push.jpg')
    def test_push(self):
        # ref/Transform/compat/push()
        size(125, 125)
        fill(0.2)
        fontsize(14)
        rotate(90)
        text("one", 40, 80)
        
        push()
        rotate(-90)
        text("two", 40, 40)
        pop()
        
        text("three", 50, 80)


def suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(GeometryTests))
  return suite
