# Create organic balls using text.

size(600, 600)

font('Zapfino')
fontsize(72)

# Draw a black background. Setting the background to None
# gives an empty background.
background(0)

# Move to the center of the composition. Note that, because
# we use Zapfino, the ball will end up off-center.
translate(WIDTH/2,HEIGHT/2)
for i in range(100):
    # The trick is skewing, rotating and scaling without
    # moving so all elements share the same centerpoint.
    push()
    # Select a value between (0,0,0) (black) and (1,0,0) (red).
    fill(random(),0,0)
    rotate(random(0,800))
    scale(random()*2)
    skew(random(200))
    text('(',0,0)
    pop()