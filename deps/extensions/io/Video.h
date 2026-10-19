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
    NSString *transferFunction; // the movie's (and its buffers')
}
@property NSInteger framesWritten;
@property BOOL doneWriting;
@property (readonly) BOOL failed; // whether the writer has given up (frames are no longer appended)

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps codec:(NSUInteger)codec;
- (PDSurface *)nextSurface; // one over a free buffer of the encoder's, or nil while it's using them all
- (void)addSurface:(PDSurface *)surface;
- (void)closeFile;

// internal callbacks
- (void)wroteFrame;
- (void)droppedFrame:(NSInteger)frameNum;
- (void)wroteLast;
@end
