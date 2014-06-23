size(400, 400)
speed(100)
# Generates sculptures using a set of mathematical functions.
# Every iteration adds a certain value to the current coordinates.
# Rewriting this program to use transforms is left as an exercise 
# for the reader.

# This program uses some mathematical functions that are not 
# standard functions of NodeBox.
# Instead, they are in Python's math library. The next
# line imports those functions.
from math import sin, cos, tan, log10
from random import seed

def setup():
    global a,b
    a = 10.0
    b = 0.0
    pass
    
def draw():
    global a,b
    seed(0)
    
    background(0,0,0.15)
    cX = a
    cY = b

    x = 180
    y = -27
    fontsize(54)
    c = 0.0
    for i in range(48):
        x += cos(cY)*5
        y += log10(cX)*8.36 + sin(cX) * 2

        fill(sin(a+c), 0.3, 0.0, 0.5)

        s = 22 + cos(cX)*17
        oval(x-s/2, y-s/2, s, s)
        # Try the next line instead of the previous one to see how
        # you can use other primitives.
        #star(x-s/2,y-s/2, random(5,10), inner=2+s*0.1,outer=10+s*0.1)

        cX += random(0.25)
        cY += random(0.25)
        c += 0.1
    a += 0.1
    b += 0.05