import sys
from os.path import join, abspath, dirname, exists

# do some special-case handling when the module is imported from within the source dist.
# if the libraries build dir exists, add it to the path so we can pick up the .so files,
# otherwise leave the path as it is and bomb on failure to find the libraries.
lib_root = abspath(dirname(__file__))
inplace = exists(join(lib_root, '../../etc/main.m'))
if inplace:
    sys.path.append(join(lib_root, '../../build/ext'))

try:
    import geometry, io, pathmatics
except ImportError:
    print "failed with path", sys.path
    suggest = ' (try running `python setup.py build` before using the module from within the repository)'
    notfound = "Couldn't locate C extensions%s." % (suggest if inplace else '')
    raise RuntimeError(notfound)

