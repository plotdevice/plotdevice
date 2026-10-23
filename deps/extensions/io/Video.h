//
//  Animation.h
//  PlotDevice
//
//  Created by Christian Swinehart on 12/7/13.
//
//

#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <AVFoundation/AVFoundation.h>
#import <CoreVideo/CoreVideo.h>
#import "Surface.h"
#import <Accelerate/Accelerate.h>

@interface Video : NSObject{
    AVAssetWriter *videoWriter;
    AVAssetWriterInput* videoWriterInput;
    AVAssetWriterInputPixelBufferAdaptor *adaptor;
    NSInteger frameRate;
    NSInteger frameCount;
    NSOperationQueue *frames;
    NSInteger framesWritten;
    BOOL doneWriting;
    BOOL reported;
    BOOL straightAlpha; // ProRes
    NSUInteger colors;  // p3, srgb, Rec.709, Rec.2020
}
@property NSInteger framesWritten;
@property BOOL doneWriting;
@property (readonly) BOOL failed; // the writer gave up

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps codec:(NSUInteger)codec;
- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps codec:(NSUInteger)codec colors:(NSUInteger)inColors;
- (PDSurface *)nextSurface; // nil while all buffers are busy
- (void)addSurface:(PDSurface *)surface;
- (BOOL)addUnpremultiplied:(PDSurface *)rendered; // NO while no buffer is free
- (void)closeFile;

// internal callbacks
- (void)wroteFrame;
- (void)droppedFrame:(NSInteger)frameNum;
- (void)wroteLast;
@end
