//
//  Surface.m
//  PlotDevice
//

#import <CoreVideo/CoreVideo.h>
#import "Surface.h"

@implementation PDSurface

@synthesize pixelBuffer=_pixelBuffer;

+ (instancetype)surfaceWithWidth:(NSInteger)width height:(NSInteger)height{
    return [[[self alloc] initWithWidth:width height:height] autorelease];
}

+ (instancetype)surfaceWithWidth:(NSInteger)width height:(NSInteger)height space:(CGColorSpaceRef)space{
    return [[[self alloc] initWithWidth:width height:height space:space] autorelease];
}

+ (instancetype)surfaceWithPixelBuffer:(CVPixelBufferRef)buffer{
    return [[[self alloc] initWithPixelBuffer:buffer] autorelease];
}

+ (instancetype)surfaceWithPixelBuffer:(CVPixelBufferRef)buffer space:(CGColorSpaceRef)space{
    IOSurface *surface = buffer ? (IOSurface *)CVPixelBufferGetIOSurface(buffer) : nil;
    return [[[self alloc] initWithSurface:surface pixelBuffer:buffer space:space] autorelease];
}

- (instancetype)initWithWidth:(NSInteger)width height:(NSInteger)height{
    return [self initWithWidth:width height:height space:NULL];
}

- (instancetype)initWithWidth:(NSInteger)width height:(NSInteger)height space:(CGColorSpaceRef)space{
    IOSurface *surface = [[IOSurface alloc] initWithProperties:@{
        IOSurfacePropertyKeyWidth: @(width),
        IOSurfacePropertyKeyHeight: @(height),
        IOSurfacePropertyKeyBytesPerElement: @4,
        IOSurfacePropertyKeyPixelFormat: @(kCVPixelFormatType_32BGRA),
    }];
    self = [self initWithSurface:surface pixelBuffer:NULL space:space];
    [surface release];
    return self;
}

- (instancetype)initWithPixelBuffer:(CVPixelBufferRef)buffer{
    IOSurface *surface = buffer ? (IOSurface *)CVPixelBufferGetIOSurface(buffer) : nil;
    return [self initWithSurface:surface pixelBuffer:buffer space:NULL];
}

- (instancetype)initWithSurface:(IOSurface *)surface pixelBuffer:(CVPixelBufferRef)buffer space:(CGColorSpaceRef)space{
    if ((self = [super init])){
        if (!surface){
            [self release];
            return nil;
        }
        _surface = [surface retain];
        _pixelBuffer = buffer ? CVPixelBufferRetain(buffer) : NULL;
        _width = surface.width;
        _height = surface.height;
        _space = space ? CGColorSpaceRetain(space) : CGColorSpaceCreateWithName(kCGColorSpaceDisplayP3);
        CFPropertyListRef plist = CGColorSpaceCopyPropertyList(_space);
        IOSurfaceSetValue((IOSurfaceRef)_surface, kIOSurfaceColorSpace, plist);
        CFRelease(plist);
        _context = CGBitmapContextCreate(_surface.baseAddress, _width, _height, 8, _surface.bytesPerRow, _space,
                                         kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Host);
    }
    return self;
}

- (void)dealloc{
    CGContextRelease(_context);
    CGColorSpaceRelease(_space);
    [_surface release];
    if (_pixelBuffer) CVPixelBufferRelease(_pixelBuffer);
    [super dealloc];
}

- (void)lock{
    [_surface lockWithOptions:0 seed:NULL];
}

- (void)unlock{
    [_surface unlockWithOptions:0 seed:NULL];
}

@end
