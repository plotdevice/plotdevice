size(400, 400)
var("textsize", NUMBER, 50.0, 0.0, 100.0)
# Demonstrate how to randomly select a font from a list.
# In addition, it also demonstrates how to use variables
# to set the textsize.

names = ['Helvetica', 'Arial', 'Times', 'Impact', 'Verdana']

fill(1,0,0)

# Select a font randomly from the list of names.
font(choice(names))

# textsize is a variable defined under Python > Variables.
fontsize(textsize)

# Display the text. Because the coordinates start from
# the baseline, you have to add the size of the font to
# the y coordinate so it doesn't fall of of the page.
text('Hi there!', 12, textsize)