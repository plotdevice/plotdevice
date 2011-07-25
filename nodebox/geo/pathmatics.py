from math import sqrt, pow

def linepoint(t, x0, y0, x1, y1):

    """Returns coordinates for point at t on the line.

    Calculates the coordinates of x and y for a point
    at t on a straight line.

    The t parameter is a number between 0.0 and 1.0,
    x0 and y0 define the starting point of the line,
    x1 and y1 the ending point of the line,    

    """

    out_x = x0 + t * (x1-x0)
    out_y = y0 + t * (y1-y0)
    return (out_x, out_y)

def linelength(x0, y0, x1, y1):

    """Returns the length of the line."""

    a = pow(abs(x0 - x1), 2)
    b = pow(abs(y0 - y1), 2)
    return sqrt(a+b)

def curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3, handles=False):

    """Returns coordinates for point at t on the spline.

    Calculates the coordinates of x and y for a point
    at t on the cubic bezier spline, and its control points,
    based on the de Casteljau interpolation algorithm.

    The t parameter is a number between 0.0 and 1.0,
    x0 and y0 define the starting point of the spline,
    x1 and y1 its control point,
    x3 and y3 the ending point of the spline,
    x2 and y2 its control point.
    
    If the handles parameter is set,
    returns not only the point at t,
    but the modified control points of p0 and p3
    should this point split the path as well.
    """
    
    mint = 1 - t

    x01   = x0 * mint + x1 * t
    y01   = y0 * mint + y1 * t
    x12   = x1 * mint + x2 * t
    y12   = y1 * mint + y2 * t
    x23   = x2 * mint + x3 * t
    y23   = y2 * mint + y3 * t
   
    out_c1x = x01 * mint + x12 * t
    out_c1y = y01 * mint + y12 * t
    out_c2x = x12 * mint + x23 * t
    out_c2y = y12 * mint + y23 * t
    out_x = out_c1x * mint + out_c2x * t
    out_y = out_c1y * mint + out_c2y * t
    
    if not handles:
        return (out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y)
    else:
        return (out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y, x01, y01, x23, y23)

def curvelength(x0, y0, x1, y1, x2, y2, x3, y3, n=20):

    """Returns the length of the spline.

    Integrates the estimated length of the cubic bezier spline
    defined by x0, y0, ... x3, y3, by adding the lengths of
    lineair lines between points at t.

    The number of points is defined by n 
    (n=10 would add the lengths of lines between 0.0 and 0.1, 
    between 0.1 and 0.2, and so on).

    The default n=20 is fine for most cases, usually
    resulting in a deviation of less than 0.01.
    """

    length = 0
    xi = x0
    yi = y0

    for i in range(n):
        t = 1.0 * (i+1) / n
        pt_x, pt_y, pt_c1x, pt_c1y, pt_c2x, pt_c2y = \
            curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3)
        c = sqrt(pow(abs(xi-pt_x),2) + pow(abs(yi-pt_y),2))
        length += c
        xi = pt_x
        yi = pt_y
        
    return length
