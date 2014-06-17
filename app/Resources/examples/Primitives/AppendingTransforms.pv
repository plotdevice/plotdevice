size(600, 600)
# Appending transformations for very large and very small compositions.

translate(WIDTH/2, HEIGHT/2)
scale(5)
# Because we don't use push and pop, all transformations are appended
# to eachother. This means that, depending on the random value, a
# composition might grow to be very big or very small.
for i in range(100):
    rotate(random(-10, 10))
    # Use the next line instead of the previous ones to see 
    # what russian constructivism looks like.
    # rotate(random(1,4)*45) 
    scale(random(0.5,1.5))
    fill(random()-0.4, 0.2, 0.2, random())
    translate(random(-5,5),random(-5,5))
    # After all transformations are done, draw the shape.
    rect(-10, -10, 10,10)
    # The following line is commented out. Remove the
    # comment sign to see how this looks with stars.
    # star(0,0,points=random(5,50),inner=1,outer=14)

