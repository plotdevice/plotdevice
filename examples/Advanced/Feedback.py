# NodeBox allows you to query the current state of the canvas, and even
# the contents of it as an image. This allows for some nice feed-back effects.
size(500, 500)

# Currently, we use a background, so all content gets replaced.
# Enabling the next line to get a transparent background.
# background(None)

# Draw some ovals on screen, just to get something to display.
for i in range(1000):
    oval(random(WIDTH), random(HEIGHT), 20, 20, fill=(random(), random(), 0, random()))

# Now do the feedback ten times.
for i in range(10):
    # Scale each copy down a bit, and rotate it. This gives the familiar feedback effect.
    # Play with these parameters to get other effects.
    scale(0.98)
    rotate(1)
    # This is the trick. We don't use an image from file, but we load image data from the canvas.
    # The canvas is a variable set in the local namespace: it has a private _nsImage property 
    # that renders its current contents as an NSImage, which the image command accepts.
    # Try blurring the image: add alpha=0.8
    image(None, random(-50,49), random(-50,49), image=canvas._nsImage)
