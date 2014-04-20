size(625, 625)
# Create a color Grid.
# This example also shows of the HSB color mode that allows
# you to select colors more naturally, by specifying a hue,
# saturation and brightness.

colormode(HSB)

# Set some initial values. You can and should play around with these.
h = 0
s = 0.5
b = 0.9
a = .5

# Size is the size of one grid square.
size = 50

# Using the translate command, we can give the grid some margin.
translate(50,50)

# Create a grid with 10 rows and 10 columns. The width of the columns
# and the height of the rows is defined in the 'size' variable.
for x, y in grid(10, 10, size, size):                 
    # Increase the hue while choosing a random saturation.
    # Try experimenting here, like decreasing the brightness while
    # changing the alpha value etc.
    h+=.01
    s=random()
    
    # Set this to be the current fill color.
    fill(h, s, b, a)

    # Draw a rectangle that is one and a half times larger than the
    # grid size to get an overlap.
    rect(x, y, size*1.5, size*1.5)
