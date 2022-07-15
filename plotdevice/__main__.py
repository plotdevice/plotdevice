#!/usr/bin/env python3
# encoding: utf-8
"""
Examples:
  Run a script:
    python3 -m plotdevice script.pv

  Run fullscreen:
    python3 -m plotdevice -f script.pv

  Save script's output to pdf:
    python3 -m plotdevice script.pv --export output.pdf

  Generate 1:1 and retina-scaled png files:
    python3 -m plotdevice script.pv --export normal.png
    python3 -m plotdevice script.pv --export retina.png --zoom 200
    python3 -m plotdevice script.pv --export also-retina@2x.png

Animation Examples:
  Create a 5 second long H.265 video at 2 megabits/sec:
    python3 -m plotdevice script.pv --export output.mov --frames 150 --rate 2.0

  Create a sequence of numbered png files – one for each frame in the animation:
    python3 -m plotdevice script.pv --export output.png --frames 10

  Create an animated gif that loops every 2 seconds:
    python3 -m plotdevice script.pv --export output.gif --frames 60 --fps 30 --loop

Installing Libraries:
  python3 -m plotdevice --install urllib3 jinja2 numpy
"""

import sys, os, re
import argparse
from os.path import exists, islink, dirname, basename, abspath, realpath, join, splitext


