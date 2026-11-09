from collections import namedtuple
from math import degrees, atan2, sqrt, pow, radians, sin, cos
from .cocoa import NSBezierPath
from ..gfx.geometry import Point
from ..gfx.bezier import Bezier, Curve

# Trig helpers

def inverse_sqrt(x):
    return 1.0 / sqrt(x)

isqrt = inverse_sqrt

def angle(x0, y0, x1, y1):
    a = degrees( atan2(y1-y0, x1-x0) )
    return a

def distance(x0, y0, x1, y1):
    return sqrt(pow(x1-x0, 2) + pow(y1-y0, 2))

def coordinates(x0, y0, distance, angle):
    x1 = x0 + cos(radians(angle)) * distance
    y1 = y0 + sin(radians(angle)) * distance
    return x1, y1

def reflect(x0, y0, x1, y1, d=1.0, a=180):
    d *= distance(x0, y0, x1, y1)
    a += angle(x0, y0, x1, y1)
    x, y = coordinates(x0, y0, d, a)
    return x, y


# Ye olde polymagic

from ._native import intersects, union, intersect, difference, xor
from ._native import pdf_outline as _pdf_outline
def pdf_outline(pdf_data):
    """Traces the vector shapes in `pdf_data` (raw bytes of a PDF file, page 1
    only) into a single NSBezierPath, in the page's own (y-up) coordinates."""
    return _pdf_outline(pdf_data, NSBezierPath.bezierPath())

from ._native import stroke_to_fill as _stroke_to_fill
def stroke_to_fill(path, width, cap, join, miter=10.0):
    """Converts a stroked PDPath into its equivalent fill-only outline
    (in the same local coordinate space as path itself)."""
    return _stroke_to_fill(path, width, cap, join, miter)

from ._native import offset as _offset
def offset(path, delta, join, miter=10.0, flatness=0.6):
    """Grows (delta > 0) or shrinks (delta < 0) a PDPath's boundary."""
    return _offset(path, delta, join, miter, flatness)

from ._native import simplify as _simplify
def simplify(path, epsilon, flatness=0.6):
    """Reduces a PDPath's point count, keeping every remaining point
    within epsilon of the original boundary."""
    return _simplify(path, epsilon, flatness)

from ._native import area as _area
def area(path, flatness=0.6):
    """Returns the total unsigned fill area enclosed by a PDPath."""
    return _area(path, flatness)

try:
    from ._native import linepoint, linelength, curvepoint, curvelength
except ImportError:
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



# Bezier - last updated for PlotDevice 1.8.3
# Author: Tom De Smedt <tomdesmedt@trapdoor.be>
# Manual: http://nodebox.net/code/index.php/Bezier
# Copyright (c) 2007 by Tom De Smedt.
# Refer to the "Use" section on http://nodebox.net/code
# Thanks to Dr. Florimond De Smedt at the Free University of Brussels for the math routines.
from plotdevice import DeviceError
from Quartz import NSMoveToBezierPathElement as MOVETO, NSLineToBezierPathElement as LINETO
from Quartz import NSCurveToBezierPathElement as CURVETO, NSClosePathBezierPathElement as CLOSE

def segment_lengths(path, relative=False, n=20):
    """Returns a list with the lengths of each segment in the path.

    >>> path = Bezier(None)
    >>> segment_lengths(path)
    []
    >>> path.moveto(0, 0)
    >>> segment_lengths(path)
    []
    >>> path.lineto(100, 0)
    >>> segment_lengths(path)
    [100.0]
    >>> path.lineto(100, 300)
    >>> segment_lengths(path)
    [100.0, 300.0]
    >>> segment_lengths(path, relative=True)
    [0.25, 0.75]
    >>> path = Bezier(None)
    >>> path.moveto(1, 2)
    >>> path.curveto(3, 4, 5, 6, 7, 8)
    >>> segment_lengths(path)
    [8.4852813742385695]
    """

    lengths = []
    first = True

    for el in path:
        if first == True:
            close_x, close_y = el.x, el.y
            first = False
        elif el.cmd == MOVETO:
            close_x, close_y = el.x, el.y
            lengths.append(0.0)
        elif el.cmd == CLOSE:
            lengths.append(linelength(x0, y0, close_x, close_y))
        elif el.cmd == LINETO:
            lengths.append(linelength(x0, y0, el.x, el.y))
        elif el.cmd == CURVETO:
            x3, y3, x1, y1, x2, y2 = el.x, el.y, el.ctrl1.x, el.ctrl1.y, el.ctrl2.x, el.ctrl2.y
            lengths.append(curvelength(x0, y0, x1, y1, x2, y2, x3, y3, n))

        if el.cmd != CLOSE:
            x0 = el.x
            y0 = el.y

    if relative:
        length = sum(lengths)
        try:
            return [l / length for l in lengths]
        except ZeroDivisionError: # If the length is zero, just return zero for all segments
            return [0.0] * len(lengths)
    else:
        return lengths

