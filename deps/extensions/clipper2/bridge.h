// A small extern "C" adapter around Clipper2's boolean-op engine, so plain
// Objective-C (pathmatics.m) can call into it without needing Objective-C++.
// Paths come in as the contours of a flattened path and go back out as CGPaths.
#ifndef CLIPPER2_BRIDGE_H
#define CLIPPER2_BRIDGE_H

#include <CoreGraphics/CoreGraphics.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// A flattened path's contours, collected element by element. A close repeats
// the contour's start, a lineto after one starts a new contour there, and
// contours of fewer than 3 points (which can't enclose any area) are dropped
// as they end. Call pd_contours_end after the last element.
typedef struct PDContours PDContours;
PDContours *pd_contours_new(void);
void pd_contours_moveto(PDContours *contours, double x, double y);
void pd_contours_lineto(PDContours *contours, double x, double y);
void pd_contours_close(PDContours *contours);
void pd_contours_end(PDContours *contours);
void pd_contours_free(PDContours *contours);

typedef enum { PD_UNION, PD_INTERSECT, PD_DIFFERENCE, PD_XOR } PDBooleanOp;

// Performs a boolean op between two sets of contours, using the non-zero fill
// rule. This matters beyond styling: one of the two inputs can be a
// stroke-to-fill outline (see Bezier.trace()), whose offset curves self-overlap
// at sharp/concave corners -- under an even-odd rule that self-overlap reads as
// a hole (even-odd only cares about crossing *parity*), carving spurious notches
// out of the result. Non-zero treats any non-zero coverage as solid regardless
// of how many times it's covered, which is what a self-overlapping stroke
// outline actually means. Returns a new CGPath, or NULL on failure.
CGMutablePathRef pd_contours_boolean(PDBooleanOp op, const PDContours *a, const PDContours *b);

// Whether the two sets of contours' intersection covers any area.
bool pd_contours_intersect(const PDContours *a, const PDContours *b);

// Grows (delta > 0) or shrinks (delta < 0) the contours' boundary by delta,
// treating every contour as a closed polygon. Returns a new CGPath, or NULL
// for an unknown join.
CGMutablePathRef pd_contours_offset(const PDContours *contours, double delta,
                                    CGLineJoin join, double miterLimit);

// Reduces the contours' point count while keeping every remaining point
// within epsilon of the original boundary. Returns a new CGPath.
CGMutablePathRef pd_contours_simplify(const PDContours *contours, double epsilon);

// The area the contours will fill under the nonzero rule: holes subtract, but
// all non-overlapping contours add.
double pd_contours_area(const PDContours *contours);

#ifdef __cplusplus
}
#endif

#endif
