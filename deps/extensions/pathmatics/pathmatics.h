#import <Cocoa/Cocoa.h>
#include <Python.h>

PyObject * cPathmatics_linepoint(PyObject *self, PyObject *args);
PyObject * cPathmatics_linelength(PyObject *self, PyObject *args);
PyObject * cPathmatics_curvepoint(PyObject *self, PyObject *args);
PyObject * cPathmatics_curvelength(PyObject *self, PyObject *args);
PyObject * cPathmatics_intersects(PyObject *self, PyObject *args);
PyObject * cPathmatics_union(PyObject *self, PyObject *args);
PyObject * cPathmatics_intersect(PyObject *self, PyObject *args);
PyObject * cPathmatics_difference(PyObject *self, PyObject *args);
PyObject * cPathmatics_xor(PyObject *self, PyObject *args);
PyObject * fast_inverse_sqrt(PyObject *self, PyObject *args);
PyObject * angle(PyObject *self, PyObject *args);
PyObject * distance(PyObject *self, PyObject *args);
PyObject * coordinates(PyObject *self, PyObject *args);
