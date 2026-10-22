//
//  Animation.m
//  PlotDevice
//
//  Created by Christian Swinehart on 12/7/13.
//
//

#import "Video.h"

#define kPoolThreshold 8

@interface FrameWriter : NSOperation{
    Video *delegate;
    NSInteger frameNum;
    NSInteger frameRate;
    PDSurface *surface;
    AVAssetWriter *videoWriter;
    AVAssetWriterInput* videoWriterInput;
    AVAssetWriterInputPixelBufferAdaptor *adaptor;
}
@property (nonatomic, assign) Video *delegate;
@property (nonatomic, assign) NSInteger frameNum;
@property (nonatomic, assign) NSInteger frameRate;
@property (nonatomic, retain) PDSurface *surface;
@property (nonatomic, retain) AVAssetWriter *videoWriter;
@property (nonatomic, retain) AVAssetWriterInput* videoWriterInput;
@property (nonatomic, retain) AVAssetWriterInputPixelBufferAdaptor *adaptor;
@end

@implementation FrameWriter
@synthesize delegate, surface, frameNum, frameRate, videoWriter, videoWriterInput, adaptor;
-(void) main{
    @autoreleasepool{
        if (self.isCancelled || !surface){
            if (videoWriter.status != AVAssetWriterStatusWriting){
                NSLog(@"Video export failed: %@", videoWriter.error);
                [self.delegate wroteLast];
                return;
            }
            [videoWriterInput markAsFinished];
            [videoWriter finishWritingWithCompletionHandler:^{
                if (videoWriter.status != AVAssetWriterStatusCompleted){
                    NSLog(@"Video export failed: %@", videoWriter.error);
                }
                [self.delegate wroteLast];
            }];
            return;
        }

        while (!videoWriterInput.readyForMoreMediaData && videoWriter.status == AVAssetWriterStatusWriting){
            [NSThread sleepForTimeInterval:0.005];
        }
        BOOL ok = NO;
        if (videoWriter.status == AVAssetWriterStatusWriting){
            CMTime frameTime = CMTimeMake(frameNum, (int32_t)frameRate);
            ok = [adaptor appendPixelBuffer:surface.pixelBuffer withPresentationTime:frameTime];
        }
        if (ok){
            [self.delegate wroteFrame];
        }else{
            [self.delegate droppedFrame:frameNum];
        }
    }
}

- (void)dealloc{
    self.surface = nil;
    self.videoWriter = nil;
    self.videoWriterInput = nil;
    self.adaptor = nil;
    [super dealloc];
}

@end


@implementation Video
@synthesize framesWritten, doneWriting;
- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps codec:(NSUInteger)codec{
    return [self initWithFile:fileName size:aSize fps:fps bitrate:mbps codec:codec srgb:NO];
}

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps codec:(NSUInteger)codec srgb:(BOOL)inSRGB{
	if ((self = [super init])) {

        NSError *error = nil;
        frameRate = fps;
        frameCount = 0;
        frames = [[NSOperationQueue alloc] init];
        frames.maxConcurrentOperationCount = 1;

        videoWriter = [[AVAssetWriter alloc] initWithURL: [NSURL fileURLWithPath:fileName] fileType:AVFileTypeQuickTimeMovie error:&error];
        NSParameterAssert(videoWriter);
        srgb = inSRGB;
        transferFunction = AVVideoTransferFunction_ITU_R_709_2;
        if (@available(macOS 15.0, *)) transferFunction = AVVideoTransferFunction_IEC_sRGB;
        [transferFunction retain];
        NSArray *codecs = @[AVVideoCodecTypeHEVC, AVVideoCodecTypeH264, AVVideoCodecTypeAppleProRes4444];
        straightAlpha = codec == 2;
        NSMutableDictionary *videoSettings = [NSMutableDictionary dictionaryWithDictionary:@{
                                         AVVideoCodecKey: codecs[codec],
                                         AVVideoWidthKey: @(aSize.width),
                                         AVVideoHeightKey: [NSNumber numberWithInt:aSize.height],
                                         AVVideoColorPropertiesKey: @{
                                            AVVideoColorPrimariesKey: srgb ? AVVideoColorPrimaries_ITU_R_709_2 : AVVideoColorPrimaries_P3_D65,
                                            AVVideoTransferFunctionKey: transferFunction,
                                            AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2}
                                         }];
        if (codec != 2){
            videoSettings[AVVideoCompressionPropertiesKey] = @{
                AVVideoAverageBitRateKey:@((int)(mbps*1000000))
                /*AVVideoMaxKeyFrameIntervalKey: @1*/};
        }
        videoWriterInput = [[AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeVideo
                                                               outputSettings:videoSettings] retain];

        NSDictionary *bufferAttributes = @{ (id)kCVPixelBufferPixelFormatTypeKey: @(kCVPixelFormatType_32BGRA),
                                            (id)kCVPixelBufferWidthKey: @(aSize.width),
                                            (id)kCVPixelBufferHeightKey: @(aSize.height),
                                            (id)kCVPixelBufferIOSurfacePropertiesKey: @{} };
        adaptor = [[AVAssetWriterInputPixelBufferAdaptor
                    assetWriterInputPixelBufferAdaptorWithAssetWriterInput:videoWriterInput
                    sourcePixelBufferAttributes:bufferAttributes] retain];

        NSParameterAssert(videoWriterInput);
        NSParameterAssert([videoWriter canAddInput:videoWriterInput]);
        videoWriterInput.expectsMediaDataInRealTime = YES;
        [videoWriter addInput:videoWriterInput];

        //Start a session:
        [videoWriter startWriting];
        [videoWriter startSessionAtSourceTime:kCMTimeZero];
        self.framesWritten = 0;
        self.doneWriting = NO;
    }
    return self;
}

