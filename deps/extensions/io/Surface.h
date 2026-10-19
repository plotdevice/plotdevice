//
//  Surface.h
//  PlotDevice
//
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
@property (readonly) CVPixelBufferRef pixelBuffer; // the buffer it draws into, if made from one (else NULL)
+ (instancetype)surfaceWithWidth:(NSInteger)width height:(NSInteger)height;
+ (instancetype)surfaceWithPixelBuffer:(CVPixelBufferRef)buffer; // an IOSurface-backed one, e.g. from a video encoder's pool
- (void)lock;
- (void)unlock;
@end
