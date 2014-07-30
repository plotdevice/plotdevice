# encoding: utf-8
from AppKit import NSFontManager

from plotdevice.util import random, choice

COMP_WIDTH = 500
COMP_HEIGHT = 500

XCOORD = 1
YCOORD = 2
XSIZE = 3
YSIZE = 4
ROTATION = 5
SCALE = 6
CONTROLPOINT = 7
COLOR = 8
STROKEWIDTH = 9
LOOP = 10
GRIDDELTA = 12
GRIDCOUNT = 13
GRIDWIDTH = 14
GRIDHEIGHT = 15
SKEW = 16
STARPOINTS = 17

class Context:
    def __init__(self):
        self._indent = 0
        self._grid = False

    def indent(self):
        self._indent += 1

    def dedent(self):
        self._indent -= 1

    def spaces(self):
        return "    " * self._indent

    def inGrid(self):
        return self._grid

def nrReally(ctx, numberclass):
    if numberclass == XCOORD:
        if ctx.inGrid():
            #return "x"
            return "x + %s" % nr(ctx,GRIDDELTA)
        else:
            return random(-COMP_WIDTH/2,COMP_WIDTH/2)
    elif numberclass == YCOORD:
        if ctx.inGrid():
            #return "y"
            return "y + %s" % nr(ctx,GRIDDELTA)
        else:
            return random(-COMP_HEIGHT/2,COMP_HEIGHT/2)
    elif numberclass == XSIZE:
        return random(0,COMP_WIDTH)
    elif numberclass == YSIZE:
        return random(0,COMP_HEIGHT)
    elif numberclass == ROTATION:
        return random(0,360)
    elif numberclass == SCALE:
        return random(0.5,1.5)
    elif numberclass == CONTROLPOINT:
        return random(-100,100)
    elif numberclass == COLOR:
        return random()
    elif numberclass == STROKEWIDTH:
        return random(1,20)
    elif numberclass == LOOP:
        return random(2, 20)
    elif numberclass == GRIDDELTA:
        return random(-100,100)
    elif numberclass == GRIDCOUNT:
        return random(2, 10)
    elif numberclass == GRIDWIDTH:
        return 20
        return random(1,100)
    elif numberclass == GRIDHEIGHT:
        return 20
        return random(1, 100)
    elif numberclass == SKEW:
        return random(1,80)
    elif numberclass == STARPOINTS:
        return random(2,100)

def nr(ctx, numberclass):
    if not ctx.inGrid() and random() > 0.5:
        return "random(%s)" % nrReally(ctx, numberclass)
    else:
        return "%s" % nrReally(ctx, numberclass)

### DRAWING COMMANDS ###

def genDraw(ctx):
    fn = choice((genRect,genOval,genArrow,genStar,genPath))
    return fn(ctx)

def genRect(ctx):
    return ctx.spaces() + """rect(%s,%s,%s,%s)\n"""  % (
        nr(ctx,XCOORD),nr(ctx,YCOORD),nr(ctx,XSIZE),nr(ctx,YSIZE))

def genOval(ctx):
    return ctx.spaces() + """oval(%s,%s,%s,%s)\n"""  % (
        nr(ctx,XCOORD),nr(ctx,YCOORD),nr(ctx,XSIZE),nr(ctx,YSIZE))

def genArrow(ctx):
    return ctx.spaces() + """arrow(%s,%s,%s)\n""" % (
        nr(ctx,XCOORD),nr(ctx,YCOORD),nr(ctx,XSIZE))

def genStar(ctx):
    return ctx.spaces() + """star(%s,%s,%s,%s,%s)\n""" % (
        nr(ctx,XCOORD),nr(ctx,YCOORD),nr(ctx,STARPOINTS),nr(ctx,XSIZE),nr(ctx,XSIZE))

def genPath(ctx):
    s = ctx.spaces() + """beginpath(%s,%s)\n""" % (
        nr(ctx,XCOORD),nr(ctx,YCOORD))
    for i in range(random(1,10)):
        s += genPathDraw(ctx)
    s += ctx.spaces() + """endpath()\n"""
    return s

def genPathDraw(ctx):
    fn = choice((genLineto, genCurveto))
    return fn(ctx)

def genLineto(ctx):
    return ctx.spaces() + """lineto(%s,%s)\n""" % (nr(ctx,XCOORD),nr(ctx,YCOORD))

