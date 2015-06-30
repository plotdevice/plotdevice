#import <Cocoa/Cocoa.h>
#import <Python.h>

#define str(s) #s

int main(int argc, char *argv[])
{
    @autoreleasepool{
        NSProcessInfo *proc = [NSProcessInfo processInfo];
        NSString *mainFilePath = [[NSBundle mainBundle] pathForResource:@"plotdevice-app" ofType:@"py"];
        NSString *interpreter = [NSString stringWithUTF8String:str(PYTHON_BIN)];
#ifdef PY3K
        wchar_t *py_bin = (wchar_t *)[interpreter cStringUsingEncoding:NSUTF32LittleEndianStringEncoding];
        wchar_t **py_argv = (wchar_t **)calloc(argc, sizeof(wchar_t *));
        for (int i=0; i<argc; i++){
          py_argv[i] = (wchar_t *)[proc.arguments[i] cStringUsingEncoding:NSUTF32LittleEndianStringEncoding];
        }
#else
        char *py_bin = (char *)[interpreter UTF8String];
        char **py_argv = argv;
#endif
        Py_SetProgramName(py_bin);
        Py_Initialize();
        PySys_SetArgv(argc, py_argv);
        return PyRun_SimpleFile(fopen([mainFilePath UTF8String], "r"), (char *)[mainFilePath UTF8String]);
    }
}
