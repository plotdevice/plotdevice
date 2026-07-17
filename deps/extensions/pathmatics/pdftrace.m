#import "pathmatics.h"
#import <Quartz/Quartz.h>
#include <string.h>

// Traces the path-construction operators in a PDF's content stream (page 1
// only) into a single NSBezierPath, in the page's own (y-up, mediabox-relative)
// space. Recurses into Form XObjects invoked via `Do` (but not Image XObjects,
// and not soft-mask groups reachable only via an ExtGState `gs` -- those
// modulate alpha rather than contributing actual painted ink, so folding them
// in as if they were geometry would be wrong, not just incomplete).
// Used to build a vector clip()/mask() outline instead of a rasterized one.
//
// Path geometry is accumulated in *local* (pre-`cm`) coordinates and only
// transformed into page space at paint time (see `commit_paint`), rather than
// baking the CTM into each point as it's parsed. This is what lets stroked
// paths be converted into their equivalent fill outline correctly: stroking
// has to happen in the same local units the PDF declared its line width in,
// with the CTM applied to the already-stroked result afterward (matching
// `CGPathCreateCopyByStrokingPath`'s own `transform` semantics), or else
// anisotropic `cm`s would scale/shear the stroke width incorrectly.

typedef struct {
    PyObject_HEAD
    id        objc_object;
    int       flags;
} PDFTracePyObjCObject;

extern PyObject * build_objc_instance(PyTypeObject *ob_type, id obj);

#define MAX_CTM_STACK 128
#define MAX_FORM_DEPTH 16

// The subset of PDF graphics state this tracer cares about: the CTM plus the
// stroke attributes (all of which are saved/restored by q/Q together, same as
// the CTM is).
typedef struct {
    CGAffineTransform ctm;
    CGFloat           lineWidth;
    int               lineCap;    // matches CGLineCap's raw values (butt/round/square = 0/1/2)
    int               lineJoin;   // matches CGLineJoin's raw values (miter/round/bevel = 0/1/2)
    CGFloat           miterLimit;
} GState;

typedef struct {
    NSMutableArray    *chunkPaths;   // NSBezierPath*, each in local (pre-CTM) coordinates
    NSMutableArray    *chunkCTMs;    // NSValue-wrapped CGAffineTransform, parallel to chunkPaths
    NSBezierPath      *committed;    // finalized (actually painted) geometry, in page space
    NSBezierPath      *current;      // in-progress local-space path for the active chunk
    CGAffineTransform currentCTM;    // ctm that was active when `current` was started
    GState            gs;            // live graphics state
    GState            stack[MAX_CTM_STACK];
    int               depth;
    BOOL              hasCurrentPoint;
    CGPDFOperatorTableRef table;      // shared across recursive Do-invoked scans
    CGPDFDictionaryRef    resources;  // resources dict for /Do lookups at this level
    int                   formDepth;  // Form XObject recursion depth (distinct from q/Q `depth`)
} PDFTraceState;

// Forward declaration -- op_Do (below) recurses into a Form XObject's own
// content stream via this same function.
static NSBezierPath *
trace_content_stream(CGPDFContentStreamRef content, CGPDFOperatorTableRef table,
                      CGPDFDictionaryRef resources, CGAffineTransform initialCTM,
                      GState inheritedGS, int formDepth);

// Closes out the in-progress chunk (if it has any content) onto the chunk
// list, tagged with the CTM that was active while it was built, and starts a
// fresh empty chunk under whatever CTM is current now.
static void
close_chunk(PDFTraceState *st)
{
    if (![st->current isEmpty]) {
        [st->chunkPaths addObject:st->current];
        NSValue *ctmValue = [NSValue valueWithBytes:&st->currentCTM objCType:@encode(CGAffineTransform)];
        [st->chunkCTMs addObject:ctmValue];
    }
    st->current = [NSBezierPath bezierPath];
    st->currentCTM = st->gs.ctm;
    st->hasCurrentPoint = NO;
}

