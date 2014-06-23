import os
import errno
from glob import glob
from os.path import dirname, basename, abspath, isdir, join

libs_root = dirname(abspath(__file__))

# temporary workaround for broken clang 5.1 error: `unknown argument: '-mno-fused-madd'`
quickfix = 'ARCHFLAGS=-Wno-error=unused-command-line-argument-hard-error-in-future'
build_cmd = '%s python2.7 setup.py -q build'%quickfix

def mkdirs(newdir, mode=0777):
    try: os.makedirs(newdir, mode)
    except OSError, err:
        # Reraise the error unless it's about an already existing directory
        if err.errno != errno.EEXIST or not isdir(newdir):
            raise

def build_libraries(dst_root):
    print "Compiling required c-extensions"

    # Store the current working directory for later.
    # Find all setup.py files in the current folder
    setup_scripts = glob('%s/*/setup.py'%libs_root)
    for setup_script in setup_scripts:
        lib_name = basename(dirname(setup_script))
        print "Building %s..."% lib_name
        os.chdir(dirname(setup_script))
        result = os.system(build_cmd) # call the lib's setup.py
        if result > 0:
            raise OSError("Could not build %s" % lib_name)
        os.chdir(libs_root)

    # Make sure the destination folder exists.
    mkdirs(dst_root)

    # Copy all build results to the ../../build/deps folder.
    build_dirs = glob("%s/*/build/lib*"%libs_root)
    for build_dir in build_dirs:
        lib_name = dirname(dirname(build_dir))
        # print "Copying", lib_name
        cmd = 'cp -R -p %s/* %s' % (build_dir, dst_root)
        print cmd
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

    if len(sys.argv)>1:
        arg = sys.argv[1]
        if os.path.exists(arg):
            dst_root = join(arg, 'plotdevice/lib')
            build_libraries(dst_root)
        elif arg=='clean':
            clean_build_files()
    else:
        print "usage: python build.py <destination-path>"
