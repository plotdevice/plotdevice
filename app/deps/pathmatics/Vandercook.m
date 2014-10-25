//
//  Vandercook.m
//  PlotDevice
//
//  Created by Christian Swinehart on 10/24/14.
//
//

#import "Vandercook.h"

@implementation Vandercook

+ (NSBezierPath *)traceGlyphs:(NSRange)glyph_range atOffset:(NSPoint)offset withLayout:(NSLayoutManager *)layout{
    NSBezierPath *path = [NSBezierPath bezierPath];
    NSTextStorage *store = layout.textStorage;
    NSUInteger start = glyph_range.location;
    NSUInteger end = start + glyph_range.length;

    for (NSUInteger glyph_idx=start; glyph_idx<end; glyph_idx++){
        // don't draw tabs, newlines, etc.
        if([layout notShownAttributeForGlyphAtIndex:glyph_idx]) continue;

        // shift the glyph's location by the line- and frame-offsets
        NSRect line_rect = [layout lineFragmentRectForGlyphAtIndex:glyph_idx effectiveRange:nil];
        NSPoint glyph_pt = [layout locationForGlyphAtIndex:glyph_idx];
        glyph_pt.x += line_rect.origin.x + offset.x;
        glyph_pt.y += line_rect.origin.y + offset.y;
        glyph_pt.y *= -1;
        [path moveToPoint:glyph_pt];

        // add the glyph to the path
        NSUInteger txt_idx = [layout characterIndexForGlyphAtIndex:glyph_idx];
        NSFont *font = [store attribute:@"NSFont" atIndex:txt_idx effectiveRange:nil];
        NSGlyph glyph = [layout glyphAtIndex:glyph_idx];
        [path appendBezierPathWithGlyph:glyph inFont:font];
        [path closePath];
    }

    return path;

}

+ (CGPathRef)cgPath:(NSBezierPath *)nsPath{
    NSInteger i, numElements;

    // Need to begin a path here.
    CGPathRef           immutablePath = NULL;

    // Then draw the path elements.
    numElements = [nsPath elementCount];
    if (numElements > 0){
        CGMutablePathRef    path = CGPathCreateMutable();
        NSPoint             points[3];
        BOOL                didClosePath = YES;

        for (i = 0; i < numElements; i++){
            switch ([nsPath elementAtIndex:i associatedPoints:points]){
                case NSMoveToBezierPathElement:
                    CGPathMoveToPoint(path, NULL, points[0].x, points[0].y);
                    break;

                case NSLineToBezierPathElement:
                    CGPathAddLineToPoint(path, NULL, points[0].x, points[0].y);
                    didClosePath = NO;
                    break;

                case NSCurveToBezierPathElement:
                    CGPathAddCurveToPoint(path, NULL, points[0].x, points[0].y,
                                        points[1].x, points[1].y,
                                        points[2].x, points[2].y);
                    didClosePath = NO;
                    break;

                case NSClosePathBezierPathElement:
                    CGPathCloseSubpath(path);
                    didClosePath = YES;
                    break;
            }
        }

        // Be sure the path is closed or Quartz may not do valid hit detection.
        if (!didClosePath)
            CGPathCloseSubpath(path);

        immutablePath = CGPathCreateCopy(path);
        CGPathRelease(path);
    }

    return immutablePath;
}

@end