// Stamps the chunk's CTM the moment it starts accumulating content (called
// from the two operators that can begin a fresh subpath: `m` and `re`).
static void
ensure_chunk_ctm(PDFTraceState *st)
{
    if ([st->current isEmpty]) {
        st->currentCTM = st->gs.ctm;
    }
}

static void
op_m(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal x, y;
    if (!CGPDFScannerPopNumber(scanner, &y)) return;
    if (!CGPDFScannerPopNumber(scanner, &x)) return;
    ensure_chunk_ctm(st);
    [st->current moveToPoint:NSMakePoint(x, y)];
    st->hasCurrentPoint = YES;
}

static void
op_l(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal x, y;
    if (!CGPDFScannerPopNumber(scanner, &y)) return;
    if (!CGPDFScannerPopNumber(scanner, &x)) return;
    if (!st->hasCurrentPoint) return;
    [st->current lineToPoint:NSMakePoint(x, y)];
}

static void
op_c(CGPDFScannerRef scanner, void *info)
{
    // x1 y1 x2 y2 x3 y3 c -- cubic curve w/ two explicit control points
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal x1, y1, x2, y2, x3, y3;
    if (!CGPDFScannerPopNumber(scanner, &y3)) return;
    if (!CGPDFScannerPopNumber(scanner, &x3)) return;
    if (!CGPDFScannerPopNumber(scanner, &y2)) return;
    if (!CGPDFScannerPopNumber(scanner, &x2)) return;
    if (!CGPDFScannerPopNumber(scanner, &y1)) return;
    if (!CGPDFScannerPopNumber(scanner, &x1)) return;
    if (!st->hasCurrentPoint) return;
    [st->current curveToPoint:NSMakePoint(x3, y3)
              controlPoint1:NSMakePoint(x1, y1)
              controlPoint2:NSMakePoint(x2, y2)];
}

static void
op_v(CGPDFScannerRef scanner, void *info)
{
    // x2 y2 x3 y3 v -- cubic curve whose first control point is the current point
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal x2, y2, x3, y3;
    if (!CGPDFScannerPopNumber(scanner, &y3)) return;
    if (!CGPDFScannerPopNumber(scanner, &x3)) return;
    if (!CGPDFScannerPopNumber(scanner, &y2)) return;
    if (!CGPDFScannerPopNumber(scanner, &x2)) return;
    if (!st->hasCurrentPoint) return;
    NSPoint cur = [st->current currentPoint];
    [st->current curveToPoint:NSMakePoint(x3, y3)
              controlPoint1:cur
              controlPoint2:NSMakePoint(x2, y2)];
}

static void
op_y(CGPDFScannerRef scanner, void *info)
{
    // x1 y1 x3 y3 y -- cubic curve whose second control point is the endpoint
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal x1, y1, x3, y3;
    if (!CGPDFScannerPopNumber(scanner, &y3)) return;
    if (!CGPDFScannerPopNumber(scanner, &x3)) return;
    if (!CGPDFScannerPopNumber(scanner, &y1)) return;
    if (!CGPDFScannerPopNumber(scanner, &x1)) return;
    if (!st->hasCurrentPoint) return;
    [st->current curveToPoint:NSMakePoint(x3, y3)
              controlPoint1:NSMakePoint(x1, y1)
              controlPoint2:NSMakePoint(x3, y3)];
}

static void
op_h(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    if (!st->hasCurrentPoint) return;
    [st->current closePath];
}

