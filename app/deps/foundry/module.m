#import <Python.h>
#include "../compat.h"

PyMethodDef methods[] = {
  {NULL, NULL},
};

MOD_INIT(cFoundry){
    PyObject *m;
    MOD_DEF(m, "cFoundry", "Dept. of Typography & Tracing", methods)
    return MOD_SUCCESS_VAL(m);
}
