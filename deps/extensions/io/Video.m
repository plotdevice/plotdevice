//
//  Animation.m
//  PlotDevice
//
//  Created by Christian Swinehart on 12/7/13.
//
//

#import "Video.h"

// max buffer count (2 for the window, 2 currently being rendered, 4 being encoded)
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

        // wait for the encoder unless it gave up
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
    return [self initWithFile:fileName size:aSize fps:fps bitrate:mbps codec:codec colors:0];
}

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps codec:(NSUInteger)codec colors:(NSUInteger)inColors{
	if ((self = [super init])) {

        NSError *error = nil;
        frameRate = fps;
        frameCount = 0;
        frames = [[NSOperationQueue alloc] init];
        frames.maxConcurrentOperationCount = 1;
        videoWriter = [[AVAssetWriter alloc] initWithURL: [NSURL fileURLWithPath:fileName] fileType:AVFileTypeQuickTimeMovie error:&error];
        NSParameterAssert(videoWriter);

        // tag the movie's color space
        colors = inColors;
        NSString *transferFunction = AVVideoTransferFunction_ITU_R_709_2;
        if (colors < 2) {
            // AVFoundation only writes the sRGB curve on macOS 15+
            if (@available(macOS 15.0, *)) transferFunction = AVVideoTransferFunction_IEC_sRGB;
        }
        NSString *primaries = @[AVVideoColorPrimaries_P3_D65, AVVideoColorPrimaries_ITU_R_709_2, AVVideoColorPrimaries_ITU_R_709_2,
                                AVVideoColorPrimaries_ITU_R_2020][colors];
        NSString *matrix = colors == 3 ? AVVideoYCbCrMatrix_ITU_R_2020
                                       : AVVideoYCbCrMatrix_ITU_R_709_2;
        NSArray *codecs = @[AVVideoCodecTypeHEVC, AVVideoCodecTypeH264, AVVideoCodecTypeAppleProRes4444];
        straightAlpha = codec == 2; // only ProRes 4444 has alpha
        NSMutableDictionary *videoSettings = [NSMutableDictionary dictionaryWithDictionary:@{
                                         AVVideoCodecKey: codecs[codec],
                                         AVVideoWidthKey: @(aSize.width),
                                         AVVideoHeightKey: [NSNumber numberWithInt:aSize.height],
                                         AVVideoColorPropertiesKey: @{
                                            AVVideoColorPrimariesKey: primaries,
                                            AVVideoTransferFunctionKey: transferFunction,
                                            AVVideoYCbCrMatrixKey: matrix}
                                         }];
        if (codec != 2){ // ProRes has no bitrate
            videoSettings[AVVideoCompressionPropertiesKey] = @{
                AVVideoAverageBitRateKey:@((int)(mbps*1000000))
            };
        }
        videoWriterInput = [[AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeVideo
                                                               outputSettings:videoSettings] retain];

        // frames render straight into the pool's buffers
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

    // tag the buffer with the space its frame is drawn in (sRGB or P3), then let the encoder convert to the movie's space.
    // CG can't be trusted to draw in Rec.709/2020 (because it applies the wrong gamma)
    CFStringRef primaries = colors == 1 ? kCVImageBufferColorPrimaries_ITU_R_709_2 : kCVImageBufferColorPrimaries_P3_D65;
    CVBufferSetAttachment(buffer, kCVImageBufferColorPrimariesKey, primaries, kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(buffer, kCVImageBufferYCbCrMatrixKey, colors == 3 ? kCVImageBufferYCbCrMatrix_ITU_R_2020 : kCVImageBufferYCbCrMatrix_ITU_R_709_2,
                          kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(buffer, kCVImageBufferTransferFunctionKey, kCVImageBufferTransferFunction_sRGB, kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(buffer, kCVImageBufferAlphaChannelModeKey,
                          straightAlpha ? kCVImageBufferAlphaChannelMode_StraightAlpha : kCVImageBufferAlphaChannelMode_PremultipliedAlpha,
                          kCVAttachmentMode_ShouldPropagate);
    CGColorSpaceRef space = colors == 1 ? CGColorSpaceCreateWithName(kCGColorSpaceSRGB) : NULL /* Display P3 */;
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

// CG draws premultiplied, but ProRes decoders need the surface converted to straight alpha
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
            reported = YES; // only log once
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
    [super dealloc];
}

@end
