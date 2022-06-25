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

@interface Video : NSObject{
    AVAssetWriter *videoWriter;
    AVAssetWriterInput* videoWriterInput;
    AVAssetWriterInputPixelBufferAdaptor *adaptor;
    NSInteger frameRate;
    NSInteger frameCount;
    NSOperationQueue *frames;
    NSInteger framesWritten;
    BOOL doneWriting;
}
@property NSInteger framesWritten;
@property BOOL doneWriting;

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps codec:(NSUInteger)codec;
- (void)addFrame:(NSImage *)frame;
- (void)closeFile;

// internal callbacks
- (void)wroteFrame;
- (void)wroteLast;
@end

