# encoding: utf-8
import math
import unittest
from . import PlotDeviceTestCase, reference
from plotdevice import *
from plotdevice import DeviceError
from AppKit import NSAffineTransform, NSBezierPath
from _plotdevice import PDPath

class DrawingTests(PlotDeviceTestCase):
    @reference('drawing/paths-transform-pre.png')
    def test_paths_transform_pre(self):
        # tut/Bezier_Paths (1)
        size(180, 180)
        font("Rockwell", "bold", 280)
        path = textpath("e", 10, 150)
        bezier(path, stroke='black', fill=None)

    @reference('drawing/paths-transform-post.png')
    def test_paths_transform_post(self):
        # tut/Bezier_Paths (2)
        size(180, 180)
        font("Rockwell", "bold", 280)
        path = textpath("e", 10, 150)
        curves = []
        for curve in path:
            curve.y += 20 # nudge the point downward
            curves.append(curve)
        
        # draw a new bezier (built from our list of Curve objects)
        bezier(curves, stroke='black', fill=None)

    @reference('drawing/paths-broken.jpg')
    def test_paths_broken(self):
        # tut/Bezier_Paths (3)
        size(334, 87)
        font("Rockwell", "bold", 90)
        path = textpath("broken", 0,80)
        
        curves = []
        for curve in path:
            if curve.cmd == CURVETO:
                curve.ctrl2.x += 5
                curve.ctrl2.y -= 10
                curve.y += 5
            curves.append(curve)
        
        with stroke(0), nofill():
            bezier(curves)

    @reference('drawing/pathmatics-contours.png')
    def test_pathmatics_contours(self):
        # tut/Bezier_Paths (4)
        size(181, 70)
        font("Rockwell", "bold", 50)
        with pen(2), nofill():
            path = textpath("@#$&!", 10, 50)
            for contour in path.contours:
                stroke(HSV, random(), 1, .8)
                bezier(contour)

    @reference('drawing/paths-compound1.png')
    def test_paths_compound1(self):
        # tut/Bezier_Paths (5)
        size(200, 270)
        stroke(0, .3) # use a translucent black
        pen(4, cap=ROUND)
        
        # draw twelve overlapping lines separately
        translate(5,5)
        for i in range(12):
            line(0, i*10, i*15, 120)
        
        # draw them as a single compound-path
        translate(0, 140)
        with bezier():
            for i in range(12):
                line(0, i*10, i*15, 120)

    @reference('drawing/paths-compound2.png')
    def test_paths_compound2(self):
        # tut/Bezier_Paths (6)
        size(200, 200)
        # capture the bezier into the `path` variable
        with bezier(plot=False) as path:
            for x,y in grid(10,10, 20,20):
                shape = choice([rect, oval])
                shape(x,y, 15,15)
        
        # apply a gradient fill color to the compound path
        fill('green', 'cyan')
        bezier(path)

    def test_paths_compound_units(self):
        # shapes transformed inside a compound path land where they would on their own, in any unit
        size(20, 20, unit=cm)
        with bezier(plot=False) as path:
            with transform():
                translate(1.5, -.5)
                rect(2, 3, 4, 2)
        (x, y), (w, h) = path.bounds
        self.assertEqual([round(v, 9) for v in (x, y, w, h)], [3.5, 2.5, 4, 2])

        transform(CENTER)
        with bezier(plot=False) as path:
            with transform():
                rotate(30)
                rect(2, 3, 4, 2)
        self.assertAlmostEqual(path.center.x, 4)
        self.assertAlmostEqual(path.center.y, 4)

    def test_paths_xy(self):
        # a path's x & y are its fulcrum's, or else its bounds' origin
        size(100, 100)
        box = rect(10, 20, 30, 40, plot=False)
        self.assertEqual((box.x, box.y), (10, 20))
        spiky = star(50, 60, 5, 20, plot=False)
        self.assertEqual((spiky.x, spiky.y), (50, 60))
        box.x, box.y = 15, 25
        self.assertEqual(tuple(box.bounds.origin), (15, 25))

    def test_paths_closepath(self):
        # closepath() closes the current subpath, once, and does nothing without one
        def triangle(x):
            moveto(x, 0)
            lineto(x + 10, 0)
            lineto(x + 5, 8)
        closes = lambda path: [el.cmd for el in path].count(CLOSE)

        with bezier(plot=False) as path:
            triangle(0)
            closepath()
            closepath()
            triangle(20)
            closepath()
        self.assertEqual(closes(path), 2)

        beginpath()
        triangle(0)
        closepath()
        triangle(20)
        self.assertEqual(closes(endpath(plot=False)), 2) # the open one is autoclosed

        with bezier(plot=False, close=True) as path:
            triangle(0)
            closepath()
        self.assertEqual(closes(path), 1)

        beginpath()
        self.assertEqual(len(endpath(plot=False)), 0)

    def test_pdpath_matches_nsbezierpath(self):
        # PDPath's shapes, closes, and transformed copies have NSBezierPath's elements and bounds
        # (its ovals and arcs are computed rather than built by ns, so their points can differ in the last bits)
        def elements(ns):
            return tuple((int(cmd), tuple((pt.x, pt.y) for pt in pts))
                         for cmd, pts in (ns.elementAtIndex_associatedPoints_(i) for i in range(ns.elementCount())))
        def assertElementsClose(got, expected):
            self.assertEqual([cmd for cmd, _ in got], [cmd for cmd, _ in expected])
            for (_, pts), (_, ns_pts) in zip(got, expected):
                for pt, ns_pt in zip(pts, ns_pts):
                    self.assertAlmostEqual(pt[0], ns_pt[0], places=9)
                    self.assertAlmostEqual(pt[1], ns_pt[1], places=9)
        p, ns = PDPath(), NSBezierPath.bezierPath()
        p.moveto(0, 0); ns.moveToPoint_((0, 0))
        p.lineto(10, 0); ns.lineToPoint_((10, 0))
        p.curveto(12, 2, 12, 6, 10, 8); ns.curveToPoint_controlPoint1_controlPoint2_((10, 8), (12, 2), (12, 6))
        p.closepath(); ns.closePath()
        p.rect(20, 0, 10, 6); ns.appendBezierPathWithRect_(((20, 0), (10, 6)))
        p.lineto(25, 12); ns.lineToPoint_((25, 12))
        p.rect(40, 0, 10, 6, 2, 3); ns.appendBezierPathWithRoundedRect_xRadius_yRadius_(((40, 0), (10, 6)), 2, 3)
        p.oval(60, 0, 10, 6); ns.appendBezierPathWithOvalInRect_(((60, 0), (10, 6)))
        p.arc(80, 3, 5, 30, 250, True); ns.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_((80, 3), 5, 30, 250, True)
        p.arcto(90, 10, 100, 0, 3); ns.appendBezierPathWithArcFromPoint_toPoint_radius_((90, 10), (100, 0), 3)
        assertElementsClose(p.elements(), elements(ns))
        self.assertEqual(len(p), ns.elementCount())
        (x, y), (w, h) = ns.bounds()
        for got, expected in zip(p.bounds(), (x, y, w, h)):
            self.assertAlmostEqual(got, expected, places=9)

        xf = NSAffineTransform.transform()
        xf.rotateByDegrees_(30)
        xf.translateXBy_yBy_(4, -2)
        assertElementsClose(p.transformed(tuple(xf.transformStruct())).elements(), elements(xf.transformBezierPath_(ns)))
        both = NSBezierPath.bezierPath()
        both.appendBezierPath_(ns)
        both.appendBezierPath_(xf.transformBezierPath_(ns))
        added = PDPath()
        added.add(p)
        added.add(p, tuple(xf.transformStruct()))
        assertElementsClose(added.elements(), elements(both))
        self.assertEqual(PDPath(ns).elements(), elements(ns.copy()))
        assertElementsClose(PDPath(p).elements(), elements(ns.copy()))

    def test_pdpath_rejects_nonfinite_values(self):
        # NaN and infinity raise rather than leaving a path cg has silently shortened
        for bad in (float('nan'), float('inf')):
            p = PDPath()
            p.moveto(0, 0)
            for call in (lambda: p.moveto(bad, 0), lambda: p.lineto(0, bad), lambda: p.curveto(bad, 0, 1, 1, 2, 2),
                         lambda: p.rect(0, 0, bad, 10), lambda: p.oval(bad, 0, 10, 10), lambda: p.arc(0, 0, bad, 0, 90, 0),
                         lambda: p.arcto(bad, 0, 10, 10, 3), lambda: p.transformed((1, 0, 0, bad, 0, 0))):
                with self.assertRaisesRegex(ValueError, 'NaN or infinity'):
                    call()
            self.assertEqual(len(p), len(p.elements()))
        ns = NSBezierPath.bezierPathWithRect_(((0, 0), (float('inf'), 10))) # appkit keeps infinity in a rect
        with self.assertRaisesRegex(ValueError, 'NaN or infinity'):
            PDPath(ns)

    @reference('drawing/paths-flat-union.png')
    def test_paths_flat_union(self):
        # tut/Bezier_Paths (7)
        size(175, 109)
        path1 = arc( 50,50, 40, plot=False)
        path2 = arc(100,50, 40, plot=False)
        compound = path1.union(path2)
        with stroke(0), nofill():
            bezier(compound)

    @reference('drawing/paths-flat-intersect.png')
    def test_paths_flat_intersect(self):
        # tut/Bezier_Paths (8)
        size(175, 109)
        path1 = arc( 50,50, 40, plot=False)
        path2 = arc(100,50, 40, plot=False)
        compound = path1.intersect(path2)
        with stroke(0), nofill():
            bezier(compound)

    @reference('drawing/paths-flat-difference.png')
    def test_paths_flat_difference(self):
        # tut/Bezier_Paths (9)
        size(175, 109)
        path1 = arc( 50,50, 40, plot=False)
        path2 = arc(100,50, 40, plot=False)
        compound = path1.difference(path2)
        with stroke(0), nofill():
            bezier(compound)

    @reference('drawing/paths-flat-xor.png')
    def test_paths_flat_xor(self):
        # tut/Bezier_Paths (10)
        size(175, 109)
        path1 = arc( 50,50, 40, plot=False)
        path2 = arc(100,50, 40, plot=False)
        compound = path1.xor(path2)
        with stroke(0), fill(0.8):
            bezier(compound)

    @reference('drawing/paths-trace.png')
    def test_paths_trace(self):
        # trace() converts a path's stroke footprint into an equivalent,
        # independently-fillable outline -- here a ring twice as wide as the
        # source circle's own outline
        size(175, 109)
        path = arc(87, 55, 40, plot=False)
        outline = path.trace(nib=16, cap=BUTT, join=MITER)
        with stroke(None), fill(0.2):
            bezier(outline)

    @reference('drawing/paths-trace-default-pen.png')
    def test_paths_trace_default_pen(self):
        # omitted nib/cap/join fall back to the canvas's current pen() settings
        size(175, 109)
        pen(12, cap=ROUND, join=ROUND)
        path = arc(87, 55, 40, plot=False)
        outline = path.trace()
        with stroke(None), fill(0.2):
            bezier(outline)

    @reference('drawing/paths-trace-union.png')
    def test_paths_trace_union(self):
        # trace() + union() composes into a stroke-aware clip/mask stencil,
        # without clip()/mask() needing any special-case stroke handling.
        # (a smooth, convex shape is used here -- a sharply-pointed star's
        # narrow arms can trip up gpc's polygon union with tiny sliver
        # artifacts where the fill and stroke-outline edges nearly coincide;
        # that's an unrelated gpc robustness limitation, not something to
        # paper over by tuning the miter limit)
        size(175, 109)
        pen(14)
        path = arc(87, 55, 30, plot=False)
        combined = path.union(path.trace())
        with stroke(None), fill(0.7):
            bezier(combined)
        # outline the original (un-widened) shape on top for visual contrast
        with stroke(0), nofill(), pen(1):
            bezier(path)

    @reference('drawing/paths-trace-union-sharp.png')
    def test_paths_trace_union_sharp(self):
        # a sharply-pointed star's narrow arms make path.trace()'s stroke
        # outline self-overlap at the concave notches between points -- under
        # an even-odd fill rule that self-overlap reads as a hole, carving
        # spurious sliver notches out of path.union(path.trace()). This is
        # the exact case that exposed that bug; it should render as a clean,
        # fully-filled star with no notches.
        size(175, 109)
        pen(10)
        path = star(87, 55, points=5, outer=45, inner=20, plot=False)
        combined = path.union(path.trace())
        with stroke(None), fill(0):
            bezier(combined)

    @reference('drawing/paths-inset.png')
    def test_paths_inset(self):
        # inset() shrinks/grows a path's own boundary -- distinct from
        # trace(), which converts an existing stroke into fill geometry
        size(175, 109)
        path = oval(47, 34, 80, 40, plot=False)
        with stroke(None), fill(0.85):
            bezier(path.inset(-10))
        with stroke(None), fill(0.3):
            bezier(path)
        with stroke(None), fill(0):
            bezier(path.inset(10))

    @reference('drawing/paths-inset-join.png')
    def test_paths_inset_join(self):
        # a sharply-pointed star exercises inset()'s corner styles at acute
        # angles -- the same kind of sharp/concave-corner edge case that
        # exposed the even-odd/gpc bug for trace()+union(), just reaching
        # Clipper2's offsetting code path (ClipperOffset) instead of its
        # boolean-op engine this time. Should render as three cleanly
        # offset stars with visibly different (but artifact-free) corners.
        size(175, 109)
        for x, j in ((30, MITER), (87, ROUND), (144, BEVEL)):
            star_path = star(x, 58, points=5, outer=25, inner=11, plot=False)
            with stroke(None), fill(0.2):
                bezier(star_path.inset(-6, join=j))

    def test_paths_inset_collapse(self):
        # shrinking by more than the shape can support should collapse
        # cleanly to an empty path, not crash or produce garbage geometry
        size(50, 50)
        path = oval(5, 5, 40, 40, plot=False)
        collapsed = path.inset(100)
        self.assertEqual(len(collapsed), 0)
        self.assertEqual(collapsed.area, 0)

    def test_paths_inset_bad_join(self):
        path = oval(0, 0, 40, 40, plot=False)
        with self.assertRaises(DeviceError):
            path.inset(5, join="bogus")

    @reference('drawing/paths-simplify.png')
    def test_paths_simplify(self):
        # a dense, noisy polyline (the kind of thing simplify() is actually
        # for -- traced/scanned artwork, mouse input -- not a smooth curve
        # primitive, which is already maximally compact in its native
        # bezier-curve form) should lose most of its redundant points while
        # keeping its overall silhouette
        size(175, 109)
        dense = Bezier()
        n = 120
        for i in range(n):
            t = i / n * 2 * math.pi
            r = 40 + 2 * math.sin(t * 7)  # slight wobble, not a perfect circle
            x, y = 87 + r * math.cos(t), 55 + r * math.sin(t)
            if i == 0:
                dense.moveto(x, y)
            else:
                dense.lineto(x, y)
        dense.closepath()
        simplified = dense.simplify(5.0)
        self.assertLess(len(simplified), len(dense))
        with stroke(0), nofill(), pen(1):
            bezier(dense)
        with stroke(None), fill(0.3):
            bezier(simplified)

    def test_paths_simplify_degenerate(self):
        # a path that's already minimal shouldn't gain points -- regression
        # check for a bug where bezierPathByFlatteningPath's trailing empty
        # moveto leaked through path_to_polygon as a spurious zero-area
        # contour, which simplify() (unlike the boolean ops) then faithfully
        # preserved and returned as extra output
        size(50, 50)
        tri = Bezier()
        tri.moveto(0, 0)
        tri.lineto(40, 0)
        tri.lineto(20, 40)
        tri.closepath()
        simplified = tri.simplify(1.0)
        self.assertEqual(len(simplified.contours), 1)
        self.assertLessEqual(len(simplified), len(tri) + 1)

    def test_paths_simplify_multicontour(self):
        # simplify() must simplify each contour independently, not merge or
        # drop any of them
        size(50, 50)
        multi = Bezier()
        multi.moveto(0, 0)
        multi.lineto(20, 0)
        multi.lineto(10, 20)
        multi.closepath()
        multi.moveto(30, 0)
        multi.lineto(50, 0)
        multi.lineto(50, 20)
        multi.lineto(30, 20)
        multi.closepath()
        simplified = multi.simplify(1.0)
        self.assertEqual(len(simplified.contours), 2)

    def test_points_terminal_closed(self):
        # points()'s (and point()'s) final sample -- t=1.0 -- on a closed
        # path should deterministically land back at the contour's start,
        # not depend on which way floating-point rounding happens to fall
        # while walking through the segment lengths
        size(50, 50)
        path = Bezier()
        path.moveto(10, 10)
        path.lineto(40, 10)
        path.lineto(40, 40)
        path.lineto(10, 40)
        path.closepath()

        for amount in (2, 3, 10, 50):
            last = list(path.points(amount))[-1]
            self.assertAlmostEqual(last.x, 10)
            self.assertAlmostEqual(last.y, 10)

        last = path.point(1.0)
        self.assertAlmostEqual(last.x, 10)
        self.assertAlmostEqual(last.y, 10)

    def test_points_terminal_closed_regression(self):
        # concrete case that used to fail: a closed single-contour path
        # whose curve segment lengths (computed via curvelength()'s
        # numerical integration) don't sum back to exactly 1.0 after
        # normalization, so walking to t=1.0 via sequential float
        # subtraction landed one segment short of the true end -- returning
        # that segment's *start* point (36.4, 81.6) instead of the path's
        # closing point (88.3, 121.3)
        size(300, 300)
        path = Bezier()
        path.moveto(88.27067439614919, 121.32033860337843)
        path.curveto(104.66667655583079, 108.22238366948213,
                      93.61796989717415, 105.69607801799869,
                      137.93382079208237, 126.3591858790463)
        path.curveto(158.21931501065927, 103.45082857666593,
                      113.07418841217653, 88.42477435427688,
                      107.19225013723411, 88.31466000455157)
        path.lineto(76.34634743828859, 112.17512535544664)
        path.curveto(98.80484754759375, 159.83582764375234,
                      78.81003434914938, 90.47499568294214,
                      36.398958247367666, 81.58688316455398)
        path.closepath()

        last = path.point(1.0)
        self.assertAlmostEqual(last.x, 88.27067439614919)
        self.assertAlmostEqual(last.y, 121.32033860337843)

        last2 = list(path.points(2))[-1]
        self.assertAlmostEqual(last2.x, 88.27067439614919)
        self.assertAlmostEqual(last2.y, 121.32033860337843)

    def test_points_contour_boundary(self):
        # a t landing exactly on the seam between two contours (rather than
        # within either one) used to resolve to the *end of the previous*
        # contour (100, 0); it should resolve to the *start of the next*
        # contour (500, 500) instead
        size(700, 700)
        path = Bezier()
        path.moveto(0, 0)
        path.lineto(100, 0)     # contour 1: length 100, open
        path.moveto(500, 500)
        path.lineto(600, 500)   # contour 2: length 100, open

        mid = path.point(0.5)
        self.assertAlmostEqual(mid.x, 500)
        self.assertAlmostEqual(mid.y, 500)

        pts = list(path.points(3)) # t = 0.0, 0.5, 1.0
        self.assertAlmostEqual(pts[1].x, 500)
        self.assertAlmostEqual(pts[1].y, 500)

    def test_points_subrange(self):
        # start/end restrict the sweep to a sub-range of the path instead of
        # always covering the whole 0.0-1.0 span
        size(100, 100)
        path = Bezier()
        path.moveto(0, 0)
        path.lineto(100, 0)

        pts = list(path.points(5, start=0.25, end=0.75))
        self.assertEqual(len(pts), 5)
        self.assertAlmostEqual(pts[0].x, 25)
        self.assertAlmostEqual(pts[-1].x, 75)
        for pt, x in zip(pts, (25, 37.5, 50, 62.5, 75)):
            self.assertAlmostEqual(pt.x, x)
            self.assertAlmostEqual(pt.y, 0)

        # out-of-range start/end are clamped rather than extrapolated
        clamped = list(path.points(3, start=-1, end=2))
        self.assertAlmostEqual(clamped[0].x, 0)
        self.assertAlmostEqual(clamped[-1].x, 100)

        # a single point in a sub-range lands on its start, not on t=0.0
        single = list(path.points(1, start=0.3, end=0.9))
        self.assertEqual(len(single), 1)
        self.assertAlmostEqual(single[0].x, 30)

    def test_area(self):
        size(50, 50)
        path = rect(0, 0, 40, 25, plot=False)
        self.assertAlmostEqual(path.area, 40 * 25)

    def test_area_hole(self):
        # area() must net out holes correctly for boolean-op-produced shapes
        # (whose contours are already consistently wound by Clipper2 itself)
        # -- an annulus's area should be pi*r_outer^2 - pi*r_inner^2, not the
        # sum of both circles' areas
        size(120, 120)
        outer = oval(0, 0, 100, 100, plot=False)
        inner = oval(25, 25, 50, 50, plot=False)
        annulus = outer.difference(inner)
        expected = math.pi * 50**2 - math.pi * 25**2
        self.assertAlmostEqual(annulus.area, expected, delta=expected * 0.02)

    def test_area_opposite_windings(self):
        # contours wound the other way add where they don't overlap (star winds clockwise, rect counterclockwise)
        size(150, 50)
        with bezier(plot=False) as path:
            rect(0, 0, 30, 30)
            star(100, 15, 5, 15, 6)
        self.assertAlmostEqual(path.area, 900 + star(100, 15, 5, 15, 6, plot=False).area, places=4)

        # and a hand-made hole still subtracts
        path = Bezier()
        path.extend([(0, 0), (30, 0), (30, 30), (0, 30)])
        path.closepath()
        path.moveto(10, 10)
        for pt in [(10, 20), (20, 20), (20, 10)]:
            path.lineto(*pt)
        path.closepath()
        self.assertAlmostEqual(path.area, 800, places=4)

    @reference('drawing/color-gradients1.png')
    def test_color_gradients1(self):
        # tut/Color (11)
        size(99, 275)
        stroke('#aaa')
        
        fill('black', 'white')
        rect(20,20,75,75)
        
        fill('black', 'white', steps=[.3,.6])
        rect(20,110,75,75)
        
        fill('black', 'red', 'white', steps=[0,.3,.6])
        oval(20,200,75,75)

    @reference('drawing/color-gradients2.png')
    def test_color_gradients2(self):
        # tut/Color (12)
        size(97, 277)
        stroke('#aaa')
        
        fill('black', 'white', angle=0)
        rect(20,20,75,75)
        
        fill('black', 'white', angle=45, steps=[.3,.6])
        rect(20,110,75,75)
        
        fill('black', 'red', 'white', angle=180, steps=[0,.3,.6])
        oval(20,200,75,75)

    @reference('drawing/color-gradients3.png')
    def test_color_gradients3(self):
        # tut/Color (13)
        size(200, 200)
        background(None)
        
        fill('black', ('black',0), center=[-1,-1])
        rect(20,20,75,75)
        
        fill('black', ('black',0), center=[1,-1])
        rect(100,20,75,75)
        
        fill('black', ('black',0), center=[-1,1])
        rect(20,100,75,75)
        
        fill('black', ('black',0), center=[1,1])
        rect(100,100,75,75)

    @reference('drawing/color-pattern.png')
    def test_color_pattern(self):
        # tut/Color (14)
        size(150, 90)
        background('tests/_in/macpaint-dark.png')
        with fill('http://plotdevice.io/data/macpaint-tile.png'):
            poly(45,45,25, sides=5)
        with fill(image('tests/_in/macpaint-thatch.png')):
            rect(80,20,50,50)

    def test_stroke_takes_images_and_paths(self):
        # stroke() makes a pattern from an image or a path, as fill() does
        from plotdevice import _ctx
        from Quartz import CGDataProviderCopyData, CGImageGetDataProvider
        def drawn(*args):
            clear(all)
            size(100, 100)
            nofill()
            stroke(*args)
            strokewidth(20)
            rect(20, 20, 60, 60)
            frame = _ctx.canvas.commit()
            pixels = memoryview(CGDataProviderCopyData(CGImageGetDataProvider(frame._render_to_cgimage(1.0, 1.0)))).tobytes()
            return len(frame.grobs), pixels
        path = 'tests/_in/macpaint-thatch.png'
        made = drawn(Pattern(path))
        self.assertEqual(drawn(path), made)
        self.assertEqual(drawn(image(path)), made) # the image isn't also drawn on its own

    def test_patterns_tile_from_where_their_image_would_draw(self):
        # a pattern's tiles follow its image's position & size, at the render's scale
        from plotdevice import _ctx
        from Quartz import CGDataProviderCopyData, CGImageGetDataProvider
        def drawn(paint, box, dpr):
            clear(all)
            size(100, 100)
            background('white')
            if box is None:
                paint.draw()
            else:
                with clip(rect(*box, plot=False)):
                    rect(0, 0, 100, 100, fill=paint)
            frame = _ctx.canvas.commit()
            return memoryview(CGDataProviderCopyData(CGImageGetDataProvider(frame._render_to_cgimage(1.0, dpr)))).tobytes()
        for path in ('tests/_in/plaid.png', 'tests/_in/tiny-triangle.pdf', 'tests/_in/vector-fill.svg'):
            img = image(path, 13, 7, width=40, plot=False)
            box = tuple(img.bounds.origin) + tuple(img.bounds.size)
            for dpr in (1.0, 2.0):
                self.assertEqual(drawn(Pattern(img), box, dpr), drawn(img, None, dpr), (path, dpr))

    def test_patterns_take_images_placement(self):
        # Pattern(src, x, y, width=...) tiles as an image(src, x, y, width=...) fill does
        from plotdevice import _ctx
        from Quartz import CGDataProviderCopyData, CGImageGetDataProvider
        def drawn(paint):
            clear(all)
            size(100, 100)
            fill(paint)
            rect(0, 0, 100, 100)
            frame = _ctx.canvas.commit()
            return memoryview(CGDataProviderCopyData(CGImageGetDataProvider(frame._render_to_cgimage(1.0, 2.0)))).tobytes()
        path = 'tests/_in/plaid.png'
        self.assertEqual(drawn(Pattern(path, 13, 7, width=40)), drawn(image(path, 13, 7, width=40, plot=False)))
        img = image(path, 50, 50, width=30, plot=False)
        self.assertEqual(drawn(Pattern(img, 13, 7)), drawn(image(img, 13, 7, plot=False))) # overriding its own place
        self.assertEqual(drawn(Pattern(Pattern(path), x=5)), drawn(image(path, x=5, plot=False)))
        with self.assertRaises(TypeError):
            Pattern(path, angle=45)

    def test_vector_patterns_stay_vectors_in_pdfs(self):
        # svg, pdf & canvas patterns draw their shapes rather than a bitmap
        import re
        from plotdevice import _ctx
        size(60, 40)
        oval(5, 5, 30, 30, fill='teal')
        text('Hi', 30, 30, size=20)
        tiles = [Pattern(_ctx.canvas), Pattern('tests/_in/vector-fill.svg'), Pattern('tests/_in/tiny-triangle.pdf')]
        for tile in tiles:
            clear(all)
            size(200, 200)
            background(tile)
            rect(20, 20, 160, 160, fill=tile)
            pdf = bytes(_ctx.canvas.commit()._getImageData('pdf'))
            self.assertEqual(len(re.findall(rb'/Subtype\s*/Image', pdf)), 0)
            self.assertEqual(len(re.findall(rb'/PatternType', pdf)), 1) # the background and rect share a tile

    def test_canvas_pattern_shadows_match_in_pdfs(self):
        # a canvas tile's shadows point and scale the same way in a PDF as in a bitmap
        from plotdevice import _ctx
        from Quartz import (CGPDFDocumentCreateWithProvider, CGDataProviderCreateWithCFData, CGPDFDocumentGetPage,
                            CGContextDrawPDFPage, CGBitmapContextCreate, CGBitmapContextCreateImage, CGContextScaleCTM,
                            CGColorSpaceCreateWithName, kCGColorSpaceDisplayP3, kCGImageAlphaPremultipliedFirst,
                            kCGBitmapByteOrder32Host, CGDataProviderCopyData, CGImageGetDataProvider)
        size(100, 80)
        background(None)
        with shadow('black', blur=4, offset=3):
            oval(15, 15, 40, 40, fill='teal')
        snapshot = plot(_ctx.canvas, 0, 0)
        clear(all)
        size(200, 150)
        background('white')
        with clip(rect(10, 10, 150, 120, plot=False)):
            rect(0, 0, 200, 150, fill=Pattern(snapshot, 10, 10, width=150))
        frame = _ctx.canvas.commit()
        bitmap = memoryview(CGDataProviderCopyData(CGImageGetDataProvider(frame._render_to_cgimage(1.0, 2.0)))).tobytes()
        doc = CGPDFDocumentCreateWithProvider(CGDataProviderCreateWithCFData(frame._getImageData('pdf')))
        ctx = CGBitmapContextCreate(None, 400, 300, 8, 1600, CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3),
                                    kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Host)
        CGContextScaleCTM(ctx, 2, 2)
        CGContextDrawPDFPage(ctx, CGPDFDocumentGetPage(doc, 1))
        pdf = memoryview(CGDataProviderCopyData(CGImageGetDataProvider(CGBitmapContextCreateImage(ctx)))).tobytes()
        self.assertLessEqual(max(abs(a - b) for a, b in zip(bitmap, pdf)), 8)

    def test_canvases_tile_vectors_and_their_images_bitmaps(self):
        # fill(canvas) draws its shapes into the tiles, fill(image(canvas)) its 2x snapshot
        import re
        from plotdevice import _ctx
        size(60, 40)
        background(None)
        oval(5, 5, 30, 30, fill='teal')
        canvas = _ctx.canvas
        vectors, bitmap = Pattern(canvas), Pattern(image(canvas, plot=False))
        for paint, rasterized in ((vectors, False), (bitmap, True)):
            clear(all)
            size(200, 200)
            rect(20, 20, 160, 160, fill=paint)
            pdf = bytes(_ctx.canvas.commit()._getImageData('pdf'))
            self.assertEqual(bool(re.findall(rb'/Subtype\s*/Image', pdf)), rasterized)
        with self.assertRaisesRegex(DeviceError, "takes an image as its only argument"):
            fill(canvas, 'red')

    def test_fills_from_one_image_share_a_tile(self):
        # each fill() makes a new Pattern, but they all draw the image's one tile
        import re
        from plotdevice import _ctx
        size(60, 40)
        oval(5, 5, 30, 30, fill='teal')
        snapshot = image(_ctx.canvas, 0, 0, width=30, plot=False)
        clear(all)
        size(200, 200)
        for x in (0, 50, 100):
            fill(snapshot)
            rect(x, 20, 40, 160)
        pdf = bytes(_ctx.canvas.commit()._getImageData('pdf'))
        self.assertEqual(len(re.findall(rb'/PatternType', pdf)), 1)

    @reference('drawing/background.png')
    def test_background(self):
        # ref/Canvas/commands/background()
        size(125, 125)
        background(.2)
        fill(1)
        rect(10,10, 50,50)

    @reference('drawing/clear.png')
    def test_clear(self):
        # ref/Canvas/commands/clear()
        size(125, 125)
        r = rect(0,0, 100,10) # add a rectangle
        t = poly(50,50, 25)   # add a square
        c = arc(125,125, 50)  # add a circle
        clear(r, c) # remove the rectangle & circle

    @reference('drawing/plot-delay.png')
    def test_plot_delay(self):
        # ref/Canvas/commands/plot()
        size(125, 125)
        # create a shape (but don't draw it immediately)
        r = rect(20,20,40,40, plot=False)
        # ...
        # draw the saved shape (but override the canvas's fill color)
        plot(r, fill='red')

    @reference('drawing/plot-disable.png')
    def test_plot_disable(self):
        # ref/Canvas/commands/plot()
        size(125, 125)
        # the plot keyword arg prevents this from being drawn
        o = oval(0,0,100,100, plot=False)
        
        # the plot() command disables drawing for the entire block
        with plot(False):
            o = oval(0,0,100,100)   # not drawn
            s = rect(100,100,10,10) # same here

    def test_plot_live(self):
        # live=True plots the object itself rather than a copy (and isn't a property to validate)
        size(125, 125)
        r = rect(20,20,40,40, plot=False)
        self.assertIs(plot(r, live=True, fill='red'), r)
        self.assertEqual(tuple(r.fill.rgba), tuple(Color('red').rgba))

    def test_with_state_restores(self):
        fill('red'); stroke('blue'); font('Avenir', 12); font('Baskerville', 30)
        with fill('green'):
            with fill('yellow'):
                fill('purple')
            self.assertEqual(fill().hex, '#008000')
        self.assertEqual(fill().hex, '#f00')
        with nostroke():
            self.assertIsNone(stroke())
        self.assertEqual((fill().hex, stroke().hex), ('#f00', '#00f'))
        with font():
            font('Futura', 50)
        self.assertEqual((font().family, font().size), ('Baskerville', 30))

    def test_with_pen_restores(self):
        fill('blue'); stroke('red')
        with pen(2, stroke=None):
            self.assertIsNone(stroke())
        with pen(2, fill=fill('green')):
            self.assertEqual(fill().hex, '#008000')
        self.assertEqual((fill().hex, stroke().hex), ('#00f', '#f00'))
        with self.assertRaises(DeviceError):
            pen(2, foo=1)

    def test_with_state_set_earlier(self):
        # entered after the state has moved on, a fill()/stroke()/font()/layout() applies itself
        # for the block and then restores the state it found
        fill('black'); red = fill('red'); fill('blue')
        for _ in range(2):
            with red:
                self.assertEqual(fill().hex, '#f00')
            self.assertEqual(fill().hex, '#00f')
        stroke('blue'); off = nostroke(); stroke('green')
        with off:
            self.assertIsNone(stroke())
        self.assertEqual(stroke().hex, '#008000')
        font('Avenir', 12); baskerville = font('Baskerville', 20); font(size=30)
        with baskerville:
            self.assertEqual((font().family, font().size), ('Baskerville', 20))
        self.assertEqual((font().family, font().size), ('Baskerville', 30))
        centered = layout(align=CENTER); layout(align=LEFT)
        with centered:
            self.assertEqual(font().align, CENTER)
        self.assertEqual(font().align, LEFT)

    @unittest.skip("fix colors library first")
    @reference('drawing/ximport-colors.png')
    def test_ximport_colors(self):
        # ref/Canvas/compat/ximport()
        size(125, 125)
        colors = ximport("colors")
        background(colors.papayawhip())
        fill(colors.chocolate())
        rect(10, 10, 50, 50)

    @reference('drawing/arcto-simple.png')
    def test_arcto_simple(self):
        # ref/Drawing/commands/arcto()
        size(125, 125)
        for i in range(9):
            with bezier(50,120, stroke=0.2, fill=None):
                arcto(100, 100-i*10)

    @reference('drawing/arcto.png')
    def test_arcto(self):
        # ref/Drawing/commands/arcto()
        size(125, 125)
        with bezier(30, 50, stroke=0.2, fill=None):
            arcto(55,100, 80,50, 10)

    @reference('drawing/beginpath.png')
    def test_beginpath(self):
        # ref/Drawing/commands/bezier()
        size(125, 125)
        # define a path inside of a 'with' block
        with bezier(10, 10, stroke=0.2) as path:
            lineto(40, 10)

    @reference('drawing/bezier.png')
    def test_bezier(self):
        # ref/Drawing/commands/bezier()
        size(125, 125)
        # define a list of x,y points for the path
        points = [(10, 10), (50, 90), (120, 50), (60, 10), (60, 60)]
        
        # draw the path twice; once with straight lines in light grey
        # and again with smoothed lines in dark grey
        nofill()
        bezier(points, stroke=0.75)
        bezier(points, stroke=0.25, smooth=True)
        
        # draw red dots at the point coordinates
        for x, y in points:
            arc(x, y, radius=3, fill='red')

    @reference('drawing/curveto.png')
    def test_curveto(self):
        # ref/Drawing/commands/curveto()
        size(125, 125)
        nofill()
        stroke(0.2)
        with bezier(10,50) as path:
            curveto(10,0, 110,100, 110,50)

    @reference('drawing/lineto.jpg')
    def test_lineto(self):
        # ref/Drawing/commands/lineto()
        size(125, 125)
        nofill()
        with bezier(10, 10, stroke=0.2) as path:
            lineto(40, 40)
            lineto(80, 40, close=True)

    @reference('drawing/moveto.jpg')
    def test_moveto(self):
        # ref/Drawing/commands/moveto()
        size(125, 125)
        with bezier(10, 10, stroke=0.2) as path:
            lineto(50, 100)
            moveto(60, 100)
            lineto(100, 100)

    @reference('drawing/beginpath.png')
    def test_beginpath(self):
        # ref/Drawing/compat/beginpath()
        size(125, 125)
        stroke(0.2)
        beginpath(10, 10)
        lineto(40, 10)
        endpath()

    @reference('drawing/drawpath.jpg')
    def test_drawpath(self):
        # ref/Drawing/compat/drawpath()
        size(125, 125)
        stroke(0.2)
        beginpath(10, 10)
        lineto(40, 10)
        p = endpath(plot=False)
        drawpath(p)

    @reference('drawing/endpath.png')
    def test_endpath(self):
        # ref/Drawing/compat/endpath()
        size(125, 125)
        stroke(0.2)
        beginpath(10, 10)
        lineto(40, 10)
        p = endpath(plot=False)
        drawpath(p)

    @reference('drawing/findpath.png')
    def test_findpath(self):
        # ref/Drawing/compat/findpath()
        size(125, 125)
        points = [(10, 10), (90, 90), (350, 200)]
        for x, y in points:
            oval(x-2, y-2, 4, 4)
        
        nofill()
        stroke(0.2)
        autoclosepath(False)
        path = findpath(points)
        drawpath(path)

    @reference('drawing/fill.png')
    def test_fill(self):
        # ref/Line+Color/commands/fill()
        size(125, 125)
        fill(1.0, 0.0, 0.5)
        rect(10, 10, 25, 25)
        fill(.3, 0.0, 0.4)
        oval(40, 40, 40, 40)

    @reference('drawing/strokewidth.jpg')
    def test_strokewidth(self):
        # ref/Line+Color/commands/pen()
        size(125, 125)
        nofill()
        stroke(0.2)
        pen(1.5)
        rect(10, 10, 20, 40)
        pen(3)
        rect(40, 10, 20, 40)

    @reference('drawing/capstyle.png')
    def test_capstyle(self):
        # ref/Line+Color/commands/pen()
        size(125, 125)
        nofill()
        stroke(0)
        pen(10, cap=BUTT)
        line(20,20, 50,20)
        with pen(cap=ROUND):
            line(20,40, 50,40)
        with pen(cap=SQUARE):
            line(20,60, 50,60)

    @reference('drawing/joinstyle.png')
    def test_joinstyle(self):
        # ref/Line+Color/commands/pen()
        size(125, 125)
        with nofill(), stroke(0), pen(10):
            pen(join=MITER)
            bezier([(20,20), (40,40), (60,20)])
            pen(join=ROUND)
            bezier([(20,50), (40,70), (60,50)])
            pen(join=BEVEL)
            bezier([(20,80), (40,100), (60,80)])

    @reference('drawing/stroke.jpg')
    def test_stroke(self):
        # ref/Line+Color/commands/stroke()
        size(125, 125)
        nofill()
        strokewidth(3)
        stroke(0.3, 0.0, 0.4)
        rect(10, 10, 20, 40)
        stroke(1.0, 0.0, 0.5)
        rect(40, 10, 20, 40)

    @reference('drawing/capstyle.png')
    def test_capstyle(self):
        # ref/Line+Color/compat/capstyle()
        size(125, 125)
        fill(None)
        stroke(0)
        strokewidth(10)
        capstyle(BUTT)
        line(20,20, 50,20)
        capstyle(ROUND)
        line(20,40, 50,40)
        capstyle(SQUARE)
        line(20,60, 50,60)

    @reference('drawing/colormode.jpg')
    def test_colormode(self):
        # ref/Line+Color/compat/colormode()
        size(125, 125)
        colormode(RGB)
        fill(0.25, 0.25, 0.25)
        rect(10, 10, 40, 40)
        
        colormode(HSV)
        fill(0, 0, 0.25)
        rect(60, 10, 40, 40)

    @reference('drawing/joinstyle.png')
    def test_joinstyle(self):
        # ref/Line+Color/compat/joinstyle()
        size(125, 125)
        fill(None)
        stroke(0)
        strokewidth(10)
        
        joinstyle(MITER)
        bezier([(20,20), (40,40), (60,20)])
        
        joinstyle(ROUND)
        bezier([(20,50), (40,70), (60,50)])
        
        joinstyle(BEVEL)
        bezier([(20,80), (40,100), (60,80)])

    @reference('drawing/nofill.jpg')
    def test_nofill(self):
        # ref/Line+Color/compat/nofill()
        size(125, 125)
        strokewidth(1.5)
        stroke(0.2)
        fill(0.2)
        rect(10, 10, 20, 40)
        nofill()
        rect(40, 10, 20, 40)

    @reference('drawing/nostroke.png')
    def test_nostroke(self):
        # ref/Line+Color/compat/nostroke()
        size(125, 125)
        fill(0.2)
        strokewidth(6)
        stroke(1.0, 0.0, 0.5)
        rect(10, 10, 20, 40)
        nostroke()
        rect(40, 10, 20, 40)

    @reference('drawing/strokewidth.jpg')
    def test_strokewidth(self):
        # ref/Line+Color/compat/strokewidth()
        size(125, 125)
        nofill()
        stroke(0.2)
        strokewidth(1.5)
        rect(10, 10, 20, 40)
        strokewidth(3)
        rect(40, 10, 20, 40)


def suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(DrawingTests))
  return suite
