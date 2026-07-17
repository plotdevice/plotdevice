// A small extern "C" adapter around Clipper2's boolean-op engine, so plain
// Objective-C (pathmatics.m) can call into it without needing Objective-C++.
// Mirrors the shape of gpc.h's gpc_polygon/gpc_polygon_clip API, which this
// replaces as the polygon-boolean backend for union/intersect/difference/xor.
#ifndef PD_CLIPPER2_BRIDGE_H
#define PD_CLIPPER2_BRIDGE_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct { double x, y; } PDPoint;
typedef struct { PDPoint *points; long count; } PDContour;
typedef struct { PDContour *contours; long count; } PDPolygon;

typedef enum { PD_UNION, PD_INTERSECT, PD_DIFFERENCE, PD_XOR } PDBooleanOp;

// Performs a boolean op between two polygons (each a list of closed
// contours), using the non-zero fill rule. This matters beyond styling: one
// of the two inputs can be a stroke-to-fill outline (see Bezier.trace()),
// whose offset curves self-overlap at sharp/concave corners -- under an
// even-odd rule that self-overlap reads as a hole (even-odd only cares about
// crossing *parity*), carving spurious notches out of the result. Non-zero
// treats any non-zero coverage as solid regardless of how many times it's
// covered, which is what a self-overlapping stroke outline actually means.
// Returns a newly-allocated result polygon, or NULL on failure. Caller must
// free a non-NULL result via pd_free_polygon.
PDPolygon *pd_polygon_boolean(PDBooleanOp op, const PDPolygon *a, const PDPolygon *b);

void pd_free_polygon(PDPolygon *poly);

#ifdef __cplusplus
}
#endif

#endif
