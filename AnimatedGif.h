//
//  AnimatedGif.h
//  NodeBox
//
//  Created by Christian Swinehart on 12/6/13.
//
//

#import <Foundation/Foundation.h>

#define kGifHeader "GIF89a"
#define kGifTrailer 0x3B
#define kGraphicControlLabel 0xF9
#define kApplicationExtLabel 0xFF
#define kImageSeparator 0x2C
#define kExtSeparator 0x21

typedef struct {
    NSInteger clr_addr; // color table
    NSInteger clr_n;
    UInt8 clr_depth;
    
    NSInteger data_addr; // image data
    NSInteger data_n;
    
    NSInteger desc_addr; // image descriptor
    NSInteger desc_n;
    
    NSInteger gfx_addr;  // graphics control extension
    NSInteger gfx_n;

    NSInteger ext_addr;  // application extension
    NSInteger ext_n;    
} GifMap;

@interface AnimatedGif : NSObject{
    NSFileHandle *fileHandle;
    NSString *filePath;
    double frameRate;
}

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps loop:(NSInteger)count;
- (void)addFrame:(NSData *)gifData;
- (void)closeFile;
- (GifMap)_getOffsets:(NSData *)imRep; // find data regions within a candidate frame

@end
