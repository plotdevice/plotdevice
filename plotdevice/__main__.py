#!/usr/bin/env python3
# encoding: utf-8
"""
Examples:
  Run a script:
    python -m plotdevice script.pv

  Run fullscreen:
    python -m plotdevice -f script.pv

  Save script's output to pdf:
    python -m plotdevice script.pv --export output.pdf

Animation Examples:
  Create a 5 second long H.265 video at 2 megabits/sec:
    python -m plotdevice script.pv --export output.mov --frames 150 --rate 2.0

  Create a sequence of numbered png files – one for each frame in the animation:
    python -m plotdevice script.pv --export output.png --frames 10

  Create an animated gif that loops every 2 seconds:
    python -m plotdevice script.pv --export output.gif --frames 60 --fps 30 --loop
"""

from __future__ import print_function
import sys, os, re
import argparse
import json
import signal
from glob import glob
from subprocess import Popen, PIPE
from os.path import exists, islink, dirname, abspath, realpath, join
from .run.console import run

def main():
  """Run python scripts in a window or export graphics to a
     document (pdf/eps), image (png/jpg/heic/gif/tiff), or movie (mov/gif)."""
  parser = argparse.ArgumentParser(description=main.__doc__, add_help=False, prog='python -m plotdevice')
  o = parser.add_argument_group("Options", None)
  o.add_argument('-h','--help', action='help', help='show this help message and exit')
  o.add_argument('-f', dest='fullscreen', action='store_const', const=True, default=False, help='run full-screen')
  o.add_argument('-b', dest='activate', action='store_const', const=False, default=True, help='run PlotDevice in the background')
  o.add_argument('--virtualenv', metavar='PATH', help='path to virtualenv whose libraries you want to use (this should point to the top-level virtualenv directory; a folder containing a lib/python3.x/site-packages subdirectory)')
  o.add_argument('--export', '-o', metavar='FILE', help='a destination filename ending in pdf, eps, png, tiff, jpg, heic, gif, or mov')
  o.add_argument('--frames', metavar='N or M-N', help='number of frames to render or a range specifying the first and last frames (default "1-")')
  o.add_argument('--fps', metavar='N', default=30, type=int, help='frames per second in exported video (default 30)')
  o.add_argument('--rate', metavar='N', default=1.0, type=float, dest='bitrate', help='bitrate in megabits per second (video only)')
  o.add_argument('--loop', metavar='N', default=0, nargs='?', const=-1, help='number of times to loop an exported animated gif (omit N to loop forever)')
  o.add_argument('--cmyk', action='store_const', const=True, default=False, help='convert colors to c/m/y/k during exports')
  o.add_argument('--live', action='store_const', const=True, help='re-render graphics each time the file is saved')
  o.add_argument('--args', nargs='*', default=[], metavar=('a','b'), help='arguments to be passed to the script as sys.argv')
  i = parser.add_argument_group("PlotDevice Script File", None)
  i.add_argument('script', help='the python script to be rendered')

  try:
      opts = parser.parse_args()
  except:
      parser.print_help()
      print(sys.modules[__name__].__doc__)
      return

  if opts.virtualenv:
    libdirs = glob('%s/lib/python*/site-packages'%opts.virtualenv)
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
    # screen out unsupported file extensions
    _, ext = opts.export.lower().rsplit('.',1)
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

  # set it off
  run(vars(opts))

if __name__ == "__main__":
  main()
