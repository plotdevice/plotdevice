#import <Python.h>

PyMethodDef methods[] = {
  {NULL, NULL},
};

#if PY_MAJOR_VERSION < 3

void initcIO()
  {
    (void)Py_InitModule("cIO", methods);
  }

#else // PY_MAJOR_VERSION >= 3

static struct PyModuleDef moduledef = {
	PyModuleDef_HEAD_INIT,
	"cIO",
	"This is the cIO module",
	-1,
	methods,
	NULL,
	NULL,
	NULL,
	NULL,
};

PyMODINIT_FUNC PyInit_cIO()
  {
    return PyModule_Create(&moduledef);
  }

#endif // PY_MAJOR_VERSION
