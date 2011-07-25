size(1000, 1000)
# Play around with elementary math functions.
# Here, we are creating some sort of tunnel effect by
# using sinus and cosinus functions.

# Sinus and cosinus are not standard functions of NodeBox.
# Instead, they are in Python's math library. The next
# line imports those functions.
from math import sin, cos

startX = startY = 100
startval = random()
stroke(0.2)
c = random()
for i in range(300):
    delta = (random()-0.5) * 0.1
    x = 400 + sin(c+delta) * (i+random(-10,10))
    y = 400 + cos(c+delta) * (i+random(-10,10))
    s = random(c*2)
    
    fill(random()-0.4, 0.2, 0.2, random())
    
    # The next line two lines look straightforward,
    # but actually show off a really powerful Python feature. 
    # We choose here between two functions, the oval
    # and rect function. After we put the desired function 
    # in the primitive variable, we execute that function with
    # the given parameters. Note that the parameters of
    # the two functions should match for this to work.
    primitive = choice((oval,rect))
    primitive(x-s/2, y-s/2, s, s)
    
    c += random()*0.25