//
//  Pages.h
//  PlotDevice
//
//  Created by Christian Swinehart on 12/8/13.
//
//

#import <Foundation/Foundation.h>

@interface Pages : NSObject{
    NSOperationQueue *queue;
    NSInteger framesWritten;
    NSInteger pageCount;
    NSString *filePath;
    NSString *filePattern;
    BOOL doneWriting;
}
@property (nonatomic, copy) NSString *filePath;
@property (nonatomic, copy) NSString *filePattern;
@property (nonatomic, assign) NSInteger pageCount;
@property NSInteger framesWritten;
@property BOOL doneWriting;

- (id)initWithPattern:(NSString *)pat;
- (id)initWithFile:(NSString *)fname;
- (void)closeFile;

// internal callbacks
- (void)wrotePage;
- (void)wroteLast;

@end
