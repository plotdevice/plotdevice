//
//  Pages.m
//  PlotDevice
//
//  Created by Christian Swinehart on 12/8/13.
//
//

#import "Pages.h"

//
// batch imagefile writer
//
@interface IterWriter : NSOperation{
    Pages *delegate;
    NSString *fname;
    NSData *image;
}
@property (nonatomic, assign) Pages *delegate;
@property (nonatomic, retain) NSString *fname;
@property (nonatomic, retain) NSData *image;
@end

@implementation IterWriter
@synthesize delegate, fname, image;
-(void)main{
    @autoreleasepool{
        if (!self.image){
            [self.delegate wroteLast];
        }else{
            [self.image writeToFile:self.fname atomically:NO];
            [self.delegate wrotePage];
        }
    }
}

- (void)dealloc{
    self.fname = nil;
    self.image = nil;
    [super dealloc];
}
@end

@implementation Pages
@synthesize framesWritten, doneWriting, filePath, filePattern, pageCount;


- (id)init{
    if ((self = [super init])) {
        queue = [[NSOperationQueue alloc] init];
        queue.maxConcurrentOperationCount = 1;
        self.framesWritten = self.pageCount = 0;
    }
    return self;
}

- (id)initWithPattern:(NSString *)pat{
    if ((self = [self init])) {
        self.filePattern = pat;
    }
    return self;
}

- (id)initWithFile:(NSString *)fname{
    if ((self = [self init])) {
        self.filePath = fname;
    }
    return self;
}

- (void)addPage:(NSData *)img{
    self.pageCount++;

    // create another in the sequence of output files
    IterWriter *iw = [[[IterWriter alloc] init] autorelease];
    iw.delegate = self;
    iw.image = img;
    if (self.filePath){
        iw.fname = self.filePath;
    }else{
        iw.fname = [NSString stringWithFormat:self.filePattern, self.pageCount];;
    }
    [queue addOperation:iw];
}

- (void)closeFile{
    // create an all-done operation to add to the end of the queue
    IterWriter *iw = [[[IterWriter alloc] init] autorelease];
    iw.delegate = self;
    [queue addOperation:iw];
}

- (void)wrotePage{
    @synchronized(self){ self.framesWritten++; }
}

- (void)wroteLast{
    @synchronized(self){ self.doneWriting = YES; }
}

- (void)dealloc{
    [queue release];
    [super dealloc];
}

@end
