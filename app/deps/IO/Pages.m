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
@interface ImageWriter : NSOperation{
    Pages *delegate;
    NSString *fname;
    NSData *image;
}
@property (nonatomic, assign) Pages *delegate;
@property (nonatomic, retain) NSString *fname;
@property (nonatomic, retain) NSData *image;
@end

@implementation ImageWriter
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
@synthesize framesWritten, doneWriting, filePath, paginated, book, pageCount;
- (id)initWithFile:(NSString *)fname paginated:(BOOL)isMultipage{
	if ((self = [super init])) {
		self.framesWritten = self.pageCount = 0;
        self.paginated = isMultipage;
        queue = [[NSOperationQueue alloc] init];

        if (isMultipage){
            self.filePath = fname;
            queue.maxConcurrentOperationCount = 1;
        }else{
            NSString *ext = [fname pathExtension];
            NSString *basename = [fname stringByDeletingPathExtension];
            NSString *seq = @"%04d";
            self.filePath = [NSString stringWithFormat:@"%@-%@.%@", basename, seq, ext];
            queue.maxConcurrentOperationCount = 3;
        }

	}
	return self;
}

- (void)addPage:(NSData *)img{
    if (self.paginated){
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
        ImageWriter *iw = [[[ImageWriter alloc] init] autorelease];
        iw.delegate = self;
        iw.fname = [NSString stringWithFormat:self.filePath, ++self.pageCount];;
        iw.image = img;
        [queue addOperation:iw];
    }
}

- (void)closeFile{
    if (!self.paginated) return;

    PaperbackWriter *pw = [[[PaperbackWriter alloc] init] autorelease];
    pw.delegate = self;
    pw.book = self.book;
    pw.page = nil;
    pw.destination = self.filePath;
    [queue addOperation:pw];

    NSInvocationOperation *done = [[NSInvocationOperation alloc] initWithTarget:self
                                                                        selector:@selector(_wroteAll)
                                                                          object:nil];
    [done addDependency:pw];
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
