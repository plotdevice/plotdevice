from setuptools import setup
from setuptools.extension import Extension

sources = ['module.m', 'SysAdmin.m', 'Pages.m', 'AnimatedGif.m', 'Video.m']
frameworks = ['AppKit', 'Foundation', 'Quartz', 'Security', 'AVFoundation', 'CoreMedia', 'CoreVideo']
cIO = Extension('cIO', sources=sources, extra_link_args=sum((['-framework', fmwk] for fmwk in frameworks), []))

setup (name = "cIO",
       version = "1.0",
       author = "Christian Swinehart",
       description = "Image and video export routines.",
       ext_modules = [cIO])