static void
op_re(CGPDFScannerRef scanner, void *info)
{
    // x y w h re -- appends a closed rectangular subpath
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal x, y, w, h;
    if (!CGPDFScannerPopNumber(scanner, &h)) return;
    if (!CGPDFScannerPopNumber(scanner, &w)) return;
    if (!CGPDFScannerPopNumber(scanner, &y)) return;
    if (!CGPDFScannerPopNumber(scanner, &x)) return;
    ensure_chunk_ctm(st);
    [st->current moveToPoint:NSMakePoint(x, y)];
    [st->current lineToPoint:NSMakePoint(x + w, y)];
    [st->current lineToPoint:NSMakePoint(x + w, y + h)];
    [st->current lineToPoint:NSMakePoint(x, y + h)];
    [st->current closePath];
    st->hasCurrentPoint = YES;
}

static void
op_cm(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal a, b, c, d, e, f;
    if (!CGPDFScannerPopNumber(scanner, &f)) return;
    if (!CGPDFScannerPopNumber(scanner, &e)) return;
    if (!CGPDFScannerPopNumber(scanner, &d)) return;
    if (!CGPDFScannerPopNumber(scanner, &c)) return;
    if (!CGPDFScannerPopNumber(scanner, &b)) return;
    if (!CGPDFScannerPopNumber(scanner, &a)) return;
    CGAffineTransform m = CGAffineTransformMake(a, b, c, d, e, f);
    CGAffineTransform newCTM = CGAffineTransformConcat(m, st->gs.ctm);

    // if the in-progress chunk already has content, it was built under the
    // *old* ctm -- close it out before adopting the new one so each chunk
    // stays internally consistent with a single ctm (this only matters for
    // the unusual case of `cm` appearing mid-path; ordinarily it appears
    // once, right after `q`, before any path construction).
    if (![st->current isEmpty] && !CGAffineTransformEqualToTransform(newCTM, st->gs.ctm)) {
        close_chunk(st);
    }
    st->gs.ctm = newCTM;
}

static void
op_q(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    if (st->depth < MAX_CTM_STACK) {
        st->stack[st->depth++] = st->gs;
    }
}

static void
op_Q(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    if (st->depth > 0) {
        GState restored = st->stack[--st->depth];
        if (![st->current isEmpty] && !CGAffineTransformEqualToTransform(restored.ctm, st->gs.ctm)) {
            close_chunk(st);
        }
        st->gs = restored;
    }
}

static void
op_w(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal width;
    if (!CGPDFScannerPopNumber(scanner, &width)) return;
    st->gs.lineWidth = width;
}

static void
op_J(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal cap;
    if (!CGPDFScannerPopNumber(scanner, &cap)) return;
    st->gs.lineCap = (int)cap;
}

static void
op_j(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal join;
    if (!CGPDFScannerPopNumber(scanner, &join)) return;
    st->gs.lineJoin = (int)join;
}

static void
op_M(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    CGPDFReal limit;
    if (!CGPDFScannerPopNumber(scanner, &limit)) return;
    st->gs.miterLimit = limit;
}

// Replays a CGPath's segments onto a fresh NSBezierPath (the reverse of
// `bezier_to_cgpath` below) -- needed to fold CGPathCreateCopyByStrokingPath/
// CGPathCreateCopyByTransformingPath's output back into `committed`.
static void
_apply_cgpath_element(void *info, const CGPathElement *element)
{
    NSBezierPath *path = (NSBezierPath *)info;
    CGPoint *pts = element->points;
    switch (element->type) {
        case kCGPathElementMoveToPoint:
            [path moveToPoint:NSMakePoint(pts[0].x, pts[0].y)];
            break;
        case kCGPathElementAddLineToPoint:
            [path lineToPoint:NSMakePoint(pts[0].x, pts[0].y)];
            break;
        case kCGPathElementAddQuadCurveToPoint: {
            // elevate quadratic to cubic (NSBezierPath has no quad primitive)
            NSPoint cur = [path currentPoint];
            CGPoint c = pts[0], p = pts[1];
            NSPoint c1 = NSMakePoint(cur.x + (c.x - cur.x) * (2.0/3.0), cur.y + (c.y - cur.y) * (2.0/3.0));
            NSPoint c2 = NSMakePoint(p.x + (c.x - p.x) * (2.0/3.0), p.y + (c.y - p.y) * (2.0/3.0));
            [path curveToPoint:NSMakePoint(p.x, p.y) controlPoint1:c1 controlPoint2:c2];
            break;
        }
        case kCGPathElementAddCurveToPoint:
            [path curveToPoint:NSMakePoint(pts[2].x, pts[2].y)
                  controlPoint1:NSMakePoint(pts[0].x, pts[0].y)
                  controlPoint2:NSMakePoint(pts[1].x, pts[1].y)];
            break;
        case kCGPathElementCloseSubpath:
            [path closePath];
            break;
    }
}

