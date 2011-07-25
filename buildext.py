import os
import glob
import subprocess
from distutils.core import run_setup
from shutil import copyfile

# Extensions will be copied in the nodebox ext source folder.
dstdir = 'nodebox/ext'

# Setup creates the needed extensions
run_setup('setup.py', ['build_ext'])

# These extensions are stored in a folder that looks like build/lib.macosx-10.6-universal-2.6
# Find all extensions from that folder.
extensions = glob.glob("build/lib*/*.so")

# Copy all found extensions to the nodebox ext source folder.
for src in extensions:
    dst = os.path.join(dstdir, os.path.basename(src))
    print src, '-->', dst
    copyfile(src, dst)