def length(path, segmented=False, n=20):

    """Returns the length of the path.

    Calculates the length of each spline in the path,
    using n as a number of points to measure.

    When segmented is True, returns a list
    containing the individual length of each spline
    as values between 0.0 and 1.0,
    defining the relative length of each spline
    in relation to the total path length.

    The length of an empty path is zero:
    >>> path = Bezier(None)
    >>> length(path)
    0.0

    >>> path.moveto(0, 0)
    >>> path.lineto(100, 0)
    >>> length(path)
    100.0

    >>> path.lineto(100, 100)
    >>> length(path)
    200.0

    # Segmented returns a list of each segment
    >>> length(path, segmented=True)
    [0.5, 0.5]
    """

    if not segmented:
        return sum(segment_lengths(path, n=n), 0.0)
    else:
        return segment_lengths(path, relative=True, n=n)

def _curve_at(seg_t, x0, y0, p1, closeto):
    """Builds the Curve at `seg_t` (0..1) along the segment running from
    (x0, y0) to p1, p1 being the segment's own endpoint element as returned
    by iterating a Bezier. A CLOSE segment interpolates toward `closeto`
    (the contour's start point) rather than p1's own placeholder (0,0)."""

    if p1.cmd == CLOSE:
        x, y = linepoint(seg_t, x0, y0, closeto.x, closeto.y)
        return Curve(LINETO, ((x, y),))
    elif p1.cmd == LINETO:
        x, y = linepoint(seg_t, x0, y0, p1.x, p1.y)
        return Curve(LINETO, ((x, y),))
    elif p1.cmd == CURVETO:
        x3, y3, x1, y1, x2, y2 = p1.x, p1.y, p1.ctrl1.x, p1.ctrl1.y, p1.ctrl2.x, p1.ctrl2.y
        x, y, c1x, c1y, c2x, c2y = curvepoint(seg_t, x0, y0, x1, y1, x2, y2, x3, y3)
        return Curve(CURVETO, ((c1x, c1y), (c2x, c2y), (x, y)))
    else:
        raise DeviceError("Unknown cmd for p1 %s" % p1)

