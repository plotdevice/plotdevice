#!/usr/bin/env python
# encoding: utf-8
"""
nodebox.py

Run nodebox scripts from the command line:

  $ nodebox.py [--live] [--virtualenv=path/to/env] <filename>

"""

import sys
import os
from pdb import set_trace as tron
from collections import defaultdict as ddict
py_root = os.path.dirname(os.path.abspath(__file__))
_mkdir = lambda pth: os.path.exists(pth) or os.makedirs(pth)
from pprint import pprint

import argparse
import xmlrpclib
import socket
from time import sleep

PORT = 9000

def connected(proxy):
  try:
    return proxy.status() == 'ready'
  except:
    return False

def main():
  parser = argparse.ArgumentParser(description='Run python scripts in NodeBox.app')
  parser.add_argument('--frame', dest='range', metavar='FIRST[-LAST]', help='first (and optionally last) frame to render')
  parser.add_argument('--virtualenv', metavar='PATH', help='path to virtualenv whose libraries you want to use')
  parser.add_argument('--live', action='store_const', const=True, help='re-render graphics each time the file is saved')
  parser.add_argument('file', help='the python script to be rendered')
  parser.add_argument('args', nargs=argparse.REMAINDER, metavar='<arg ...>', help='optional arguments to be passed to the script')
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

  if opts.range:
    try:
      frames = [int(f) for f in opts.range.split('-')]
    except ValueError:
      parser.exit(1, 'bad argument [--frame]\nmust be a single integer ("42") or a hyphen-separated range ("33-66").\ncouldn\'t make sense of "%s"\n'%opts.range)

    if len(frames) > 1 and frames[1]<frames[0]:
      parser.exit(1, "bad argument [--frame]\nfinal-frame number is less than first-frame\n")

    opts.range = frames

  proxy = xmlrpclib.ServerProxy('http://localhost:%i'%PORT, allow_none=True)
  if not connected(proxy):
    os.system('open -a NodeBox "%s"'%opts.file)
    while not connected(proxy):
      sleep(0.2)
  print proxy.exec_command(opts)

if __name__ == "__main__":
  main()
