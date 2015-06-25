#import <Cocoa/Cocoa.h>
#import <Python.h>

int main(int argc, char *argv[])
{
    @autoreleasepool{
        Py_SetProgramName("/usr/bin/python");
        Py_Initialize();
        PySys_SetArgv(argc, (char **)argv);
        NSString *mainFilePath = [[NSBundle mainBundle] pathForResource:@"plotdevice-app" ofType:@"py"];
        return PyRun_SimpleFile(fopen([mainFilePath UTF8String], "r"), (char *)[mainFilePath UTF8String]);
    }
}