def _locate(path, t, lengths=None, segments=None):

    """Finds which segment of the path a path-wide t (0.0 to 1.0) falls
    within, and how far along just that one segment it is.

    Returns (index, t_segment, closeto).

    A path is a sequence of lines and curves (segments). The returned `index` 
    indicates which segment in the patch contains the target point `t` 
    (a fraction of the path's total length, 0–1). The returned  `t_segment` 
    is also a 0–1 value but identifies where the target point lies on this 
    particular segment (i.e., at path[index]).

    `closeto` is the current contour's starting coordinate. It's needed because 
    a CLOSE segment's own stored coordinates are just a placeholder; the
    point it actually closes back to is `closeto`.

    Zero length segment (e.g., MOVETO) are skipped over or rounded down to 
    the previous 'real' segment if at t=1.0.

    To speed up repeated calls for the same path, you can pass in:
        lengths = path.segmentlengths(relative=True)
        segments = list(path)
    
    >>> path = Bezier(None)
    >>> _locate(path, 0.0)
    Traceback (most recent call last):
        ...
    DeviceError: The given path is empty
    >>> path.moveto(0,0)
    >>> _locate(path, 0.0)
    Traceback (most recent call last):
        ...
    DeviceError: The given path is empty
    >>> path.lineto(100, 100)
    >>> _locate(path, 0.0)
    (0, 0.0, Point(x=0.0, y=0.0))
    >>> _locate(path, 1.0)
    (0, 1.0, Point(x=0.0, y=0.0))
    """

    if segments is None:
        segments = list(path)
        
    if lengths is None:
        lengths = path.segmentlengths(relative=True)

    if len(lengths) == 0:
        raise DeviceError("The path is empty")

    for i, el in enumerate(segments):
        if i == 0 or el.cmd == MOVETO:
            closeto = Point(el.x, el.y)

        if lengths[i] == 0:
            # A zero-length segment marks either a MOVETO jump between contours
            # or the meaningless MOVETO NSBezierPath appends after closePath()
            if i < len(lengths)-1:
                continue # mid-path, just move on to the next segment
            else:
                # at the end, with nothing left to skip to -- resolve to the
                # end of the path instead: t=1.0 on the preceding, real
                # segment. A single step back isn't always enough -- e.g. a
                # CLOSE (or LINETO) that's already at its destination is
                # *also* zero-length, and can cascade with the trailing
                # MOVETO -- so walk backward until segments[i+1] (the
                # segment's own endpoint) isn't itself a MOVETO (the only
                # element type _curve_at() can't resolve; a zero-length
                # CLOSE/LINETO/CURVETO is harmless, since its start and end
                # coincide). Bounded at i>=0: segments[0] is always a MOVETO
                # (every path starts with one), so checking segments[i+1]
                # at i==-1 could only ever come back true, which would just
                # drive the next step to i==-2 -- and segments[-1] in
                # Python silently wraps around to the *end* of the list
                # instead of erroring. Since that always-true check can't
                # tell us anything we don't already know, treat needing it
                # as having run out of real content instead of making it.
                while i >= 0 and segments[i+1].cmd == MOVETO:
                    i -= 1
                if i < 0:
                    raise DeviceError("The path has no non-empty contours")
                t_segment = 1.0
                break

        # Strict `<` (not `<=`) so an exact tie -- t landing precisely at a
        # segment's far edge -- falls through to the next segment rather
        # than stopping here; that's what lets a tie that lands on a
        # following zero-length marker actually reach the skip-forward
        # handling above instead of resolving to this segment's t=1.0.
        if t < lengths[i] or i == len(lengths)-1:
            t_segment = t / lengths[i]
            break
        else:
            t -= lengths[i]

    return (i, t_segment, closeto)

def point(path, t, lengths=None, segments=None):

    """Returns coordinates for point at t on the path.

    Gets the length of the path, based on the length
    of each curve and line in the path.
    Determines in what segment t falls.
    Gets the point on that segment.

    When you supply the list of segment lengths yourself,
    as returned from length(path, segmented=True),
    point() works about thirty times faster in a for-loop,
    since it doesn't need to recalculate the length
    during each iteration.

    `segments` is passed straight through to _locate() -- see its
    docstring -- and, when given, is also used here in place of `path` to
    look up the segment's own endpoints.

    >>> path = Bezier(None)
    >>> point(path, 0.0)
    Traceback (most recent call last):
        ...
    DeviceError: The given path is empty
    >>> path.moveto(0, 0)
    >>> point(path, 0.0)
    Traceback (most recent call last):
        ...
    DeviceError: The given path is empty
    >>> path.lineto(100, 0)
    >>> point(path, 0.0)
    Curve(LINETO, ((0.0, 0.0),))
    >>> point(path, 0.1)
    Curve(LINETO, ((10.0, 0.0),))
    """

    if len(path) == 0:
        raise DeviceError("The given path is empty")

    i, t, closeto = _locate(path, t, lengths=lengths, segments=segments)

    src = path if segments is None else segments
    x0, y0 = src[i].x, src[i].y
    p1 = src[i+1]

    return _curve_at(t, x0, y0, p1, closeto)