static NSBezierPath *
cgpath_to_bezier(CGPathRef cgPath)
{
    NSBezierPath *path = [NSBezierPath bezierPath];
    if (cgPath) {
        CGPathApply(cgPath, path, _apply_cgpath_element);
    }
    return path;
}

// NSBezierPath -> CGPathRef (the reverse direction of the above), needed so
// local-space chunk geometry can be fed to CGPathCreateCopyByStrokingPath/
// CGPathCreateCopyByTransformingPath.
static CGPathRef
bezier_to_cgpath(NSBezierPath *nsPath)
{
    CGMutablePathRef path = CGPathCreateMutable();
    NSInteger numElements = [nsPath elementCount];
    NSPoint points[3];
    for (NSInteger i = 0; i < numElements; i++) {
        NSBezierPathElement elt = [nsPath elementAtIndex:i associatedPoints:points];
        if (elt == NSBezierPathElementMoveTo) {
            CGPathMoveToPoint(path, NULL, points[0].x, points[0].y);
        } else if (elt == NSBezierPathElementLineTo) {
            CGPathAddLineToPoint(path, NULL, points[0].x, points[0].y);
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunguarded-availability-new"
#if HAS_QUADRATIC_PATH_ELEMENTS
        } else if (elt == NSBezierPathElementCubicCurveTo) {
            CGPathAddCurveToPoint(path, NULL, points[0].x, points[0].y, points[1].x, points[1].y, points[2].x, points[2].y);
        } else if (elt == NSBezierPathElementQuadraticCurveTo) {
            CGPathAddQuadCurveToPoint(path, NULL, points[0].x, points[0].y, points[1].x, points[1].y);
#else
        } else if (elt == NSBezierPathElementCurveTo) {
            CGPathAddCurveToPoint(path, NULL, points[0].x, points[0].y, points[1].x, points[1].y, points[2].x, points[2].y);
#endif
#pragma clang diagnostic pop
        } else if (elt == NSBezierPathElementClosePath) {
            CGPathCloseSubpath(path);
        }
    }
    return path;
}

// Closes out any in-progress chunk, then folds every accumulated chunk's fill
// and/or stroke contribution (as applicable) into `committed`, each
// transformed by its own chunk's ctm. `shouldClose` mirrors the implicit
// closepath that `s`/`b`/`b*` apply before stroking (PDF spec: `s` == `h S`,
// `b`/`b*` == `h B`/`h B*`) -- without it, a stroked shape that relies on
// that implicit close would get end caps instead of a proper join at the seam.
static void
commit_paint(PDFTraceState *st, BOOL doFill, BOOL doStroke, BOOL shouldClose)
{
    if (shouldClose) {
        [st->current closePath];
    }
    close_chunk(st);

    NSUInteger n = [st->chunkPaths count];
    for (NSUInteger i = 0; i < n; i++) {
        NSBezierPath *localPath = st->chunkPaths[i];
        CGAffineTransform chunkCTM;
        [st->chunkCTMs[i] getValue:&chunkCTM];
        CGPathRef localCGPath = bezier_to_cgpath(localPath);

        if (doFill) {
            CGPathRef filledCGPath = CGPathCreateCopyByTransformingPath(localCGPath, &chunkCTM);
            if (filledCGPath) {
                [st->committed appendBezierPath:cgpath_to_bezier(filledCGPath)];
                CGPathRelease(filledCGPath);
            }
        }

        if (doStroke) {
            CGPathRef strokedCGPath = CGPathCreateCopyByStrokingPath(localCGPath, &chunkCTM,
                st->gs.lineWidth, (CGLineCap)st->gs.lineCap, (CGLineJoin)st->gs.lineJoin, st->gs.miterLimit);
            if (strokedCGPath) {
                [st->committed appendBezierPath:cgpath_to_bezier(strokedCGPath)];
                CGPathRelease(strokedCGPath);
            }
        }

        CGPathRelease(localCGPath);
    }

    [st->chunkPaths removeAllObjects];
    [st->chunkCTMs removeAllObjects];
}

