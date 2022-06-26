#import <Python.h>
#define MOD_ERROR_VAL NULL
#define MOD_SUCCESS_VAL(val) val
#define MOD_INIT(name) PyMODINIT_FUNC PyInit_##name(void)
#define MOD_DEF(ob, name, doc, methods) \
        static struct PyModuleDef moduledef = { \
          PyModuleDef_HEAD_INIT, name, doc, -1, methods, }; \
        ob = PyModule_Create(&moduledef);

PyMethodDef methods[] = {
  {NULL, NULL},
};

// void initcIO()
MOD_INIT(cIO){
    PyObject *m;
    MOD_DEF(m, "cIO", "Image and video export routines", methods)
    return MOD_SUCCESS_VAL(m);
}
