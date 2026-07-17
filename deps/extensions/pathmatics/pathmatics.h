#import <Cocoa/Cocoa.h>
#include <Python.h>

// the macOS 14 SDK renamed NSBezierPathElementCurveTo to ...CubicCurveTo and
// added a new ...QuadraticCurveTo element type
#if defined(MAC_OS_VERSION_14_0) && MAC_OS_X_VERSION_MAX_ALLOWED >= MAC_OS_VERSION_14_0
  #define HAS_QUADRATIC_PATH_ELEMENTS 1
#else
  #define HAS_QUADRATIC_PATH_ELEMENTS 0
#endif

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
PyObject * cPathmatics_pdfOutline(PyObject *self, PyObject *args);
PyObject * cPathmatics_strokeToFill(PyObject *self, PyObject *args);
PyObject * fast_inverse_sqrt(PyObject *self, PyObject *args);
PyObject * angle(PyObject *self, PyObject *args);
PyObject * distance(PyObject *self, PyObject *args);
PyObject * coordinates(PyObject *self, PyObject *args);

// Shared NSBezierPath <-> CGPathRef conversion (used by the boolean-op backend
// and cPathmatics_strokeToFill in pathmatics.m, and by the PDF content-stream
// tracer in pdftrace.m).
@interface Pathmatician : NSObject
+ (CGPathRef)cgPath:(NSBezierPath *)nsPath;
+ (NSBezierPath *)bezierPath:(CGPathRef)cgPath;
@end
