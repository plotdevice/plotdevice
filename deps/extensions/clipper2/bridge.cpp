#include "bridge.h"
#include "clipper2/clipper.core.h"
#include "clipper2/clipper.engine.h"
#include "clipper2/clipper.h"
#include <cmath>

using namespace Clipper2Lib;

struct PDContours {
    PathsD paths;
    bool open = false; // the last contour can still take points
    PointD start;      // where the last contour began
};

static void
begin_contour(PDContours *contours)
{
    // room for most flattened contours, so they rarely grow point by point
    contours->paths.emplace_back();
    contours->paths.back().reserve(32);
    contours->paths.back().push_back(contours->start);
    contours->open = true;
}

static void
end_contour(PDContours *contours)
{
    if (!contours->open) return;
    if (contours->paths.back().size() < 3) contours->paths.pop_back();
    contours->open = false;
}

PDContours *
pd_contours_new(void)
{
    return new PDContours();
}

void
pd_contours_moveto(PDContours *contours, double x, double y)
{
    end_contour(contours);
    contours->start = PointD(x, y);
    begin_contour(contours);
}

void
pd_contours_lineto(PDContours *contours, double x, double y)
{
    if (!contours->open) begin_contour(contours);
    contours->paths.back().push_back(PointD(x, y));
}

void
pd_contours_close(PDContours *contours)
{
    // a closed contour repeats its start
    if (contours->open) contours->paths.back().push_back(contours->start);
    end_contour(contours);
}

void
pd_contours_end(PDContours *contours)
{
    end_contour(contours);
}

void
pd_contours_free(PDContours *contours)
{
    delete contours;
}

static CGMutablePathRef
to_cgpath(const PathsD &paths)
{
    CGMutablePathRef path = CGPathCreateMutable();
    for (const PathD &contour : paths) {
        CGPathMoveToPoint(path, NULL, contour[0].x, contour[0].y);
        for (size_t v = 1; v < contour.size(); v++)
            CGPathAddLineToPoint(path, NULL, contour[v].x, contour[v].y);
        CGPathCloseSubpath(path);
    }
    return path;
}

static bool
boolean_op(PDBooleanOp op, const PDContours *a, const PDContours *b, PathsD &result)
{
    ClipType clipType;
    switch (op) {
        case PD_UNION:      clipType = ClipType::Union; break;
        case PD_INTERSECT:  clipType = ClipType::Intersection; break;
        case PD_DIFFERENCE: clipType = ClipType::Difference; break;
        case PD_XOR:        clipType = ClipType::Xor; break;
        default:            return false;
    }

    ClipperD clipper;
    clipper.AddSubject(a->paths);
    clipper.AddClip(b->paths);
    return clipper.Execute(clipType, FillRule::NonZero, result);
}

CGMutablePathRef
pd_contours_boolean(PDBooleanOp op, const PDContours *a, const PDContours *b)
{
    PathsD result;
    if (!boolean_op(op, a, b, result)) return NULL;
    return to_cgpath(result);
}

bool
pd_contours_intersect(const PDContours *a, const PDContours *b)
{
    PathsD result;
    return boolean_op(PD_INTERSECT, a, b, result) && !result.empty();
}

CGMutablePathRef
pd_contours_offset(const PDContours *contours, double delta, CGLineJoin join, double miterLimit)
{
    JoinType jt;
    switch (join) {
        case kCGLineJoinMiter: jt = JoinType::Miter; break;
        case kCGLineJoinRound: jt = JoinType::Round; break;
        case kCGLineJoinBevel: jt = JoinType::Bevel; break;
        default:               return NULL;
    }

    return to_cgpath(InflatePaths(contours->paths, delta, jt, EndType::Polygon, miterLimit));
}

CGMutablePathRef
pd_contours_simplify(const PDContours *contours, double epsilon)
{
    return to_cgpath(SimplifyPaths(contours->paths, epsilon, /*isClosedPath=*/true));
}

double
pd_contours_area(const PDContours *contours)
{
    // union the contours (at top precision) so the winding rule is applied before calculating area
    PathsD filled = Union(contours->paths, FillRule::NonZero, 8);
    return std::fabs(Area(filled));
}
