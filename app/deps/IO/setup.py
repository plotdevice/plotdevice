from setuptools import setup
from setuptools.extension import Extension

sources = ['module.m', 'SysAdmin.m', 'Pages.m', 'AnimatedGif.m', 'Video.m']
frameworks = ['AppKit', 'Foundation', 'Quartz', 'Security', 'AVFoundation', 'CoreMedia', 'CoreVideo']
flags = sum((['-framework', fmwk] for fmwk in frameworks), [])
cIO = Extension('cIO', sources=sources, extra_link_args=flags)

setup (name = "cIO",
       version = "1.0",
       author = "Christian Swinehart",
       description = "Image and video export routines.",
       ext_modules = [cIO])