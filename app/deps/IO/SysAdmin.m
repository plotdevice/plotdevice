//
//  SysAdmin.m
//  PlotDevice
//
//  Created by Christian Swinehart on 12/13/13.
//
//

#import "SysAdmin.h"

@implementation SysAdmin

+ (BOOL)createSymlink:(NSString *)toolPath{
    NSString *toolDir = [toolPath stringByDeletingLastPathComponent];
    NSString *bundle_path = [[NSBundle mainBundle ] bundlePath];
    NSString *console_py = [bundle_path stringByAppendingString:@"/Contents/SharedSupport/plotdevice"];
    OSStatus status;
    FILE *pipe = NULL;
        
    char *src = (char *)[console_py UTF8String];
    char *dst = (char *)[toolPath UTF8String];
    char *dstdir = (char *)[toolDir UTF8String];
    char *mkdir = "/bin/mkdir";
    char *mkdirArgs[] = {"-p", dstdir, NULL};
    char *link = "/bin/ln";
    char *linkArgs[] = {"-s", "-f", "-F", "-h", src, dst, NULL};

    AuthorizationRef ref;
    AuthorizationFlags flags = kAuthorizationFlagDefaults;

    #pragma clang diagnostic ignored "-Wdeprecated-declarations" 
    status = AuthorizationCreate(NULL, kAuthorizationEmptyEnvironment, flags, &ref);
    if (status) return NO;
    status = AuthorizationExecuteWithPrivileges(ref, mkdir, flags, mkdirArgs, &pipe);
    if (status) return NO;
    status = AuthorizationExecuteWithPrivileges(ref, link, flags, linkArgs, &pipe);
    if (status) return NO;
    return YES;
    #pragma clang diagnostic warning "-Wdeprecated-declarations"
}

+ (void)handleInterrupt{
    dispatch_source_t source = dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL, SIGINT, 0, dispatch_get_global_queue(0, 0));
    dispatch_source_set_event_handler(source, ^{
        // quit on ctrl-c
        [NSApp terminate:nil];
    });
    dispatch_resume(source);

    struct sigaction action = { 0 };
    action.sa_handler = SIG_IGN;
    sigaction(SIGINT, &action, NULL);
}
@end
