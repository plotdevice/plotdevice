from sys import exc_info
from os.path import abspath, dirname, relpath
from traceback import format_list, format_exception_only, extract_tb

def stacktrace(script=None):
    """print a clean traceback and optionally rewrite the paths relative to a script path"""

    # use the most recently caught exception
    etype, value, tb = exc_info()

    # preprocess the stacktrace
    stack = []
    basedir = dirname(script) if script else None
    moduledir = abspath(dirname(dirname(__file__)))
    for frame in extract_tb(tb):
        # omit module internals from stacktrace (both the gui/* classes and context.py)
        if moduledir in frame[0]:
            continue
        # rewrite file paths relative to the script's path (but only if it's shorter)
        if basedir:
            full = frame[0]
            rel = relpath(full, basedir)
            frame = (rel if len(rel) < len(full) else full,) + frame[1:]
        stack.append(frame)

    # return formatted traceback as a single string (with multiple newlines)
    return "Traceback (most recent call last):\n%s" % "".join(format_list(stack) + format_exception_only(etype, value))

# make the main classes from the submodules accessible
from nodebox.run.export import MovieExportSession, ImageExportSession
from nodebox.run.listener import CommandListener
from nodebox.run.sandbox import Sandbox