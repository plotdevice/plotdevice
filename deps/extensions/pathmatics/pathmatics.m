#import "pathmatics.h"
#include <math.h>
#include <stdio.h>
#include "gpc.h"

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


// ploymagic

static int
contours_in_path(NSBezierPath *path)
{
    NSBezierPathElement    et;
    int                    sp, i, ec = (int)[path elementCount];

    sp = 0;

    for( i = 0; i < ec; ++i )
    {
        et = [path elementAtIndex:i];

        if ( et == NSBezierPathElementMoveTo )
            ++sp;
    }

    return sp;
}

static int
contours_in_path_from_el(NSBezierPath *path, int se)
{
    NSBezierPathElement    et;
    int                    sp, i, ec = (int)[path elementCount];

    sp = 1;

    for( i = se + 1; i < ec; ++i )
    {
        et = [path elementAtIndex:i];

        if ( et == NSBezierPathElementMoveTo )
            break;

        ++sp;
    }

    return sp;
}

static gpc_polygon*
path_to_polygon(NSBezierPath *path, float flatness)
{
    [NSBezierPath setDefaultFlatness: flatness];
    [path setFlatness: flatness];
    //printf("setFlatness %.2f\n", flatness);

    NSBezierPath*            flat = [path bezierPathByFlatteningPath];
    NSBezierPathElement      elem;
    NSPoint                  ap[3];
    int                      i, ec = (int)[flat elementCount];
    gpc_polygon*             poly;

    [flat setWindingRule:[path windingRule]];

    // allocate memory for the poly.

    poly = malloc( sizeof( gpc_polygon ));

    // how many contours do we need?

    poly->num_contours = contours_in_path(flat);
    poly->contour = malloc( sizeof( gpc_vertex_list ) * poly->num_contours );

    // how many elements in each contour?

    int es = 0;

    for( i = 0; i < poly->num_contours; ++i )
    {
        int spc = contours_in_path_from_el(flat, es);
        //printf("contours_in_path_from_el: %i\n", spc);

        // allocate enough memory to hold this many points

        poly->contour[i].num_vertices = spc;
        poly->contour[i].vertex = malloc( sizeof( gpc_vertex ) * spc );

        es += spc;
    }

    // es will now keep track of which contour we are adding to; k is the element index within it.

    int k = 0;
    es = -1;
    NSPoint     spStart;

    for( i = 0; i < ec; ++i )
    {
        elem = [flat elementAtIndex:i associatedPoints:ap];

        switch( elem )
        {
            case NSBezierPathElementMoveTo:
            // begins a new contour.

            if ( es != -1 )
            {
                // close the previous contour by adding a vertex with the subpath start

                poly->contour[es].vertex[k].x = spStart.x;
                poly->contour[es].vertex[k].y = spStart.y;
            }
            // next contour:
            ++es;
            k = 0;
            // keep a note of the start of the subpath so we can close it
            spStart = ap[0];

            // sanity check es - must not exceed contour count - 1

            if ( es >= poly->num_contours )
            {
                printf("discrepancy in contour count versus number of subpaths encountered - bailing\n");

                gpc_free_polygon( poly );
                return NULL;
            }

            // fall through to record the vertex for the moveto

            case NSBezierPathElementLineTo:
            // add a vertex to the list
            poly->contour[es].vertex[k].x = ap[0].x;
            poly->contour[es].vertex[k].y = ap[0].y;
            ++k;
            break;

            case NSBezierPathElementCurveTo:
                // should never happen - we have already converted the path to a flat version. Bail.
                printf("Got a curveto unexpectedly - bailing.\n");
                gpc_free_polygon( poly );
                return NULL;

            case NSBezierPathElementClosePath:
                // ignore
            break;
        }
    }

    return poly;
}

static NSBezierPath *
polygon_to_path(gpc_polygon *poly)
{
    // returns a new NSBezierPath object equivalent to the polygon passed to it. The caller is responsible for freeing
    // the polygon. The returned path is autoreleased as per usual cocoa rules.

    NSBezierPath*    path = [NSBezierPath bezierPath];
    NSPoint            p;
    int                cont;

    for( cont = 0; cont < poly->num_contours; ++cont )
    {
        p.x = poly->contour[cont].vertex[0].x;
        p.y = poly->contour[cont].vertex[0].y;
        [path moveToPoint:p];

        int vert;

        for( vert = 1; vert < poly->contour[cont].num_vertices; ++vert )
        {
            p.x = poly->contour[cont].vertex[vert].x;
            p.y = poly->contour[cont].vertex[vert].y;
            [path lineToPoint:p];
        }

        [path closePath];
    }

    // set the default winding rule to be the one most useful for shapes
    // with holes.

    [path setWindingRule:NSWindingRuleEvenOdd];

    return path;
}

