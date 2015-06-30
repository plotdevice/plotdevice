import re, sys, linecache
from io import open
from os.path import abspath, dirname, relpath
from traceback import format_list, format_exception_only

### encoding-pragma helpers ###

def encoded(pth):
    """Searches the first two lines of a string looking for an `# encoding: ???` comment."""
    re_enc = re.compile(r'coding[=:]\s*([-\w.]+)')
    lines = open(pth, encoding='ascii', errors='ignore').readlines()
    for line in lines[:2]:
        if not line.strip().startswith('#'):
            continue
        m = re_enc.search(line)
        if not m:
            continue
        return m.group(1)
    return "utf-8"

def uncoded(src):
    """Strips out any `# encoding: ???` lines found at the head of the source listing"""
    lines = src.split("\n")
    for i in range(min(len(lines), 2)):
        lines[i] = re.sub(r'#.*coding[=:]\s*([-\w.]+)', '#', lines[i])
    return "\n".join(lines)

### crash reporting helpers ###

def stacktrace(script=None, src=None):
    """print a clean traceback and optionally rewrite the paths relative to a script path"""

    # preprocess the stacktrace
    stack = []
    basedir = dirname(script) if script else None
    err_msg, frames = coredump(script, src, syntax=False)
    for frame in frames:
        # rewrite file paths relative to the script's path (but only if it's shorter)
        if basedir:
            full = frame[0]
            rel = relpath(full, basedir)
            frame = (rel if len(rel) < len(full) else full,) + frame[1:]
        stack.append(frame)

    # return formatted traceback as a single string (with multiple newlines)
    if stack:
        msg = "".join([l for l in format_list(stack) + err_msg])
    else:
        msg = ("".join(err_msg))
        # we only want to prepend the Traceback text for syntax errs
        if 'SyntaxError' not in msg: return msg

    return u"Traceback (most recent call last):\n%s" % msg

def coredump(script=None, src=None, syntax=True):
    """Get a clean stacktrace with absolute paths and source pulled from the editor rather than disk"""
    # use the most recently caught exception
    etype, value, tb = sys.exc_info()
    script = script or '<Untitled>' if src else None
    frames = extract_tb(tb, script, src)

    # syntax errors are peculiar in that there's no stack trace and the line-level
    # error reporting happens in the formatted exception instead. since the editor
    # needs the line number, synthesize a tracebak frame for it (unless the syntax
    # arg is False, as it is when building up the stacktrace message...)
    if syntax and etype is SyntaxError: # and value.filename==script:
        frames.append((script, value.lineno, '', ''))

    return [format_exception_only(etype, value), frames]

def extract_tb(tb, script=None, src=None):
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

    # omit the internal plotdevice stack frames in `dist` builds
    from AppKit import NSBundle
    debug = 'flux' in NSBundle.mainBundle().infoDictionary().get('CFBundleVersion','')
    if not debug:
        moduledir = abspath(dirname(dirname(__file__)))
        return [frame for frame in list if moduledir not in frame[0]]
    return list