static void op_fill(CGPDFScannerRef scanner, void *info) { commit_paint((PDFTraceState *)info, YES, NO, NO); }
static void op_stroke(CGPDFScannerRef scanner, void *info) { commit_paint((PDFTraceState *)info, NO, YES, NO); }
static void op_closestroke(CGPDFScannerRef scanner, void *info) { commit_paint((PDFTraceState *)info, NO, YES, YES); }
static void op_fillstroke(CGPDFScannerRef scanner, void *info) { commit_paint((PDFTraceState *)info, YES, YES, NO); }
static void op_closefillstroke(CGPDFScannerRef scanner, void *info) { commit_paint((PDFTraceState *)info, YES, YES, YES); }

// n -- ends the current path without painting it (typically used to install
// a clip region via a preceding W/W*). Discard rather than commit: the path
// itself never produced any visible ink.
static void
op_n(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    st->current = [NSBezierPath bezierPath];
    st->hasCurrentPoint = NO;
    [st->chunkPaths removeAllObjects];
    [st->chunkCTMs removeAllObjects];
}

// Do -- invokes an XObject. Image XObjects have no vector geometry and are
// skipped; Form XObjects are recursively traced (their own content stream,
// scanned with the graphics state active at this call as a starting point,
// per PDF spec 8.10.2) and their resulting page-space geometry is folded
// straight into `committed`.
static void
op_Do(CGPDFScannerRef scanner, void *info)
{
    PDFTraceState *st = (PDFTraceState *)info;
    const char *name;
    if (!CGPDFScannerPopName(scanner, &name)) return;
    if (st->formDepth >= MAX_FORM_DEPTH || !st->resources) return;

    CGPDFContentStreamRef currentStream = CGPDFScannerGetContentStream(scanner);
    CGPDFObjectRef obj = CGPDFContentStreamGetResource(currentStream, "XObject", name);
    if (!obj) return;
    CGPDFStreamRef xobjStream;
    if (!CGPDFObjectGetValue(obj, kCGPDFObjectTypeStream, &xobjStream)) return;

    CGPDFDictionaryRef xobjDict = CGPDFStreamGetDictionary(xobjStream);
    const char *subtype;
    if (!CGPDFDictionaryGetName(xobjDict, "Subtype", &subtype) || strcmp(subtype, "Form") != 0) {
        return; // Image XObjects (or anything unrecognized) have no vector geometry to trace
    }

    CGAffineTransform formMatrix = CGAffineTransformIdentity;
    CGPDFArrayRef matrixArray;
    if (CGPDFDictionaryGetArray(xobjDict, "Matrix", &matrixArray) && CGPDFArrayGetCount(matrixArray) == 6) {
        CGPDFReal m[6];
        for (int i = 0; i < 6; i++) CGPDFArrayGetNumber(matrixArray, i, &m[i]);
        formMatrix = CGAffineTransformMake(m[0], m[1], m[2], m[3], m[4], m[5]);
    }
    CGAffineTransform formCTM = CGAffineTransformConcat(formMatrix, st->gs.ctm);

    // CGPDFDictionaryGetDictionary clobbers its out-param even when the key
    // is absent, so read into a scratch variable and only adopt it on success
    // -- otherwise a Form with no /Resources of its own would lose the
    // fallback to the invoker's resources.
    CGPDFDictionaryRef formResources = st->resources; // fallback: inherit invoker's
    CGPDFDictionaryRef ownResources;
    if (CGPDFDictionaryGetDictionary(xobjDict, "Resources", &ownResources)) {
        formResources = ownResources;
    }
    if (!formResources) return; // can't safely call CreateWithStream without one

    CGPDFContentStreamRef formContent =
        CGPDFContentStreamCreateWithStream(xobjStream, formResources, currentStream);
    NSBezierPath *nested = trace_content_stream(formContent, st->table, formResources,
                                                 formCTM, st->gs, st->formDepth + 1);
    CGPDFContentStreamRelease(formContent);

    [st->committed appendBezierPath:nested];
}

