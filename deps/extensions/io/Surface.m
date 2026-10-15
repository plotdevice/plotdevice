//
//  Surface.m
//  PlotDevice
//

#import <CoreVideo/CoreVideo.h>
#import "Surface.h"

@implementation PDSurface

+ (instancetype)surfaceWithWidth:(NSInteger)width height:(NSInteger)height{
    return [[[self alloc] initWithWidth:width height:height] autorelease];
}

- (instancetype)initWithWidth:(NSInteger)width height:(NSInteger)height{
    if ((self = [super init])){
        _width = width;
        _height = height;
        _surface = [[IOSurface alloc] initWithProperties:@{
            IOSurfacePropertyKeyWidth: @(width),
            IOSurfacePropertyKeyHeight: @(height),
            IOSurfacePropertyKeyBytesPerElement: @4,
            IOSurfacePropertyKeyPixelFormat: @(kCVPixelFormatType_32BGRA),
        }];
        if (!_surface){
            [self release];
            return nil;
        }
        _space = CGColorSpaceCreateDeviceRGB();
        _context = CGBitmapContextCreate(_surface.baseAddress, width, height, 8, _surface.bytesPerRow, _space,
                                         kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Host);
    }
    return self;
}

- (void)dealloc{
    CGContextRelease(_context);
    CGColorSpaceRelease(_space);
    [_surface release];
    [super dealloc];
}

- (void)lock{
    [_surface lockWithOptions:0 seed:NULL];
}

- (void)unlock{
    [_surface unlockWithOptions:0 seed:NULL];
}

@end