def main():
  import plotdevice
  from .run.console import run

  parser = argparse.ArgumentParser(
    add_help=False,
    description="Run PlotDevice scripts in a window or export graphics to a document (pdf/eps), image (png/jpg/heic/gif/tiff), or movie (mov/gif).",
    epilog=sys.modules[__name__].__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    prog=os.environ.pop('_p_l_o_t_d_e_v_i_c_e_', 'python3 -m plotdevice')
  )
  o = parser.add_argument_group("Options", None)
  o.add_argument('-h','--help', action='help', help='show this help message and exit')
  o.add_argument('-f', dest='fullscreen', action='store_const', const=True, default=False, help='run full-screen')
  o.add_argument('-b', dest='activate', action='store_const', const=False, default=True, help='run PlotDevice in the background (i.e., leave focus in the active application)')
  o.add_argument('-q', dest='mode', action='store_const', const='headless', default='windowed', help='run a PlotDevice script ‘quietly’ (without opening a window)')
  o.add_argument('--virtualenv', metavar='PATH', help='path to virtualenv whose libraries you want to use (this should point to the top-level virtualenv directory; a folder containing a lib/python3.x/site-packages subdirectory)')
  o.add_argument('--frames', metavar='N or M-N', help='number of frames to render or a range specifying the first and last frames (default "1-")')
  o.add_argument('--fps', metavar='N', default=30, type=int, help='frames per second in exported video (default 30)')
  o.add_argument('--rate', metavar='N', default=1.0, type=float, dest='bitrate', help='bitrate in megabits per second (video only)')
  o.add_argument('--loop', metavar='N', default=0, nargs='?', const=-1, help='number of times to loop an exported animated gif (omit N to loop forever)')
  o.add_argument('--live', action='store_const', const=True, help='re-render graphics each time the file is saved')
  o.add_argument('--args', nargs='*', default=[], metavar=('a','b'), help='arguments to be passed to the script as sys.argv')
  o.add_argument('--version', action='version', version='PlotDevice %s' % plotdevice.__version__)

  x = parser.add_argument_group("Export Options")
  x.add_argument('--export', '-o', metavar='FILE', help='a destination filename ending in pdf, eps, png, tiff, jpg, heic, gif, or mov')
  x.add_argument('--zoom', metavar='PERCENT', default=100, type=int, help='scale of the output image (100 = regular size) unless specified by a filename ending in @2x/@3x/etc')
  x.add_argument('--cmyk', action='store_const', const=True, default=False, help='convert colors to c/m/y/k during exports')

  i = parser.add_argument_group("PlotDevice Script File", None)
  i.add_argument('script', help='the python script to be rendered')

  p = parser.add_argument_group("Installing Packages")
  p.add_argument('--install', nargs='*', default=[], metavar='package', help="Use `pip` to download libraries into the ~/Library/Application Support/PlotDevice directory, making them `import`-able in the application and by scripts run from the command line")


  if len(sys.argv)==1:
    parser.print_usage()
    print('for more detail:\n  %s --help' % parser.prog)
    return
  elif sys.argv[1] == '--install':
    # --install has to be the first argument (in which case we can handle it now and bail)
    libDir = os.path.join(os.getenv("HOME"), "Library", "Application Support", "PlotDevice")
    if not os.path.exists(libDir):
        os.mkdir(libDir)

    from subprocess import call
    PIP = os.environ.pop('_p_l_o_t_d_e_v_i_c_e___p_i_p_', 'pip3')
    sys.exit(call([PIP, 'install', '--isolated', '--target', libDir, *sys.argv[2:]]))

  opts = parser.parse_args()

  if opts.virtualenv:
    libdirs = glob('%s/lib/python3.*/site-packages'%opts.virtualenv)
    if len(libdirs) and exists(libdir[0]):
      opts.virtualenv = abspath(libdir[0])
    else:
      parser.exit(1, "bad argument [--virtualenv]\nvirtualenv site-packages dir not found: %s\n"%libdir)

  if opts.script:
    opts.script = abspath(opts.script)
    if not exists(opts.script):
      parser.exit(1, "file not found: %s\n"%opts.script)

  if opts.frames:
    try:
      frames = [int(f) if f else None for f in opts.frames.split('-')]
    except ValueError:
      parser.exit(1, 'bad argument [--frame]\nmust be a single integer ("42") or a hyphen-separated range ("33-66").\ncouldn\'t make sense of "%s"\n'%opts.frames)

    if len(frames) == 1:
      opts.first, opts.last = (1, int(frames[0]))
    elif len(frames) == 2:
      if frames[1] is not None and frames[1]<frames[0]:
        parser.exit(1, "bad argument [--frame]\nfinal-frame number is less than first-frame\n")
      opts.first, opts.last = frames
  else:
    opts.first, opts.last = (1, None)
  del opts.frames

  if opts.export:
    # don't open a window
    opts.mode = 'headless'

    # screen out unsupported file extensions
    try:
      outname, ext = opts.export.lower().rsplit('.',1)
    except ValueError:
      ext = opts.export.lower()
      outname = splitext(basename(opts.script))[0]
      opts.export = '.'.join([outname, ext])
    if ext not in ('pdf', 'eps', 'png', 'jpg', 'heic', 'tiff', 'gif', 'mov'):
      parser.exit(1, 'bad argument [--export]\nthe output filename must end with a supported format:\n  pdf, eps, png, tiff, jpg, heic, gif, or mov\n')

    # make sure the output path is sane
    if '/' in opts.export:
      export_dir = dirname(opts.export)
      if not exists(export_dir):
        parser.exit(1,'export directory not found: %s\n'%abspath(export_dir))
    opts.export = abspath(opts.export)

    # movies aren't allowed to be infinitely long (sorry)
    if opts.last is None and ext in ('mov','gif'):
      opts.first, opts.last = (1, 150)

    # if it's a multiframe pdf, check for a telltale "{n}" to determine whether
    # it's a `single' doc or a sequence of numbered pdf files
    opts.single = bool(ext=='pdf' and not re.search('{\d+}', opts.export) and opts.last and opts.first < opts.last)

    if m:= re.search(r'@(\d+)[xX]$', outname):
      opts.zoom = float(m.group(1))
    else:
      opts.zoom = max(0.01, opts.zoom/100)

  if opts.install:
    print("The --install option must be used on its own, not in combination with other flags")
    sys.exit(1)

  # set it off
  plotdevice.__all__.clear()
  run(vars(opts))

if __name__ == "__main__":
  main()