def genCurveto(ctx):
    return ctx.spaces() + """curveto(%s,%s,%s,%s,%s,%s)\n""" % (
        nr(ctx,XCOORD),nr(ctx,YCOORD),nr(ctx,CONTROLPOINT),nr(ctx,CONTROLPOINT),nr(ctx,CONTROLPOINT),nr(ctx,CONTROLPOINT))

### TRANSFORM ###

def genTransform(ctx):
    fn = choice((genRotate, genTranslate, genScale, genSkew, genReset))
    return fn(ctx)

def genRotate(ctx):
    return ctx.spaces() + """rotate(%s)\n""" % nr(ctx,ROTATION)

def genTranslate(ctx):
    return ctx.spaces() + """translate(%s,%s)\n""" % (nr(ctx,XCOORD), nr(ctx,YCOORD))

def genScale(ctx):
    return ctx.spaces() + """scale(%s)\n""" % (nr(ctx,SCALE))

def genSkew(ctx):
    return ctx.spaces() + """skew(%s)\n""" % (nr(ctx,SKEW))

def genReset(ctx):
    return ctx.spaces() + """reset()\n"""

### COLOR ###

def genColor(ctx):
    fn = choice((genFill,genFill,genFill,genFill,genFill,genFill,genStroke,genStroke,genStroke,genNofill,genNostroke,genStrokewidth))
    return fn(ctx)

def genFill(ctx):
    return ctx.spaces() + """fill(%s,%s,%s,%s)\n""" % (nr(ctx,COLOR),nr(ctx,COLOR), nr(ctx,COLOR), nr(ctx,COLOR))

def genStroke(ctx):
    return ctx.spaces() + """stroke(%s,%s,%s,%s)\n""" % (nr(ctx,COLOR), nr(ctx,COLOR), nr(ctx,COLOR), nr(ctx,COLOR))

def genNofill(ctx):
    return ctx.spaces() + """nofill()\n"""

def genNostroke(ctx):
    return ctx.spaces() + """nostroke()\n"""

def genStrokewidth(ctx):
    return ctx.spaces() + """strokewidth(%s)\n""" % nr(ctx,STROKEWIDTH)

### LOOP ###
def genLoop(ctx):
    fn = choice((genFor, genGrid))
    return fn(ctx)

def genFor(ctx):
    if ctx._indent >= 2: return ""
    s = ctx.spaces() + """for i in range(%s):\n""" % nr(ctx,LOOP)
    ctx.indent()
    for i in range(random(5)):
        s += genStatement(ctx)
    s += genVisual(ctx)
    ctx.dedent()
    return s

def genGrid(ctx):
    if ctx.inGrid(): return ""
    s = ctx.spaces() + """for x, y in grid(%s,%s,%s,%s):\n""" % (nr(ctx,GRIDCOUNT), nr(ctx,GRIDCOUNT), nr(ctx,GRIDWIDTH), nr(ctx,GRIDHEIGHT))
    ctx.indent()
    ctx._grid = True
    for i in range(random(5)):
        s += genStatement(ctx)
    s += genVisual(ctx)
    ctx.dedent()
    ctx._grid = False
    return s

### MAIN ###

def genVisual(ctx):
    fn = choice((genDraw,))
    return fn(ctx)

def genStatement(ctx):
    fn = choice((genVisual,genLoop,genColor,genTransform))
    return fn(ctx)

def genProgram():
    s = """# This code is generated with OTTOBOT,
# the automatic PlotDevice code generator.
size(%s, %s)
translate(%s, %s)
colormode(HSB)
""" % (COMP_WIDTH, COMP_HEIGHT, COMP_WIDTH/2, COMP_HEIGHT/2)
    ctx = Context()
    for i in range(random(10,20)):
        s += genStatement(ctx)
    return s

def genTemplate(kind='sketch'):
    if kind=='sketch':
        return u"""size(512, 512)
background(1)

text("Welcome to PlotDevice", 40, 40)
"""
    elif kind=='anim':
        return u"""# to create an animation, call speed() with a
# frame-rate value. This has the side-effect of
# running setup, draw, and stop in the pattern
# described below:
speed(30)

# runs once before the first frame of animation
def setup():
    size(500, 500)
    background(1)
    print "start"

# runs repeatedly until you cancel with ⌘.
def draw():
    text("Frame %i"%FRAME, 20,40)

# runs once after the animation was cancelled
def stop():
    print "done"
"""
    elif kind=='ottobot':
        return genProgram()

if __name__ == '__main__':
    print genProgram()