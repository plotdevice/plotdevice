size(700, 700)
# A foliage generator!
# The foliage are actually green stars with random 
# inner and outer radii and a random number of points.
# They are skewed to make it look more random.

translate(50,50)
# By using HSB colormode, we can change the saturation and brightness
# of the leaves to get more natural color variations.
colormode(HSB)

# Generate a 50 x 50 grid. Each row and column is 12 points wide.
for x, y in grid(50,50,12,12):
    push()
    fill(0.3,random(),random(0.2,0.6),0.8)
    skew(random(-50,50))
    star(x+random(-5,5),y+random(-5,5),random(10),random(1,40),15)
    pop()