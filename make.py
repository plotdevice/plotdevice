#!/usr/bin/env python3
"""Maintainer/CI build tool for PlotDevice (not part of the pip-installable package)

Subcommands:
    dev          set up virtualenv in deps/local with required dependencies
    app          build PlotDevice.app (requires full Xcode install
    py2app       build PlotDevice.app via py2app (requires Xcode command line tools)
    dist         build app (codesigned, notarized, & zipped) and update release.json
    icon         regenerate app/Resources/Assets.car from app/art/PlotDevice-app.icon
    clean        remove build artifacts
    distclean    also remove the embedded Python.framework and deps/local
"""
import argparse, os, sys, json, plistlib, tempfile
from glob import glob
from shutil import rmtree, copy
from subprocess import call, run, Popen, PIPE
from os.path import join, exists, dirname, basename, abspath, getsize

ROOT = dirname(abspath(__file__))
sys.path.insert(0, ROOT)

APP_NAME = 'PlotDevice'
SPARKLE_VERSION = '2.1.0'
SPARKLE_URL = 'https://github.com/sparkle-project/Sparkle/releases/download/%(v)s/Sparkle-%(v)s.tar.xz' % {'v': SPARKLE_VERSION}

## Helpers ##

# helpers for dealing with plists & git (spiritual cousins if ever there were)
def info_plist(pth='app/info.plist'):
    info = plistlib.load(open(pth, 'rb'))
    # overwrite the xcode placeholder vars
    info['CFBundleExecutable'] = info['CFBundleName'] = APP_NAME
    return info

def update_plist(pth, **modifications):
    info = plistlib.load(open(pth, 'rb'))
    for key, val in modifications.items():
        if val is None:
            info.pop(key)
        else:
            info[key] = val
    with open(pth, 'wb') as f:
        plistlib.dump(info, f)

def gosub(cmd, on_err=True):
    """Run a shell command and return the output"""
    shell = isinstance(cmd, str)
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=shell)
    out, err = proc.communicate()
    ret = proc.returncode
    if on_err:
        msg = '%s:\n' % on_err if isinstance(on_err, str) else ''
        if ret != 0:
            print(msg + out.decode('utf8') + err.decode('utf8'))
    return out, err, ret

def last_commit():
    commit_count, _, _ = gosub('git log --oneline | wc -l')
    return 'r%s' % commit_count.decode('utf-8').strip()

def timestamp():
    from datetime import datetime
    return datetime.now().strftime("%a, %d %b %Y %H:%M:%S")

def spawn(cmd, **kwargs):
    run(cmd, check=True, **kwargs)


## Subcommands ##

def cmd_dev(args):
    # install pyobjc, requests and the other pypi dependencies in deps/local
    import platform, venv
    venv_dir = join('deps/local', platform.python_version())
    if not exists(venv_dir):
        venv.create(venv_dir, symlinks=True, with_pip=True)
        PIP = join(venv_dir, 'bin/pip3')
        call([PIP, 'install', '-q', '--upgrade', 'pip', 'setuptools', 'wheel', 'py2app', 'twine'])
        call([PIP, 'install', '-q', '-e', ROOT])

    print("\nA local development environment has been set up in %s" % venv_dir)


def cmd_icon(args):
    _, _, ret = gosub(['xcrun', '--find', 'actool'], on_err=False)
    if ret != 0:
        print("make.py: Couldn't find `actool`. Try installing the full Xcode (not just the command line tools)")
        sys.exit(1)

    ICON_SRC = 'app/art/PlotDevice-app.icon'
    ICON_OUT = 'app/Resources/Assets.car'
    info = info_plist()

    with tempfile.TemporaryDirectory() as tmp:
        spawn(['xcrun', 'actool',
               '--output-format', 'human-readable-text', '--notices', '--warnings', '--errors',
               '--platform', 'macosx', '--minimum-deployment-target', info['LSMinimumSystemVersion'],
               '--app-icon', info['CFBundleIconName'],
               '--output-partial-info-plist', join(tmp, 'partial-info.plist'),
               '--compile', tmp,
               ICON_SRC])
        copy(join(tmp, 'Assets.car'), ICON_OUT)

    print("done building %s" % ICON_OUT)


