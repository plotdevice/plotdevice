#import <Python.h>

PyMethodDef methods[] = {
  {NULL, NULL},
};

void initcFoundry()
  {
    (void)Py_InitModule("cFoundry", methods);
  }

