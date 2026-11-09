#import <Cocoa/Cocoa.h>
#include <dlfcn.h>

int main(int argc, char *argv[])
{
    @autoreleasepool{
        // launch using the user's preferred version of the Python framework (free-threaded or vanilla)
        BOOL freeThreaded = [[NSUserDefaults standardUserDefaults] boolForKey:@"plotdevice:free-threading"];
        NSString *name = freeThreaded ? @"PythonT" : @"Python";
        NSString *version = [[[NSBundle mainBundle] privateFrameworksPath] stringByAppendingFormat:@"/%@.framework/Versions/Current", name];
        NSString *interpreter = [version stringByAppendingString:freeThreaded ? @"/bin/python3t" : @"/bin/python3"];
        NSString *mainFilePath = [[NSBundle mainBundle] pathForResource:@"plotdevice-app" ofType:@"py"];
        void *libpython = dlopen([[version stringByAppendingPathComponent:name] fileSystemRepresentation], RTLD_NOW | RTLD_GLOBAL);
        int (*Py_BytesMain)(int, char **) = libpython ? dlsym(libpython, "Py_BytesMain") : NULL;
        if (!Py_BytesMain){
            NSLog(@"Could not load %@: %s", name, dlerror());
            return 1;
        }

        char **py_argv = (char **)calloc(argc + 5, sizeof(char *));
        int py_argc = 0;
        py_argv[py_argc++] = (char *)[interpreter fileSystemRepresentation];
        py_argv[py_argc++] = "-B"; // don't generate bytecode in the signed bundle
        if (freeThreaded && !getenv("PYTHON_GIL")){
            // don't let user imports disable the GIL
            py_argv[py_argc++] = "-X";
            py_argv[py_argc++] = "gil=0";
        }
        py_argv[py_argc++] = (char *)[mainFilePath fileSystemRepresentation];
        for (int i=1; i<argc; i++){
            py_argv[py_argc++] = argv[i];
        }
        return Py_BytesMain(py_argc, py_argv);
    }
}