def cmd_clean(args):
    paths = [
        'build',
        'dist',
        '*.egg',
        '*.egg-info',
        '.eggs',
        'PKG',
        'tests/_out',
        'tests/_diff',
        'details.html',
        '_plotdevice.*.so',
        'plotdevice/rsrc',
        'MANIFEST.in',
        '**/*.pyc',
        '**/__pycache__',
        '**/.DS_Store',
    ]

    # Add framework paths if --dist flag is used
    if args.dist:
        paths.extend([
            'deps/local',
            'deps/frameworks/Python.framework',
            'deps/frameworks/relocatable-python',
        ])

    for path_pattern in paths:
        for path in glob(path_pattern, recursive=True):
            if exists(path):
                print('removing %s' % path)
                if os.path.isdir(path):
                    rmtree(path)
                else:
                    os.unlink(path)

    # Run make clean in svg extensions dir
    if exists('deps/extensions/svg'):
        os.system('cd deps/extensions/svg && make clean')


def cmd_distclean(args):
    cmd_clean(argparse.Namespace(dist=True))


def cmd_app(args):
    # make sure the embedded framework exists (and has updated app/python.xcconfig)
    print("Set up Python.framework for app build")
    env = os.environ.copy()
    if args.no_cache:
        env['PIP_NO_CACHE_DIR'] = '1'
    call('cd deps/frameworks && make', shell=True, env=env)

    spawn(['xcodebuild', '-configuration', 'Release'])
    dsym = 'dist/PlotDevice.app.dSYM'
    if exists(dsym):
        rmtree(dsym)
    print("done building PlotDevice.app in ./dist")


def cmd_py2app(args):
    try:
        import py2app
    except ImportError:
        print("""make.py: py2app build failed
  Couldn't find the py2app module. To set up a virtualenv that contains all the necessary
  dependencies in the deps/local directory, call the `dev` command first:
  > python3 make.py dev
  > ./deps/local/<python-version>/bin/python3 make.py py2app""")
        sys.exit(1)

    from py2app.build_app import py2app as build_py2app

    # make sure _plotdevice.so + plotdevice/rsrc/ are built first
    call([sys.executable, 'setup.py', 'build_ext', '--inplace'])

    class BuildPy2AppCommand(build_py2app):
        def finalize_options(self):
            # pyproject.toml's [project.dependencies] gets merged into
            # self.distribution.install_requires automatically since setup()
            # below runs from the same directory as pyproject.toml; py2app
            # bundles dependencies directly and rejects install_requires, so
            # clear it before py2app's own finalize_options checks for it.
            self.distribution.install_requires = None
            build_py2app.finalize_options(self)

        def run(self):
            build_py2app.run(self)
            if self.dry_run:
                return

            # undo py2app's weird treatment of the config.version value
            update_plist('dist/PlotDevice.app/Contents/Info.plist', CFBundleShortVersionString=None)

            # place the command line tool in SharedSupport
            BIN = join(dirname(self.resdir), 'SharedSupport')
            self.mkpath(BIN)
            self.copy_file("app/plotdevice", BIN)

            print("done building PlotDevice.app in ./dist")

    from setuptools import setup
    old_argv = sys.argv
    try:
        sys.argv = ['make.py', 'py2app']
        setup(
            name='plotdevice',
            app=[{
                'script': "app/plotdevice-app.py",
                'plist': info_plist(),
            }],
            data_files=[ # type: ignore[list-item]
                "app/Resources/ui",
                "app/Resources/colors.json",
                "app/Resources/en.lproj",
                "app/Resources/PlotDevice.icns",
                "app/Resources/PlotDeviceFile.icns",
                "app/Resources/Assets.car",
                "examples",
            ],
            options={ # type: ignore[dict-item]
                "py2app": {
                    "iconfile": "app/Resources/PlotDevice.icns",
                    "semi_standalone": True,
                    "site_packages": True,
                    "strip": False,
                }
            },
            cmdclass={'py2app': BuildPy2AppCommand},
        )
    finally:
        sys.argv = old_argv

## Packaging Commands (really only useful to the maintainer) ##

