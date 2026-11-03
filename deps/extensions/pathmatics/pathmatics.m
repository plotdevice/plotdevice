#import "pathmatics.h"
#include <math.h>
#include <stdio.h>
#import "../clipper2/bridge.h"

void _linepoint(double t, double x0, double y0, double x1, double y1,
                double *out_x, double *out_y
                )
{
    *out_x = x0 + t * (x1-x0);
    *out_y = y0 + t * (y1-y0);
}


void _linelength(double x0, double y0, double x1, double y1,
                double *out_length
                )
{
    double a, b;
    a = pow(fabs(x0 - x1), 2);
    b = pow(fabs(y0 - y1), 2);
    *out_length = sqrt(a + b);
}

void _curvepoint(double t, double x0, double y0, double x1, double y1,
                 double x2, double y2, double x3, double y3,
                 double *out_x, double *out_y,
                 double *out_c1x, double *out_c1y, double *out_c2x, double *out_c2y
                 )
{
    double mint, x01, y01, x12, y12, x23, y23;

    mint  = 1 - t;
    x01 = x0 * mint + x1 * t;
    y01 = y0 * mint + y1 * t;
    x12 = x1 * mint + x2 * t;
    y12 = y1 * mint + y2 * t;
    x23 = x2 * mint + x3 * t;
    y23 = y2 * mint + y3 * t;

    *out_c1x = x01 * mint + x12 * t;
    *out_c1y = y01 * mint + y12 * t;
    *out_c2x = x12 * mint + x23 * t;
    *out_c2y = y12 * mint + y23 * t;
    *out_x = *out_c1x * mint + *out_c2x * t;
    *out_y = *out_c1y * mint + *out_c2y * t;
}

void _curvepoint_handles(double t, double x0, double y0, double x1, double y1,
                 double x2, double y2, double x3, double y3,
                 double *out_x, double *out_y,
                 double *out_c1x, double *out_c1y, double *out_c2x, double *out_c2y,
                 double *out_h1x, double *out_h1y, double *out_h2x, double *out_h2y
                 )
{
    double mint, x01, y01, x12, y12, x23, y23;

    mint  = 1 - t;
    x01 = x0 * mint + x1 * t;
    y01 = y0 * mint + y1 * t;
    x12 = x1 * mint + x2 * t;
    y12 = y1 * mint + y2 * t;
    x23 = x2 * mint + x3 * t;
    y23 = y2 * mint + y3 * t;

    *out_c1x = x01 * mint + x12 * t;
    *out_c1y = y01 * mint + y12 * t;
    *out_c2x = x12 * mint + x23 * t;
    *out_c2y = y12 * mint + y23 * t;
    *out_x = *out_c1x * mint + *out_c2x * t;
    *out_y = *out_c1y * mint + *out_c2y * t;
    *out_h1x = x01;
    *out_h1y = y01;
    *out_h2x = x23;
    *out_h2y = y23;
}

void _curvelength(double x0, double y0, double x1, double y1,
                  double x2, double y2, double x3, double y3, int n,
                  double *out_length
                  )
{
    double xi, yi, t, c;
    double pt_x, pt_y, pt_c1x, pt_c1y, pt_c2x, pt_c2y;
    int i;
    double length = 0;

    xi = x0;
    yi = y0;

    for (i=0; i<n; i++) {
        t = 1.0 * (i+1.0) / (float) n;

        _curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3,
                    &pt_x, &pt_y, &pt_c1x, &pt_c1y, &pt_c2x, &pt_c2y);
        c = sqrt(pow(fabs(xi-pt_x), 2.0) + pow(fabs(yi-pt_y), 2.0));
        length += c;
        xi = pt_x;
        yi = pt_y;
    }
    *out_length = length;
}

PyObject *
cPathmatics_linepoint(PyObject *self, PyObject *args)
{
    double t, x0, y0, x1, y1;
    double out_x, out_y;

    if (!PyArg_ParseTuple(args, "ddddd", &t, &x0, &y0, &x1, &y1))
        return NULL;

    _linepoint(t, x0, y0, x1, y1,
               &out_x, &out_y);

    return Py_BuildValue("dd", out_x, out_y);
}

