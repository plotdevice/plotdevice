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
    NSInteger framesWritten;
}
@property (nonatomic, assign) NSInteger framesWritten;

- (id)init;
- (void)writeData:(NSData *)img toFile:(NSString *)fname;
- (void)_wroteFrame;

@end
