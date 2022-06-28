# encoding: utf-8
import unittest
from . import PlotDeviceTestCase, reference
from plotdevice import *

class DrawingTests(PlotDeviceTestCase):
    @reference('drawing/paths-transform-pre.png')
    def test_paths_transform_pre(self):
        # tut/Bezier_Paths (1)
        size(180, 180)
        font("Dolly", "bold", 300)
        path = textpath("e", 10, 150)
        bezier(path, stroke='black', fill=None)

    @reference('drawing/paths-transform-post.png')
    def test_paths_transform_post(self):
        # tut/Bezier_Paths (2)
        size(180, 180)
        font("Dolly", "bold", 300)
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
        font("Dolly", "bold", 100)
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
        font("Dolly", "bold", 50)
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
  suite.addTest(unittest.makeSuite(DrawingTests))
  return suite
