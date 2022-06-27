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
    // thanks to: https://www.mikeash.com/pyblog/friday-qa-2011-04-01-signal-handling.html
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

+ (void)watchFile:(NSString*)path for:(NSObject *)observer onUpdate:(SEL)handler {
    // thanks to: https://web.archive.org/web/20170528144758/http://www.davidhamrick.com/2011/10/13/Monitoring-Files-With-GCD-Being-Edited-With-A-Text-Editor.html
    dispatch_queue_t queue = dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0);
    int fildes = open([path UTF8String], O_EVTONLY);
    __block dispatch_source_t source = dispatch_source_create(DISPATCH_SOURCE_TYPE_VNODE,fildes,
                                                              DISPATCH_VNODE_DELETE | DISPATCH_VNODE_WRITE | DISPATCH_VNODE_EXTEND | DISPATCH_VNODE_ATTRIB | DISPATCH_VNODE_LINK | DISPATCH_VNODE_RENAME | DISPATCH_VNODE_REVOKE,
                                                              queue);
    dispatch_source_set_event_handler(source, ^{
        unsigned long flags = dispatch_source_get_data(source);
        if(flags & DISPATCH_VNODE_DELETE){
            dispatch_source_cancel(source);
            [SysAdmin watchFile:path for:observer onUpdate:handler];
        }

        dispatch_async(dispatch_get_main_queue(), ^{
            [observer performSelector:handler];
        });
    });
    dispatch_source_set_cancel_handler(source, ^(void)
    {
        close(fildes);
    });
    dispatch_resume(source);
}
@end
