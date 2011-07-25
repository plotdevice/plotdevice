# Swiss Cheese Factory
# This program makes swiss cheese by cutting out circles from another
# circle. It demonstrates the use of boolean operations on paths.

size(300, 300)
background(0.0, 0.0, 0.15)

# We define a custom circle function that draws from the middle.
# This is easier to work with in this case than the regular oval
# function.
def circle(x, y, sz, draw=True):
    return oval(x-sz, y-sz, sz*2, sz*2, draw)

# Now create the "cheese" -- the central circle in the middle.
# Don't draw it yet, since we will be creating a new path were
# pieces are cut out off.
cheese = circle(WIDTH/2, HEIGHT/2, 130, draw=False)
# Instead of the circle, you can use any arbitrary path.
# Try out the following lines to use a letter.
#font("Helvetica-Bold", 400)
#cheese = textpath("S", 7, 291)

# Do ten punches out of the cheese
for i in range(10):
    # Make a circle somewhere on the canvas, with a random size.
    x = random(WIDTH)
    y = random(HEIGHT)
    sz = random(10, 60)
    c = circle(x, y, sz, draw=False)
    # Now comes the central part: create a new path out of the cheese
    # that is the difference between the cheese and the newly created
    # circle. Save this in cheese (so the old cheese gets overwritten.
    cheese  = cheese.difference(c, 0.1)
    # Another cool effect is to mirror the cutouts. Here, we create a
    # mirrored copy of the circle, then cut it out of the cheese
    # as well. (You might want to change the number of punchouts.)
    #mx = WIDTH - x
    #c = circle(mx, y, sz, draw=False)
    #cheese  = cheese.difference(c, 0.1)

# Now that the cheese is ready, draw it.

# Here's a little caveat: you can only draw an object once.
# Here, we create a copy of the cheese to use as a shadow object.
shadow_cheese = BezierPath(cheese)
fill(0.1)
drawpath(shadow_cheese)

# Once the shadow is drawn, translate the original cheese and
# draw it as well.
translate(-3, -3)
fill(0.3, 0.9, 0.1,  0.8)
drawpath(cheese)
