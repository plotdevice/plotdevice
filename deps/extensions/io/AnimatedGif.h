//
//  AnimatedGif.h
//  PlotDevice
//
//  Created by Christian Swinehart on 12/6/13.
//
//

#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>

#define kGifHeader "GIF89a"
#define kGifTrailer 0x3B
#define kGraphicControlLabel 0xF9
#define kApplicationExtLabel 0xFF
#define kImageSeparator 0x2C
#define kExtSeparator 0x21

typedef struct {
    NSInteger clr_addr; NSInteger clr_n; // color table
    UInt8 clr_depth; // color table depth (in bpp-1 form)
    NSInteger data_addr; NSInteger data_n; // image data
    NSInteger desc_addr; NSInteger desc_n; // image descriptor
    NSInteger gfx_addr; NSInteger gfx_n; // graphics control extension
    NSInteger ext_addr; NSInteger ext_n; // application extension
} GifMap;

@interface AnimatedGif : NSObject{
    NSFileHandle *fileHandle;
    NSString *filePath;
    double frameRate;
    NSOperationQueue *frames;
    NSInteger framesWritten;
    BOOL doneWriting;
}
@property NSInteger framesWritten;
@property BOOL doneWriting;

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps loop:(NSInteger)count;
- (void)addFrame:(NSData *)gifData;
- (void)closeFile;

// internal callbacks
- (void)wroteFrame;
- (void)wroteLast;
@end
