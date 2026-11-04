#import "PDPath.h"

// A mutable CGPath holding the elements NSBezierPath would (including the moveto it adds after an
// explicit close but not after a shape's own), and tracking its last element, subpath start, and
// element count, so closing, len(), and indexing don't have to walk it.

enum { PD_EMPTY = -1, PD_MOVETO = 0, PD_LINETO = 1, PD_CURVETO = 2, PD_CLOSE = 3 };

typedef struct {
    PyObject_HEAD
    CGMutablePathRef path;
    int last;
    CGPoint start;
    BOOL pending; // the trailing moveto (to start) isn't in the cgpath yet
    Py_ssize_t count;
    PyObject *elements; // cached by elements(), cleared by every edit
    PyObject *proxy;    // cached by .cgpath
} PDPathObject;

// pyobjc's object layout, as in pathmatics.h (flags 0x20 marks a CF object)
typedef struct {
    PyObject_HEAD
    id objc_object;
    int flags;
} PDObjCObject;

static PyTypeObject *
pyobjc_type(const char *module, const char *name)
{
    PyObject *mod = PyImport_ImportModule(module);
    if (!mod) return NULL;
    PyObject *type = PyObject_GetAttrString(mod, name);
    Py_DECREF(mod);
    return (PyTypeObject *)type; // kept for the life of the process
}

static PyObject *
wrap_objc(PyTypeObject *type, id obj, int flags)
{
    PyObject *result = type->tp_alloc(type, 0);
    if (!result) return NULL;
    ((PDObjCObject *)result)->objc_object = obj;
    ((PDObjCObject *)result)->flags = flags;
    return result;
}

static id
unwrap_objc(PyObject *obj, const char *type_name)
{
    if (strcmp(Py_TYPE(obj)->tp_name, type_name) != 0) return nil;
    return ((PDObjCObject *)obj)->objc_object;
}

// edits that keep the bookkeeping

static void
pd_flush(PDPathObject *self)
{
    // add a pending moveto to the cgpath, before anything that follows or reads it
    if (!self->pending) return;
    CGPathMoveToPoint(self->path, NULL, self->start.x, self->start.y);
    self->pending = NO;
}

static CGPoint
pd_current_point(PDPathObject *self)
{
    return self->pending ? self->start : CGPathGetCurrentPoint(self->path);
}

static void
pd_moveto(PDPathObject *self, CGFloat x, CGFloat y)
{
    // a moveto replaces a trailing one, as in ns; it's held back from the cgpath until something
    // follows it, since cg replaces a moveto in time proportional to the path's length
    if (self->last != PD_MOVETO) self->count += 1;
    self->last = PD_MOVETO;
    self->start = CGPointMake(x, y);
    self->pending = YES;
    Py_CLEAR(self->elements);
}

static void
pd_lineto(PDPathObject *self, CGFloat x, CGFloat y)
{
    pd_flush(self);
    CGPathAddLineToPoint(self->path, NULL, x, y);
    self->count += 1;
    self->last = PD_LINETO;
    Py_CLEAR(self->elements);
}

static void
pd_curveto(PDPathObject *self, CGFloat x1, CGFloat y1, CGFloat x2, CGFloat y2, CGFloat x3, CGFloat y3)
{
    pd_flush(self);
    CGPathAddCurveToPoint(self->path, NULL, x1, y1, x2, y2, x3, y3);
    self->count += 1;
    self->last = PD_CURVETO;
    Py_CLEAR(self->elements);
}

static void
pd_quadto(PDPathObject *self, CGPoint c, CGPoint p)
{
    // elevated to a cubic, as pathmatics.m's _bezierPathApplier does
    CGPoint cur = pd_current_point(self);
    pd_curveto(self, cur.x + (c.x - cur.x) * (2.0/3.0), cur.y + (c.y - cur.y) * (2.0/3.0),
               p.x + (c.x - p.x) * (2.0/3.0), p.y + (c.y - p.y) * (2.0/3.0), p.x, p.y);
}

static void
pd_end_subpath(PDPathObject *self)
{
    // a close as a shape records it, with no moveto after it (cg ignores a second close)
    if (self->last == PD_EMPTY || self->last == PD_CLOSE) return;
    pd_flush(self);
    CGPathCloseSubpath(self->path);
    self->count += 1;
    self->last = PD_CLOSE;
    Py_CLEAR(self->elements);
}

