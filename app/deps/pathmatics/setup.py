from setuptools import setup
from setuptools.extension import Extension

cPathmatics = Extension("cPathmatics", sources = ["pathmatics.m", "gpc.c"], extra_link_args=['-framework', 'Cocoa'])

setup (name = "pathmatics",
       version = "1.0",
       author = "Written for NodeBox by Tom De Smedt and Frederik De Bleser",
       description = "Fast bezier math routines.",
       ext_modules = [cPathmatics])