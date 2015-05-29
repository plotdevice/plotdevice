#!/usr/bin/env python
# encoding: utf-8
"""
setup.py

Created by Christian Swinehart on 2015/05/28.
Copyright (c) 2015 Samizdat Drafting Co All rights reserved.
"""

# this is a ‘stub’ setup.py that's just here for compatibility with the
# main deps build.py script. it passes the current interpreter path to
# make and lets it take over from there...

import os, sys
os.system('PYTHON="%s" make -s'%sys.executable)
