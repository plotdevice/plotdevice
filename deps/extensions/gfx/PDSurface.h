//
//  PDSurface.h
//  PlotDevice
//
//  An IOSurface-backed render target for windows and exports.
//

#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <IOSurface/IOSurfaceObjC.h>
#import <CoreVideo/CoreVideo.h>

@interface PDSurface : NSObject{
    IOSurface *_surface;
    CGContextRef _context;
    CGColorSpaceRef _space;
    CVPixelBufferRef _pixelBuffer;
    NSInteger _width;
    NSInteger _height;
}
@property (readonly) IOSurface *surface;   // assign to a CALayer's contents
@property (readonly) CGContextRef context; // draw into this between lock and unlock
@property (readonly) NSInteger width;      // in pixels
@property (readonly) NSInteger height;
@property (readonly) CVPixelBufferRef pixelBuffer; // unset if not derived from one
+ (instancetype)surfaceWithWidth:(NSInteger)width height:(NSInteger)height;
+ (instancetype)surfaceWithWidth:(NSInteger)width height:(NSInteger)height space:(CGColorSpaceRef)space; // P3 by default
+ (instancetype)surfaceWithPixelBuffer:(CVPixelBufferRef)buffer space:(CGColorSpaceRef)space;
- (instancetype)initWithWidth:(NSInteger)width height:(NSInteger)height space:(CGColorSpaceRef)space;
- (void)lock;
- (void)unlock;
@end