- (BOOL)failed{
    return videoWriter.status == AVAssetWriterStatusFailed;
}

- (PDSurface *)nextSurface{
    CVPixelBufferPoolRef pool = adaptor.pixelBufferPool;
    if (!pool) return nil;
    NSDictionary *aux = @{ (id)kCVPixelBufferPoolAllocationThresholdKey: @(kPoolThreshold) };
    CVPixelBufferRef buffer = NULL;
    CVReturn err = CVPixelBufferPoolCreatePixelBufferWithAuxAttributes(NULL, pool, (CFDictionaryRef)aux, &buffer);
    if (err != kCVReturnSuccess || !buffer) return nil;
    CVBufferSetAttachment(buffer, kCVImageBufferColorPrimariesKey, srgb ? kCVImageBufferColorPrimaries_ITU_R_709_2 : kCVImageBufferColorPrimaries_P3_D65,
                          kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(buffer, kCVImageBufferYCbCrMatrixKey, kCVImageBufferYCbCrMatrix_ITU_R_709_2, kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(buffer, kCVImageBufferTransferFunctionKey, (CFStringRef)transferFunction, kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(buffer, kCVImageBufferAlphaChannelModeKey,
                          straightAlpha ? kCVImageBufferAlphaChannelMode_StraightAlpha : kCVImageBufferAlphaChannelMode_PremultipliedAlpha,
                          kCVAttachmentMode_ShouldPropagate);
    CGColorSpaceRef space = srgb ? CGColorSpaceCreateWithName(kCGColorSpaceSRGB) : NULL;
    PDSurface *surface = [PDSurface surfaceWithPixelBuffer:buffer space:space];
    CGColorSpaceRelease(space);
    CVPixelBufferRelease(buffer);
    return surface;
}

- (void)addSurface:(PDSurface *)surface{
    FrameWriter *fw = [[[FrameWriter alloc] init] autorelease];
    fw.surface = surface;
    fw.frameNum = frameCount++;
    fw.frameRate = frameRate;
    fw.videoWriter = videoWriter;
    fw.videoWriterInput = videoWriterInput;
    fw.adaptor = adaptor;
    fw.delegate = self;
    [frames addOperation:fw];
}

- (BOOL)addUnpremultiplied:(PDSurface *)rendered{
    PDSurface *surface = [self nextSurface];
    if (!surface) return NO;
    [rendered lock];
    [surface lock];
    vImage_Buffer src = {rendered.surface.baseAddress, rendered.height, rendered.width, rendered.surface.bytesPerRow};
    vImage_Buffer dst = {surface.surface.baseAddress, surface.height, surface.width, surface.surface.bytesPerRow};
    vImageUnpremultiplyData_BGRA8888(&src, &dst, kvImageNoFlags);
    [surface unlock];
    [rendered unlock];
    [self addSurface:surface];
    return YES;
}

- (void)closeFile{
    FrameWriter *fw = [[[FrameWriter alloc] init] autorelease];
    fw.videoWriter = videoWriter;
    fw.videoWriterInput = videoWriterInput;
    fw.delegate = self;
    [frames addOperation:fw];
}

- (void)wroteFrame{
    @synchronized(self){ self.framesWritten++; }
}

- (void)droppedFrame:(NSInteger)frameNum{
    @synchronized(self){
        if (!reported){
            NSLog(@"Video export failed: couldn't write frame %li (%@)", (long)frameNum, videoWriter.error);
            reported = YES;
        }
    }
}

- (void)wroteLast{
    @synchronized(self){ self.doneWriting = YES; }
}

- (void)dealloc{
    [frames release];
    [videoWriter release];
    [videoWriterInput release];
    [adaptor release];
    [transferFunction release];
    [super dealloc];
}

@end
