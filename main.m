#import <Python.h>
#import <Cocoa/Cocoa.h>

int main(int argc, char *argv[])
{
    @autoreleasepool {
        NSBundle *mainBundle = [NSBundle mainBundle];
        NSString *resourcePath = [mainBundle resourcePath];
        setenv("PYTHONPATH", [[resourcePath stringByAppendingPathComponent:@"python"] UTF8String], 1);        

        NSArray *possibleMainExtensions = @[@"py", @"pyc", @"pyo"];
        NSString *mainFilePath = nil;
        for (NSString *possibleMainExtension in possibleMainExtensions) {
            mainFilePath = [mainBundle pathForResource: @"macboot" ofType: possibleMainExtension];
            if ( mainFilePath != nil ) break;
        }
        
        if ( !mainFilePath ) {
            [NSException raise: NSInternalInconsistencyException format: @"%s:%d main() Failed to find the macboot.{py,pyc,pyo} file in the application wrapper's Resources directory.", __FILE__, __LINE__];
        }
        
        Py_SetProgramName("/usr/bin/python");
        Py_Initialize();
        PySys_SetArgv(argc, (char **)argv);
        
        const char *mainFilePathPtr = [mainFilePath UTF8String];
        FILE *mainFile = fopen(mainFilePathPtr, "r");
        int result = PyRun_SimpleFile(mainFile, (char *)[[mainFilePath lastPathComponent] UTF8String]);
        
        if ( result != 0 )
        [NSException raise: NSInternalInconsistencyException
                    format: @"%s:%d main() PyRun_SimpleFile failed with file '%@'.  See console for errors.", __FILE__, __LINE__, mainFilePath];
        return result;
    }
}