// Scans a single content stream (the page's own, or a Form XObject's, when
// recursing via `op_Do`) into a fresh NSBezierPath. `resources` is whatever
// resource dictionary is in scope for resolving this stream's own `Do` calls;
// `inheritedGS` seeds the graphics state (only `ctm` is overridden), matching
// PDF spec 8.10.2: a Form XObject's content stream runs in a copy of the
// invoker's graphics state, not a fresh default one.
static NSBezierPath *
trace_content_stream(CGPDFContentStreamRef content, CGPDFOperatorTableRef table,
                      CGPDFDictionaryRef resources, CGAffineTransform initialCTM,
                      GState inheritedGS, int formDepth)
{
    PDFTraceState state;
    state.committed = [NSBezierPath bezierPath];
    state.current = [NSBezierPath bezierPath];
    state.chunkPaths = [NSMutableArray array];
    state.chunkCTMs = [NSMutableArray array];
    state.gs = inheritedGS;
    state.gs.ctm = initialCTM;
    state.currentCTM = initialCTM;
    state.depth = 0;
    state.hasCurrentPoint = NO;
    state.table = table;
    state.resources = resources;
    state.formDepth = formDepth;

    CGPDFScannerRef scanner = CGPDFScannerCreate(content, table, &state);
    CGPDFScannerScan(scanner);
    CGPDFScannerRelease(scanner);

    return state.committed;
}