static void
pd_closepath_ns(PDPathObject *self)
{
    // ns's closePath, as copying or appending a path replays it: a close (even right after a
    // moveto, where ns records another), then a moveto to the subpath's start
    if (self->last == PD_EMPTY) return;
    pd_end_subpath(self);
    pd_moveto(self, self->start.x, self->start.y);
}

static void
pd_close(PDPathObject *self)
{
    // closepath(): ns's closePath, for an open subpath only
    if (self->last == PD_LINETO || self->last == PD_CURVETO) pd_closepath_ns(self);
}

static void
pd_append_ns(PDPathObject *self, NSBezierPath *ns, BOOL skip_first, BOOL as_closepath)
{
    // replay an NSBezierPath's elements as they are, or with every close made as closePath makes it
    NSInteger count = [ns elementCount];
    NSPoint p[3];
    for (NSInteger i = skip_first ? 1 : 0; i < count; i++) {
        NSBezierPathElement el = [ns elementAtIndex:i associatedPoints:p];
        if (el == NSBezierPathElementMoveTo) {
            pd_moveto(self, p[0].x, p[0].y);
        } else if (el == NSBezierPathElementLineTo) {
            pd_lineto(self, p[0].x, p[0].y);
        } else if (el == NSBezierPathElementClosePath) {
            if (as_closepath) pd_closepath_ns(self);
            else pd_end_subpath(self);
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunguarded-availability-new"
#if HAS_QUADRATIC_PATH_ELEMENTS
        } else if (el == NSBezierPathElementQuadraticCurveTo) {
            pd_quadto(self, p[0], p[1]);
#endif
#pragma clang diagnostic pop
        } else {
            pd_curveto(self, p[0].x, p[0].y, p[1].x, p[1].y, p[2].x, p[2].y);
        }
    }
}

typedef struct {
    PDPathObject *path;
    CGAffineTransform t;
    BOOL as_closepath; // close as closePath does (with a moveto) rather than copying closes as is
} Append;

static void
pd_append_applier(void *info, const CGPathElement *el)
{
    Append *a = (Append *)info;
    PDPathObject *self = a->path;
    CGPoint p[3];
    int n = el->type == kCGPathElementAddCurveToPoint ? 3 : el->type == kCGPathElementAddQuadCurveToPoint ? 2 : el->type == kCGPathElementCloseSubpath ? 0 : 1;
    for (int i = 0; i < n; i++) p[i] = CGPointApplyAffineTransform(el->points[i], a->t);
    switch (el->type) {
        case kCGPathElementMoveToPoint: pd_moveto(self, p[0].x, p[0].y); break;
        case kCGPathElementAddLineToPoint: pd_lineto(self, p[0].x, p[0].y); break;
        case kCGPathElementAddQuadCurveToPoint: pd_quadto(self, p[0], p[1]); break;
        case kCGPathElementAddCurveToPoint: pd_curveto(self, p[0].x, p[0].y, p[1].x, p[1].y, p[2].x, p[2].y); break;
        case kCGPathElementCloseSubpath:
            if (a->as_closepath) pd_closepath_ns(self);
            else pd_end_subpath(self);
            break;
    }
}

static void
pd_append_cg(PDPathObject *self, CGPathRef src, CGAffineTransform t, BOOL as_closepath)
{
    Append a = {self, t, as_closepath};
    CGPathRef walked = src == self->path ? CGPathCreateCopy(src) : CGPathRetain(src); // don't walk what's growing
    CGPathApply(walked, &a, pd_append_applier);
    CGPathRelease(walked);
}

// python interface

static PyTypeObject PDPathType;

static int
parse_doubles(PyObject *const *args, Py_ssize_t nargs, Py_ssize_t min, Py_ssize_t max, double *out)
{
    if (nargs < min || nargs > max) {
        PyErr_Format(PyExc_TypeError, "expected %zd to %zd arguments, got %zd", min, max, nargs);
        return -1;
    }
    for (Py_ssize_t i = 0; i < nargs; i++) {
        out[i] = PyFloat_AsDouble(args[i]);
        if (out[i] == -1.0 && PyErr_Occurred()) return -1;
    }
    return 0;
}

