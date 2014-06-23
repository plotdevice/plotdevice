#import <Python.h>

PyMethodDef methods[] = {
  {NULL, NULL},
};

void initcIO()
  {
    (void)Py_InitModule("cIO", methods);
  }

