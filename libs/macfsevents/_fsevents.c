#include <Python.h>
#include <CoreFoundation/CoreFoundation.h>
#include <CoreServices/CoreServices.h>
#include <signal.h>
#include "compat.h"

#if PY_VERSION_HEX < 0x02050000 && !defined(PY_SSIZE_T_MIN)
typedef int Py_ssize_t;
#define PY_SSIZE_T_MAX INT_MAX
#define PY_SSIZE_T_MIN INT_MIN
#endif

#if PY_MAJOR_VERSION >= 3
  #define MOD_ERROR_VAL NULL
  #define MOD_SUCCESS_VAL(val) val
  #define MOD_INIT(name) PyMODINIT_FUNC PyInit_##name(void)
  #define MOD_DEF(ob, name, doc, methods) \
          static struct PyModuleDef moduledef = { \
            PyModuleDef_HEAD_INIT, name, doc, -1, methods, }; \
          ob = PyModule_Create(&moduledef);
#else
  #define MOD_ERROR_VAL
  #define MOD_SUCCESS_VAL(val)
  #define MOD_INIT(name) void init##name(void)
  #define MOD_DEF(ob, name, doc, methods) \
          ob = Py_InitModule3(name, methods, doc);
#endif

const char callback_error_msg[] = "Unable to call callback function.";

PyObject* loops = NULL;
PyObject* streams = NULL;

typedef struct {
    PyObject* callback;
    FSEventStreamRef stream;
    CFRunLoopRef loop;
    PyThreadState* state;
} FSEventStreamInfo;

static void handler(FSEventStreamRef stream,
                    FSEventStreamInfo* info,
                    int numEvents,
                    const char *const eventPaths[],
                    const FSEventStreamEventFlags *eventMasks,
                    const uint64_t *eventIDs) {
  
    PyGILState_STATE state = PyGILState_Ensure();
    PyThreadState *_save = PyEval_SaveThread();
    PyEval_RestoreThread(info->state);

    /* convert event data to Python objects */
    PyObject *eventPathList = PyList_New(numEvents);
    PyObject *eventMaskList = PyList_New(numEvents);
    if ((!eventPathList) || (!eventMaskList))
        return;

    int i;
    for (i = 0; i < numEvents; i++) {
        PyObject *str = PyBytes_FromString(eventPaths[i]);

        #if PY_MAJOR_VERSION >= 3
            PyObject *num = PyLong_FromLong(eventMasks[i]);
        #else
            PyObject *num = PyInt_FromLong(eventMasks[i]);
        #endif

        if ((!num) || (!str)) {
            Py_DECREF(eventPathList);
            Py_DECREF(eventMaskList);
            return;
        }
        PyList_SET_ITEM(eventPathList, i, str);
        PyList_SET_ITEM(eventMaskList, i, num);
    }

    if (PyObject_CallFunction(info->callback, "OO", eventPathList,
                              eventMaskList) == NULL) {
        /* may can return NULL if an exception is raised */
        if (!PyErr_Occurred())
            PyErr_SetString(PyExc_ValueError, callback_error_msg);

        /* stop listening */
        CFRunLoopStop(info->loop);
    }

    PyThreadState_Swap(_save);
    PyGILState_Release(state);
}