static int
parse_matrix(PyObject *obj, CGAffineTransform *t)
{
    PyObject *seq = PySequence_Fast(obj, "a transform matrix must be a sequence of 6 numbers");
    if (!seq) return -1;
    double m[6];
    int ok = PySequence_Fast_GET_SIZE(seq) == 6 ? 0 : -1;
    if (ok < 0) PyErr_SetString(PyExc_ValueError, "a transform matrix must have 6 values");
    for (int i = 0; ok == 0 && i < 6; i++) {
        m[i] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(seq, i));
        if (m[i] == -1.0 && PyErr_Occurred()) ok = -1;
    }
    Py_DECREF(seq);
    if (ok == 0) *t = CGAffineTransformMake(m[0], m[1], m[2], m[3], m[4], m[5]);
    return ok;
}

static PDPathObject *
pd_alloc(CGMutablePathRef path)
{
    PDPathObject *self = (PDPathObject *)PDPathType.tp_alloc(&PDPathType, 0);
    if (!self) {
        CGPathRelease(path);
        return NULL;
    }
    self->path = path;
    self->last = PD_EMPTY;
    return self;
}

static PyObject *
PDPath_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    // PDPath([src]): empty, or a copy of a PDPath or NSBezierPath with every close made as
    // closePath makes it, as NSBezierPath's copy makes them
    PyObject *src = NULL;
    if (!PyArg_ParseTuple(args, "|O:PDPath", &src)) return NULL;

    PDPathObject *self = pd_alloc(CGPathCreateMutable());
    if (!self || !src || src == Py_None) return (PyObject *)self;

    NSBezierPath *ns = unwrap_objc(src, "NSBezierPath");
    if (PyObject_TypeCheck(src, &PDPathType)) {
        pd_flush((PDPathObject *)src);
        pd_append_cg(self, ((PDPathObject *)src)->path, CGAffineTransformIdentity, YES);
    } else if (ns) {
        pd_append_ns(self, ns, NO, YES);
    } else {
        Py_DECREF(self);
        PyErr_Format(PyExc_TypeError, "can't make a PDPath from %s", Py_TYPE(src)->tp_name);
        return NULL;
    }
    return (PyObject *)self;
}