static NSBezierPath *
path_operation(NSBezierPath* p1, NSBezierPath* p2, gpc_op op, float flatness)
{
    NSBezierPath*    resultPath;
    gpc_polygon        *poly1, *poly2, *resultPoly;

    poly1 = path_to_polygon(p1, flatness);
    poly2 = path_to_polygon(p2, flatness);

    resultPoly = malloc( sizeof( gpc_polygon ));

    // this line does all the really hard work:
    gpc_polygon_clip( op, poly1, poly2, resultPoly );

    resultPath = polygon_to_path( resultPoly );

    gpc_free_polygon( poly1 );
    gpc_free_polygon( poly2 );
    gpc_free_polygon( resultPoly );

    return resultPath;
}

static bool
intersects_path(NSBezierPath* p1, NSBezierPath* p2)
{
    NSRect        bbox = [p2 bounds];
    if ( NSIntersectsRect( bbox, [p1 bounds]))
    {
        // bounds intersect, so it's a possibility - find the intersection and see if it's empty.
        NSBezierPath* ip = path_operation(p1, p2, GPC_INT, 0.1);
        return ![ip isEmpty];
    }
    else
        return false;
}

typedef struct {
    PyObject_HEAD
    id        objc_object;
    int       flags;
} PyObjCObject;

static bool
parse_double_path_args(PyObject *self, PyObject *args, NSBezierPath **path1, NSBezierPath **path2)
{
    PyObject *pyObject1, *pyObject2;
    if (!PyArg_ParseTuple(args, "OO", &pyObject1, &pyObject2))
        return false;

    // Check if the two objects are NSBezierPaths.
    if (strcmp("NSBezierPath", pyObject1->ob_type->tp_name) != 0) {
        PyErr_SetString(PyExc_TypeError, "first argument is not a NSBezierPath");
        return false;
    }

    if (strcmp("NSBezierPath", pyObject2->ob_type->tp_name) != 0) {
        PyErr_SetString(PyExc_TypeError, "second argument is not a NSBezierPath");
        return false;
    }

    *path1 = ((PyObjCObject *) pyObject1)->objc_object;
    *path2 = ((PyObjCObject *) pyObject2)->objc_object;

    return true;
}

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

// Check if two NSBezierPaths intersect.
PyObject *
cPathmatics_intersects(PyObject *self, PyObject *args)
{
    NSBezierPath *path1, *path2;
    PyObject *result;

    if (!parse_double_path_args(self, args, &path1, &path2))
        return NULL;

    if (intersects_path(path1, path2)) {
        Py_INCREF(Py_True);
        result = Py_True;
    } else {
        Py_INCREF(Py_False);
        result = Py_False;
    }

    return result;
}

static bool
check_path_types(PyObject *pyObject1, PyObject *pyObject2) {
    // Check if the two objects are NSBezierPaths.
    if (strcmp("NSBezierPath", pyObject1->ob_type->tp_name) != 0) {
        PyErr_SetString(PyExc_TypeError, "first argument is not a NSBezierPath");
        return false;
    }

    if (strcmp("NSBezierPath", pyObject2->ob_type->tp_name) != 0) {
        PyErr_SetString(PyExc_TypeError, "second argument is not a NSBezierPath");
        return false;
    }
    return true;
}


static PyObject*
cPathmatics_operation(PyObject *self, PyObject *args, int op)
{
    PyObject *pyObject1, *pyObject2;
    NSBezierPath *path1, *path2, *pathResult;
    // PyObject *result;
    // PyTypeObject *cls_type;
    float flatness = 0.6;

    if (!PyArg_ParseTuple(args, "OO|f", &pyObject1, &pyObject2, &flatness))
        return NULL;

    if (flatness < 0.1) {
        flatness = 0.1;
    } else if (flatness > 5.0) {
        flatness = 5.0;
    }

    if (!check_path_types(pyObject1, pyObject2))
        return NULL;

    path1 = ((PyObjCObject *) pyObject1)->objc_object;
    path2 = ((PyObjCObject *) pyObject2)->objc_object;

    pathResult = path_operation(path1, path2, op, flatness);
    [pathResult retain];

    // To get access to a NSBezierPath ObjC instance, we use an
    // existing reference (that from pyObject1) to build our new
    // object out of. I'm not sure if we have to indicate that
    // we borrow this reference. Currently, nothing of that sort
    // happens.
    return build_objc_instance(pyObject1->ob_type, pathResult);
}

// Returns the union of two NSBezierPaths as a new NSBezierPath.
PyObject *
cPathmatics_union(PyObject *self, PyObject *args)
{
    return cPathmatics_operation(self, args, GPC_UNION);
}

// Returns the intersection of two NSBezierPaths as a new NSBezierPath.
PyObject *
cPathmatics_intersect(PyObject *self, PyObject *args)
{
    return cPathmatics_operation(self, args, GPC_INT);
}

// Returns the difference of two NSBezierPaths as a new NSBezierPath.
PyObject *
cPathmatics_difference(PyObject *self, PyObject *args)
{
    return cPathmatics_operation(self, args, GPC_DIFF);
}

// Returns the exclusive or of two NSBezierPaths as a new NSBezierPath.
PyObject *
cPathmatics_xor(PyObject *self, PyObject *args)
{
    return cPathmatics_operation(self, args, GPC_XOR);
}



