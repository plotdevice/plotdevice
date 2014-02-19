//
//  SysAdmin.h
//  NodeBox
//
//  Created by Christian Swinehart on 12/13/13.
//
//

#import <Foundation/Foundation.h>

@interface SysAdmin : NSObject
+ (BOOL)createSymlink:(NSString *)toolPath;
@end