def points(path, amount=100, start=0, end=1):
    """Returns an iterator with a list of calculated points for the path.
    This method calls the point method <amount> times, increasing t,
    distributing point spacing linearly.

    `start`/`end` restrict the sweep to a sub-range of the path (fractions
    of its total length, the same units as point()'s `t`) instead of
    always covering it from 0.0 to 1.0. Each is clamped to the valid
    0.0-1.0 range.

    >>> path = Bezier(None)
    >>> list(points(path))
    Traceback (most recent call last):
        ...
    DeviceError: The given path is empty
    >>> path.moveto(0, 0)
    >>> list(points(path))
    Traceback (most recent call last):
        ...
    DeviceError: The given path is empty
    >>> path.lineto(100, 0)
    >>> list(points(path, amount=4))
    [Curve(LINETO, ((0.0, 0.0),)), Curve(LINETO, ((33.333, 0.0),)), Curve(LINETO, ((66.667, 0.0),)), Curve(LINETO, ((100.0, 0.0),))]
    """

    if len(path) == 0:
        raise DeviceError("The given path is empty")

    start = max(start, 0.0)
    end = min(end, 1.0)

    # The delta value is divided by amount - 1, because we also want the last point (t=end)
    # If I wouldn't use amount - 1, I fall one point short of the end.
    # E.g. if amount = 4, I want point at t start, start+.33*span, start+.66*span
    # and end, if amount = 2, I want point at t start and t end
    try:
        delta = (end-start)/(amount-1)
    except ZeroDivisionError:
        delta = 1.0

    # point()/_locate() each re-walk `path` from its first element by
    # default, and every element access crosses the PyObjC bridge
    # (elementAtIndex:associatedPoints:) -- fine for a single lookup, but
    # this generator calls point() `amount` times, which made the naive
    # `[point(path, delta*i) for i in range(amount)]` cost O(amount x
    # len(path)) bridge crossings. Materialize the path's segments once and
    # hand them to point() so every one of those calls indexes a plain list
    # instead, and the segment lengths so they aren't recomputed each time.
    segments = list(path)
    lengths = path.segmentlengths(relative=True)

    for step in range(amount):
        yield point(path, start + delta*step, lengths=lengths, segments=segments)

def contours(path):
    """Returns a list of contours in the path.

    A contour is a sequence of lines and curves
    separated from the next contour by a MOVETO.

    For example, the glyph "o" has two contours:
    the inner circle and the outer circle.

    >>> path = Bezier(None)
    >>> path.moveto(0, 0)
    >>> path.lineto(100, 100)
    >>> len(contours(path))
    1

    A new contour is defined as something that starts with a moveto:
    >>> path.moveto(50, 50)
    >>> path.curveto(150, 150, 50, 250, 80, 95)
    >>> len(contours(path))
    2

    Empty moveto's don't do anything:
    >>> path.moveto(50, 50)
    >>> path.moveto(50, 50)
    >>> len(contours(path))
    2

    It doesn't matter if the path is closed or open:
    >>> path.closepath()
    >>> len(contours(path))
    2
    """

    contours = []
    current_contour = None
    empty = True
    for i, el in enumerate(path):
        if el.cmd == MOVETO:
            if not empty:
                contours.append(current_contour)
            current_contour = Bezier()
            current_contour.moveto(el.x, el.y)
            empty = True
        elif el.cmd == LINETO:
            empty = False
            current_contour.lineto(el.x, el.y)
        elif el.cmd == CURVETO:
            empty = False
            current_contour.curveto(el.ctrl1.x, el.ctrl1.y,
                el.ctrl2.x, el.ctrl2.y, el.x, el.y)
        elif el.cmd == CLOSE:
            current_contour.closepath()
    if not empty:
        contours.append(current_contour)
    return contours

def findpath(points, curvature=1.0):

    """Constructs a path between the given list of points.

    Interpolates the list of points and determines
    a smooth bezier path betweem them.

    The curvature parameter offers some control on
    how separate segments are stitched together:
    from straight angles to smooth curves.
    Curvature is only useful if the path has more than three points.
    """

    # The list of points consists of Point objects,
    # but it shouldn't crash on something straightforward
    # such as someone supplying a list of (x,y)-tuples.
    points = list(points)  # copy to avoid modifying the input
    for i, pt in enumerate(points):
        if isinstance(pt, (tuple, list)):
            points[i] = Point(pt[0], pt[1])

    if len(points) == 0: return None
    if len(points) == 1:
        path = Bezier(None)
        pt = points[0]
        path.moveto(pt.x, pt.y)
        return path
    if len(points) == 2:
        path = Bezier(None)
        pt1, pt2 = points[:2]
        path.moveto(pt1.x, pt1.y)
        path.lineto(pt2.x, pt2.y)
        return path

    # Zero curvature means straight lines.

    curvature = max(0, min(1, curvature))
    if curvature == 0:
        path = Bezier(None)
        path.moveto(points[0].x, points[0].y)
        for i in range(len(points)):
            path.lineto(points[i].x, points[i].y)
        return path

    curvature = 4 + (1.0-curvature)*40
    dx = {0: 0, len(points)-1: 0}
    dy = {0: 0, len(points)-1: 0}
    bi = {1: -0.25}
    ax = {1: (points[2].x-points[0].x-dx[0]) / 4.0}
    ay = {1: (points[2].y-points[0].y-dy[0]) / 4.0}

    for i in range(2, len(points)-1):
        bi[i] = -1.0 / (curvature + bi[i-1])
        ax[i] = -(points[i+1].x-points[i-1].x-ax[i-1]) * bi[i]
        ay[i] = -(points[i+1].y-points[i-1].y-ay[i-1]) * bi[i]

    for i in reversed(range(1, len(points)-1)):
        dx[i] = ax[i] + dx[i+1] * bi[i]
        dy[i] = ay[i] + dy[i+1] * bi[i]

    path = Bezier(None)
    path.moveto(points[0].x, points[0].y)
    for i in range(len(points)-1):
        path.curveto(points[i].x + dx[i],
                     points[i].y + dy[i],
                     points[i+1].x - dx[i+1],
                     points[i+1].y - dy[i+1],
                     points[i+1].x,
                     points[i+1].y)

    return path

