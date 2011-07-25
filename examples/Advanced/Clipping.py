size(300,300)
# Examples of clipping in NodeBox.
# NodeBox can clip to any path using the beginclip() and endclip() commands.
# The beginclip can take any path, be it one of the drawing primitives or text 
# (using the textpath command demonstrated below)

# ---- PART 1: Clipping Primitives ---- #

# Transformation commands can have an effect on the clipped path, the things within
# the clipped path, or both. If you only want to rotate the clipped path 
# (and not subsequent draws), make sure you surround the command that generates the path 
# (in this case, the arrow) with push() and pop().
push()
# Rotate the arrow to let it point down.
rotate(-90)
# The last parameter instructs the command not to draw the output, but return it as a path.
p = arrow(250, 100, 200, draw=False)
pop()

# The path is an object that has several useful methods. We use the bounds method to 
# get the bounding box of the arrow, used for defining where we should draw the ovals.
(x,y), (w,h) = p.bounds

# Begin the clipping operation.
# All drawing methods inside of the beginclip() and endclip() are clipped according
# to the given path.
beginclip(p)
# Draw 200 ovals of a random size.
for i in range(200):
    fill(random(), 0.7, 0, random())
    s = random(50)
    oval(x+random(w), y+random(h), s, s)
endclip()

# ---- PART 2: Clipping Text ---- #
# There is no fundamental difference in clipping text or primitives: 
# all you have to do is to use the textpath command to return the path. 
# Note that you CANNOT use text("<string>", x, y, draw=False).

# Set the font. Note that all state operations work as expected for the textpath
# command, such as font, align, and giving a width.
font('Lucida Grande Bold', 72)
align(CENTER)
# Return a path that can be used for clipping. Textpaths never draw on screen.
p = textpath("Clippy!", 0, 270, width=300)

# The path is an object that has several useful methods. We use the bounds method to 
# get the bounding box of the arrow, used for defining where we should draw the ovals.
(x,y), (w,h) = p.bounds
# Begin the clipping operation.
# All drawing methods inside of the beginclip() and endclip() are clipped according
# to the given path.
beginclip(p)
# Draw 200 rectangles of a random size.
for i in range(105):
    fill(random(), random(), 0, random())
    s = random(50)
    rotate(random(5, -5))
    rect(x+random(w), y+random(h), s, s)
endclip()
