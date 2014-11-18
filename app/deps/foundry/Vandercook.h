//
//  Vandercook.h
//  PlotDevice
//
//  Created by Christian Swinehart on 11/08/14.
//
//

#import <Cocoa/Cocoa.h>

@interface Vandercook : NSObject
+ (NSDictionary *)aatAttributes:(NSDictionary *)options;
+ (NSBezierPath *)traceGlyphs:(NSRange)glyph_range atOffset:(NSPoint)offset withLayout:(NSLayoutManager *)layout;
+ (NSArray *)lineFragmentsInRange:(NSRange)char_range withLayout:(NSLayoutManager *)layout;
+ (NSArray *)textContainersInRange:(NSRange)rng withLayout:(NSLayoutManager *)layout;
@end
