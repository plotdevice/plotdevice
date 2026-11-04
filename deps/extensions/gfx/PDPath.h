#import <Cocoa/Cocoa.h>
#include <Python.h>

// the macOS 14 SDK renamed NSBezierPathElementCurveTo to ...CubicCurveTo and
// added a new ...QuadraticCurveTo element type
#if defined(MAC_OS_VERSION_14_0) && MAC_OS_X_VERSION_MAX_ALLOWED >= MAC_OS_VERSION_14_0
  #define HAS_QUADRATIC_PATH_ELEMENTS 1
#else
  #define HAS_QUADRATIC_PATH_ELEMENTS 0
#endif

// the PDPath type (PDPath.m): adding it to the module, the CGPath behind one (NULL if obj isn't a
// PDPath), and a new one of a CGPath with its closes made as closePath makes them
int PDPath_register(PyObject *module);
CGPathRef PDPath_CGPath(PyObject *obj);
PyObject *PDPath_FromCGPath(CGPathRef path);
