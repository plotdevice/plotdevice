size(800, 600)
# Generate compositions using random text.

font('Arial Black')

def rndText():
    """Returns a random string of up to 9 characters."""
    t = u""
    for i in range(random(10)):
        t += chr(random(10,120))
    return t
        

# Define some colors.
colormode(HSB)
white = color(1,1,1,0.8)
black = color(0,0,0,0.8)
red = color(random(),0,0.2,0.8)

translate(0,-200)
for i in range(100):
    # This translation is not reset every time, so it is 
    # appended to previous translations. This gives
    # interesting effects.
    translate(random(-100,100),random(-100,100))
    # Save the current transformation. It's a good idea
    # to do this in the beginning of a loop. End the 
    # loop with a pop.
    push()
    # Rotate in increments of 45 degrees.
    rotate(random(5)*45)
    fontsize(random(800))
    fill(choice((white,black,red)))
    someText = rndText()
    text(someText, 0,0)
    pop()