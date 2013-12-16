#import <Cocoa/Cocoa.h>
#import <Python.h>

@interface TaskAppDelegate : NSObject{
    int _argc;
    char **_argv;
}
- (id)initWithArgc:(int)argc argv:(char **)argv;
@end

@implementation TaskAppDelegate
- (id)initWithArgc:(int)argc argv:(char **)argv{
    if ((self = [super init])) {
        _argc = argc;
        _argv = argv;
    }
    return self;
}
- (void)applicationDidFinishLaunching:(NSNotification *)aNotification{
    NSBundle *mainBundle = [NSBundle mainBundle];
    NSString *taskPath = [[mainBundle resourcePath] stringByAppendingString:@"/python/nodebox/run/task.py"];
    Py_SetProgramName("/usr/bin/python");
    Py_Initialize();
    PySys_SetArgv(_argc, (char **)_argv);

    const char *taskPathPtr = [taskPath UTF8String];
    FILE *mainFile = fopen(taskPathPtr, "r");
    int result = PyRun_SimpleFile(mainFile, taskPathPtr);
    if ( result != 0 ) [[NSApplication sharedApplication] terminate:self];
}
@end

int main(int argc, const char * argv[])
{
    @autoreleasepool {
        [NSApplication sharedApplication];
        [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];
        id delegate = [[TaskAppDelegate alloc] initWithArgc:argc argv:(char **)argv];
        [NSApp setDelegate:delegate];
        [NSApp run];
    }
    
    return 0;
}