/*
// dumps poly structure to log for testing/debug
static void
logPoly( gpc_polygon* poly )
{

    printf("polygon <contours: %i>\n", poly->num_contours);

    int cont;

    for( cont = 0; cont < poly->num_contours; ++cont )
    {
        printf("contour #%i: %i vertices: \n", cont, poly->contour[cont].num_vertices);
        printf("drawpath([");

        int vert;
        for( vert = 0; vert < poly->contour[cont].num_vertices; ++vert ) {
            printf("(%.3f, %.3f),", poly->contour[cont].vertex[vert].x, poly->contour[cont].vertex[vert].y);

        }
        printf("])");
        printf("\n------ end of contour %i ------\n", cont);
    }
    printf("------ end of polygon ------\n");
}
*/

/*
// intersection test
int xmain(int argc, char *argv[])
{
    [[NSAutoreleasePool alloc] init];
    NSBezierPath *p1, *p2;
    NSFont *helveticaFont;
    //NSGlyph *aGlpyh;
    //p1 = [NSBezierPath bezierPathWithOvalInRect:NSMakeRect(0, 0, 100, 100)];
    //p2 = [NSBezierPath bezierPathWithOvalInRect:NSMakeRect(50, 72, 100, 100)]; // x=50 intersects

    helveticaFont = [NSFont fontWithName:@"Helvetica" size:24];
    p1 = [NSBezierPath bezierPath];
    [p1 moveToPoint:NSMakePoint(68, 100)];
    [p1 appendBezierPathWithGlyph:68 inFont:helveticaFont];
    p2 = [NSBezierPath bezierPath];
    [p2 moveToPoint:NSMakePoint(70, 100)];
    [p2 appendBezierPathWithGlyph:68 inFont:helveticaFont];

    printf("p1: %i\n", (int)[p1 elementCount]);
    if (intersects_path(p1, p2)) {
        printf("INTERSECTS\n");
    } else {
        printf("Doesn't intersect.\n");
    }
    [p1 release];
    [p2 release];
    return 0;
}

*/


////  Slightly faster(?) trig routines

// FAST INVERSE SQRT. Chris Lomont, http://www.math.purdue.edu/~clomont/Math/Papers/2003/InvSqrt.pdf
float _fast_inverse_sqrt(float x) {
    float xhalf = 0.5f*x;
    int i = *(int*)&x;
    i = 0x5f3759df - (i>>1);
    x = *(float*)&i;
    x = x*(1.5f-xhalf*x*x);
    return x;
}

// we're not running doom on a 32 bit cpu anymore...
PyObject *
fast_inverse_sqrt(PyObject *self, PyObject *args) {
    double x;
    if (!PyArg_ParseTuple(args, "d", &x))
        return NULL;
    x = 1.0/sqrt(x);
    return Py_BuildValue("d", x);
}

// ANGLE
void _angle(double x0, double y0, double x1, double y1, double *a) {
    *a = atan2(y1-y0, x1-x0) / M_PI * 180;
}
PyObject *
angle(PyObject *self, PyObject *args) {
    double x0, y0, x1, y1, a;
    if (!PyArg_ParseTuple(args, "dddd", &x0, &y0, &x1, &y1))
        return NULL;
    _angle(x0, y0, x1, y1, &a);
    return Py_BuildValue("d", a);
}

// DISTANCE
void _distance(double x0, double y0, double x1, double y1, double *d) {
    *d = sqrt((x1-x0)*(x1-x0) + (y1-y0)*(y1-y0));
}
PyObject *
distance(PyObject *self, PyObject *args) {
    double x0, y0, x1, y1, d;
    if (!PyArg_ParseTuple(args, "dddd", &x0, &y0, &x1, &y1))
        return NULL;
    _distance(x0, y0, x1, y1, &d);
    return Py_BuildValue("d", d);
}

// COORDINATES
void _coordinates(double x0, double y0, double d, double a, double *x1, double *y1) {
    *x1 = x0 + cos(a/180*M_PI) * d;
    *y1 = y0 + sin(a/180*M_PI) * d;
}
PyObject *
coordinates(PyObject *self, PyObject *args) {
    double x0, y0, d, a, x1, y1;
    if (!PyArg_ParseTuple(args, "dddd", &x0, &y0, &d, &a))
        return NULL;
    _coordinates(x0, y0, d, a, &x1, &y1);
    return Py_BuildValue("dd", x1, y1);
}


// NSBezierPath -> CGPathRef conversion
@interface Pathmatician : NSObject
+ (CGPathRef)cgPath:(NSBezierPath *)nsPath;
@end
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
            }else if(elt==NSBezierPathElementCurveTo){
                CGPathAddCurveToPoint(path, NULL, points[0].x, points[0].y, points[1].x, points[1].y, points[2].x, points[2].y);
            }else if(elt==NSBezierPathElementClosePath){
                CGPathCloseSubpath(path);
            }
        }
        immutablePath = CGPathCreateCopy(path);
        CGPathRelease(path);
    }
    return immutablePath;
}
@end
