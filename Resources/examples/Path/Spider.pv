# This example uses the points method to connect letters together.
# It actually draws lines between points of each letter contour
# that are a certain distance from eachother.

size(600, 207)
background(0.3,0,0.2)

# This utility method calculates the length between points.
# It's just a standard Pythagoras algorithm.
def calc_length(x1, y1, x2, y2):
    from math import sqrt, pow
    return sqrt(pow(x2-x1, 2) + pow(y2-y1, 2))


# First, create a textpath that we will use further on.
fontsize(150)
path = textpath("SPIDER",20, 150)

# Select a color for the lines.
nofill()
stroke(1)
strokewidth(0.3)

# The mutation adds a little extra randomness to each calculated point.
# Increase it to make the lines deviate more from the template path.
mutation = 2.0

# The maximum distance between two points. Increase this to get a more
# "spidery" effect.
maxdist = 40.0

# Amount of lines for each contour.
lines_per_contour = 300

# A path has a contours property that returns each seperate contours.
# Note that "holes" in a letter (such as a P or D) are contours as well.
for contour in path.contours:
    # Get a list of 100 points on each contour, properly divided amongst
    # the path. This is different from the elements of the path, because
    # the points are evenly distributed along the path.
    path_points = list(contour.points(100))
    
    # We want a certain amount of lines.
    for i in range(lines_per_contour):
        # Choose a point on the path
        pt1 = choice(path_points)
        # To find the second point, we use a "brute-force" approach.
        # We randomly select a point on the path, and see if its distance
        # from the first point is smaller than the maximum allowed distance.
        # If it is, the point is selected; otherwise, we try another point.
        # Note that this might loop infinitely for very short (or negative) distances.
        # Use Command-Period to break out of the loop.
        
        # Initialize the current length to "infinity", which means it won't get selected.
        length = float("inf")        
        while length > maxdist:
            pt2  = choice(path_points) 
            length = calc_length(pt1.x, pt1.y, pt2.x, pt2.y)
            
        # Once we've found a second point, draw it. Use the mutation parameter to add a bit
        # of randomness to the position of the line.
        line(pt1.x + random(-mutation, mutation), pt1.y + random(-mutation, mutation), \
             pt2.x + random(-mutation, mutation), pt2.y + random(-mutation, mutation))
        