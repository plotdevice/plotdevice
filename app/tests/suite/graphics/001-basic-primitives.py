size(300, 300)

_total_w = 0
def flow(w, h):
    global _total_w
    if _total_w + w*2 >= WIDTH:
        translate(-_total_w, h)
        _total_w = 0 
    else:
        translate(w, 0)
        _total_w += w

x, y = 10, 10
rect(x, y, 50, 50)
flow(60, 60)
rect(x, y, 50, 50, 0.6)
flow(60, 60)
oval(x, y, 50, 50)
flow(60, 60)
star(x+25, y+25, 20, outer=25, inner=15)
flow(60, 60)
arrow(x+50, y+25, 50)
flow(60, 60)
arrow(x+50, y, 50, type=FORTYFIVE)
flow(60, 60)
oval(x, y, 50, 50)