def insert_point(path, t):

    """Returns a path copy with an extra point at t.
    >>> path = Bezier(None)
    >>> path.moveto(0, 0)
    >>> insert_point(path, 0.1)
    Traceback (most recent call last):
        ...
    DeviceError: The given path is empty
    >>> path.moveto(0, 0)
    >>> insert_point(path, 0.2)
    Traceback (most recent call last):
        ...
    DeviceError: The given path is empty
    >>> path.lineto(100, 50)
    >>> len(path)
    2
    >>> path = insert_point(path, 0.5)
    >>> len(path)
    3
    >>> path[1]
    Curve(LINETO, ((50.0, 25.0),))
    >>> path = Bezier(None)
    >>> path.moveto(0, 100)
    >>> path.curveto(0, 50, 100, 50, 100, 100)
    >>> path = insert_point(path, 0.5)
    >>> path[1]
    Curve(LINETO, ((25.0, 62.5), (0.0, 75.0), (50.0, 62.5))
    """

    i, t, closeto = _locate(path, t)

    x0 = path[i].x
    y0 = path[i].y
    p1 = path[i+1]
    p1cmd, x3, y3, x1, y1, x2, y2 = p1.cmd, p1.x, p1.y, p1.ctrl1.x, p1.ctrl1.y, p1.ctrl2.x, p1.ctrl2.y

    if p1cmd == CLOSE:
        pt_cmd = LINETO
        pt_x, pt_y = linepoint(t, x0, y0, closeto.x, closeto.y)
    elif p1cmd == LINETO:
        pt_cmd = LINETO
        pt_x, pt_y = linepoint(t, x0, y0, x3, y3)
    elif p1cmd == CURVETO:
        pt_cmd = CURVETO
        pt_x, pt_y, pt_c1x, pt_c1y, pt_c2x, pt_c2y, pt_h1x, pt_h1y, pt_h2x, pt_h2y = \
            curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3, True)
    else:
        raise DeviceError("Locate should not return a MOVETO")

    new_path = Bezier(None)
    new_path.moveto(path[0].x, path[0].y)
    for j in range(1, len(path)):
        if j == i+1:
            if pt_cmd == CURVETO:
                new_path.curveto(pt_h1x, pt_h1y,
                             pt_c1x, pt_c1y,
                             pt_x, pt_y)
                new_path.curveto(pt_c2x, pt_c2y,
                             pt_h2x, pt_h2y,
                             path[j].x, path[j].y)
            elif pt_cmd == LINETO:
                new_path.lineto(pt_x, pt_y)
                if path[j].cmd != CLOSE:
                    new_path.lineto(path[j].x, path[j].y)
                else:
                    new_path.closepath()
            else:
                raise DeviceError("Didn't expect pt_cmd %s here" % pt_cmd)

        else:
            if path[j].cmd == MOVETO:
                new_path.moveto(path[j].x, path[j].y)
            if path[j].cmd == LINETO:
                new_path.lineto(path[j].x, path[j].y)
            if path[j].cmd == CURVETO:
                new_path.curveto(path[j].ctrl1.x, path[j].ctrl1.y,
                             path[j].ctrl2.x, path[j].ctrl2.y,
                             path[j].x, path[j].y)
            if path[j].cmd == CLOSE:
                new_path.closepath()
    return new_path
