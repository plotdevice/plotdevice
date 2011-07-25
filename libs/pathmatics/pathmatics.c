#include <Python.h>
#include <math.h>

void _linepoint(double t, double x0, double y0, double x1, double y1,
                double *out_x, double *out_y
                )
{
    *out_x = x0 + t * (x1-x0);
    *out_y = y0 + t * (y1-y0);
}


void _linelength(double x0, double y0, double x1, double y1,
                double *out_length
                )
{
    double a, b;
    a = pow(fabs(x0 - x1), 2);
    b = pow(fabs(y0 - y1), 2);
    *out_length = sqrt(a + b);
}

void _curvepoint(double t, double x0, double y0, double x1, double y1, 
                 double x2, double y2, double x3, double y3,
                 double *out_x, double *out_y, 
                 double *out_c1x, double *out_c1y, double *out_c2x, double *out_c2y
                 )
{
    double mint, x01, y01, x12, y12, x23, y23;

    mint  = 1 - t;
    x01 = x0 * mint + x1 * t;
    y01 = y0 * mint + y1 * t;
    x12 = x1 * mint + x2 * t;
    y12 = y1 * mint + y2 * t;
    x23 = x2 * mint + x3 * t;
    y23 = y2 * mint + y3 * t;
    
    *out_c1x = x01 * mint + x12 * t;
    *out_c1y = y01 * mint + y12 * t;
    *out_c2x = x12 * mint + x23 * t;
    *out_c2y = y12 * mint + y23 * t;
    *out_x = *out_c1x * mint + *out_c2x * t;
    *out_y = *out_c1y * mint + *out_c2y * t;
}

void _curvepoint_handles(double t, double x0, double y0, double x1, double y1, 
                 double x2, double y2, double x3, double y3,
                 double *out_x, double *out_y, 
                 double *out_c1x, double *out_c1y, double *out_c2x, double *out_c2y,
                 double *out_h1x, double *out_h1y, double *out_h2x, double *out_h2y
                 )
{
    double mint, x01, y01, x12, y12, x23, y23;

    mint  = 1 - t;
    x01 = x0 * mint + x1 * t;
    y01 = y0 * mint + y1 * t;
    x12 = x1 * mint + x2 * t;
    y12 = y1 * mint + y2 * t;
    x23 = x2 * mint + x3 * t;
    y23 = y2 * mint + y3 * t;
    
    *out_c1x = x01 * mint + x12 * t;
    *out_c1y = y01 * mint + y12 * t;
    *out_c2x = x12 * mint + x23 * t;
    *out_c2y = y12 * mint + y23 * t;
    *out_x = *out_c1x * mint + *out_c2x * t;
    *out_y = *out_c1y * mint + *out_c2y * t;
    *out_h1x = x01;
    *out_h1y = y01;
    *out_h2x = x23;
    *out_h2y = y23;
}

void _curvelength(double x0, double y0, double x1, double y1, 
                  double x2, double y2, double x3, double y3, int n, 
                  double *out_length
                  )
{
    double xi, yi, t, c;
    double pt_x, pt_y, pt_c1x, pt_c1y, pt_c2x, pt_c2y;
    int i;
    double length = 0;
    
    xi = x0;
    yi = y0;
    
    for (i=0; i<n; i++) {
        t = 1.0 * (i+1.0) / (float) n;
        
        _curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3,
                    &pt_x, &pt_y, &pt_c1x, &pt_c1y, &pt_c2x, &pt_c2y);
        c = sqrt(pow(fabs(xi-pt_x), 2.0) + pow(fabs(yi-pt_y), 2.0));
        length += c;
        xi = pt_x;
        yi = pt_y;
    }
    *out_length = length;
}

static PyObject *
cPathmatics_linepoint(PyObject *self, PyObject *args)
{
    double t, x0, y0, x1, y1;
    double out_x, out_y;
    
    if (!PyArg_ParseTuple(args, "ddddd", &t, &x0, &y0, &x1, &y1))
        return NULL;
        
    _linepoint(t, x0, y0, x1, y1,
               &out_x, &out_y);

    return Py_BuildValue("dd", out_x, out_y);
}

static PyObject *
cPathmatics_linelength(PyObject *self, PyObject *args)
{
    double x0, y0, x1, y1;
    double out_length;
    
    if (!PyArg_ParseTuple(args, "dddd", &x0, &y0, &x1, &y1))
        return NULL;
        
    _linelength(x0, y0, x1, y1,
                &out_length);

    return Py_BuildValue("d", out_length);
}


static PyObject *
cPathmatics_curvepoint(PyObject *self, PyObject *args)
{
    double t, x0, y0, x1, y1, x2, y2, x3, y3, handles = 0;
    double out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y, out_h1x, out_h1y, out_h2x, out_h2y;
    
    if (!PyArg_ParseTuple(args, "ddddddddd|i", &t, &x0, &y0, &x1, &y1, &x2, &y2, &x3, &y3, &handles))
        return NULL;
        
    if (!handles) {
        _curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3,
            &out_x, &out_y, &out_c1x, &out_c1y, &out_c2x, &out_c2y);

        return Py_BuildValue("dddddd", out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y);

    } else {
        _curvepoint_handles(t, x0, y0, x1, y1, x2, y2, x3, y3,
            &out_x, &out_y, &out_c1x, &out_c1y, &out_c2x, &out_c2y,
            &out_h1x, &out_h1y, &out_h2x, &out_h2y);

        return Py_BuildValue("dddddddddd", out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y,
            out_h1x, out_h1y, out_h2x, out_h2y);
    }
}

static PyObject *
cPathmatics_curvelength(PyObject *self, PyObject *args)
{
    double x0, y0, x1, y1, x2, y2, x3, y3;
    int n = 20;
    double out_length;
    
    if (!PyArg_ParseTuple(args, "dddddddd|i", &x0, &y0, &x1, &y1, &x2, &y2, &x3, &y3, &n))
        return NULL;

    _curvelength(x0, y0, x1, y1, x2, y2, x3, y3, n,
                 &out_length);

    return Py_BuildValue("d", out_length);
}

static PyObject *PathmaticsError;

static PyMethodDef PathmaticsMethods[] = {
    {"linepoint",  cPathmatics_linepoint, METH_VARARGS, "Calculate linepoint."},
    {"linelength",  cPathmatics_linelength, METH_VARARGS, "Calculate linelength."},
    {"curvepoint",  cPathmatics_curvepoint, METH_VARARGS, "Calculate curvepoint."},
    {"curvelength",  cPathmatics_curvelength, METH_VARARGS, "Calculate curvelength."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

PyMODINIT_FUNC
initcPathmatics(void)
{
    PyObject *m;
    
    m = Py_InitModule("cPathmatics", PathmaticsMethods);
    
    PathmaticsError = PyErr_NewException("cPathmatics.error", NULL, NULL);
    Py_INCREF(PathmaticsError);
    PyModule_AddObject(m, "error", PathmaticsError);
}

int
main(int argc, char *argv[])
{
    /* Pass argv[0] to the Python interpreter */
    Py_SetProgramName(argv[0]);

    /* Initialize the Python interpreter.  Required. */
    Py_Initialize();

    /* Add a static module */
    initcPathmatics();
    
    return 0;
}