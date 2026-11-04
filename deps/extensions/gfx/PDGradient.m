//
//  PDGradient.m
//  PlotDevice
//

#import "PDGradient.h"
#include <dlfcn.h>

typedef CGGradientRef (*GradientWithOptions)(CGColorSpaceRef, CFArrayRef, const CGFloat *, CFDictionaryRef);

static CGContextRef begin(void){
    CGContextRef port = [[NSGraphicsContext currentContext] CGContext];
    CGContextSaveGState(port);
    CGContextSetRenderingIntent(port, kCGRenderingIntentPerceptual);
    return port;
}

static void clipTo(CGContextRef port, CGPathRef path){
    CGContextSetFlatness(port, 0.6);
    CGContextBeginPath(port);
    CGContextAddPath(port, path);
    CGContextClip(port);
}

static void drawRadial(CGContextRef port, CGGradientRef gradient, CGRect box, NSPoint rel){
    // centered at the specified relative position within the box, extending to its farthest corner
    CGFloat w = box.size.width, h = box.size.height;
    CGPoint c = CGPointMake(CGRectGetMidX(box) + rel.x * w / 2, CGRectGetMidY(box) + rel.y * h / 2);
    CGFloat radius = 0;
    for (int i=0; i<4; i++){
        CGFloat x = box.origin.x + (i & 1 ? w : 0), y = box.origin.y + (i & 2 ? h : 0);
        radius = fmax(radius, hypot(c.x - x, c.y - y));
    }
    CGContextDrawRadialGradient(port, gradient, c, 0, c, radius, 0);
}

@implementation PDGradient

- (instancetype)initWithColors:(NSArray *)colors atLocations:(NSArray *)locations colorSpace:(CGColorSpaceRef)space{
    if (!(self = [super init])) return nil;

    // interpolating with premultiplied values (like NSGradient does) requires looking up an un-declared function
    static GradientWithOptions createWithOptions;
    static CFStringRef premultiplied;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        createWithOptions = (GradientWithOptions)dlsym(RTLD_DEFAULT, "CGGradientCreateWithColorsAndOptions");
        CFStringRef *key = (CFStringRef *)dlsym(RTLD_DEFAULT, "kCGGradientInterpolatesPremultiplied");
        premultiplied = key ? *key : NULL;
    });

    NSUInteger count = locations.count;
    CGFloat locs[count];
    for (NSUInteger i=0; i<count; i++) locs[i] = [locations[i] doubleValue];
    if (createWithOptions && premultiplied){
        NSDictionary *opts = @{(id)premultiplied: @YES};
        _gradient = createWithOptions(space, (CFArrayRef)colors, locs, (CFDictionaryRef)opts);
    }else{
        _gradient = CGGradientCreateWithColors(space, (CFArrayRef)colors, locs);
    }
    return self;
}

- (void)dealloc{
    CGGradientRelease(_gradient);
    [super dealloc];
}

- (id)copyWithZone:(NSZone *)zone{
    return [self retain]; // immutable
}

- (void)drawInPath:(CGPathRef)path angle:(CGFloat)angle{
    if (CGPathIsEmpty(path)) return;
    CGContextRef port = begin();
    clipTo(port, path);

    // fit the gradient to the path's extent along the angle by un-rotating it and spanning its bounds rect
    CGAffineTransform turn = CGAffineTransformMakeRotation(angle * M_PI / 180);
    CGAffineTransform unturn = CGAffineTransformInvert(turn);
    CGPathRef turned = CGPathCreateCopyByTransformingPath(path, &unturn);
    CGRect box = CGPathGetPathBoundingBox(turned);
    CGPathRelease(turned);
    CGPoint start = CGPointApplyAffineTransform(box.origin, turn);
    CGPoint end = CGPointApplyAffineTransform(CGPointMake(CGRectGetMaxX(box), box.origin.y), turn);
    CGContextDrawLinearGradient(port, _gradient, start, end, 0);
    CGContextRestoreGState(port);
}

- (void)drawInPath:(CGPathRef)path relativeCenterPosition:(NSPoint)center{
    if (CGPathIsEmpty(path)) return;
    CGContextRef port = begin();
    clipTo(port, path);
    drawRadial(port, _gradient, CGPathGetPathBoundingBox(path), center);
    CGContextRestoreGState(port);
}

- (void)drawInRect:(NSRect)rect angle:(CGFloat)angle{
    CGContextRef port = begin();
    CGContextClipToRect(port, rect);

    // fit the gradient to the rect's extent along the angle, centered at its midpoint
    CGFloat t = angle * M_PI / 180, dx = cos(t), dy = sin(t);
    CGFloat reach = (rect.size.width * fabs(dx) + rect.size.height * fabs(dy)) / 2;
    CGFloat cx = NSMidX(rect), cy = NSMidY(rect);
    CGContextDrawLinearGradient(port, _gradient, CGPointMake(cx - reach * dx, cy - reach * dy), CGPointMake(cx + reach * dx, cy + reach * dy), 0);
    CGContextRestoreGState(port);
}

- (void)drawInRect:(NSRect)rect relativeCenterPosition:(NSPoint)center{
    CGContextRef port = begin();
    CGContextClipToRect(port, rect);
    drawRadial(port, _gradient, rect, center);
    CGContextRestoreGState(port);
}

@end
