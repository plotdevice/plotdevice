size(300, 300)

def draw_rect(*args, **kwargs):
    r = rect(0, 0, 12, 42) # Draw default square
    r = rect(20, 0, 42, 42, *args, **kwargs)
    return r
    
_counter = 1
def move():
    global _counter
    text(_counter, 80, 25, fontsize=12, fill=0)
    _counter += 1
    translate(0, 50)    

# 1: Give the color using a tuple
draw_rect(fill=(1, 0, 0))
move()

# 2: Give the color using a Color object
draw_rect(fill=Color(1, 0, 0))
move()

# 3: Use HSB Colors
colormode(HSB)
draw_rect(fill=Color(0, 1, 1))
move()

# 4: Use CMYK Colors
colormode(CMYK)
draw_rect(fill=Color(0, 0, 0, 1))
move()

# 5: Color range
colormode(RGB)
colorrange(255)
draw_rect(fill=(128, 0, 0)) # One red component
move()

