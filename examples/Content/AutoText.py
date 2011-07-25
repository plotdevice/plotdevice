# Automatically generates text based on the Kant Generator Pro.
# The Kant Generator Pro is an example script of the
# "Dive Into Python" manual.

size(400, 1000)

# Generate automatic text from an XML file and store it as a string
# in the txt variable. Also try the "thanks.xml", which generates
# "thank you" notes, and "insults.xml", which generates all sorts
# of crazy insults.
txt = autotext("kant.xml") 

font("Times", 12)
lineheight(1.7)

text(txt, 25, 30, width=320, height=950)