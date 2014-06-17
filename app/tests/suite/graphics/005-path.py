# Path semantics

size(300, 300)

_total_w = 0
_counter = 1
def flow(w=50, h=70):
    global _total_w
    global _counter
    text(_counter, 17, 60, fontsize=12, fill=0)
    _counter += 1
    if _total_w + w*2 >= WIDTH:
        translate(-_total_w, h)
        _total_w = 0 
    else:
        translate(w, 0)
        _total_w += w

def draw_rect(*args, **kwargs):
    r = rect(0, 0, 42, 42, *args, **kwargs)
    return r
    
# 1: A basic bezier path filled with a color
pt = BezierPath(fill=(1,0,0))
pt.rect(0, 0, 42, 42)
pt.draw()
flow()

# 2: Using the transform bezier path method should copy color
trans = Transform()
trans.translate(50, 0)
pt2 = trans.transformBezierPath(pt)
pt2.draw()
flow()
