//
//  ImageSequence.m
//  NodeBox
//
//  Created by Christian Swinehart on 12/8/13.
//
//

#import "ImageSequence.h"

@interface ImageWriter : NSOperation
@property (nonatomic, assign) ImageSequence *delegate;
@property (nonatomic, retain) NSString *fname;
@property (nonatomic, retain) NSData *image;
@end

@implementation ImageWriter
-(void)main{
	@autoreleasepool{
		[self.image writeToFile:self.fname atomically:NO];
		[self.delegate performSelectorOnMainThread:@selector(_wroteFrame) withObject:nil waitUntilDone:NO];
	}
}
@end


@implementation ImageSequence
@synthesize framesWritten;
- (id)init{
	if ((self = [super init])) {
		self.framesWritten = 0;
		queue = [[NSOperationQueue alloc] init];
		queue.maxConcurrentOperationCount = 3;
	}
	return self;
}

- (void)writeData:(NSData *)img toFile:(NSString *)fname{
    ImageWriter *iw = [[ImageWriter alloc] init];
    iw.delegate = self;
    iw.fname = fname;
    iw.image = img;
    [queue addOperation:iw];
}

- (void)_wroteFrame{
    self.framesWritten++;
}

- (void)dealloc{
	[queue release];
    [super dealloc];
}

@end
