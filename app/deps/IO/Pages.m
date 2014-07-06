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

//
// multipage pdf writer
//
@interface PaperbackWriter : NSOperation{
    Pages *delegate;
    NSData *page;
    NSString *destination;
}
@property (nonatomic, assign) Pages *delegate;
@property (nonatomic, retain) NSData *page;
@property (nonatomic, retain) NSString *destination;
@end

@implementation PaperbackWriter
@synthesize delegate, page, destination;
-(void)main{
    @autoreleasepool{
        if (self.destination){
            [self.delegate.book writeToFile:self.destination];
            [self.delegate wroteLast];
        }else{
            PDFDocument *pageDoc = [[PDFDocument alloc] initWithData:self.page];
            if (!self.delegate.book){
                self.delegate.book = pageDoc;
            }else{
                [self.delegate.book insertPage:[pageDoc pageAtIndex:0] atIndex:[self.delegate.book pageCount]];
            }
            [self.delegate wrotePage];
        }
    }
}

- (void)dealloc{
    self.page = nil;
    self.destination = nil;
    [super dealloc];
}

@end


@implementation Pages
@synthesize framesWritten, doneWriting, filePath, filePattern, paginated, book, pageCount;


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
        PaperbackWriter *pw = [[[PaperbackWriter alloc] init] autorelease];
        pw.delegate = self;
        pw.page = img;
        [queue addOperation:pw];
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
    if (self.paginated){
        // create an EOF operation if we're generating a paginated pdf file
        PaperbackWriter *pw = [[[PaperbackWriter alloc] init] autorelease];
        pw.delegate = self;
        pw.page = nil;
        pw.destination = self.filePath;
        [queue addOperation:pw];
    }else{
        // create an all-done operation to add to the end of the queue
        IterWriter *iw = [[[IterWriter alloc] init] autorelease];
        iw.delegate = self;
        [queue addOperation:iw];
    }
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
