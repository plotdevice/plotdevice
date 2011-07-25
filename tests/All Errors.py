# All errors available in NodeBox

# Wrong arrow type
arrow(0,0,100,type=3.141)

# Too many pops
pop()

# Remove current font (normally impossible because _ctx is private)
del _ctx.fontname
text("hello", 10, 10)
textmetrics("hello")

# Non-existant font
font("NON-EXISTANT FONT")
text("hello", 10,10)
textmetrics("hello")

