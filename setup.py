# encoding: utf-8
"""setup.py for building the mixed C/Objective-C/Swift/C++ `_plotdevice` extension

This file exists only for the things `pyproject.toml` can't handle, in particular
the prebuild and compilation steps necessary for setuptools to package the module.
You needn't run this script directly, just use one of the ordinary installation
approaches like `pip install .` or `python -m build`.
"""
import zlib
from glob import glob
from subprocess import call
from os.path import dirname, abspath, basename, exists, join, getmtime

from setuptools import setup
from setuptools.extension import Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.sdist import sdist

ROOT = dirname(abspath(__file__))

def stale(dst, src):
    return exists(src) and (not exists(dst) or getmtime(dst) < getmtime(src))

class BuildExtCommand(build_ext):
    """Build SwiftDraw.o before linking _plotdevice, then populate
    plotdevice/rsrc/ with the runtime resources plotdevice.util.rsrc_path
    depends on (icns, colors.json, an ibtool-compiled nib, the press profiles)."""

    def run(self):
        call('cd deps/extensions/svg && make', shell=True, cwd=ROOT)
        call('cd deps/extensions/clipper2 && make', shell=True, cwd=ROOT)

        # relink if any .o is updated
        for ext in self.extensions:
            ext.depends = list(ext.depends) + list(ext.extra_objects)
        build_ext.run(self)

        # include some ui resources for running a script from the command line
        rsrc_dir = join(ROOT, self.build_lib if not self.inplace else '.', 'plotdevice', 'rsrc')
        self.mkpath(rsrc_dir)
        self.copy_file(join(ROOT, 'app/Resources/PlotDeviceFile.icns'), rsrc_dir)
        self.copy_file(join(ROOT, 'app/Resources/colors.json'), rsrc_dir)

        # recompile the command-line UI nib if necessary
        xib = join(ROOT, 'app/Resources/en.lproj/PlotDeviceScript.xib')
        nib = join(ROOT, 'app/Resources/viewer.nib')
        if stale(nib, xib):
            self.spawn(['/usr/bin/ibtool', '--compile', nib, xib])
        self.copy_file(nib, rsrc_dir)

        # and the press profiles, zlib'd, with their licenses
        press_dir = join(rsrc_dir, 'press')
        self.mkpath(press_dir)
        for path in glob(join(ROOT, 'deps/press/*')):
            if path.endswith('.icc'):
                dst = join(press_dir, basename(path) + '.zlib')
                if stale(dst, path):
                    with open(path, 'rb') as src, open(dst, 'wb') as out:
                        out.write(zlib.compress(src.read(), 9))
            else:
                self.copy_file(path, press_dir)

class SdistPrepCommand(sdist):
    """Make sure an sdist can be installed without needing Xcode/ibtool, and
    bundles the SwiftDraw sources for offline/reproducible builds."""

    def finalize_options(self):
        with open(join(ROOT, 'MANIFEST.in'), 'w') as f:
            f.write("""
                graft app/Resources
                prune app/Resources/en.lproj
                prune app/Resources/ui
                include app/plotdevice
                include deps/extensions/*/*.h
                recursive-include deps/extensions/svg *.swift *.tmpl Makefile
                recursive-include deps/extensions/clipper2 *
                graft deps/press
                prune plotdevice/rsrc/press
                include tests/*.py
                graft tests/_in
                graft examples
                include *.md
                include *.url
            """)
        sdist.finalize_options(self)

    def run(self):
        # include a compiled nib in the sdist so ibtool (and thus Xcode.app) isn't required to install
        xib = join(ROOT, 'app/Resources/en.lproj/PlotDeviceScript.xib')
        nib = join(ROOT, 'app/Resources/viewer.nib')
        if stale(nib, xib):
            self.spawn(['/usr/bin/ibtool', '--compile', nib, xib])

        # make sure we have the sources for SwiftDraw
        call('cd deps/extensions/svg && make SwiftDraw', shell=True, cwd=ROOT)

        # build the sdist based on our MANIFEST.in additions
        sdist.run(self)

setup(
    ext_modules=[Extension(
        '_plotdevice',
        sources=['deps/extensions/module.m', *glob('deps/extensions/*/*.[cm]')],
        extra_objects=['deps/extensions/svg/SwiftDraw.o',
                       'deps/extensions/clipper2/clipper.engine.o',
                       'deps/extensions/clipper2/clipper.offset.o',
                       'deps/extensions/clipper2/bridge.o'],
        extra_link_args=sum((['-framework', fmwk] for fmwk in
            ['AppKit', 'Foundation', 'Quartz', 'Security', 'AVFoundation', 'CoreMedia', 'CoreVideo', 'CoreText', 'IOSurface', 'Accelerate']
        ), []),
    )],
    cmdclass={
        'build_ext': BuildExtCommand,
        'sdist': SdistPrepCommand,
    },
)
