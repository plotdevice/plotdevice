colormode(RGB)

fill(0)
rect(0,0,100,100)

r = 0.5
g = 0.5
b = 0.0

c = 1 - r
m = 1 - g
y = 1 - b

k = min(c,m,y)

c -= k
m -= k
y -= k

fill(r,g,b)
rect(100.0,0,100,100)

colormode(CMYK)
fill(c,m,y,k)
rect(100.0,100,100,100)




colormode(CMYK)
fill(0,0,0,1)
rect(200.0,0,100,100)
