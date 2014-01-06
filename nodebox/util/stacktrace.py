from sys import exc_info
from os.path import abspath, dirname, relpath
from traceback import format_list, format_exception_only, extract_tb

MODULE_ROOT = abspath(dirname(dirname(__file__)))

def prettify(script=None):
    # use the most recently caught exception
    etype, value, tb = exc_info()

    stack = []
    basedir = dirname(script) if script else None
    for frame in extract_tb(tb):
        # omit module internals from stacktrace (both the gui/* classes and context.py)
        if MODULE_ROOT in frame[0]:
            continue
        # rewrite file paths relative to the script's path (but only if it's shorter)
        if basedir:
            full = frame[0]
            rel = relpath(full, basedir)
            frame = (rel if len(rel) < len(full) else full,) + frame[1:]
        stack.append(frame)

    return "Traceback (most recent call last):\n%s" % "".join(format_list(stack) + format_exception_only(etype, value))
