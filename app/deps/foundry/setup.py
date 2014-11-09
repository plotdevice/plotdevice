from setuptools import setup
from setuptools.extension import Extension

sources = ['module.m', 'Vandercook.m', ]
frameworks = ['AppKit', 'Foundation', 'Quartz', 'CoreText',]
flags = sum((['-framework', fmwk] for fmwk in frameworks), [])
cFoundry = Extension('cFoundry', sources=sources, extra_link_args=flags)

setup (name = "cFoundry",
       version = "1.0",
       author = "Christian Swinehart",
       description = "Dept. of Typography & Tracing.",
       ext_modules = [cFoundry])