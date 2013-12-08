//
//  Animation.h
//  NodeBox
//
//  Created by Christian Swinehart on 12/7/13.
//
//

#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#import <CoreVideo/CoreVideo.h>

@interface Animation : NSObject{
    AVAssetWriter *videoWriter;
    AVAssetWriterInput* videoWriterInput;
    AVAssetWriterInputPixelBufferAdaptor *adaptor;
    NSInteger frameRate;
    NSInteger frameCount;
}

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps;
- (void)addFrame:(NSImage *)frame;
- (void)closeFile;
- (CVPixelBufferRef)_pixelBufferFromNSImage:(NSImage *)image;

@end