static void
PDPath_dealloc(PDPathObject *self)
{
    CGPathRelease(self->path);
    Py_XDECREF(self->elements);
    Py_XDECREF(self->proxy);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static Py_ssize_t
PDPath_len(PDPathObject *self)
{
    return self->count;
}

static PyObject *
PDPath_moveto(PDPathObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    double v[2];
    if (parse_doubles(args, nargs, 2, 2, v) < 0) return NULL;
    pd_moveto(self, v[0], v[1]);
    Py_RETURN_NONE;
}

static PyObject *
PDPath_lineto(PDPathObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    double v[2];
    if (parse_doubles(args, nargs, 2, 2, v) < 0) return NULL;
    if (self->last == PD_EMPTY) pd_moveto(self, 0, 0); // an implicit origin, as Bezier.lineto has
    pd_lineto(self, v[0], v[1]);
    Py_RETURN_NONE;
}

static PyObject *
PDPath_curveto(PDPathObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    double v[6];
    if (parse_doubles(args, nargs, 6, 6, v) < 0) return NULL;
    pd_curveto(self, v[0], v[1], v[2], v[3], v[4], v[5]);
    Py_RETURN_NONE;
}

static PyObject *
PDPath_closepath(PDPathObject *self, PyObject *unused)
{
    pd_close(self);
    Py_RETURN_NONE;
}

static PyObject *
PDPath_rect(PDPathObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    // rect(x, y, w, h[, rx, ry]): a rect, or a rounded one, with ns's elements
    double v[6];
    if (parse_doubles(args, nargs, 4, 6, v) < 0) return NULL;
    if (nargs == 5) {
        PyErr_SetString(PyExc_TypeError, "a rounded rect needs both radii");
        return NULL;
    }
    double x0 = fmin(v[0], v[0] + v[2]), y0 = fmin(v[1], v[1] + v[3]), x1 = x0 + fabs(v[2]), y1 = y0 + fabs(v[3]);
    if (nargs == 4) {
        pd_moveto(self, x0, y0);
        pd_lineto(self, x1, y0);
        pd_lineto(self, x1, y1);
        pd_lineto(self, x0, y1);
        pd_end_subpath(self);
        Py_RETURN_NONE;
    }

    // ns draws nothing for an empty or flipped rect, and a square-cornered one for a radius <= 0
    double w = v[2], h = v[3], rx = fmin(v[4], w / 2), ry = fmin(v[5], h / 2);
    if (!(w > 0 && h > 0)) Py_RETURN_NONE;
    if (rx <= 0 || ry <= 0) {
        pd_moveto(self, x0, y0);
        pd_lineto(self, x1, y0);
        pd_lineto(self, x1, y1);
        pd_lineto(self, x0, y1);
        pd_closepath_ns(self);
        Py_RETURN_NONE;
    }

    // ns's corners, counterclockwise from the top edge; each offset is its own statement so
    // the compiler can't fuse it into a multiply-add and round differently than ns
    double kx = rx * 0.55228, ky = ry * 0.55228;
    double left = x0 + rx, right = x1 - rx, bottom = y0 + ry, top = y1 - ry;
    pd_moveto(self, left, y1);
    pd_curveto(self, left - kx, y1, x0, top + ky, x0, top);
    pd_lineto(self, x0, bottom);
    pd_curveto(self, x0, bottom - ky, left - kx, y0, left, y0);
    pd_lineto(self, right, y0);
    pd_curveto(self, right + kx, y0, x1, bottom - ky, x1, bottom);
    pd_lineto(self, x1, top);
    pd_curveto(self, x1, top + ky, right + kx, y1, right, y1);
    pd_closepath_ns(self);
    Py_RETURN_NONE;
}

static PyObject *
PDPath_oval(PDPathObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    // oval(x, y, w, h): ns's four unclosed quarters from -45°, within a few ulps of its points
    double v[4];
    if (parse_doubles(args, nargs, 4, 4, v) < 0) return NULL;
    double rx = v[2] / 2, ry = v[3] / 2, cx = v[0] + rx, cy = v[1] + ry;
    double k = 4.0 / 3.0 * tan(M_PI / 8), a = -M_PI / 4;
    pd_moveto(self, cx + rx * cos(a), cy + ry * sin(a));
    for (int i = 0; i < 4; i++) {
        double b = a + M_PI / 2, ca = cos(a), sa = sin(a), cb = cos(b), sb = sin(b);
        pd_curveto(self, cx + rx * (ca - k * sa), cy + ry * (sa + k * ca), cx + rx * (cb + k * sb), cy + ry * (sb - k * cb), cx + rx * cb, cy + ry * sb);
        a = b;
    }
    Py_RETURN_NONE;
}

static PyObject *
PDPath_arc(PDPathObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    // arc(x, y, radius, start, end, clockwise): ns's arc around a center, in degrees, joined to
    // the current point by a line
    double v[6];
    if (parse_doubles(args, nargs, 6, 6, v) < 0) return NULL;
    double cx = v[0], cy = v[1], r = v[2], start = v[3], end = v[4];
    if (!isfinite(r) || !isfinite(start) || !isfinite(end)) {
        PyErr_SetString(PyExc_ValueError, "an arc's radius and angles must be finite");
        return NULL;
    }

    // wrap the sweep to the direction in degrees, where whole turns are exact (ns does it in
    // radians, so a non-integer start can tip a whole turn into nothing or a full circle)
    double sweep = end - start;
    if (v[5] != 0 && sweep > 0) sweep -= 360 * ceil(sweep / 360);
    if (v[5] == 0 && sweep < 0) sweep += 360 * ceil(-sweep / 360);

    double t0 = start * M_PI / 180;
    double x0 = cx + r * cos(t0), y0 = cy + r * sin(t0);
    if (self->last == PD_EMPTY) pd_moveto(self, x0, y0);
    else pd_lineto(self, x0, y0);

    // quarter turns or less, each with its controls along the tangents at its ends (or on the
    // ends for a step too small for cos to see, as ns does)
    for (double at = start, left = sweep; left != 0;) {
        double step = fmax(-90, fmin(90, left));
        double a = at * M_PI / 180, b = (at + step) * M_PI / 180;
        double ca = cos(a), sa = sin(a), cb = cos(b), sb = sin(b);
        double x1 = cx + r * cb, y1 = cy + r * sb;
        if (cos((b - a) / 2) == 1) {
            pd_curveto(self, cx + r * ca, cy + r * sa, x1, y1, x1, y1);
        } else {
            double k = 4.0 / 3.0 * tan((b - a) / 4);
            pd_curveto(self, cx + r * (ca - k * sa), cy + r * (sa + k * ca), cx + r * (cb + k * sb), cy + r * (sb - k * cb), x1, y1);
        }
        at += step;
        left -= step;
    }
    Py_RETURN_NONE;
}

static PyObject *
PDPath_arcto(PDPathObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    // arcto(x1, y1, x2, y2, radius): ns's arc from the current point toward x1,y1 then x2,y2,
    // made by ns in a scratch NSBezierPath that starts at the current point
    double v[5];
    if (parse_doubles(args, nargs, 5, 5, v) < 0) return NULL;
    if (self->last == PD_EMPTY) {
        PyErr_SetString(PyExc_ValueError, "No current point for arc");
        return NULL;
    }
    CGPoint cur = pd_current_point(self);
    NSBezierPath *ns = [[NSBezierPath alloc] init];
    [ns moveToPoint:NSMakePoint(cur.x, cur.y)];
    [ns appendBezierPathWithArcFromPoint:NSMakePoint(v[0], v[1]) toPoint:NSMakePoint(v[2], v[3]) radius:v[4]];
    pd_append_ns(self, ns, YES, NO);
    [ns release];
    Py_RETURN_NONE;
}

static PyObject *
PDPath_add(PDPathObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    // add(path[, matrix]): append another PDPath, transformed by a 6-tuple matrix if given, as ns's
    // appendBezierPath: would (it makes every close as closePath does, as transformBezierPath: does)
    if (nargs < 1 || nargs > 2 || !PyObject_TypeCheck(args[0], &PDPathType)) {
        PyErr_SetString(PyExc_TypeError, "add() takes a PDPath and an optional matrix");
        return NULL;
    }
    PDPathObject *other = (PDPathObject *)args[0];
    CGAffineTransform t = CGAffineTransformIdentity;
    if (nargs == 2 && args[1] != Py_None && parse_matrix(args[1], &t) < 0) return NULL;
    pd_flush(other);
    pd_append_cg(self, other->path, t, YES);
    Py_RETURN_NONE;
}

static PyObject *
PDPath_transformed(PDPathObject *self, PyObject *matrix)
{
    // a copy mapped by a 6-tuple matrix, as ns's transformBezierPath: makes one
    CGAffineTransform t;
    if (parse_matrix(matrix, &t) < 0) return NULL;
    PDPathObject *result = pd_alloc(CGPathCreateMutable());
    pd_flush(self);
    if (result) pd_append_cg(result, self->path, t, YES);
    return (PyObject *)result;
}

static PyObject *
PDPath_bounds(PDPathObject *self, PyObject *unused)
{
    // (x, y, w, h) of the path's outline (not its control points), or None if it's empty
    if (self->last == PD_EMPTY) Py_RETURN_NONE;
    pd_flush(self);
    CGRect r = CGPathGetPathBoundingBox(self->path);
    if (CGRectIsNull(r)) Py_RETURN_NONE;
    return Py_BuildValue("dddd", r.origin.x, r.origin.y, r.size.width, r.size.height);
}

static PyObject *
PDPath_contains(PDPathObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    double v[2];
    if (parse_doubles(args, nargs, 2, 2, v) < 0) return NULL;
    pd_flush(self);
    return PyBool_FromLong(CGPathContainsPoint(self->path, NULL, CGPointMake(v[0], v[1]), false));
}

static PyObject *
PDPath_current_point(PDPathObject *self, PyObject *unused)
{
    CGPoint p = pd_current_point(self);
    return Py_BuildValue("dd", p.x, p.y);
}

typedef struct {
    PyObject *list;
    int failed;
} Walk;

static void
walk_emit(Walk *w, int cmd, CGPoint *pts, int n)
{
    if (w->failed) return;
    PyObject *points = PyTuple_New(n);
    for (int i = 0; points && i < n; i++)
        PyTuple_SET_ITEM(points, i, Py_BuildValue("dd", pts[i].x, pts[i].y));
    PyObject *el = points ? Py_BuildValue("(iN)", cmd, points) : NULL;
    if (!el || PyList_Append(w->list, el) < 0) w->failed = 1;
    Py_XDECREF(el);
}

static void
walk_applier(void *info, const CGPathElement *el)
{
    Walk *w = (Walk *)info;
    switch (el->type) {
        case kCGPathElementMoveToPoint: walk_emit(w, PD_MOVETO, el->points, 1); break;
        case kCGPathElementAddLineToPoint: walk_emit(w, PD_LINETO, el->points, 1); break;
        case kCGPathElementAddCurveToPoint: walk_emit(w, PD_CURVETO, el->points, 3); break;
        case kCGPathElementCloseSubpath: walk_emit(w, PD_CLOSE, NULL, 0); break;
        case kCGPathElementAddQuadCurveToPoint: break; // never stored, since pd_quadto makes cubics
    }
}

static PyObject *
PDPath_elements(PDPathObject *self, PyObject *unused)
{
    // the path's elements, as NSBezierPath's codes: a tuple of (cmd, ((x, y), ...))
    if (!self->elements) {
        pd_flush(self);
        Walk w = {PyList_New(0), 0};
        if (!w.list) return NULL;
        CGPathApply(self->path, &w, walk_applier);
        if (w.failed) {
            Py_DECREF(w.list);
            return NULL;
        }
        self->elements = PyList_AsTuple(w.list);
        Py_DECREF(w.list);
        if (!self->elements) return NULL;
    }
    Py_INCREF(self->elements);
    return self->elements;
}

static PyObject *
PDPath_cgpath(PDPathObject *self, void *closure)
{
    // the path as pyobjc's CGPathRef, for Quartz calls (a live view of this path, not a copy)
    static PyTypeObject *cg_type = NULL;
    pd_flush(self);
    if (!self->proxy) {
        if (!cg_type && !(cg_type = pyobjc_type("Quartz", "CGPathRef"))) return NULL;
        self->proxy = wrap_objc(cg_type, (id)CGPathRetain(self->path), 0x20);
        if (!self->proxy) return NULL;
    }
    Py_INCREF(self->proxy);
    return self->proxy;
}

static PyMethodDef PDPath_methods[] = {
    {"moveto", (PyCFunction)(void(*)(void))PDPath_moveto, METH_FASTCALL, NULL},
    {"lineto", (PyCFunction)(void(*)(void))PDPath_lineto, METH_FASTCALL, NULL},
    {"curveto", (PyCFunction)(void(*)(void))PDPath_curveto, METH_FASTCALL, NULL},
    {"closepath", (PyCFunction)PDPath_closepath, METH_NOARGS, NULL},
    {"rect", (PyCFunction)(void(*)(void))PDPath_rect, METH_FASTCALL, NULL},
    {"oval", (PyCFunction)(void(*)(void))PDPath_oval, METH_FASTCALL, NULL},
    {"arc", (PyCFunction)(void(*)(void))PDPath_arc, METH_FASTCALL, NULL},
    {"arcto", (PyCFunction)(void(*)(void))PDPath_arcto, METH_FASTCALL, NULL},
    {"add", (PyCFunction)(void(*)(void))PDPath_add, METH_FASTCALL, NULL},
    {"transformed", (PyCFunction)PDPath_transformed, METH_O, NULL},
    {"bounds", (PyCFunction)PDPath_bounds, METH_NOARGS, NULL},
    {"contains", (PyCFunction)(void(*)(void))PDPath_contains, METH_FASTCALL, NULL},
    {"current_point", (PyCFunction)PDPath_current_point, METH_NOARGS, NULL},
    {"elements", (PyCFunction)PDPath_elements, METH_NOARGS, NULL},
    {NULL}
};

static PyGetSetDef PDPath_getset[] = {
    {"cgpath", (getter)PDPath_cgpath, NULL, NULL, NULL},
    {NULL}
};

static PySequenceMethods PDPath_sequence = {
    .sq_length = (lenfunc)PDPath_len,
};

static PyTypeObject PDPathType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_plotdevice.PDPath",
    .tp_doc = "A CGMutablePath with NSBezierPath's elements",
    .tp_basicsize = sizeof(PDPathObject),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = PDPath_new,
    .tp_dealloc = (destructor)PDPath_dealloc,
    .tp_methods = PDPath_methods,
    .tp_getset = PDPath_getset,
    .tp_as_sequence = &PDPath_sequence,
};

CGPathRef
PDPath_CGPath(PyObject *obj)
{
    if (!PyObject_TypeCheck(obj, &PDPathType)) return NULL;
    pd_flush((PDPathObject *)obj);
    return ((PDPathObject *)obj)->path;
}

PyObject *
PDPath_FromCGPath(CGPathRef path)
{
    PDPathObject *self = pd_alloc(CGPathCreateMutable());
    if (self) pd_append_cg(self, path, CGAffineTransformIdentity, YES);
    return (PyObject *)self;
}

int
PDPath_register(PyObject *module)
{
    if (PyType_Ready(&PDPathType) < 0) return -1;
    Py_INCREF(&PDPathType);
    return PyModule_AddObject(module, "PDPath", (PyObject *)&PDPathType);
}
