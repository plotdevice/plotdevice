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
    CGSize size;
    BOOL prores;           // unpremultiplied, no bitrate
    BOOL rec2020;          // use the Rec.2020 matrix rather than Rec.709's
    CGColorSpaceRef space; // what frames are drawn in: sRGB, or NULL for P3
}
@property NSInteger framesWritten;
@property BOOL doneWriting;
@property (readonly) BOOL failed; // the writer gave up

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps codec:(NSString *)codec colors:(NSString *)colors;
- (PDSurface *)nextSurface; // a surface to draw the next frame in, or nil while all buffers are busy
- (BOOL)addSurface:(PDSurface *)drawn; // NO while no buffer is free
- (void)closeFile;

// internal callbacks
- (void)wroteFrame;
- (void)droppedFrame:(NSInteger)frameNum;
- (void)wroteLast;
@end
