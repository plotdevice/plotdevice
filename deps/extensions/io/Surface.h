//
//  Surface.h
//  PlotDevice
//
//

#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <IOSurface/IOSurfaceObjC.h>

@interface PDSurface : NSObject{
    IOSurface *_surface;
    CGContextRef _context;
    CGColorSpaceRef _space;
    NSInteger _width;
    NSInteger _height;
}
@property (readonly) IOSurface *surface;   // assign to a CALayer's contents
@property (readonly) CGContextRef context; // draw into this between lock and unlock
@property (readonly) NSInteger width;      // in pixels
@property (readonly) NSInteger height;
+ (instancetype)surfaceWithWidth:(NSInteger)width height:(NSInteger)height;
- (void)lock;
- (void)unlock;
@end
