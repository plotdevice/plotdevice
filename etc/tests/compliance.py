size(800,2600)

def header():
    font("Helvetica Neue", 18)
    text("PlotDevice Compliance Tests", 20, 60)
    stroke(0.5)
    line(0,60,WIDTH,60)
    fontsize(12)
    nostroke()
    text("This functional suite tests all the available PlotDevice functions, to see if they comply to their contract." , 20, 80, width=300)
    fontsize(10)
    
def primitives(x, y):
    nostroke()
    rect(x, y, 50, 50)
    x += 60
    rect(x, y, 50, 50, 13)
    x += 60
    oval(x, y, 50, 50)
    x += 60
    with layer():
        oval(x, y, 50, 50, range=180)
        arc(x+25, y+25, 25, range=(180,0), fill=.5)
    x += 60
    star(x+25, y+25, 20, outer=25, inner=15)
    x += 60
    arrow(x+50, y+25, 50)
    x += 60
    arrow(x+60, y+25, 50, type=FORTYFIVE).rotate(-45)
    
def basictext(x, y):
    text("Hello", x, y)

    x += 60
    align(LEFT)
    stroke(0)
    nofill()    
    rect(x, y-12,50,20)
    fill(0)
    text("Hello", x, y, width=50)

    x += 60
    align(CENTER)
    stroke(0)
    nofill()    
    rect(x, y-12,50,20)
    fill(0)
    text("Hello", x, y, width=50)

    x += 60
    align(RIGHT)
    stroke(0)
    nofill()    
    rect(x, y-12,50,20)
    fill(0)
    text("Hello", x, y, width=50)    

    align(LEFT)

def textblock(x, y):
    align(LEFT)
    stroke(0)
    nofill()
    rect(x, y-12, 50, 50)
    fill(0)
    text("Lorem ipsum dolor sit amet, consectetuer adipiscing elit.", x, y, width=50, height=50)

    x += 60
    align(CENTER)
    stroke(0)
    nofill()
    rect(x, y-12, 50, 50)
    fill(0)
    text("Lorem ipsum dolor sit amet, consectetuer adipiscing elit.", x, y, width=50, height=50)

    x += 60
    align(RIGHT)
    stroke(0)
    nofill()
    rect(x, y-12, 50, 50)
    fill(0)
    text("Lorem ipsum dolor sit amet, consectetuer adipiscing elit.", x, y, width=50, height=50)

    x += 60
    align(JUSTIFY)
    stroke(0)
    nofill()
    rect(x, y-12, 50, 50)
    fill(0)
    text("Lorem ipsum dolor sit amet, consectetuer adipiscing elit.", x, y, width=50, height=50)

    align(LEFT)
    
def grays(x, y):
    nostroke()
    colormode(RGB)
    align(CENTER)
    for i in range(11):
        fill(i/10.0)
        rect(x, y, 50, 50)
        fill(0)
        text(str(i), x, y+62, 50)
        x += 60

def alphas(x, y):
    nostroke()
    colormode(RGB)
    align(CENTER)
    for i in range(11):
        fill(0, i/10.0)
        rect(x, y, 50, 50)
        fill(0)
        text(str(i), x, y+62, 50)
        x += 60
    
def _clr(x, y, *args):
    fill(args)
    rect(x, y, 50, 50)
    fill(0)
    align(CENTER)
    text(str(args), x, y+62, 50)
    return x + 60

def rgbColors(x, y):
    nostroke()
    colormode(RGB)
    x = _clr(x, y, 0,0,0)
    x = _clr(x, y, 0,0,1)
    x = _clr(x, y, 0,1,0)
    x = _clr(x, y, 0,1,1)
    x = _clr(x, y, 1,0,0)
    x = _clr(x, y, 1,0,1)
    x = _clr(x, y, 1,1,0)
    x = _clr(x, y, 1,1,1)
    
def cmykColors(x, y):
    nostroke()
    colormode(CMYK)
    x = _clr(x, y, 0,0,0,1)
    x = _clr(x, y, 0,0,1,0)
    x = _clr(x, y, 0,1,0,0)
    x = _clr(x, y, 1,0,0,0)
    x = _clr(x, y, 1,1,0,0)
    x = _clr(x, y, 0,1,1,0)
    x = _clr(x, y, 1,0,1,0)
    x = _clr(x, y, 1,1,1,0)
    x = _clr(x, y, 0,0,0,0)

