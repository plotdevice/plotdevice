//
//  AnimatedGif.m
//  NodeBox
//
//  Created by Christian Swinehart on 12/6/13.
//
//

#import "AnimatedGif.h"

// macros for splitting 16-bit uints into a pair of little-endian-ordered bytes
#define LO(longInt) ((UInt8)((UInt16)longInt&0xFF))
#define HI(longInt) ((UInt8)((UInt16)longInt>>8))

@implementation AnimatedGif

- (id)initWithFile:(NSString *)fileName size:(CGSize)aSize fps:(NSUInteger)fps loop:(NSInteger)count{
	if ((self = [super init])) {
		if (![[NSFileManager defaultManager] fileExistsAtPath:fileName]) {
			[[NSFileManager defaultManager] createFileAtPath:fileName contents:[NSData data] attributes:nil];
		}
		fileHandle = [NSFileHandle fileHandleForWritingAtPath:fileName];
		filePath = fileName;
		frameRate = 100.0/(double)fps;
		
		// write header
		[fileHandle writeData:[NSData dataWithBytes:kGifHeader length:strlen(kGifHeader)]];
		
		// write logical screen desc
		UInt8 screen_desc[7] = { LO(aSize.width),HI(aSize.width),
		                         LO(aSize.height),HI(aSize.height),
		                         7<<4, // global color table flags ()
		                         0,    // bg color (from global color map)
		                         0};   // pixel aspect ratio
		[fileHandle writeData:[NSData dataWithBytesNoCopy:&screen_desc length:7 freeWhenDone:NO]];

		// if looping is enabled, write an application extension block with the loop count
		if (count!=0){
			UInt16 loopCount = (count==-1) ? 0 : count;
			UInt8 loop_ext[19] = { kExtSeparator, kApplicationExtLabel, 
								   11, 'N','E','T','S','C','A','P','E','2','.','0',
								   3, 1, LO(loopCount), HI(loopCount), 0 };
			[fileHandle writeData:[NSData dataWithBytesNoCopy:&loop_ext length:19 freeWhenDone:NO]];
		}	
	}
	return self;
}

- (void) addFrame:(NSImage *)gifImage{
	// have CG render the frame and extract the gif89 data
	NSBitmapImageRep *imRep = [NSBitmapImageRep imageRepWithData:[gifImage TIFFRepresentation]];
	NSData *gifData = [imRep representationUsingType:NSGIFFileType properties:[NSDictionary dictionaryWithObject:[NSNumber numberWithBool:YES] forKey:NSImageDitherTransparency]];
	UInt8 *gif = (UInt8 *)[gifData bytes];
	GifMap map = [self _getOffsets:gifData]; // find the offsets for the important data blocks in the gif

    // don't echo the application extension (though maybe one of them should get passed through?)
	// if (map.ext_addr) [fileHandle writeData:[NSData dataWithBytesNoCopy:gif+map.ext_addr length:map.ext_n freeWhenDone:NO]];
	
	// write graphics control extension for frame
	UInt8 *buf = gif+map.gfx_addr;
	UInt16 rate = round(frameRate);
	UInt8 gfx_ctrl[8] = { kExtSeparator, kGraphicControlLabel, 4, 
						  (buf[3] & 1) | (3 << 2), // <Packed Fields> w/ transp color from img + disposal method #3
						  LO(rate), HI(rate), // delay
						  buf[6], // transparent color idx
						  0};
	[fileHandle writeData:[NSData dataWithBytesNoCopy:&gfx_ctrl length:8 freeWhenDone:NO]];

	// write image descriptor
	buf = gif+map.desc_addr;
	UInt8 img_desc[10];
	memcpy(&img_desc, buf, 10);
	img_desc[9] = 0x80 | map.clr_depth; // use local color map of same depth as source's global map
	[fileHandle writeData:[NSData dataWithBytesNoCopy:&img_desc length:10 freeWhenDone:NO]];

	// write local color table
	if (map.clr_addr) [fileHandle writeData:[NSData dataWithBytesNoCopy:gif+map.clr_addr length:map.clr_n freeWhenDone:NO]];

	// write image data
	[fileHandle writeData:[NSData dataWithBytesNoCopy:gif+map.data_addr length:map.data_n freeWhenDone:NO]];
}

- (void) closeFile{
	UInt8 aByte = kGifTrailer;
	NSMutableData *encoded = [NSMutableData data];
	[encoded appendBytes:&aByte length:1];
	[fileHandle writeData:encoded];
	[fileHandle closeFile];
}

- (GifMap)_getOffsets:(NSData *)gifData{
	GifMap map;
	memset(&map, 0, sizeof map);
	UInt8 *gif = (UInt8 *)[gifData bytes];
	
	// step over the header, screen description, and global color map (if present)
	UInt8 gColorFlags = gif[10];
	BOOL hasGlobalColors = gColorFlags & 0x80;
	UInt8 depth = 1 + ((gColorFlags >> 4) & 0x7);
	UInt16 numCols = pow(2, depth);
	UInt8 *cursor = gif + 13;
	if (hasGlobalColors){
		map.clr_addr = 13;
		map.clr_n = numCols*3;
		map.clr_depth = depth - 1;
		cursor += map.clr_n;
	}

	// after the global color map the file is a series of image and extension blocks.
	// iterate through them until we reach the trailer byte
	while (cursor[0]==kExtSeparator || cursor[0]==kImageSeparator){
		if (cursor[0]==kImageSeparator){
			// found an image descriptor
			map.desc_addr = cursor-gif;
			map.desc_n = 10;
			BOOL hasLocalColors = cursor[9] & 0x80;
			cursor+=10; // skip over descriptor

			// found a local color table (will almost certainly not happen)
			if (hasLocalColors){
				UInt8 depth = 1 + (cursor[9] & 0x7);
				UInt16 numCols = pow(2, depth);
				if (!map.clr_addr){
					map.clr_addr = cursor+10;
					map.clr_addr = 3*numCols;
				}
				cursor += 3*numCols;
			}

			// walk to end of image data
			int imstart = cursor-gif;
			cursor++;
			UInt8 blockSize = cursor[0];
			while(blockSize){
				cursor += blockSize + 1;
				blockSize = cursor[0];
			}
			cursor++;
			map.data_addr = imstart;
			map.data_n = cursor-gif-imstart;
		}else{
			// found an extension block
			UInt8 extCode = cursor[1];
			UInt16 blockSize;
			UInt16 extStart = cursor-gif;
			switch (extCode) {

				case 0xF9: // graphics control extension
					map.gfx_addr = extStart;
					map.gfx_n = 8;
					cursor += 8; // skip over control block
					break;
				
				case 0xFF: // application extension
					cursor+=2;
					blockSize = cursor[0];
					while(blockSize){
						cursor += blockSize + 1;
						blockSize = cursor[0];
					}
					cursor++;
					map.ext_addr = extStart;
					map.ext_n = cursor-gif-extStart;
					break;

				case 0x01: // plain text
				case 0xFE: // comment extension
					cursor+=2;
					blockSize = cursor[0];
					while(blockSize){
						cursor += blockSize + 1;
						blockSize = cursor[0];
					}
					cursor++;
					break;
			}
		}

	}
	if (cursor[0]==kGifTrailer){
		// Success!
	}else{
		NSLog(@"ERR %lu/%lu", cursor-gif, [gifData length]);
	}

	return map;	
}

@end
