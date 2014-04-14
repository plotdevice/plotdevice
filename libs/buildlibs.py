import os
import errno
from glob import glob
from os.path import dirname, basename, abspath, isdir

libs_root = dirname(abspath(__file__))

def mkdirs(newdir, mode=0777):
    try: os.makedirs(newdir, mode)
    except OSError, err:
        # Reraise the error unless it's about an already existing directory
        if err.errno != errno.EEXIST or not isdir(newdir):
            raise

def build_libraries():
    print "Compiling required c-extensions"

    # Store the current working directory for later.
    # Find all setup.py files in the current folder
    setup_scripts = glob('%s/*/setup.py'%libs_root)
    for setup_script in setup_scripts:
        lib_name = basename(dirname(setup_script))
        print "Building %s..."% lib_name
        # run_setup gave some wonky errors, so we're defaulting to a simple os.system call.
        os.chdir(dirname(setup_script))
        # temporary workaround for broken clang 5.1 error: `unknown argument: '-mno-fused-madd'`
        cmd = ('set -x ARCHFLAGS=-Wno-error=unused-command-line-argument-hard-error-in-future '
                '&& python2.7 setup.py -q build')
        result = os.system(cmd)
        if result > 0:
            raise OSError("Could not build %s" % lib_name)
        os.chdir(libs_root)

    # Make sure the destination folder exists.
    mkdirs('../build/ext')

    # Copy all build results to the ../build/ext folder.
    build_dirs = glob("%s/*/build/lib*"%libs_root)
    for build_dir in build_dirs:
        lib_name = dirname(dirname(build_dir))
        # print "Copying", lib_name
        cmd = 'cp -R -p %s/* ../build/ext' % build_dir
        # print cmd
        result = os.system(cmd)
        if result > 0:
            raise OSError("Could not copy %s" % lib_name)

def clean_build_files():
    print "Cleaning all library build files..."

    build_dirs = glob('%s/*/build'%libs_root)
    for build_dir in build_dirs:
        lib_name = dirname(build_dir)
        print "Cleaning", lib_name
        os.system('rm -r %s' % build_dir)

if __name__=='__main__':
    import sys
    clean = len(sys.argv)>1 and sys.argv[1]=='clean'

    if clean or os.environ.get('ACTION')=='clean':
        clean_build_files()
    else:
        build_libraries()
