#import <Python.h>

PyMethodDef methods[] = {
  {NULL, NULL},
};

#if PY_MAJOR_VERSION < 3

void initcFoundry()
  {
    (void)Py_InitModule("cFoundry", methods);
  }

#else // PY_MAJOR_VERSION >= 3

static struct PyModuleDef moduledef = {
	PyModuleDef_HEAD_INIT,
	"cFoundry",
	"This is the cFoundry module",
	-1,
	methods,
	NULL,
	NULL,
	NULL,
	NULL,
};

PyMODINIT_FUNC PyInit_cFoundry()
  {
    return PyModule_Create(&moduledef);
  }


#endif // PY_MAJOR_VERSION
