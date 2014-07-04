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
        [self.image writeToFile:self.fname atomically:NO];
        [self.delegate performSelectorOnMainThread:@selector(_wroteFrame) withObject:nil waitUntilDone:NO];
        self.fname = nil;
        self.image = nil;
    }
}
@end

//
// multipage pdf writer
//
@interface PaperbackWriter : NSOperation{
    Pages *delegate;
    PDFDocument *book;
    NSData *page;
    NSString *destination;
}
@property (nonatomic, assign) Pages *delegate;
@property (nonatomic, retain) PDFDocument *book;
@property (nonatomic, retain) NSData *page;
@property (nonatomic, retain) NSString *destination;
@end

@implementation PaperbackWriter
@synthesize delegate, book, page, destination;
-(void)main{
    @autoreleasepool{
        if (self.destination){
            [self.book writeToFile:self.destination];
            return;
        }
        PDFDocument *pageDoc = [[PDFDocument alloc] initWithData:self.page];
        [self.book insertPage:[pageDoc pageAtIndex:0] atIndex:[self.book pageCount]];
        [self.delegate performSelectorOnMainThread:@selector(_wroteFrame) withObject:nil waitUntilDone:NO];
    }
}

- (void)dealloc{
    self.book = nil;
    self.page = nil;
    self.destination = nil;
    [super dealloc];
}

@end

@implementation Pages
@synthesize framesWritten, doneWriting, filePath, filePattern, paginated, book, pageCount;


- (id)init{
    if ((self = [super init])) {
        self.framesWritten = self.pageCount = 0;
        queue = [[NSOperationQueue alloc] init];
        queue.maxConcurrentOperationCount = 3;
    }
    return self;
}

- (id)initWithPattern:(NSString *)pat{
    if ((self = [self init])) {
        self.filePattern = pat;
        self.paginated = NO;
    }
    return self;
}

- (id)initWithFile:(NSString *)fname{
    if ((self = [self init])) {
        self.filePath = fname;
        self.paginated = [[[fname pathExtension] lowercaseString] isEqualToString:@"pdf"];
    }
    return self;
}

- (void)addPage:(NSData *)img{
    self.pageCount++;

    if (self.paginated){
        // add a pdf page to the one-and-only output file
        if (!self.book){
            self.book = [[PDFDocument alloc] initWithData:img];
            [self _wroteFrame];
        }else{
            PaperbackWriter *pw = [[[PaperbackWriter alloc] init] autorelease];
            pw.delegate = self;
            pw.book = self.book;
            pw.page = img;
            [queue addOperation:pw];
        }
    }else{
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
}

- (void)closeFile{
    // create an all-done operation to add to the end of the queue
    NSInvocationOperation *done = [[[NSInvocationOperation alloc] initWithTarget:self
                                                                        selector:@selector(_wroteAll)
                                                                          object:nil] autorelease];
    // create an EOF operation if we're generating a paginated pdf file
    if (self.paginated){
        PaperbackWriter *pw = [[[PaperbackWriter alloc] init] autorelease];
        pw.delegate = self;
        pw.book = self.book;
        pw.page = nil;
        pw.destination = self.filePath;

        // make the all-done op wait for our EOF to go through the pipeline before running
        [queue addOperation:pw];
        [done addDependency:pw];
    }

    // stick the done op on the queue and wait for it to call _wroteAll
    [queue addOperation:done];
}

- (void)_wroteFrame{
    self.framesWritten++;
}

- (void)_wroteAll{
    self.doneWriting = YES;
}

- (void)dealloc{
    [queue release];
    [super dealloc];
}

@end
