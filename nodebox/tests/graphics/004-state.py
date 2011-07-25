# State semantics

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
    
# 1: The current state specifies the color of an object.
fill(1, 0, 0)
draw_rect()
flow()

# 2: The current state can be overridden by direct access.
draw_rect(fill=(0, 0, 1))
flow()

# 3: You can also change things "after the facts"
r = draw_rect()
r.fill = 0, 0, 1
flow()

# 4: Re-inheriting from the context
r = draw_rect() # Would be red
fill(0, 1, 0) # The current fill is now green
r.inheritFromContext() # Copy the fill
flow()

# 5: By default, objects don't inherit from the context
pt = BezierPath()
pt.rect(200, 0, 42, 42) # Note that I set the position directly
pt.draw()
flow()

# 6: You have to let them inherit
pt = BezierPath()
pt.rect(0, 0, 42, 42)
pt.inheritFromContext()
pt.draw()
flow()

# 7: Drawpath does a inheritFromContext
pt = BezierPath()
pt.rect(0, 0, 42, 42)
pt.fill = 0, 0, 1 # This gets overridden by inheritFromContext
drawpath(pt)
flow()

# 8: Drawpath can also override attributes
pt = BezierPath()
pt.rect(0, 0, 42, 42)
drawpath(pt, fill=(0, 0, 1))
flow()

