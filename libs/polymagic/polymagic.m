#import <Cocoa/Cocoa.h>
#include <Python.h>

#include <math.h>
#include <stdio.h>
#include "gpc.h"


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

static int
contours_in_path(NSBezierPath *path)
{
    NSBezierPathElement    et;
    int                    sp, i, ec = [path elementCount];
    
    sp = 0;
    
    for( i = 0; i < ec; ++i )
    {
        et = [path elementAtIndex:i];
        
        if ( et == NSMoveToBezierPathElement )
            ++sp;
    }
    
    return sp;    
}

static int
contours_in_path_from_el(NSBezierPath *path, int se)
{
    NSBezierPathElement    et;
    int                    sp, i, ec = [path elementCount];
    
    sp = 1;
    
    for( i = se + 1; i < ec; ++i )
    {
        et = [path elementAtIndex:i];
        
        if ( et == NSMoveToBezierPathElement )
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
    int                      i, ec = [flat elementCount];
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
            case NSMoveToBezierPathElement:
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
            
            case NSLineToBezierPathElement:
            // add a vertex to the list
            poly->contour[es].vertex[k].x = ap[0].x;
            poly->contour[es].vertex[k].y = ap[0].y;
            ++k;
            break;
            
            case NSCurveToBezierPathElement:
                // should never happen - we have already converted the path to a flat version. Bail.
                printf("Got a curveto unexpectedly - bailing.\n");
                gpc_free_polygon( poly );
                return NULL;
                
            case NSClosePathBezierPathElement:
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
    
    [path setWindingRule:NSEvenOddWindingRule];
    
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

static PyObject *
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
static PyObject *
cPolymagic_intersects(PyObject *self, PyObject *args)
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
cPolymagic_operation(PyObject *self, PyObject *args, int op)
{
    PyObject *pyObject1, *pyObject2;
    NSBezierPath *path1, *path2, *pathResult;
    PyObject *result;
    PyTypeObject *cls_type;
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
static PyObject *
cPolymagic_union(PyObject *self, PyObject *args)
{
    return cPolymagic_operation(self, args, GPC_UNION);
}

// Returns the intersection of two NSBezierPaths as a new NSBezierPath.
static PyObject *
cPolymagic_intersect(PyObject *self, PyObject *args)
{
    return cPolymagic_operation(self, args, GPC_INT);
}

// Returns the difference of two NSBezierPaths as a new NSBezierPath.
static PyObject *
cPolymagic_difference(PyObject *self, PyObject *args)
{
    return cPolymagic_operation(self, args, GPC_DIFF);
}

// Returns the exclusive or of two NSBezierPaths as a new NSBezierPath.
static PyObject *
cPolymagic_xor(PyObject *self, PyObject *args)
{
    return cPolymagic_operation(self, args, GPC_XOR);
}

static PyObject *PolymagicError;

static PyMethodDef PolymagicMethods[] = {
    {"intersects",  cPolymagic_intersects, METH_VARARGS, "Check if two NSBezierPaths intersect."},
    {"union",  cPolymagic_union, METH_VARARGS, "Calculates the union of two NSBezierPaths."},
    {"intersect",  cPolymagic_intersect, METH_VARARGS, "Calculates the intersection of two NSBezierPaths."},
    {"difference",  cPolymagic_difference, METH_VARARGS, "Calculates the difference of two NSBezierPaths."},
    {"xor",  cPolymagic_xor, METH_VARARGS, "Calculates the exclusive or of two NSBezierPaths."},
    {NULL, NULL, 0, NULL}        //  Sentinel
};

PyMODINIT_FUNC
initcPolymagic(void)
{
    PyObject *m;
    
    m = Py_InitModule("cPolymagic", PolymagicMethods);
    
    PolymagicError = PyErr_NewException("cPolymagic.error", NULL, NULL);
    Py_INCREF(PolymagicError);
    PyModule_AddObject(m, "error", PolymagicError);
}

int
main(int argc, char *argv[])
{
    // Pass argv[0] to the Python interpreter
    Py_SetProgramName(argv[0]);

    // Initialize the Python interpreter.  Required.
    Py_Initialize();

    // Add a static module
    initcPolymagic();
    
    return 0;
}
/*
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
    
    printf("p1: %i\n", [p1 elementCount]);
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