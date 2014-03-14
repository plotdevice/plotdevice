import linecache
from sys import exc_info
from os.path import abspath, dirname, relpath
from traceback import format_list, format_exception_only

def stacktrace(script=None, src=None):
    """print a clean traceback and optionally rewrite the paths relative to a script path"""

    # preprocess the stacktrace
    stack = []
    basedir = dirname(script) if script else None
    err_msg, frames = coredump(script, src)
    # print "raw", format_list(frames)
    for frame in frames:
        # rewrite file paths relative to the script's path (but only if it's shorter)
        if basedir:
            full = frame[0]
            rel = relpath(full, basedir)
            frame = (rel if len(rel) < len(full) else full,) + frame[1:]
        stack.append(frame)

    # return formatted traceback as a single string (with multiple newlines)
    if stack:
        return "Traceback (most recent call last):\n%s" % "".join(format_list(stack) + err_msg)
    else:
        return "".join(err_msg)

def coredump(script=None, src=None):
    """Get a clean stacktrace with absolute paths and source pulled from the editor rather than disk"""
    # use the most recently caught exception
    etype, value, tb = exc_info()
    script = script or '<Untitled>' if src else None
    frames = extract_tb(tb, script, src)
    return [format_exception_only(etype, value), frames]

def extract_tb(tb, script=None, src=None, debug=True):
    """Return a list of pre-processed entries from traceback."""
    list = []
    n = 0
    while tb is not None:
        f = tb.tb_frame
        lineno = tb.tb_lineno
        co = f.f_code
        filename = co.co_filename
        name = co.co_name
        if filename==script:
            line = src.split('\n')[lineno-1]
        else:
            linecache.checkcache(filename)
            line = linecache.getline(filename, lineno, f.f_globals)
        if line: line = line.strip()
        else: line = None
        list.append((filename, lineno, name, line))
        tb = tb.tb_next

    # omit the internal plotdevice stack frames unless debugging
    if not debug:
        moduledir = abspath(dirname(dirname(__file__)))
        return [frame for frame in list if moduledir not in frame[0]]
    return list

def resource_path(resource=None):
    """Return absolute path of the rsrc directory (used by task.py)"""
    from os.path import abspath, dirname, exists, join
    module_root = abspath(dirname(__file__))
    rsrc_root = join(module_root, 'rsrc')

    if not exists(rsrc_root):
        # hack to run in-place in sdist
        from glob import glob
        for pth in glob(join(module_root, '../../build/lib/plotdevice/rsrc')):
            rsrc_root = abspath(pth)
            break
        else:
            notfound = "Couldn't locate resources directory (try running `python setup.py build` before running from the source dist)."
            raise RuntimeError(notfound)
    if resource:
        return join(rsrc_root, resource)
    return rsrc_root

# make the main classes from the submodules accessible
from plotdevice.run.export import MovieExportSession, ImageExportSession
from plotdevice.run.listener import CommandListener
from plotdevice.run.sandbox import Sandbox