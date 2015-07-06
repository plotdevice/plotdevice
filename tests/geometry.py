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

    @reference('geometry/point-angle.png')
    def test_point_angle(self):
        # ref/Misc/types/Point
        size(125, 125)
        src = Point(25,75)
        dst = Point(75,25)
        theta = src.angle(dst)
        arc(src, 4, fill='red')
        arc(dst, 4, fill='orange')
        with pen(dash=5), stroke(.5), nofill():
            arc(src, 32, range=theta)
        self.assertAlmostEqual(theta, -45.0)

    @reference('geometry/point-distance.png')
    def test_point_distance(self):
        # ref/Misc/types/Point
        size(125, 125)
        src = Point(25,25)
        dst = Point(100,100)
        length = src.distance(dst)
        arc(src, 4, fill='red')
        arc(dst, 4, fill='orange')
        with pen(dash=5), stroke(.8):
            line(src, dst)
        self.assertAlmostEqual(length, 106.066017178)

    @reference('geometry/point-reflect.png')
    def test_point_reflect(self):
        # ref/Misc/types/Point
        size(125, 125)
        origin = Point(50,50)
        src = Point(25,40)
        dst = origin.reflect(src, d=2.0)
        arc(src, 4, fill='red')
        arc(dst, 4, fill='orange')
        arc(origin, 4, fill=.7)

    @reference('geometry/point-coordinates.png')
    def test_point_coordinates(self):
        # ref/Misc/types/Point
        size(125, 125)
        origin = Point(50,50)
        dst = origin.coordinates(50, 45)
        arc(origin, 4, fill=.7)
        arc(dst, 4, fill='orange')
        with pen(dash=3), stroke(.5), nofill():
            arc(origin, 25, range=45)

    @reference('geometry/region-intersect.png')
    def test_region_intersect(self):
        # ref/Misc/types/Region
        size(125, 125)
        r1 = Region(20,20, 40,30)
        r2 = Region(40,40, 30,40)
        overlap = r1.intersect(r2)
        with nofill(), stroke(.7):
            rect(r1)
            rect(r2)
            rect(overlap, stroke='red', dash=3)

    @reference('geometry/region-union.png')
    def test_region_union(self):
        # ref/Misc/types/Region
        size(125, 125)
        r1 = Region(20,20, 40,30)
        r2 = Region(40,40, 30,40)
        union = r1.union(r2)
        with nofill(), stroke(.7):
            rect(r1)
            rect(r2)
            rect(union, stroke='red', dash=3)

    @reference('geometry/region-shift.png')
    def test_region_shift(self):
        # ref/Misc/types/Region
        size(125, 125)
        r = Region(20,20, 40,30)
        shifted = r.shift(20,15)
        nofill()
        rect(r, stroke=.7)
        rect(shifted, stroke='red', dash=3)

    @reference('geometry/region-inset.png')
    def test_region_inset(self):
        # ref/Misc/types/Region
        size(125, 125)
        r = Region(30,40, 60,40)
        shrunk = r.inset(20,5)
        grown = r.inset(-20)
        nofill()
        rect(r, stroke=.7)
        rect(shrunk, stroke='orange', dash=3)
        rect(grown, stroke='red', dash=3)

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

    @reference('geometry/pop.png')
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

    @reference('geometry/push.png')
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
