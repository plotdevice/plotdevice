#import <Python.h>
#import <Cocoa/Cocoa.h>

int main(int argc, char *argv[])
{
    @autoreleasepool {
        NSBundle *mainBundle = [NSBundle mainBundle];
        NSString *mainFilePath = [mainBundle pathForResource: @"nodebox-app" ofType:@"py"];
        if ( !mainFilePath ) {
            [NSException raise: NSInternalInconsistencyException format: @"%s:%d main() Failed to find the nodebox-app.py file in the application wrapper's Resources directory.", __FILE__, __LINE__];
        }
        
        Py_SetProgramName("/usr/bin/python");
        Py_Initialize();
        PySys_SetArgv(argc, (char **)argv);
        
        const char *mainFilePathPtr = [mainFilePath UTF8String];
        FILE *mainFile = fopen(mainFilePathPtr, "r");
        int result = PyRun_SimpleFile(mainFile, (char *)[[mainFilePath lastPathComponent] UTF8String]);
        
//        if ( result != 0 )
//        [NSException raise: NSInternalInconsistencyException
//                    format: @"%s:%d main() PyRun_SimpleFile failed with file '%@'.  See console for errors.", __FILE__, __LINE__, mainFilePath];
        return result;
    }
}
