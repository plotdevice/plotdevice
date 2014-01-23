size(600, 600)
for x, y in grid(30,30,20,20):
    if random() > 0.6:
        # Here, we choose between two functions: oval and rect. 
        # The chosen function is stored in the 'form' variable, which
        # is then called on the next line. Note that both functions 
        # should have the same parameters, and in the same order.
        form = choice((oval, rect))
        form(x, y, 18,18)