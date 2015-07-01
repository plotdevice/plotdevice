from __future__ import print_function
import os
import sys
import errno
from subprocess import call
from glob import glob
from os.path import dirname, basename, abspath, isdir, join
from shutil import rmtree

DEPS = dirname(abspath(__file__))
PYTHON = sys.executable

## Helpers ##

def build(extension):
    """Run setup.py within a given c-extension's folder"""
    result = call([PYTHON, 'setup.py', '-q', 'build'], cwd=join(DEPS, extension))
    if result > 0:
        raise OSError("Could not build %s" % extension)

def make(target, **envvars):
    """Build the specified target in the vendor Makefile"""
    os.chdir('%s/vendor'%DEPS)
    env = {"PYTHON":PYTHON, "PATH":os.environ['PATH']}
    env.update(envvars)
    result = call('make -s %s'%target, env=env, shell=True)
    if result > 0:
        raise OSError("Could not make %s" % target)
    os.chdir(DEPS)

def clean():
    """Delete build folders in dependency subdirs"""
    build_dirs = glob('%s/*/build'%DEPS)
    for build_dir in build_dirs:
        lib_name = dirname(build_dir)
        print("Cleaning", lib_name)
        call('rm -r "%s"' % build_dir)
    make('clean')

## Recipes ##

def build_extensions():
    # Find all setup.py files in the current folder
    print("\nCompiling required c-extensions")
    for setup_script in glob('%s/*/setup.py'%DEPS):
        lib_name = basename(dirname(setup_script))
        print("Building %s..."% lib_name)
        build(lib_name)

    print("Building pyobjc...")
    make('pyobjc')

def install_http_libs(mod_root):
    """Install the http modules into the Resources/python subdir"""
    print("Bundling requests module...")
    make('http', DSTROOT=mod_root) # makefile uses DSTROOT to target install

def install_extensions(ext_root):
    """Install the c-extensions and PyObjC site dir within the plotdevice module"""
    # Make sure the destination folder exists.
    if not isdir(ext_root):
        os.makedirs(ext_root)

    # Copy all build results to plotdevice/lib dir
    for extension in glob("%s/*/build/lib*"%DEPS):
        cmd = 'cp -R -p %s/* %s' % (extension, ext_root)
        result = call(cmd, shell=True)
        if result > 0:
            lib_name = dirname(dirname(extension))
            raise OSError("Could not copy %s" % lib_name)
    print()

if __name__=='__main__':
    if len(sys.argv)>1:
        arg = sys.argv[1]
        if arg=='clean':
            print("Cleaning dependency build files...")
            clean()
        else:
            mod_root = arg
            ext_root = join(mod_root, 'plotdevice/lib')
            build_extensions()
            if 'ACTION' in os.environ:
                # the ACTION env var will be defined for app and py2app builds, in which
                # case we should install the http libs into Resources/python (for non-GUI
                # builds, setup.py's install_requires will pull in dependencies automatically)
                install_http_libs(mod_root)
            install_extensions(ext_root)
    else:
        print("usage: python build.py <destination-path>")
