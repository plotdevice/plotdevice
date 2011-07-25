# This example shows one of the possibilities of the canvas: 
# the ability to access all existing objects on it.
size(550, 300)

fill(1, 0.8)
strokewidth(1.5)

# First, generate some rectangles all over the canvas, rotated randomly.
for i in range(3000):
    grob = rect(random(WIDTH)-25, random(HEIGHT)-25,50, 50)
    grob.rotate(random(360))
    
# Now comes the smart part: 
# We want to sort the objects on the canvas using a custom sorting
# method; in this case, their vertical position.
# The bounds property returns the following: ( (x, y), (width, height) )
# The lambda function thus compares the y positions against eachother.
sorted_grobs = list(canvas)
sorted_grobs.sort(lambda v1, v2: cmp(v1.bounds[0][1], v2.bounds[0][1]))

# Now that we have all the graphic objects ("grobs") sorted,
# traverse them in order and change their properties.

# t is a counter going from 0.0 to 1.0
t = 0.0
# d is the delta amount added each step
d = 1.0 / len(sorted_grobs)

for grob in sorted_grobs:
    # Grobs will get bigger
    grob.scale(t)
    # Grobs's stroke will get darker
    grob.stroke = (0.6 - t, 0.50)
    t += d

# This is really a hack, but you can replace the internal
# grob list of the canvas with your own to change the Z-ordering.
# Comment out this line to get a different effect.
canvas._grobs = sorted_grobs