//
//  Animation.m
//  NodeBox
//
//  Created by Christian Swinehart on 12/7/13.
//
//

#import "Animation.h"

@implementation Animation

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps{
	if ((self = [super init])) {

        NSError *error = nil;
        frameRate = fps;
        frameCount = 0;
        
        videoWriter = [[AVAssetWriter alloc] initWithURL: [NSURL fileURLWithPath:fileName] fileType:AVFileTypeQuickTimeMovie error:&error];
        NSParameterAssert(videoWriter);
        NSDictionary *videoSettings = @{ AVVideoCodecKey: AVVideoCodecH264,
                                         AVVideoWidthKey: [NSNumber numberWithInt:aSize.width],
                                         AVVideoHeightKey: [NSNumber numberWithInt:aSize.height] };
        videoWriterInput = [[AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeVideo
                                                               outputSettings:videoSettings] retain];
        
        adaptor = [[AVAssetWriterInputPixelBufferAdaptor
                    assetWriterInputPixelBufferAdaptorWithAssetWriterInput:videoWriterInput
                    sourcePixelBufferAttributes:nil] retain];
        
        NSParameterAssert(videoWriterInput);
        NSParameterAssert([videoWriter canAddInput:videoWriterInput]);
        videoWriterInput.expectsMediaDataInRealTime = YES;
        [videoWriter addInput:videoWriterInput];
        
        //Start a session:
        [videoWriter startWriting];
        [videoWriter startSessionAtSourceTime:kCMTimeZero];
    }
    return self;
}

- (void)addFrame:(NSImage *)frame{
    BOOL ok = NO;
    int retry = 0;
    CVPixelBufferRef buffer = [self _pixelBufferFromNSImage:frame];
    while (!ok && retry < 30){
        if (adaptor.assetWriterInput.readyForMoreMediaData) {
            CMTime frameTime = CMTimeMake(frameCount, (int32_t)frameRate);
            ok = [adaptor appendPixelBuffer:buffer withPresentationTime:frameTime];
            if(buffer) CVBufferRelease(buffer);
        }
        [NSThread sleepForTimeInterval:ok ? 0.05 : 0.1];
        retry++;
    }
    if (!ok) {
        NSLog(@"Video export failed: couldn't write frame %li", (long)frameCount);
    }
    frameCount++;
}

- (void)closeFile{
    [videoWriterInput markAsFinished];
    [videoWriter finishWriting];
}

- (CVPixelBufferRef)_pixelBufferFromNSImage:(NSImage *)image
{
    CVPixelBufferRef buffer = NULL;
    
    // config
    size_t width = [image size].width;
    size_t height = [image size].height;
    size_t bitsPerComponent = 8; // *not* CGImageGetBitsPerComponent(image);
    CGColorSpaceRef cs = CGColorSpaceCreateWithName(kCGColorSpaceGenericRGB);
    CGBitmapInfo bi = kCGImageAlphaNoneSkipFirst; // *not* CGImageGetBitmapInfo(image);
    NSDictionary *d = [NSDictionary dictionaryWithObjectsAndKeys:
                        [NSNumber numberWithBool:YES], kCVPixelBufferCGImageCompatibilityKey,
                        [NSNumber numberWithBool:YES], kCVPixelBufferCGBitmapContextCompatibilityKey, nil];
    
    // create pixel buffer
    CVPixelBufferCreate(kCFAllocatorDefault, width, height, k32ARGBPixelFormat, (CFDictionaryRef)d, &buffer);
    CVPixelBufferLockBaseAddress(buffer, 0);
    void *rasterData = CVPixelBufferGetBaseAddress(buffer);
    size_t bytesPerRow = CVPixelBufferGetBytesPerRow(buffer);
    
    // context to draw in, set to pixel buffer's address
    CGContextRef ctxt = CGBitmapContextCreate(rasterData, width, height, bitsPerComponent, bytesPerRow, cs, bi);
    if(ctxt == NULL){
        NSLog(@"could not create context");
        return NULL;
    }
    
    // draw
    NSGraphicsContext *nsctxt = [NSGraphicsContext graphicsContextWithGraphicsPort:ctxt flipped:NO];
    [NSGraphicsContext saveGraphicsState];
    [NSGraphicsContext setCurrentContext:nsctxt];
    [image drawAtPoint:NSMakePoint(0.0, 0.0) fromRect:NSZeroRect operation:NSCompositeSourceOver fraction:1.0];
    [NSGraphicsContext restoreGraphicsState];
    
    CVPixelBufferUnlockBaseAddress(buffer, 0);
    CFRelease(ctxt);
    
    return buffer;
}

- (void)dealloc{
    [videoWriter release];
    [videoWriterInput release];
    [adaptor release];
    [super dealloc];
}

@end
