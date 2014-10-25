//
//  Vandercook.h
//  PlotDevice
//
//  Created by Christian Swinehart on 10/24/14.
//
//

#import <AppKit/AppKit.h>

@interface Vandercook : NSObject
+ (CGPathRef)cgPath:(NSBezierPath *)nsPath;
+ (NSBezierPath *)traceGlyphs:(NSRange)glyph_range atOffset:(NSPoint)offset withLayout:(NSLayoutManager *)layout;
@end