static PyObject* pyfsevents_loop(PyObject* self, PyObject* args) {
    PyObject* thread;
    if (!PyArg_ParseTuple(args, "O:loop", &thread))
        return NULL;

    PyEval_InitThreads();

    /* allocate info and store thread state */
    PyObject* value = PyDict_GetItem(loops, thread);

    if (!PyCapsule_IsValid(value, NULL)) {
        CFRunLoopRef loop = CFRunLoopGetCurrent();
        value = PyCapsule_New((void*) loop, NULL, NULL);
        PyDict_SetItem(loops, thread, value);
        Py_INCREF(thread);
        Py_INCREF(value);
    }

    /* no timeout, block until events */
    Py_BEGIN_ALLOW_THREADS;
    CFRunLoopRun();
    Py_END_ALLOW_THREADS;

    /* cleanup state info data */
    if (PyDict_DelItem(loops, thread) == 0) {
        Py_DECREF(thread);
        Py_INCREF(value);
    }

    if (PyErr_Occurred()) return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject* pyfsevents_schedule(PyObject* self, PyObject* args) {
    PyObject* thread;
    PyObject* stream;
    PyObject* paths;
    PyObject* callback;

    if (!PyArg_ParseTuple(args, "OOOO:schedule",
                          &thread, &stream, &callback, &paths))
        return NULL;

    /* stream must not already have been scheduled */
    if (PyDict_Contains(streams, stream) == 1) {
        return NULL;
    }

    /* create path array */
    CFMutableArrayRef cfArray;
    cfArray = CFArrayCreateMutable(kCFAllocatorDefault, 1,
                                   &kCFTypeArrayCallBacks);
    if (cfArray == NULL)
        return NULL;

    int i;
    Py_ssize_t size = PyList_Size(paths);
    const char* path;
    CFStringRef cfStr;
    for (i=0; i<size; i++) {
        path = PyBytes_AS_STRING(PyList_GetItem(paths, i));
        cfStr = CFStringCreateWithCString(kCFAllocatorDefault,
                                          path,
                                          kCFStringEncodingUTF8);
        CFArraySetValueAtIndex(cfArray, i, cfStr);
        CFRelease(cfStr);
    }

    /* allocate stream info structure */
    FSEventStreamInfo * info = PyMem_New(FSEventStreamInfo, 1);

    /* create event stream */
    FSEventStreamContext context = {0, (void*) info, NULL, NULL, NULL};
    FSEventStreamRef fsstream = NULL;
    fsstream = FSEventStreamCreate(kCFAllocatorDefault,
                                   (FSEventStreamCallback)&handler,
                                   &context,
                                   cfArray,
                                   kFSEventStreamEventIdSinceNow,
                                   0.01, // latency
                                   kFSEventStreamCreateFlagNoDefer);
    CFRelease(cfArray);

    PyObject* value = PyCapsule_New((void*) fsstream, NULL, NULL);
    PyDict_SetItem(streams, stream, value);

    /* get runloop reference from observer info data or current */
    value = PyDict_GetItem(loops, thread);
    CFRunLoopRef loop;
    if (!PyCapsule_IsValid(value, NULL)) {
        loop = CFRunLoopGetCurrent();
    } else {
        loop = (CFRunLoopRef) PyCapsule_GetPointer(value, NULL);
    }

    FSEventStreamScheduleWithRunLoop(fsstream, loop, kCFRunLoopDefaultMode);

    /* set stream info for callback */
    info->callback = callback;
    info->stream = fsstream;
    info->loop = loop;
    info->state = PyThreadState_Get();
    Py_INCREF(callback);

    /* start event streams */
    if (!FSEventStreamStart(fsstream)) {
        FSEventStreamInvalidate(fsstream);
        FSEventStreamRelease(fsstream);
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject* pyfsevents_unschedule(PyObject* self, PyObject* stream) {
    PyObject* value = PyDict_GetItem(streams, stream);
    PyDict_DelItem(streams, stream);
    if (PyCapsule_IsValid(value, NULL)) {
	FSEventStreamRef fsstream = PyCapsule_GetPointer(value, NULL);

	FSEventStreamStop(fsstream);
	FSEventStreamInvalidate(fsstream);
	FSEventStreamRelease(fsstream);
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject* pyfsevents_stop(PyObject* self, PyObject* thread) {
    PyObject* value = PyDict_GetItem(loops, thread);
    if (PyCapsule_IsValid(value, NULL)) {
        CFRunLoopRef loop = PyCapsule_GetPointer(value, NULL);

	/* stop runloop */
	if (loop) {
	    CFRunLoopStop(loop);
	}
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef methods[] = {
    {"loop", pyfsevents_loop, METH_VARARGS, NULL},
    {"stop", pyfsevents_stop, METH_O, NULL},
    {"schedule", pyfsevents_schedule, METH_VARARGS, NULL},
    {"unschedule", pyfsevents_unschedule, METH_O, NULL},
    {NULL},
};

static char doc[] = "Low-level FSEvent interface.";

MOD_INIT(cEvents) {
    PyObject* mod;

    MOD_DEF(mod, "cEvents", doc, methods)

    if (mod == NULL)
        return MOD_ERROR_VAL;

    PyModule_AddIntConstant(mod, "CF_POLLIN", kCFFileDescriptorReadCallBack);
    PyModule_AddIntConstant(mod, "CF_POLLOUT", kCFFileDescriptorWriteCallBack);
    PyModule_AddIntConstant(mod, "FS_IGNORESELF", kFSEventStreamCreateFlagIgnoreSelf);
    PyModule_AddIntConstant(mod, "FS_FILEEVENTS", kFSEventStreamCreateFlagFileEvents);
    PyModule_AddIntConstant(mod, "FS_ITEMCREATED", kFSEventStreamEventFlagItemCreated);
    PyModule_AddIntConstant(mod, "FS_ITEMREMOVED", kFSEventStreamEventFlagItemRemoved);
    PyModule_AddIntConstant(mod, "FS_ITEMINODEMETAMOD", kFSEventStreamEventFlagItemInodeMetaMod);
    PyModule_AddIntConstant(mod, "FS_ITEMRENAMED", kFSEventStreamEventFlagItemRenamed);
    PyModule_AddIntConstant(mod, "FS_ITEMMODIFIED", kFSEventStreamEventFlagItemModified);
    PyModule_AddIntConstant(mod, "FS_ITEMFINDERINFOMOD", kFSEventStreamEventFlagItemFinderInfoMod);
    PyModule_AddIntConstant(mod, "FS_ITEMCHANGEOWNER", kFSEventStreamEventFlagItemChangeOwner);
    PyModule_AddIntConstant(mod, "FS_ITEMXATTRMOD", kFSEventStreamEventFlagItemXattrMod);
    PyModule_AddIntConstant(mod, "FS_ITEMISFILE", kFSEventStreamEventFlagItemIsFile);
    PyModule_AddIntConstant(mod, "FS_ITEMISDIR", kFSEventStreamEventFlagItemIsDir);
    PyModule_AddIntConstant(mod, "FS_ITEMISSYMLINK", kFSEventStreamEventFlagItemIsSymlink);
    loops = PyDict_New();
    streams = PyDict_New();

    return MOD_SUCCESS_VAL(mod);
}

