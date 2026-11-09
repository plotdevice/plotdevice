#!/usr/bin/env python3
# Copyright 2018 Greg Neagle; adapted for PlotDevice from gregneagle/relocatable-python@8ee72fe.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License (see LICENSE.relocate).
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Makes a Python.framework or PythonT.framework extracted from python.org's installer
relocatable. Safe to re-run, e.g. to fix the shebangs and bytecode of whatever pip has since installed.

usage: relocate.py <Python.framework | PythonT.framework>
"""

import os
import plistlib
import struct
import subprocess
import sys

FAT_MAGIC = b'\xca\xfe\xba\xbe'
MH_MAGIC_64 = 0xfeedfacf
MH_EXECUTE = 2


def run(*cmd):
    print(' '.join(cmd))
    subprocess.check_call(cmd)


def macho_filetype(path):
    """The Mach-O filetype of a (possibly universal) binary, or None for other files"""
    with open(path, 'rb') as f:
        head = f.read(20)
        if head[:4] == FAT_MAGIC and len(head) == 20:
            f.seek(struct.unpack('>I', head[16:20])[0])  # the first architecture's offset
            head = f.read(16)
    if len(head) >= 16 and struct.unpack('<I', head[:4])[0] == MH_MAGIC_64:
        return struct.unpack('<I', head[12:16])[0]


def install_name(path):
    out = subprocess.check_output(['otool', '-D', path], text=True).splitlines()
    return out[1] if len(out) > 1 else None


def deps(path):
    out = subprocess.check_output(['otool', '-L', path], text=True).splitlines()
    return {line.split(' (compatibility')[0].strip() for line in out if line.startswith('\t')}


def rpaths(path):
    out = subprocess.check_output(['otool', '-l', path], text=True).splitlines()
    return [out[i + 2].split()[1] for i, line in enumerate(out) if 'cmd LC_RPATH' in line]


def framework_dir(path):
    """The innermost .framework containing path"""
    while not path.endswith('.framework'):
        path = os.path.dirname(path)
    return path


def relocate_binaries(framework, name, binaries):
    """Replaces the /Library/Frameworks install names with @rpath ones, and has executables
    find their framework relative to themselves; returns the files changed"""
    prefix = '/Library/Frameworks/%s.framework/' % name
    renamed, changed = {}, set()
    for path in binaries:
        old_name = install_name(path)
        if old_name and old_name.startswith(prefix):
            renamed[old_name] = '@rpath/' + os.path.relpath(path, framework_dir(path))
            run('install_name_tool', '-id', renamed[old_name], path)
            changed.add(path)

    for path, filetype in binaries.items():
        linked = deps(path) & renamed.keys()
        if not linked:
            continue
        for old_name in linked:
            run('install_name_tool', '-change', old_name, renamed[old_name], path)
        if filetype == MH_EXECUTE:
            rpath = '@executable_path/%s/' % os.path.relpath(framework_dir(path), os.path.dirname(path))
            if rpath not in rpaths(path):
                run('install_name_tool', '-add_rpath', rpath, path)
        changed.add(path)
    return changed


def link_sibling(framework, binaries):
    """Points the libraries PythonT.framework borrows from Python.framework at the sibling
    next to it; returns the files changed"""
    prefix = '/Library/Frameworks/Python.framework/'
    sibling = os.path.join(os.path.dirname(framework), 'Python.framework')
    changed = set()
    for path in binaries:
        for dep in deps(path):
            if dep.startswith(prefix):
                target = os.path.join(sibling, dep[len(prefix):])
                run('install_name_tool', '-change', dep, '@loader_path/' + os.path.relpath(target, os.path.dirname(path)), path)
                changed.add(path)
    return changed


def fix_shebangs(framework, name, version):
    """Has the scripts in bin find their interpreter relative to themselves"""
    bin_dir = os.path.join(framework, 'Versions', version, 'bin')
    absolute = [b'#!' + os.path.realpath(framework).encode(), b'#!/Library/Frameworks/%s.framework' % name.encode()]
    for filename in os.listdir(bin_dir):
        path = os.path.join(bin_dir, filename)
        if os.path.islink(path) or os.path.isdir(path):
            continue
        with open(path, 'rb') as f:
            first_line, rest = f.readline().strip(), f.read()
        if not any(first_line.startswith(p) for p in absolute):
            continue
        interpreter = first_line[2:].decode().replace('/Library/Frameworks/%s.framework' % name, os.path.realpath(framework), 1)
        relative = os.path.relpath(os.path.realpath(interpreter), os.path.realpath(bin_dir))
        print('Modifying shebang for %s...' % path)
        with open(path, 'wb') as f:
            f.write(b"#!/bin/sh\n"
                    b"'''exec' \"$(dirname \"$0\")/%s\" \"$0\" \"$@\"\n"
                    b"' '''\n"
                    b"# the above calls the %s interpreter relative to the directory of this script\n"
                    % (relative.encode(), relative.encode()) + rest)


def hash_bytecode(framework, name, version):
    """Recompiles timestamp-based .pyc files as hash-based ones, which stay valid when Xcode's copy
    into the app gives every .py a new mtime"""
    pycs = []
    for dirpath, _dirs, files in os.walk(os.path.join(framework, 'Versions', version, 'lib')):
        for filename in files:
            path = os.path.join(dirpath, filename)
            if filename.endswith('.pyc') and not os.path.islink(path):
                with open(path, 'rb') as f:
                    flags = struct.unpack('<I', f.read(8)[4:8])[0]
                if flags == 0:
                    pycs.append(path)
    if not pycs:
        return
    print('Recompiling %d .pyc files in %s as hash-based...' % (len(pycs), framework))
    # only the framework's own interpreter writes bytecode it can read
    interpreter = os.path.join(framework, 'Versions', version, 'bin', 'python%s%s' % (version, 't' if name == 'PythonT' else ''))
    subprocess.check_call([interpreter, '-B', '-c', """if 1:
        import os, py_compile, sys
        for pyc in sys.argv[1:]:
            pycache, filename = os.path.split(pyc)
            src = os.path.join(os.path.dirname(pycache), filename.split('.')[0] + '.py')
            if os.path.exists(src):
                py_compile.compile(src, cfile=pyc, doraise=True, invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        """, *pycs])


def main(framework):
    framework = os.path.abspath(framework.rstrip('/'))
    name = os.path.splitext(os.path.basename(framework))[0]
    versions = os.path.join(framework, 'Versions')
    version = next(v for v in os.listdir(versions) if v != 'Current' and os.path.isdir(os.path.join(versions, v)))

    subprocess.check_call(['chmod', '-R', 'u+rw,g+r,g-w,o+r,o-w', framework])
    binaries = {}
    for dirpath, _dirs, files in os.walk(framework):
        for filename in files:
            path = os.path.join(dirpath, filename)
            filetype = None if os.path.islink(path) else macho_filetype(path)
            if filetype:
                binaries[path] = filetype

    changed = relocate_binaries(framework, name, binaries)
    if name == 'PythonT':
        changed |= link_sibling(framework, binaries)
    # install_name_tool invalidates signatures, and arm64 won't run unsigned code
    for path in sorted(changed):
        run('codesign', '-s', '-', '--force', '--preserve-metadata=identifier,entitlements,flags,runtime', path)

    fix_shebangs(framework, name, version)
    hash_bytecode(framework, name, version)
    if not os.path.exists(os.path.join(versions, 'Current')):
        os.symlink(version, os.path.join(versions, 'Current'))

    # python.org's PythonT.framework names its library "Python", but Xcode uses this to find it when embedding
    plist_path = os.path.join(versions, version, 'Resources/Info.plist')
    with open(plist_path, 'rb') as f:
        info = plistlib.load(f)
    if info.get('CFBundleExecutable') != name:
        info['CFBundleExecutable'] = name
        with open(plist_path, 'wb') as f:
            plistlib.dump(info, f)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip())
    main(sys.argv[1])