PyObject *
cPathmatics_linelength(PyObject *self, PyObject *args)
{
    double x0, y0, x1, y1;
    double out_length;

    if (!PyArg_ParseTuple(args, "dddd", &x0, &y0, &x1, &y1))
        return NULL;

    _linelength(x0, y0, x1, y1,
                &out_length);

    return Py_BuildValue("d", out_length);
}


PyObject *
cPathmatics_curvepoint(PyObject *self, PyObject *args)
{
    double t, x0, y0, x1, y1, x2, y2, x3, y3, handles = 0;
    double out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y, out_h1x, out_h1y, out_h2x, out_h2y;

    if (!PyArg_ParseTuple(args, "ddddddddd|i", &t, &x0, &y0, &x1, &y1, &x2, &y2, &x3, &y3, &handles))
        return NULL;

    if (!handles) {
        _curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3,
            &out_x, &out_y, &out_c1x, &out_c1y, &out_c2x, &out_c2y);

        return Py_BuildValue("dddddd", out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y);

    } else {
        _curvepoint_handles(t, x0, y0, x1, y1, x2, y2, x3, y3,
            &out_x, &out_y, &out_c1x, &out_c1y, &out_c2x, &out_c2y,
            &out_h1x, &out_h1y, &out_h2x, &out_h2y);

        return Py_BuildValue("dddddddddd", out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y,
            out_h1x, out_h1y, out_h2x, out_h2y);
    }
}

PyObject *
cPathmatics_curvelength(PyObject *self, PyObject *args)
{
    double x0, y0, x1, y1, x2, y2, x3, y3;
    int n = 20;
    double out_length;

    if (!PyArg_ParseTuple(args, "dddddddd|i", &x0, &y0, &x1, &y1, &x2, &y2, &x3, &y3, &n))
        return NULL;

    _curvelength(x0, y0, x1, y1, x2, y2, x3, y3, n,
                 &out_length);

    return Py_BuildValue("d", out_length);
}

PyObject *PathmaticsError;


// polymagic

static void
flat_applier(void *info, const CGPathElement *el)
{
    PDContours *contours = (PDContours *)info;
    switch (el->type) {
        case kCGPathElementMoveToPoint: pd_contours_moveto(contours, el->points[0].x, el->points[0].y); break;
        case kCGPathElementAddLineToPoint: pd_contours_lineto(contours, el->points[0].x, el->points[0].y); break;
        case kCGPathElementCloseSubpath: pd_contours_close(contours); break;
        default: break; // a flattened path has no curves
    }
}

static PDContours *
flatten(CGPathRef path, float flatness)
{
    // the path's contours, with its curves flattened into lines
    PDContours *contours = pd_contours_new();
    if (@available(macOS 13.0, *)) {
        // cg's flattening, which matches ns's point for point
        CGPathRef flattened = CGPathCreateCopyByFlattening(path, flatness);
        if (flattened) {
            CGPathApply(flattened, contours, flat_applier);
            CGPathRelease(flattened);
        }
    } else {
        NSBezierPath *ns = [Pathmatician bezierPath:path];
        [NSBezierPath setDefaultFlatness: flatness];
        [ns setFlatness: flatness];
        NSBezierPath *flattened = [ns bezierPathByFlatteningPath];
        NSPoint ap[3];
        for (NSInteger i = 0; i < [flattened elementCount]; i++) {
            NSBezierPathElement el = [flattened elementAtIndex:i associatedPoints:ap];
            if (el == NSBezierPathElementMoveTo) pd_contours_moveto(contours, ap[0].x, ap[0].y);
            else if (el == NSBezierPathElementLineTo) pd_contours_lineto(contours, ap[0].x, ap[0].y);
            else if (el == NSBezierPathElementClosePath) pd_contours_close(contours);
        }
    }
    pd_contours_end(contours);
    return contours;
}

static CGMutablePathRef
path_operation(CGPathRef p1, CGPathRef p2, PDBooleanOp op, float flatness)
{
    PDContours *contours1 = flatten(p1, flatness);
    PDContours *contours2 = flatten(p2, flatness);

    // this line does all the really hard work:
    CGMutablePathRef resultPath = pd_contours_boolean(op, contours1, contours2);

    pd_contours_free(contours1);
    pd_contours_free(contours2);

    return resultPath;
}

