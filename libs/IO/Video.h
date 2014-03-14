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
@property (assign) NSInteger framesWritten;
@property (assign) BOOL doneWriting;

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps bitrate:(double)mbps;
- (void)addFrame:(NSImage *)frame;
- (void)closeFile;
- (void)_wroteFrame;
- (void)_wroteAll;
@end

