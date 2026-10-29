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
- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps codec:(NSString *)codec colors:(NSString *)colors{
	if ((self = [super init])) {

        NSError *error = nil;
        size = aSize;
        frameRate = fps;
        frameCount = 0;
        frames = [[NSOperationQueue alloc] init];
        frames.maxConcurrentOperationCount = 1;
        videoWriter = [[AVAssetWriter alloc] initWithURL: [NSURL fileURLWithPath:fileName] fileType:AVFileTypeQuickTimeMovie error:&error];
        NSParameterAssert(videoWriter);

        // tag the movie's color space
        BOOL srgb = [colors isEqualToString:@"srgb"];
        rec2020 = [colors isEqualToString:@"rec2020"];
        space = srgb ? CGColorSpaceCreateWithName(kCGColorSpaceSRGB) : NULL;
        NSString *transferFunction = AVVideoTransferFunction_ITU_R_709_2;
        if (srgb || [colors isEqualToString:@"p3"]) {
            // AVFoundation only writes the sRGB curve on macOS 15+
            if (@available(macOS 15.0, *)) transferFunction = AVVideoTransferFunction_IEC_sRGB;
        }
        NSString *primaries = @{@"p3": AVVideoColorPrimaries_P3_D65, @"srgb": AVVideoColorPrimaries_ITU_R_709_2,
                                @"rec709": AVVideoColorPrimaries_ITU_R_709_2, @"rec2020": AVVideoColorPrimaries_ITU_R_2020}[colors];
        NSString *matrix = rec2020 ? AVVideoYCbCrMatrix_ITU_R_2020
                                   : AVVideoYCbCrMatrix_ITU_R_709_2;
        NSDictionary *codecs = @{@"hevc": AVVideoCodecTypeHEVC, @"h264": AVVideoCodecTypeH264, @"prores": AVVideoCodecTypeAppleProRes4444};
        prores = [codec isEqualToString:@"prores"];
        NSMutableDictionary *videoSettings = [NSMutableDictionary dictionaryWithDictionary:@{
                                         AVVideoCodecKey: codecs[codec],
                                         AVVideoWidthKey: @(aSize.width),
                                         AVVideoHeightKey: [NSNumber numberWithInt:aSize.height],
                                         AVVideoColorPropertiesKey: @{
                                            AVVideoColorPrimariesKey: primaries,
                                            AVVideoTransferFunctionKey: transferFunction,
                                            AVVideoYCbCrMatrixKey: matrix}
                                         }];
        if (!prores){ // ProRes has no bitrate
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

- (PDSurface *)encoderSurface{
    CVPixelBufferPoolRef pool = adaptor.pixelBufferPool;
    if (!pool) return nil;
    NSDictionary *aux = @{ (id)kCVPixelBufferPoolAllocationThresholdKey: @(kPoolThreshold) };
    CVPixelBufferRef buffer = NULL;
    CVReturn err = CVPixelBufferPoolCreatePixelBufferWithAuxAttributes(NULL, pool, (CFDictionaryRef)aux, &buffer);
    if (err != kCVReturnSuccess || !buffer) return nil;

    // tag the buffer with the space its frame is drawn in (sRGB or P3), then let the encoder convert to the movie's space.
    // CG can't be trusted to draw in Rec.709/2020 (because it applies the wrong gamma)
    CFStringRef primaries = space ? kCVImageBufferColorPrimaries_ITU_R_709_2 : kCVImageBufferColorPrimaries_P3_D65;
    CVBufferSetAttachment(buffer, kCVImageBufferColorPrimariesKey, primaries, kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(buffer, kCVImageBufferYCbCrMatrixKey, rec2020 ? kCVImageBufferYCbCrMatrix_ITU_R_2020 : kCVImageBufferYCbCrMatrix_ITU_R_709_2,
                          kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(buffer, kCVImageBufferTransferFunctionKey, kCVImageBufferTransferFunction_sRGB, kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(buffer, kCVImageBufferAlphaChannelModeKey,
                          prores ? kCVImageBufferAlphaChannelMode_StraightAlpha : kCVImageBufferAlphaChannelMode_PremultipliedAlpha,
                          kCVAttachmentMode_ShouldPropagate);
    PDSurface *surface = [PDSurface surfaceWithPixelBuffer:buffer space:space];
    CVPixelBufferRelease(buffer);
    return surface;
}

- (PDSurface *)nextSurface{
    // CG draws premultiplied, so a ProRes frame needs its own surface for addSurface: to unpremultiply
    if (prores) return [PDSurface surfaceWithWidth:size.width height:size.height space:space];
    return [self encoderSurface];
}

- (BOOL)addSurface:(PDSurface *)drawn{
    PDSurface *surface = drawn;
    if (prores){
        surface = [self encoderSurface];
        if (!surface) return NO;
        [drawn lock];
        [surface lock];
        vImage_Buffer src = {drawn.surface.baseAddress, drawn.height, drawn.width, drawn.surface.bytesPerRow};
        vImage_Buffer dst = {surface.surface.baseAddress, surface.height, surface.width, surface.surface.bytesPerRow};
        vImageUnpremultiplyData_BGRA8888(&src, &dst, kvImageNoFlags);
        [surface unlock];
        [drawn unlock];
    }

    FrameWriter *fw = [[[FrameWriter alloc] init] autorelease];
    fw.surface = surface;
    fw.frameNum = frameCount++;
    fw.frameRate = frameRate;
    fw.videoWriter = videoWriter;
    fw.videoWriterInput = videoWriterInput;
    fw.adaptor = adaptor;
    fw.delegate = self;
    [frames addOperation:fw];
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
    CGColorSpaceRelease(space);
    [frames release];
    [videoWriter release];
    [videoWriterInput release];
    [adaptor release];
    [super dealloc];
}

@end
