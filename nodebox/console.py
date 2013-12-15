#!/usr/bin/env python
# encoding: utf-8
"""
console.py

Run nodebox scripts from the command line

usage: nodebox [-h] [-f] [-b] [--virtualenv PATH] [--export FILE]
               [--frames N or M-N] [--fps N] [--rate N] [--loop [N]] [--live]
               [--args [a [b ...]]]
               file

Options:
  -h, --help          show this help message and exit
  -f                  run full-screen
  -b                  run NodeBox in the background
  --virtualenv PATH   path to virtualenv whose libraries you want to use (this
                      should point to the top-level virtualenv directory; a
                      folder containing a lib/python2.7/site-packages
                      subdirectory)
  --export FILE       a destination filename ending in pdf, eps, png, tiff,
                      jpg, gif, or mov
  --frames N or M-N   number of frames to render or a range specifying the
                      first and last frames (default "1-")
  --fps N             frames per second in exported video (default 30)
  --rate N            bitrate in megabits per second (video only)
  --loop [N]          number of times to loop an exported animated gif (omit N
                      to loop forever)
  --live              perform an export in the application rather than the
                      console. if not exporting, re-render graphics each time
                      the file is saved
  --args [a [b ...]]  remainder of command line will be passed to the script
                      as sys.argv

NodeBox Script File:
  file                the python script to be rendered

"""

import sys
import os
import re
import argparse
import xmlrpclib
import socket
import json
import select
from time import sleep

import shutil
from datetime import datetime
from subprocess import Popen, PIPE

PORT = 9000

def connect(retry=12, delay=0):
  if delay:
    sleep(delay)
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  try:
    sock.connect(("localhost", PORT))
  except socket.error, e:
    if not retry:
      return None
    return connect(retry-1, delay=.2)
  return sock

def app_path():
  parent = os.path.abspath(os.path.dirname(__file__))
  if os.path.islink(__file__):
    parent = os.path.dirname(os.path.realpath(__file__))
  if parent.endswith('Resources/python/nodebox'):
    return os.path.abspath('%s/../../../..'%parent)
  elif parent.endswith('nodebox'):
    return os.path.abspath('%s/../Build/Products/Debug/NodeBox.app'%parent)
  return None

def task_path():
  return "%s/Contents/Resources/NodeBoxTask.app/Contents/MacOS/NodeBoxTask" % app_path()

def app_name():
  return app_path() or 'NodeBox.app'

def read_and_echo(sock):
  response = sock.recv(80)
  if response:
    print response,
  return response

def exec_console(opts):
  bin_path = task_path()
  env = dict(os.environ)
  p = Popen([bin_path], env=env, stdin=PIPE, stdout=PIPE, stderr=PIPE)
  p.stdin.write(json.dumps(vars(opts))+"\n")

  ERASER = '\r%s\r'%(' '*80)
  re_progress = re.compile(r'^\r.*?\[[#\.]{10,}\]$')
  progress = ''
  try:
    while True:
      reads = [p.stdout.fileno(), p.stderr.fileno()]
      ret = select.select(reads, [], [])
      for fd in ret[0]:
        if fd == p.stdout.fileno():
          line = p.stdout.readline()
          sys.stdout.write(ERASER+line+progress)

        if fd == p.stderr.fileno():
          line = p.stderr.readline()
          # the progress bar should overwrite itself, but anything else
          # on stderr should be passed through
          if re_progress.search(line):
            line = line.rstrip()
          else:
            sys.stdout.write(ERASER)
          progress = line
          sys.stdout.write(progress)
        sys.stdout.flush()

      if p.poll() != None:
          break
  except KeyboardInterrupt:
    # print "\rCancelled."
    pass

def exec_application(opts):  
  sock = connect(0)
  if not sock:
    os.system('open -a "%s" "%s"'%(app_name(), opts.file))
    sock = connect()
  if not sock:
    print "Couldn't connect to the NodeBox application"
    sys.exit(1)

  try:
    sock.sendall(json.dumps(vars(opts)) + "\n")
    try:
      while read_and_echo(sock): pass
    except KeyboardInterrupt:
      sock.sendall('STOP\n')
      print "\n",
      while read_and_echo(sock): pass
  finally:
    sock.close()

def main():
  parser = argparse.ArgumentParser(description='Run python scripts in NodeBox.app', add_help=False)
  o = parser.add_argument_group("Options", None)
  o.add_argument('-h','--help', action='help', help='show this help message and exit')
  o.add_argument('-f', dest='fullscreen', action='store_const', const=True, default=False, help='run full-screen')
  o.add_argument('-b', dest='activate', action='store_const', const=False, default=True, help='run NodeBox in the background')
  o.add_argument('--virtualenv', metavar='PATH', help='path to virtualenv whose libraries you want to use (this should point to the top-level virtualenv directory; a folder containing a lib/python2.7/site-packages subdirectory)')
  o.add_argument('--export', metavar='FILE', help='a destination filename ending in pdf, eps, png, tiff, jpg, gif, or mov')
  o.add_argument('--frames', metavar='N or M-N', help='number of frames to render or a range specifying the first and last frames (default "1-")')
  o.add_argument('--fps', metavar='N', default=30, type=int, help='frames per second in exported video (default 30)')
  o.add_argument('--rate', metavar='N', default=1.0, type=float, help='bitrate in megabits per second (video only)')
  o.add_argument('--loop', metavar='N', default=0, nargs='?', const=-1, help='number of times to loop an exported animated gif (omit N to loop forever)')
  o.add_argument('--live', action='store_const', const=True, help='re-render graphics each time the file is saved')
  o.add_argument('--args', nargs='*', default=[], metavar=('a','b'), help='remainder of command line will be passed to the script as sys.argv')
  i = parser.add_argument_group("NodeBox Script File", None)
  i.add_argument('file', help='the python script to be rendered')
  
  opts = parser.parse_args()
  
  if opts.virtualenv:
    libdir = '%s/lib/python2.7/site-packages'%opts.virtualenv
    if os.path.exists(libdir):
      opts.virtualenv = os.path.abspath(libdir)
    else:
      parser.exit(1, "bad argument [--virtualenv]\nvirtualenv site-packages dir not found: %s\n"%libdir)

  if opts.file:
    opts.file = os.path.abspath(opts.file)
    if not os.path.exists(opts.file):
      parser.exit(1, "file not found: %s\n"%opts.file)

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
      del opts.frames
  else:
    opts.first, opts.last = (1, None)

  if opts.export:
    basename, ext = opts.export.rsplit('.',1)
    if ext.lower() not in ('pdf', 'eps', 'png', 'tiff', 'jpg', 'gif', 'mov'):
      parser.exit(1, 'bad argument [--export]\nthe output filename must end with a supported format:\npdf, eps, png, tiff, jpg, gif, or mov\n')
    if '/' in opts.export:
      export_dir = os.path.dirname(opts.export)
      if not os.path.exists(export_dir):
        parser.exit(1,'export directory not found: %s\n'%os.path.abspath(export_dir))
    opts.export = os.path.abspath(opts.export)

  if not opts.activate:
    exec_console(opts)
  else:
    exec_application(opts)

if __name__ == "__main__":
  main()