static bool
intersects_path(CGPathRef p1, CGPathRef p2)
{
    // bounds intersecting make it a possibility - find the intersection and see if it's empty.
    if ( !CGRectIntersectsRect( CGPathGetPathBoundingBox(p1), CGPathGetPathBoundingBox(p2) ))
        return false;
    PDContours *contours1 = flatten(p1, 0.1);
    PDContours *contours2 = flatten(p2, 0.1);
    bool hit = pd_contours_intersect(contours1, contours2);
    pd_contours_free(contours1);
    pd_contours_free(contours2);
    return hit;
}

typedef struct {
    PyObject_HEAD
    id        objc_object;
    int       flags;
} PyObjCObject;

PyObject *
build_objc_instance(PyTypeObject *ob_type, id obj) {
    // Because we don't want to include PyObjC on compilation,
    // we hack around the object creation by making our own
    // PyObjCObject_New.
    PyObject *result;
    result = ob_type->tp_alloc(ob_type, 0);
    ((PyObjCObject*)result)->objc_object = obj;
    ((PyObjCObject*)result)->flags = 0;
    return result;
}

static bool
parse_paths(PyObject *pyObject1, PyObject *pyObject2, CGPathRef *path1, CGPathRef *path2)
{
    *path1 = PDPath_CGPath(pyObject1);
    if (!*path1) {
        PyErr_SetString(PyExc_TypeError, "first argument is not a PDPath");
        return false;
    }
    if (path2) {
        *path2 = PDPath_CGPath(pyObject2);
        if (!*path2) {
            PyErr_SetString(PyExc_TypeError, "second argument is not a PDPath");
            return false;
        }
    }
    return true;
}

static float
clamp_flatness(float flatness)
{
    return flatness < 0.1 ? 0.1 : flatness > 5.0 ? 5.0 : flatness;
}

static PyObject *
path_result(CGMutablePathRef path)
{
    PyObject *result = PDPath_FromCGPath(path);
    CGPathRelease(path);
    return result;
}

// Check if two PDPaths intersect.
PyObject *
cPathmatics_intersects(PyObject *self, PyObject *args)
{
    PyObject *pyObject1, *pyObject2;
    CGPathRef path1, path2;
    if (!PyArg_ParseTuple(args, "OO", &pyObject1, &pyObject2) || !parse_paths(pyObject1, pyObject2, &path1, &path2))
        return NULL;

    bool hit;
    CGPathRetain(path1);
    CGPathRetain(path2);
    Py_BEGIN_ALLOW_THREADS
    hit = intersects_path(path1, path2);
    Py_END_ALLOW_THREADS
    CGPathRelease(path1);
    CGPathRelease(path2);

    return PyBool_FromLong(hit);
}

static PyObject*
cPathmatics_operation(PyObject *self, PyObject *args, int op)
{
    PyObject *pyObject1, *pyObject2;
    CGPathRef path1, path2;
    CGMutablePathRef pathResult;
    float flatness = 0.6;

    if (!PyArg_ParseTuple(args, "OO|f", &pyObject1, &pyObject2, &flatness) || !parse_paths(pyObject1, pyObject2, &path1, &path2))
        return NULL;
    flatness = clamp_flatness(flatness);

    CGPathRetain(path1);
    CGPathRetain(path2);
    Py_BEGIN_ALLOW_THREADS
    pathResult = path_operation(path1, path2, op, flatness);
    Py_END_ALLOW_THREADS
    CGPathRelease(path1);
    CGPathRelease(path2);

    if (!pathResult) {
        PyErr_SetString(PyExc_ValueError, "the paths couldn't be combined");
        return NULL;
    }
    return path_result(pathResult);
}

// Returns the union of two PDPaths as a new PDPath.
PyObject *
cPathmatics_union(PyObject *self, PyObject *args)
{
    return cPathmatics_operation(self, args, PD_UNION);
}

