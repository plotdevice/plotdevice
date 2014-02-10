size(600, 600)
# Fun with stars! 

# Use the HSB color model to generate matching random colors.
colormode(HSB)

# This loop has no push and pop, meaning that every transformation
# is appended to the previous ones. 
for y in range(100):
    fill(random(0.8,1),random(),random(0.2,0.6),random())
    rotate(random(-3,3))
    translate(random(-100,100), random(-100,100))
    star(300,300,random(1,100), random(1,5), random(1,500))
