size(100,100)

def bar(x, y, w, depth, filled=1.0):
    
    d1 = depth*filled
    
    colormode(HSB)
    f = fill()
    s = stroke()
    if f != None and f.brightness != 1:
        s = color(f.hue, f.saturation+0.2, f.brightness-0.4)
    nostroke()
 
    #front
    if f != None: fill(f)
    rect(x, y, w, w)
    
    #bottom
    beginpath(x, y+w)
    lineto(x-d1, y+w+d1)
    lineto(x-d1+w, y+w+d1)
    lineto(x+w, y+w)
    endpath()
    
    #left
    beginpath(x, y)
    lineto(x-d1, y+d1)
    lineto(x-d1, y+w+d1)
    lineto(x, y+w)
    endpath()
    
    #top
    if f != None: fill(f.hue, f.saturation-0, f.brightness-0.15)
    beginpath(x, y)
    lineto(x+w, y)
    lineto(x+w-d1, y+d1)
    lineto(x-d1, y+d1)
    endpath()
    
    #right
    if f != None: fill(f.hue, f.saturation-0, f.brightness-0.15)
    beginpath(x+w, y)
    lineto(x+w-d1, y+d1)
    lineto(x+w-d1, y+w+d1)
    lineto(x+w, y+w)
    endpath()
    
    if s != None: stroke(s)
 
    line(x, y, x+w, y)
    line(x, y, x-d1, y+d1)
    line(x+w, y, x+w, y+w)
    line(x+w, y+w, x+w-d1, y+w+d1)
    line(x, y+w, x-d1, y+w+d1)
    line(x+w, y, x+w-d1, y+d1)
    
    #front
    if f != None: fill(f)
    rect(x-d1, y+d1, w, w)
    
    x += d1
    y += d1
    d2 = depth*(1-filled)
    
    if d2 != 0:
    
        line(x, y, x+d2, y+d2)
        line(x+w, y, x+w+d2, y+d2)
        line(x+w, y+w, x+w+d2, y+w+d2)
        line(x, y+w, x+d2, y+w+d2)
    
        f = fill()
        nofill()
        rect(x+d2, y+d2, w, w)
    
        if f != None: fill(f)
    
def cube(x, y, w, filled=1.0):
    bar(x, y, w, w*0.5, filled)

from random import seed
seed(55)
w = 20
n = 3
strokewidth(0.5)

colormode(RGB)
c = color(0.05,0.65,0.85)
c.brightness += 0.2

for x in range(n):

    for y in range(n):
    
        bottom = w * n
    
        for z in range(n):
            stroke(0.1)
            strokewidth(1)
            
            colormode(RGB)
            dr = (1-c.r)/(n-1) * (x*0.85+y*0.15+z*0.05) * 1.1
            dg = (1-c.g)/(n-1) * (x*0.85+y*0.15+z*0.05) * 1.2
            db = (1-c.b)/(n-1) * (x*0.85+y*0.15+z*0.05) * 1.1
            fill(1.2-dr, 1.1-dg, 1.2-db)
            
            if random() > 0.5: 
                nostroke()
                nofill()
            
            dx = w*x - w/2*z
            dy = bottom-w*y + w/2*z
            
            transform(CORNER)
            translate(33,-17)
            scale(1.01)
            cube(dx, dy, w)
            reset()