// Returns the intersection of two PDPaths as a new PDPath.
PyObject *
cPathmatics_intersect(PyObject *self, PyObject *args)
{
    return cPathmatics_operation(self, args, PD_INTERSECT);
}

// Returns the difference of two PDPaths as a new PDPath.
PyObject *
cPathmatics_difference(PyObject *self, PyObject *args)
{
    return cPathmatics_operation(self, args, PD_DIFFERENCE);
}

// Returns the exclusive or of two PDPaths as a new PDPath.
PyObject *
cPathmatics_xor(PyObject *self, PyObject *args)
{
    return cPathmatics_operation(self, args, PD_XOR);
}

// Returns a new PDPath with its boundary grown/shrunk by delta
PyObject *
cPathmatics_offset(PyObject *self, PyObject *args)
{
    PyObject *pyObject;
    CGPathRef path;
    double delta, miter = 2.0;
    int join;
    float flatness = 0.6;

    if (!PyArg_ParseTuple(args, "Odi|df", &pyObject, &delta, &join, &miter, &flatness) || !parse_paths(pyObject, NULL, &path, NULL))
        return NULL;
    if (join < kCGLineJoinMiter || join > kCGLineJoinBevel) {
        PyErr_SetString(PyExc_ValueError, "unknown offset join");
        return NULL;
    }
    flatness = clamp_flatness(flatness);

    CGMutablePathRef resultPath;
    CGPathRetain(path);
    Py_BEGIN_ALLOW_THREADS
    PDContours *contours = flatten(path, flatness);
    resultPath = pd_contours_offset(contours, delta, (CGLineJoin)join, miter);
    pd_contours_free(contours);
    Py_END_ALLOW_THREADS
    CGPathRelease(path);

    return path_result(resultPath);
}

// Returns a new PDPath with redundant points removed (via Clipper2), keeping
// every remaining point within epsilon of the original.
PyObject *
cPathmatics_simplify(PyObject *self, PyObject *args)
{
    PyObject *pyObject;
    CGPathRef path;
    double epsilon;
    float flatness = 0.6;

    if (!PyArg_ParseTuple(args, "Od|f", &pyObject, &epsilon, &flatness) || !parse_paths(pyObject, NULL, &path, NULL))
        return NULL;
    flatness = clamp_flatness(flatness);

    PDContours *contours = flatten(path, flatness);
    CGMutablePathRef resultPath = pd_contours_simplify(contours, epsilon);
    pd_contours_free(contours);

    return path_result(resultPath);
}

// Returns the total unsigned fill area enclosed by a PDPath.
PyObject *
cPathmatics_area(PyObject *self, PyObject *args)
{
    PyObject *pyObject;
    CGPathRef path;
    float flatness = 0.6;

    if (!PyArg_ParseTuple(args, "O|f", &pyObject, &flatness) || !parse_paths(pyObject, NULL, &path, NULL))
        return NULL;
    flatness = clamp_flatness(flatness);

    PDContours *contours = flatten(path, flatness);
    double area = pd_contours_area(contours);
    pd_contours_free(contours);

    return Py_BuildValue("d", area);
}

// NSBezierPath <-> CGPathRef conversion (interface declared in pathmatics.h
// so pdftrace.m can use it too)
@implementation Pathmatician
+ (CGPathRef)cgPath:(NSBezierPath *)nsPath{
    CGPathRef immutablePath = NULL;
    NSInteger numElements = [nsPath elementCount];
    if (numElements > 0){
        CGMutablePathRef path = CGPathCreateMutable();
        NSPoint points[3];
        for (NSInteger i=0; i<numElements; i++){
            NSBezierPathElement elt = [nsPath elementAtIndex:i associatedPoints:points];
            if (elt==NSBezierPathElementMoveTo){
                CGPathMoveToPoint(path, NULL, points[0].x, points[0].y);
            }else if(elt==NSBezierPathElementLineTo){
                CGPathAddLineToPoint(path, NULL, points[0].x, points[0].y);
// NSBezierPathElement* values are compile-time constants, not linked symbols,
// so comparing against the macOS 14 names is safe at any deployment target
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunguarded-availability-new"
#if HAS_QUADRATIC_PATH_ELEMENTS
            }else if(elt==NSBezierPathElementCubicCurveTo){
                CGPathAddCurveToPoint(path, NULL, points[0].x, points[0].y, points[1].x, points[1].y, points[2].x, points[2].y);
            }else if(elt==NSBezierPathElementQuadraticCurveTo){
                CGPathAddQuadCurveToPoint(path, NULL, points[0].x, points[0].y, points[1].x, points[1].y);
#else
            }else if(elt==NSBezierPathElementCurveTo){
                CGPathAddCurveToPoint(path, NULL, points[0].x, points[0].y, points[1].x, points[1].y, points[2].x, points[2].y);
#endif
#pragma clang diagnostic pop
            }else if(elt==NSBezierPathElementClosePath){
                CGPathCloseSubpath(path);
            }
        }
        immutablePath = CGPathCreateCopy(path);
        CGPathRelease(path);
    }
    return immutablePath;
}

