//
//  Pages.h
//  PlotDevice
//
//  Created by Christian Swinehart on 12/8/13.
//
//

#import <Foundation/Foundation.h>
#import <Quartz/Quartz.h>

@interface Pages : NSObject{
    NSOperationQueue *queue;
    NSInteger framesWritten;
    PDFDocument *book;
    NSInteger pageCount;
    BOOL paginated;
    NSString *filePath;
    BOOL doneWriting;
}
@property (nonatomic, assign) NSInteger framesWritten;
@property (nonatomic, assign) NSInteger pageCount;
@property (nonatomic, assign) BOOL paginated;
@property (nonatomic, retain) PDFDocument *book;
@property (nonatomic, copy) NSString *filePath;
@property (assign) BOOL doneWriting;

- (id)initWithFile:(NSString *)fname paginated:(BOOL)isMultipage;
// - (void)writeData:(NSData *)img toFile:(NSString *)fname;
- (void)closeFile;
- (void)_wroteFrame;

@end
