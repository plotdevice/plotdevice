size(300, 300)
x, y = 10, 30
fontsize(12)

text("Hello", x, y)
drawpath(textpath("Hello", x + 100, y))
rect(x, y-12,50,20, fill=None, stroke=0)
rect(x + 100, y-12,50,20, fill=None, stroke=0)

y += 30
align(LEFT)
text("Hello", x, y, width=50)
drawpath(textpath("Hello", x + 100, y, width=50))
rect(x, y-12,50,20, fill=None, stroke=0)
rect(x + 100, y-12,50,20, fill=None, stroke=0)

y += 30
align(CENTER)
text("Hello", x, y, width=50)
drawpath(textpath("Hello", x + 100, y, width=50))
rect(x, y-12,50,20, fill=None, stroke=0)
rect(x + 100, y-12,50,20, fill=None, stroke=0)

y += 30
align(RIGHT)
text("Hello", x, y, width=50)    
drawpath(textpath("Hello", x + 100, y, width=50))
rect(x, y-12,50,20, fill=None, stroke=0)
rect(x + 100, y-12,50,20, fill=None, stroke=0)

