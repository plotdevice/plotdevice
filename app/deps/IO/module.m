#import <Python.h>
#include "../compat.h"

PyMethodDef methods[] = {
  {NULL, NULL},
};

// void initcIO()
MOD_INIT(cIO){
    PyObject *m;
    MOD_DEF(m, "cIO", "Image and video export routines", methods)
    return MOD_SUCCESS_VAL(m);
}