// Replays a CGPath's segments onto a fresh NSBezierPath (the reverse of
// cgPath: above) -- needed to fold CGPathCreateCopyByStrokingPath/
// CGPathCreateCopyByTransformingPath output back into an NSBezierPath.
static void
_bezierPathApplier(void *info, const CGPathElement *element)
{
    NSBezierPath *path = (NSBezierPath *)info;
    CGPoint *pts = element->points;
    switch (element->type) {
        case kCGPathElementMoveToPoint:
            [path moveToPoint:NSMakePoint(pts[0].x, pts[0].y)];
            break;
        case kCGPathElementAddLineToPoint:
            [path lineToPoint:NSMakePoint(pts[0].x, pts[0].y)];
            break;
        case kCGPathElementAddQuadCurveToPoint: {
            // elevate quadratic to cubic (NSBezierPath has no quad primitive)
            NSPoint cur = [path currentPoint];
            CGPoint c = pts[0], p = pts[1];
            NSPoint c1 = NSMakePoint(cur.x + (c.x - cur.x) * (2.0/3.0), cur.y + (c.y - cur.y) * (2.0/3.0));
            NSPoint c2 = NSMakePoint(p.x + (c.x - p.x) * (2.0/3.0), p.y + (c.y - p.y) * (2.0/3.0));
            [path curveToPoint:NSMakePoint(p.x, p.y) controlPoint1:c1 controlPoint2:c2];
            break;
        }
        case kCGPathElementAddCurveToPoint:
            [path curveToPoint:NSMakePoint(pts[2].x, pts[2].y)
                  controlPoint1:NSMakePoint(pts[0].x, pts[0].y)
                  controlPoint2:NSMakePoint(pts[1].x, pts[1].y)];
            break;
        case kCGPathElementCloseSubpath:
            [path closePath];
            break;
    }
}

+ (NSBezierPath *)bezierPath:(CGPathRef)cgPath{
    NSBezierPath *path = [NSBezierPath bezierPath];
    if (cgPath) {
        CGPathApply(cgPath, path, _bezierPathApplier);
    }
    return path;
}
@end

// Converts a stroked PDPath into its equivalent fill-only outline, in
// the same local coordinate space as the input path (no transform is applied
// -- the caller is responsible for staying in local/pre-transform units, same
// requirement as CGPathCreateCopyByStrokingPath's own `transform` argument,
// which is applied to the already-stroked output rather than the input).
PyObject *
cPathmatics_strokeToFill(PyObject *self, PyObject *args)
{
    PyObject *pyObject;
    CGPathRef path;
    double width, miter = 10.0;
    int cap, join;

    if (!PyArg_ParseTuple(args, "Odii|d", &pyObject, &width, &cap, &join, &miter) || !parse_paths(pyObject, NULL, &path, NULL))
        return NULL;

    CGPathRef strokedPath;
    CGPathRetain(path);
    Py_BEGIN_ALLOW_THREADS
    strokedPath = CGPathCreateCopyByStrokingPath(path, NULL, width, (CGLineCap)cap, (CGLineJoin)join, miter);
    Py_END_ALLOW_THREADS
    CGPathRelease(path);

    PyObject *result = PDPath_FromCGPath(strokedPath);
    CGPathRelease(strokedPath);
    return result;
}
