#import <Cocoa/Cocoa.h>
#include <Python.h>
#import "../gfx/PDPath.h"

PyObject * cPathmatics_linepoint(PyObject *self, PyObject *args);
PyObject * cPathmatics_linelength(PyObject *self, PyObject *args);
PyObject * cPathmatics_curvepoint(PyObject *self, PyObject *args);
PyObject * cPathmatics_curvelength(PyObject *self, PyObject *args);
PyObject * cPathmatics_intersects(PyObject *self, PyObject *args);
PyObject * cPathmatics_union(PyObject *self, PyObject *args);
PyObject * cPathmatics_intersect(PyObject *self, PyObject *args);
PyObject * cPathmatics_difference(PyObject *self, PyObject *args);
PyObject * cPathmatics_xor(PyObject *self, PyObject *args);
PyObject * cPathmatics_offset(PyObject *self, PyObject *args);
PyObject * cPathmatics_simplify(PyObject *self, PyObject *args);
PyObject * cPathmatics_area(PyObject *self, PyObject *args);
PyObject * cPathmatics_strokeToFill(PyObject *self, PyObject *args);

// Shared NSBezierPath <-> CGPathRef conversion (used by the boolean-op backend
// and cPathmatics_strokeToFill in pathmatics.m, and by the PDF content-stream
// tracer in tracer.m).
@interface Pathmatician : NSObject
+ (CGPathRef)cgPath:(NSBezierPath *)nsPath;
+ (NSBezierPath *)bezierPath:(CGPathRef)cgPath;
@end
