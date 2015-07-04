# encoding: utf-8
import unittest
from . import PlotDeviceTestCase, reference
from plotdevice import *

class UtilityTests(PlotDeviceTestCase):
    @reference('utility/point-angle.png')
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

    @reference('utility/point-distance.png')
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

    @reference('utility/point-reflect.png')
    def test_point_reflect(self):
        # ref/Misc/types/Point
        size(125, 125)
        origin = Point(50,50)
        src = Point(25,40)
        dst = origin.reflect(src, d=2.0)
        arc(src, 4, fill='red')
        arc(dst, 4, fill='orange')
        arc(origin, 4, fill=.7)

    @reference('utility/point-coordinates.png')
    def test_point_coordinates(self):
        # ref/Misc/types/Point
        size(125, 125)
        origin = Point(50,50)
        dst = origin.coordinates(50, 45)
        arc(origin, 4, fill=.7)
        arc(dst, 4, fill='orange')
        with pen(dash=3), stroke(.5), nofill():
            arc(origin, 25, range=45)

    @reference('utility/region-intersect.png')
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

    @reference('utility/region-union.png')
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

    @reference('utility/region-shift.png')
    def test_region_shift(self):
        # ref/Misc/types/Region
        size(125, 125)
        r = Region(20,20, 40,30)
        shifted = r.shift(20,15)
        nofill()
        rect(r, stroke=.7)
        rect(shifted, stroke='red', dash=3)

    @reference('utility/region-inset.png')
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


def suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(UtilityTests))
  return suite
