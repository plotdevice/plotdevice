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

    # BUG
    # this means we don't catch errors in autosaved `draft' docs...
    if etype is SyntaxError and value.filename==script:
        frames.append((script, value.lineno, '', ''))

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

# make the main classes from the submodules accessible
from plotdevice.run.export import MovieExportSession, ImageExportSession
from plotdevice.run.sandbox import Sandbox