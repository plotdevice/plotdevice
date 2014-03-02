__version__='1.10'
__MAGIC = "_n_o_d_e_b_o_x_"

def get_version():
    return __version__

app = None
def initialize(mode='headless'):
    """Add c-extensions & Extras directories to sys.path and enable error logging"""
    
    # make sure repeated calls don't keep running the setup routine
    global app
    if app is not None: return
    app = {'headless':False, 'gui':True}.get(mode)
    if app is None: return

    # add the Extras directory to sys.path since every module depends on PyObjC and friends    
    import sys
    try:
        import objc
    except ImportError:
        extras = '/System/Library/Frameworks/Python.framework/Versions/2.7/Extras/lib/python'
        sys.path.extend([extras, '%s/PyObjC'%extras])
        import objc

    # add the ext subdir to the path so we can access the c-extensions
    from os.path import abspath, dirname, join, isdir
    from glob import glob
    for extdir in [join(dirname(abspath(__file__)), "ext")] + glob(join(abspath(dirname(__file__)), '../build/lib.*-2.7/nodebox/ext')):
        if isdir(extdir):
            sys.path.append(extdir)
            break

    # make sure we can find the c-extensions when run from the sdist
    try:
        import cGeo
    except ImportError:
        notfound = "Couldn't locate C extension (try running `python setup.py build` before running from the source dist)."
        raise RuntimeError(notfound)

    # print python exceptions to the console rather than silently failing
    import objc
    objc.setVerbose(True) 

class NodeBoxError(Exception): 
    pass