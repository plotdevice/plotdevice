# This is a really simple example that draws some stroked circles.
# Note that we generate a random radius beforehand, so both width
# and height have the same value. We also use a simple formulas 
# to center the circles on screen.

size(500, 500)

# Set the background color to a specific hue of red
background(0.16, 0, 0)

# Set filling off, so ovals will be stroked only
nofill()

for i in range(50):

    # Set the stroke color to a random tint of orange
    stroke(random(), random(0.31), 0)

    # Set the stroke width
    strokewidth(random(0.2, 4.0))

    # Define the radius of the oval. This needs to be done
    # beforehand:
    # If we were to do "oval(20, 20, random(50), random(50))", 
    # width and height would each get a different random value.
    radius = random(50)

    # Draw the oval onscreen. The width/height are both set to the
    # radius * 2 to get the diameter. The radius is subtracted from the
    # x and y coordinates to place the oval in the middle.
    oval(random(WIDTH)-radius, random(HEIGHT)-radius, radius*2, radius*2)