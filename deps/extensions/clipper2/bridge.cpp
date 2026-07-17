#include "bridge.h"
#include "clipper2/clipper.core.h"
#include "clipper2/clipper.engine.h"
#include "clipper2/clipper.h"
#include <cstdlib>
#include <cmath>

using namespace Clipper2Lib;

static PathsD
to_paths(const PDPolygon *poly)
{
    PathsD paths;
    paths.reserve(poly->count);
    for (long c = 0; c < poly->count; c++) {
        const PDContour &contour = poly->contours[c];
        PathD path;
        path.reserve(contour.count);
        for (long v = 0; v < contour.count; v++) {
            path.push_back(PointD(contour.points[v].x, contour.points[v].y));
        }
        paths.push_back(std::move(path));
    }
    return paths;
}

static PDPolygon *
from_paths(const PathsD &paths)
{
    PDPolygon *poly = (PDPolygon *)malloc(sizeof(PDPolygon));
    poly->count = (long)paths.size();
    poly->contours = (PDContour *)malloc(sizeof(PDContour) * (size_t)poly->count);
    for (size_t c = 0; c < paths.size(); c++) {
        const PathD &path = paths[c];
        PDContour &contour = poly->contours[c];
        contour.count = (long)path.size();
        contour.points = (PDPoint *)malloc(sizeof(PDPoint) * path.size());
        for (size_t v = 0; v < path.size(); v++) {
            contour.points[v].x = path[v].x;
            contour.points[v].y = path[v].y;
        }
    }
    return poly;
}

PDPolygon *
pd_polygon_boolean(PDBooleanOp op, const PDPolygon *a, const PDPolygon *b)
{
    PathsD subjects = to_paths(a);
    PathsD clips = to_paths(b);

    ClipType clipType;
    switch (op) {
        case PD_UNION:      clipType = ClipType::Union; break;
        case PD_INTERSECT:  clipType = ClipType::Intersection; break;
        case PD_DIFFERENCE: clipType = ClipType::Difference; break;
        case PD_XOR:        clipType = ClipType::Xor; break;
        default:            return NULL;
    }

    PathsD result;
    ClipperD clipper;
    clipper.AddSubject(subjects);
    clipper.AddClip(clips);
    if (!clipper.Execute(clipType, FillRule::NonZero, result)) {
        return NULL;
    }

    return from_paths(result);
}

void
pd_free_polygon(PDPolygon *poly)
{
    if (!poly) return;
    for (long c = 0; c < poly->count; c++) {
        free(poly->contours[c].points);
    }
    free(poly->contours);
    free(poly);
}

PDPolygon *
pd_polygon_offset(const PDPolygon *poly, double delta, CGLineJoin join, double miterLimit)
{
    PathsD paths = to_paths(poly);

    JoinType jt;
    switch (join) {
        case kCGLineJoinMiter: jt = JoinType::Miter; break;
        case kCGLineJoinRound: jt = JoinType::Round; break;
        case kCGLineJoinBevel: jt = JoinType::Bevel; break;
        default:               return NULL;
    }

    PathsD result = InflatePaths(paths, delta, jt, EndType::Polygon, miterLimit);
    return from_paths(result);
}

PDPolygon *
pd_polygon_simplify(const PDPolygon *poly, double epsilon)
{
    PathsD paths = to_paths(poly);
    PathsD result = SimplifyPaths(paths, epsilon, /*isClosedPath=*/true);
    return from_paths(result);
}

double
pd_polygon_area(const PDPolygon *poly)
{
    // union the contours (at top precision) so the winding rule is applied before calculating area
    PathsD filled = Union(to_paths(poly), FillRule::NonZero, 8);
    return std::fabs(Area(filled));
}
