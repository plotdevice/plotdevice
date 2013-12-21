//
//  Animation.m
//  NodeBox
//
//  Created by Christian Swinehart on 12/7/13.
//
//

#import "Video.h"

@interface FrameWriter : NSOperation{
    Video *delegate;
    NSInteger frameNum;
    NSInteger frameRate;
    NSImage *frame;
    AVAssetWriter *videoWriter;
    AVAssetWriterInput* videoWriterInput;
    AVAssetWriterInputPixelBufferAdaptor *adaptor;
}
@property (nonatomic, assign) Video *delegate;
@property (nonatomic, assign) NSInteger frameNum;
@property (nonatomic, assign) NSInteger frameRate;
@property (nonatomic, retain) NSImage *frame;
@property (nonatomic, retain) AVAssetWriter *videoWriter;
@property (nonatomic, retain) AVAssetWriterInput* videoWriterInput;
@property (nonatomic, retain) AVAssetWriterInputPixelBufferAdaptor *adaptor;
@end

@implementation FrameWriter
@synthesize delegate, frame, frameNum, frameRate, videoWriter, videoWriterInput, adaptor;
-(void) main{
    @autoreleasepool{
        if (self.isCancelled || !frame){
            // close the file
            [videoWriterInput markAsFinished];
            [videoWriter finishWriting];
            return;
        }

        BOOL ok = NO;
        int retry = 30;
        CVPixelBufferRef buffer = [self _pixelBufferFromNSImage:frame];
        while (!ok && retry-->0){
            if (adaptor.assetWriterInput.readyForMoreMediaData) {
                CMTime frameTime = CMTimeMake(frameNum, (int32_t)frameRate);
                ok = [adaptor appendPixelBuffer:buffer withPresentationTime:frameTime];
                ok = YES;
                if(buffer) CVBufferRelease(buffer);
            }
            [NSThread sleepForTimeInterval:ok ? 0.05 : 0.1];
        }
        if (!ok) {
            NSLog(@"Video export failed: couldn't write frame %li", (long)frameNum);
        }
        [self.delegate performSelectorOnMainThread:@selector(_wroteFrame) withObject:nil waitUntilDone:NO];
    }
}

- (void)dealloc{
    self.frame = nil;
    self.videoWriter = nil;
    self.videoWriterInput = nil;
    self.adaptor = nil;
    [super dealloc];
}

- (CVPixelBufferRef)_pixelBufferFromNSImage:(NSImage*)image
{
    // config
    CGColorSpaceRef colorSpace = CGColorSpaceCreateWithName(kCGColorSpaceGenericRGB);
    NSDictionary* pixelBufferProperties = @{(id)kCVPixelBufferCGImageCompatibilityKey:@YES, (id)kCVPixelBufferCGBitmapContextCompatibilityKey:@YES};
    
    // create pixel buffer
    CVPixelBufferRef pixelBuffer = NULL;
    CVPixelBufferCreate(kCFAllocatorDefault, [image size].width, [image size].height, k32ARGBPixelFormat, (__bridge CFDictionaryRef)pixelBufferProperties, &pixelBuffer);
    CVPixelBufferLockBaseAddress(pixelBuffer, 0);

    // context to draw in, set to pixel buffer's address
    void* baseAddress = CVPixelBufferGetBaseAddress(pixelBuffer);
    size_t bytesPerRow = CVPixelBufferGetBytesPerRow(pixelBuffer);
    CGContextRef context = CGBitmapContextCreate(baseAddress, [image size].width, [image size].height, 8, bytesPerRow, colorSpace, kCGImageAlphaNoneSkipFirst);
    
    // draw
    NSGraphicsContext* imageContext = [NSGraphicsContext graphicsContextWithGraphicsPort:context flipped:NO];
    [NSGraphicsContext saveGraphicsState];
    [NSGraphicsContext setCurrentContext:imageContext];
    [image compositeToPoint:NSMakePoint(0.0, 0.0) operation:NSCompositeCopy];
    [NSGraphicsContext restoreGraphicsState];
    CVPixelBufferUnlockBaseAddress(pixelBuffer, 0);

    // cleanup
    CFRelease(context);
    CGColorSpaceRelease(colorSpace);
    return pixelBuffer;
}

@end


@implementation Video
@synthesize framesWritten;
- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps{
	if ((self = [super init])) {

        NSError *error = nil;
        frameRate = fps;
        frameCount = 0;
        frames = [[NSOperationQueue alloc] init];
        frames.maxConcurrentOperationCount = 1;


        videoWriter = [[AVAssetWriter alloc] initWithURL: [NSURL fileURLWithPath:fileName] fileType:AVFileTypeQuickTimeMovie error:&error];
        NSParameterAssert(videoWriter);
        NSDictionary *videoSettings = @{ AVVideoCodecKey: AVVideoCodecH264,
                                         AVVideoWidthKey: @(aSize.width),
                                         AVVideoHeightKey: [NSNumber numberWithInt:aSize.height],
                                         AVVideoCompressionPropertiesKey: @{
                                            AVVideoAverageBitRateKey:@((int)(mbps*1000000))
                                            /*AVVideoMaxKeyFrameIntervalKey: @1*/}
                                         };
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
        self.framesWritten = 0;
    }
    return self;
}

- (void)addFrame:(NSImage *)frame{
    FrameWriter *fw = [[[FrameWriter alloc] init] autorelease];
    fw.frame=frame;
    fw.frameNum = frameCount++;
    fw.frameRate = frameRate;
    fw.videoWriter = videoWriter;
    fw.videoWriterInput = videoWriterInput;
    fw.adaptor=adaptor;
    fw.delegate=self;
    [frames addOperation:fw];
}

- (void)closeFile{
    FrameWriter *fw = [[[FrameWriter alloc] init] autorelease];
    fw.videoWriter = videoWriter;
    fw.videoWriterInput = videoWriterInput;
    [frames addOperation:fw];
    // [frames waitUntilAllOperationsAreFinished];
}
        
- (void)_wroteFrame{
    self.framesWritten += 1;
}


- (void)dealloc{
    [frames release];
    [videoWriter release];
    [videoWriterInput release];
    [adaptor release];
    [super dealloc];
}

@end
