#import <Python.h>
#import <Cocoa/Cocoa.h>

int main(int argc, char *argv[])
{
    @autoreleasepool {
        Py_SetProgramName("/usr/bin/python");
        Py_Initialize();
        PySys_SetArgv(argc, (char **)argv);
        NSString *mainFilePath = [[NSBundle mainBundle] pathForResource:@"nodebox-app" ofType:@"py"];
        const char *mainFilePathPtr = [mainFilePath UTF8String];
        FILE *mainFile = fopen(mainFilePathPtr, "r");
        return PyRun_SimpleFile(mainFile, (char *)[[mainFilePath lastPathComponent] UTF8String]);
    }
}
