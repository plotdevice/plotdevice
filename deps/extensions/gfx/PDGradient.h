//
//  PDGradient.h
//  PlotDevice
//
//  A CGGradient that fills paths and rects the way NSGradient does.
//

#import <Cocoa/Cocoa.h>

@interface PDGradient : NSObject <NSCopying>{
    CGGradientRef _gradient;
}
- (instancetype)initWithColors:(NSArray *)colors atLocations:(NSArray *)locations colorSpace:(CGColorSpaceRef)space;
- (void)drawInPath:(CGPathRef)path angle:(CGFloat)angle;
- (void)drawInPath:(CGPathRef)path relativeCenterPosition:(NSPoint)center;
- (void)drawInRect:(NSRect)rect angle:(CGFloat)angle;
- (void)drawInRect:(NSRect)rect relativeCenterPosition:(NSPoint)center;
@end