def hsbColors(x, y):
    nostroke()
    colormode(HSB)
    x = _clr(x, y, 0,0,0)
    x = _clr(x, y, 0,0,1)
    x = _clr(x, y, 0,1,0)
    x = _clr(x, y, 0,1,1)
    x = _clr(x, y, 1,0,0)
    x = _clr(x, y, 1,0,1)
    x = _clr(x, y, 1,1,0)
    x = _clr(x, y, 1,1,1)    
    
def marker(y,h=25):
    colormode(CMYK)
    stroke(1, 0.1, 0.1, 0.1)
    line(0, y+h, WIDTH, y+h)

# Draw the header
header()

# Draw the primitives at their first position
nostroke()
text("Basic primitives", 20, 165)
primitives(140,140)
marker(140)

# Simple translation
translate(0, 140)
nostroke()
text("Translated primitives", 20, 165)
primitives(140,140)
marker(140)

# Translation and rotation
translate(0, 140)
nostroke()
text("Rotated primitives", 20, 165)
push()
rotate(45)
primitives(140,140)
pop()
marker(140)

# Scaling
translate(0, 140)
nostroke()
text("Scaled primitives", 20, 165)
push()
scale(0.5)
primitives(140,140)
pop()
marker(140)

# Scaling
translate(0, 140)
nostroke()
text("Shadowed primitives", 20, 165)
push()
scale(0.5)
with shadow('#aaa', 5, 7):
    primitives(140,140)
pop()
marker(140)


# Text
translate(0, 140)
nostroke()
text("Basic text", 20, 165)
basictext(140, 165)     
marker(140)

# Rotated Text
translate(0, 140)
nostroke()
text("Rotated text", 20, 165)
push()
rotate(45)
basictext(140, 165)
pop()
marker(140)

# Text blocks
translate(0, 140)
nostroke()
text("Text blocks", 20, 165)
textblock(140, 165)
marker(140)

# Text blocks
translate(0, 140)
nostroke()
text("Rotated text blocks", 20, 165)
push()
rotate(45)
textblock(140, 165)
pop()
marker(140)


# Outlined text
translate(0, 140)
nostroke()
text("Outlined text", 20, 165)
fsize = fontsize()
fontsize(48)
fill(0.5, 0.5)
text("hamburgevons", 140, 165)
nofill()
stroke(0.2)
text("hamburgevons", 140, 165, outline=True)
fontsize(fsize)
fill(0)
marker(140)

# Grays
translate(0, 140)
nostroke()
text("Grays", 20, 165)
grays(140, 140)
marker(140)

# Grays
translate(0, 140)
nostroke()
text("Alphas", 20, 165)
alphas(140, 140)
marker(140)

# RGB Colors
translate(0, 140)
nostroke()
text("RGB Colors", 20, 165)
rgbColors(140, 140)
marker(140)

# HSB Colors
translate(0, 140)
nostroke()
text("HSB Colors", 20, 165)
hsbColors(140, 140)
marker(140)

# CMYK Colors
translate(0, 140)
nostroke()
text("CMYK Colors", 20, 165)
cmykColors(140, 140)
marker(140)

# Images
translate(0, 140)
nostroke()
text("Images", 20, 165)
_ctx.noImagesHint = False
#image("icon.tif", 140,140,width=50)
push()
translate(60,0)
rotate(90)
#image("icon.tif", 140,140,width=50)
pop()
push()
translate(140,0)
scale(2.0)
#image("icon.tif", 140,140,width=50)
pop()
marker(140)

# classic Paths api
translate(0, 140)
stroke(.75)
text("Paths", 20, 165)
beginpath(165, 140)
lineto(140, 200)
curveto(160, 250, 160, 200, 190, 200)
p = endpath().copy()

stroke(0)
nofill()
sw = strokewidth()
strokewidth(2)
push()
translate(60,0)
for pt in p:
    pt.x += 60
    pt.ctrl1.x += 60
    pt.ctrl2.x += 60
drawpath(p)
pop()

# new Paths api
with transform():
    translate(120,0)
    with bezier(165, 140, strokewidth=4, stroke=.8) as p:
        lineto(140, 200)
        curveto(160, 250, 160, 200, 190, 200)
    
    p = p.copy()
    translate(60,0)
    for pt in p:
        pt.x += 60
        pt.ctrl1.x += 60
        pt.ctrl2.x += 60
    bezier(p, stroke=None, fill='red')
    bezier(p, strokewidth=2, stroke='#a00')
    
strokewidth(sw)
marker(140)
