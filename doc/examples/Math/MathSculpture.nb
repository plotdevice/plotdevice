size(400, 800)
# Generates sculptures using a set of mathematical functions.
# Every iteration adds a certain value to the current coordinates.
# Rewriting this program to use transforms is left as an exercise 
# for the reader.

# This program uses some mathematical functions that are not 
# standard functions of NodeBox.
# Instead, they are in Python's math library. The next
# line imports those functions.
from math import sin, cos, tan, log10

background(0)

cX = random(1,10)
cY = random(1,10)

x = 200
y = 54
fontsize(10)
for i in range(278):
    x += cos(cY)*10
    y += log10(cX)*1.85 + sin(cX) * 5

    fill(random()-0.4, 0.8, 0.8, random())

    s = 10 + cos(cX)*15
    oval(x-s/2, y-s/2, s, s)
    # Try the next line instead of the previous one to see how
    # you can use other primitives.
    #star(x-s/2,y-s/2, random(5,10), inner=2+s*0.1,outer=10+s*0.1)

    cX += random(0.25)
    cY += random(0.25)