def cmd_dist(args):
    import plotdevice
    VERSION = plotdevice.__version__

    APP = 'dist/PlotDevice.app'
    ZIP = 'dist/PlotDevice_app-%s.zip' % VERSION

    # run the Xcode build
    cmd_app(args)

    # set the bundle version to the current commit number and prime the updater
    info_pth = 'dist/PlotDevice.app/Contents/Info.plist'
    update_plist(info_pth,
        CFBundleVersion=last_commit(),
        CFBundleShortVersionString=VERSION,
        SUFeedURL='https://plotdevice.io/app.xml',
        SUEnableSystemProfiling='YES'
    )

    # download Sparkle (if necessary) and copy it into the bundle
    ORIG = 'deps/frameworks/Sparkle.framework'
    SPARKLE = join(APP, 'Contents/Frameworks/Sparkle.framework')
    if not exists(ORIG):
        os.makedirs(dirname(ORIG), exist_ok=True)
        print("Downloading Sparkle.framework")
        os.system('curl -L -# %s | xz -dc | tar xf - -C %s %s' % (SPARKLE_URL, dirname(ORIG), basename(ORIG)))
    os.makedirs(dirname(SPARKLE), exist_ok=True)
    spawn(['ditto', ORIG, SPARKLE])

    # code-sign the app and embedded frameworks, then verify
    def codesign(root, name=None, exec_=False, entitlement=False):
        test = []
        if name:
            test += ['-name', name]
        if exec_:
            test += ['-perm', '-u=x']

        codesign_cmd = ['codesign', '--deep', '--strict', '--timestamp', '-o', 'runtime', '-f', '-v', '-s', 'Developer ID Application']
        if entitlement:
            codesign_cmd += ['--entitlements', 'app/PlotDevice.entitlements']

        if test:
            spawn(['find', root, '-type', 'f', *test, '-exec', *codesign_cmd, "{}", ";"])
        else:
            spawn([*codesign_cmd, root])

    PYTHON = join(APP, 'Contents/Frameworks/Python.framework')
    codesign('%s/Versions/Current/lib' % PYTHON, name="*.dylib")
    codesign('%s/Versions/Current/lib' % PYTHON, name="*.o")
    codesign('%s/Versions/Current/lib' % PYTHON, name="*.a")
    codesign('%s/Versions/Current/lib' % PYTHON, exec_=True)
    codesign('%s/Versions/Current/bin' % PYTHON, exec_=True)
    codesign('%s/Versions/Current/bin' % PYTHON, name="python3.*", entitlement=True)
    codesign('%s/Versions/Current/Resources/Python.app' % PYTHON, entitlement=True)
    codesign(PYTHON)

    codesign('%s/Versions/Current/Updater.app' % SPARKLE)
    codesign(SPARKLE)

    codesign(APP, entitlement=True)
    spawn(['codesign', '--verify', '--deep', '-vv', APP])

    # create versioned zipfile of the app & notarize it
    spawn(['ditto', '-ck', '--keepParent', APP, ZIP])
    spawn(['xcrun', 'notarytool', 'submit', ZIP, '--keychain-profile', 'AC_NOTARY', '--wait'])

    # staple notarization ticket and regenerate zip
    spawn(['xcrun', 'stapler', 'staple', APP])
    spawn(['ditto', '-ck', '--keepParent', APP, ZIP])

    # write out the release metadata for plotdevice-site to consume/merge
    with open('dist/release.json', 'w') as f:
        release = dict(zipfile=basename(ZIP), bytes=getsize(ZIP),
                        version=VERSION, revision=last_commit(),
                        timestamp=timestamp())
        json.dump(release, f)

    print("\nBuilt PlotDevice.app, %s, and release.json in ./dist" % basename(ZIP))


def main():
    # make sure we're at the project root regardless of the cwd
    # (this means the various commands don't have to play path games)
    os.chdir(ROOT)

    # clear away any finder droppings that may have accumulated
    call(['find', '.', '-name', '.DS_Store', '-delete'])

    parser = argparse.ArgumentParser(prog='make.py')
    sub = parser.add_subparsers(dest='command', required=True)

    p_dev = sub.add_parser('dev', help='set up virtualenv in deps/local with required dependencies')
    p_dev.set_defaults(func=cmd_dev)

    p_icon = sub.add_parser('icon', help='regenerate app/Resources/Assets.car from app/art/PlotDevice-app.icon')
    p_icon.set_defaults(func=cmd_icon)

    p_clean = sub.add_parser('clean', help='remove build artifacts')
    p_clean.add_argument('--dist', action='store_true', help='also remove Python.framework and deps/local')
    p_clean.set_defaults(func=cmd_clean)

    p_distclean = sub.add_parser('distclean', help='also remove the embedded Python.framework and deps/local')
    p_distclean.set_defaults(func=cmd_distclean)

    p_app = sub.add_parser('app', help='build PlotDevice.app (requires full Xcode install')
    p_app.add_argument('--no-cache', action='store_true', help='do not use pip cache when installing dependencies')
    p_app.set_defaults(func=cmd_app)

    p_py2app = sub.add_parser('py2app', help='build PlotDevice.app via py2app (requires Xcode command line tools)')
    p_py2app.set_defaults(func=cmd_py2app)

    p_dist = sub.add_parser('dist', help='build, code-sign, notarize, and zip the app for release')
    p_dist.add_argument('--no-cache', action='store_true', help='do not use pip cache when installing dependencies')
    p_dist.set_defaults(func=cmd_dist)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
