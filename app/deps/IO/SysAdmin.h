//
//  SysAdmin.h
//  PlotDevice
//
//  Created by Christian Swinehart on 12/13/13.
//
//

#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>

@interface SysAdmin : NSObject
+ (BOOL)createSymlink:(NSString *)toolPath;
+ (void)handleInterrupt;
@end
