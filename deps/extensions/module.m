#import <Python.h>
#import "pathmatics/pathmatics.h"
#import "clipper2/bridge.h"

// Pathmatics routines written for NodeBox by Tom De Smedt and Frederik De Bleser
PyMethodDef methods[] = {
  // pathmatics
  {"linepoint", cPathmatics_linepoint, METH_VARARGS, "Calculate linepoint."},
  {"linelength", cPathmatics_linelength, METH_VARARGS, "Calculate linelength."},
  {"curvepoint", cPathmatics_curvepoint, METH_VARARGS, "Calculate curvepoint."},
  {"curvelength", cPathmatics_curvelength, METH_VARARGS, "Calculate curvelength."},
  // polymagic
  {"intersects", cPathmatics_intersects, METH_VARARGS, "Check if two NSBezierPaths intersect."},
  {"union", cPathmatics_union, METH_VARARGS, "Calculates the union of two NSBezierPaths."},
  {"intersect", cPathmatics_intersect, METH_VARARGS, "Calculates the intersection of two NSBezierPaths."},
  {"difference", cPathmatics_difference, METH_VARARGS, "Calculates the difference of two NSBezierPaths."},
  {"xor", cPathmatics_xor, METH_VARARGS, "Calculates the exclusive or of two NSBezierPaths."},
  {"offset", cPathmatics_offset, METH_VARARGS, "Grows or shrinks an NSBezierPath's boundary."},
  {"simplify", cPathmatics_simplify, METH_VARARGS, "Reduces an NSBezierPath's point count within a tolerance."},
  {"area", cPathmatics_area, METH_VARARGS, "Calculates the fill area enclosed by an NSBezierPath."},
  {"pdf_outline", cPathmatics_pdfOutline, METH_VARARGS, "Traces the vector shapes in a PDF's content stream into an NSBezierPath."},
  {"stroke_to_fill", cPathmatics_strokeToFill, METH_VARARGS, "Converts a stroked NSBezierPath into its equivalent fill-only outline."},
  // trig
  {"fast_inverse_sqrt", fast_inverse_sqrt, METH_VARARGS },
  {"angle", angle, METH_VARARGS },
  {"distance", distance, METH_VARARGS },
  {"coordinates", coordinates, METH_VARARGS },
  {NULL, NULL, 0, NULL} /* Sentinel */
};

PyMODINIT_FUNC PyInit__plotdevice(void){
    static struct PyModuleDef moduledef = {
      PyModuleDef_HEAD_INIT, "_plotdevice", "Typography, image/video export, and bezier math routines", -1, methods
    };

    PyObject *m = PyModule_Create(&moduledef);
    PyObject *err = PyErr_NewException("cPathmatics.error", NULL, NULL);
    Py_INCREF(err);
    PyModule_AddObject(m, "error", err);

    return m;
}
