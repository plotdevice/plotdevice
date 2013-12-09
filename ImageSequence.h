//
//  ImageSequence.h
//  NodeBox
//
//  Created by Christian Swinehart on 12/8/13.
//
//

#import <Foundation/Foundation.h>

@interface ImageSequence : NSObject{
    NSOperationQueue *queue;
}
@property (nonatomic, retain) NSString *format;
@property (nonatomic, assign) NSInteger *pages;
@property (nonatomic, assign) NSInteger pagesWritten;

- (id)initWithFormat:(NSString *)fmt pages:(NSInteger)n;
- (void)writeData:(NSData *)img toFile:(NSString *)fname;
- (void)_wroteFrame;

@end
