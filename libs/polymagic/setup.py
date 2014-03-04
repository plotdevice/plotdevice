from setuptools import setup, find_packages
from setuptools.extension import Extension

#CFLAGS=[]

quiet = {"extra_compile_args":['-Qunused-arguments']}
cPolymagic = Extension("cPolymagic", sources = ["gpc.c", "polymagic.m"], extra_link_args=['-framework', 'AppKit', '-framework', 'Foundation'], **quiet)

setup (name = "polymagic",
       version = "0.1",
       author = "Frederik De Bleser",
       description = "Additional utility functions for NSBezierPath using GPC.",
       ext_modules = [cPolymagic])