static NSBezierPath *
trace_pdf_outline(NSData *pdfData)
{
    CGDataProviderRef provider = CGDataProviderCreateWithCFData((CFDataRef)pdfData);
    if (!provider) return nil;

    CGPDFDocumentRef document = CGPDFDocumentCreateWithProvider(provider);
    CGDataProviderRelease(provider);
    if (!document) return nil;

    CGPDFPageRef page = CGPDFDocumentGetPage(document, 1);
    if (!page) {
        CGPDFDocumentRelease(document);
        return nil;
    }

    CGRect mediaBox = CGPDFPageGetBoxRect(page, kCGPDFMediaBox);
    int rotate = (int)CGPDFPageGetRotationAngle(page);
    CGRect target = (rotate == 90 || rotate == 270)
        ? CGRectMake(0, 0, mediaBox.size.height, mediaBox.size.width)
        : CGRectMake(0, 0, mediaBox.size.width, mediaBox.size.height);
    CGAffineTransform initial = CGPDFPageGetDrawingTransform(page, kCGPDFMediaBox, target, rotate, true);

    CGPDFDictionaryRef resources = NULL;
    CGPDFDictionaryGetDictionary(CGPDFPageGetDictionary(page), "Resources", &resources);

    GState initialGS;
    initialGS.ctm = initial;
    initialGS.lineWidth = 1.0;   // PDF spec 8.4.3.2 default
    initialGS.lineCap = 0;       // butt
    initialGS.lineJoin = 0;      // miter
    initialGS.miterLimit = 10.0;

    CGPDFOperatorTableRef table = CGPDFOperatorTableCreate();
    CGPDFOperatorTableSetCallback(table, "m", op_m);
    CGPDFOperatorTableSetCallback(table, "l", op_l);
    CGPDFOperatorTableSetCallback(table, "c", op_c);
    CGPDFOperatorTableSetCallback(table, "v", op_v);
    CGPDFOperatorTableSetCallback(table, "y", op_y);
    CGPDFOperatorTableSetCallback(table, "h", op_h);
    CGPDFOperatorTableSetCallback(table, "re", op_re);
    CGPDFOperatorTableSetCallback(table, "cm", op_cm);
    CGPDFOperatorTableSetCallback(table, "q", op_q);
    CGPDFOperatorTableSetCallback(table, "Q", op_Q);
    CGPDFOperatorTableSetCallback(table, "w", op_w);
    CGPDFOperatorTableSetCallback(table, "J", op_J);
    CGPDFOperatorTableSetCallback(table, "j", op_j);
    CGPDFOperatorTableSetCallback(table, "M", op_M);
    CGPDFOperatorTableSetCallback(table, "f", op_fill);
    CGPDFOperatorTableSetCallback(table, "F", op_fill);
    CGPDFOperatorTableSetCallback(table, "f*", op_fill);
    CGPDFOperatorTableSetCallback(table, "S", op_stroke);
    CGPDFOperatorTableSetCallback(table, "s", op_closestroke);
    CGPDFOperatorTableSetCallback(table, "B", op_fillstroke);
    CGPDFOperatorTableSetCallback(table, "B*", op_fillstroke);
    CGPDFOperatorTableSetCallback(table, "b", op_closefillstroke);
    CGPDFOperatorTableSetCallback(table, "b*", op_closefillstroke);
    CGPDFOperatorTableSetCallback(table, "n", op_n);
    CGPDFOperatorTableSetCallback(table, "Do", op_Do);

    CGPDFContentStreamRef content = CGPDFContentStreamCreateWithPage(page);
    NSBezierPath *committed = trace_content_stream(content, table, resources, initial, initialGS, 0);
    CGPDFContentStreamRelease(content);

    CGPDFOperatorTableRelease(table);
    CGPDFDocumentRelease(document);

    [committed setWindingRule:NSWindingRuleNonZero];
    return committed;
}

// Traces the vector shapes in `pdfData` (the raw bytes of a PDF file, page 1
// only) into a single NSBezierPath. The second argument is an existing
// NSBezierPath instance used purely to identify the PyObjC wrapper type for
// the returned object (mirroring the pattern used by cPathmatics_operation).
PyObject *
cPathmatics_pdfOutline(PyObject *self, PyObject *args)
{
    PyObject *pyData, *pyTemplatePath;
    if (!PyArg_ParseTuple(args, "OO", &pyData, &pyTemplatePath))
        return NULL;

    // NSData is a class cluster -- concrete instances are private subclasses
    // (NSConcreteData, __NSCFData, etc), so match on a substring rather than
    // requiring the exact "NSData" type name.
    if (strstr(pyData->ob_type->tp_name, "Data") == NULL) {
        PyErr_SetString(PyExc_TypeError, "first argument is not NSData");
        return NULL;
    }
    if (strcmp("NSBezierPath", pyTemplatePath->ob_type->tp_name) != 0) {
        PyErr_SetString(PyExc_TypeError, "second argument is not a NSBezierPath");
        return NULL;
    }

    NSData *pdfData = ((PDFTracePyObjCObject *) pyData)->objc_object;
    NSBezierPath *outline = trace_pdf_outline(pdfData);
    if (!outline) {
        outline = [NSBezierPath bezierPath];
    }
    [outline retain];

    return build_objc_instance(pyTemplatePath->ob_type, outline);
}
