#include <Python.h>
#include <math.h>

// FAST INVERSE SQRT
// Chris Lomont, http://www.math.purdue.edu/~clomont/Math/Papers/2003/InvSqrt.pdf
float _fast_inverse_sqrt(float x) {
    float xhalf = 0.5f*x;
    int i = *(int*)&x;
    i = 0x5f3759df - (i>>1);
    x = *(float*)&i;
    x = x*(1.5f-xhalf*x*x);
    return x;
}

// we're not running doom on a 32 bit cpu anymore...
static PyObject *
fast_inverse_sqrt(PyObject *self, PyObject *args) {
    double x;
    if (!PyArg_ParseTuple(args, "d", &x))
        return NULL;
    x = 1.0/sqrt(x);
    return Py_BuildValue("d", x);
}

// ANGLE
void _angle(double x0, double y0, double x1, double y1, double *a) {
    *a = atan2(y1-y0, x1-x0) / M_PI * 180;
}
static PyObject *
angle(PyObject *self, PyObject *args) {
    double x0, y0, x1, y1, a;
    if (!PyArg_ParseTuple(args, "dddd", &x0, &y0, &x1, &y1))
        return NULL;
    _angle(x0, y0, x1, y1, &a);
    return Py_BuildValue("d", a);
}

// DISTANCE
void _distance(double x0, double y0, double x1, double y1, double *d) {
    *d = sqrt((x1-x0)*(x1-x0) + (y1-y0)*(y1-y0));
}
static PyObject *
distance(PyObject *self, PyObject *args) {
    double x0, y0, x1, y1, d;
    if (!PyArg_ParseTuple(args, "dddd", &x0, &y0, &x1, &y1))
        return NULL;
    _distance(x0, y0, x1, y1, &d);
    return Py_BuildValue("d", d);
}

// COORDINATES
void _coordinates(double x0, double y0, double d, double a, double *x1, double *y1) {
    *x1 = x0 + cos(a/180*M_PI) * d;
    *y1 = y0 + sin(a/180*M_PI) * d;
}
static PyObject *
coordinates(PyObject *self, PyObject *args) {
    double x0, y0, d, a, x1, y1;
    if (!PyArg_ParseTuple(args, "dddd", &x0, &y0, &d, &a))
        return NULL;
    _coordinates(x0, y0, d, a, &x1, &y1);
    return Py_BuildValue("dd", x1, y1);
}

static PyMethodDef geometry_methods[]={
    { "fast_inverse_sqrt", fast_inverse_sqrt, METH_VARARGS },
    { "angle", angle, METH_VARARGS },
    { "distance", distance, METH_VARARGS },
    { "coordinates", coordinates, METH_VARARGS },
    { NULL, NULL }
};

PyMODINIT_FUNC initcGeometry(void){
    PyObject *m;
    m = Py_InitModule("cGeometry", geometry_methods);
}

int main(int argc, char *argv[])
{
    Py_SetProgramName(argv[0]);
    Py_Initialize();
    initcGeometry();
    return 0;
}