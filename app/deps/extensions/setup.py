from setuptools import setup
from setuptools.extension import Extension

sources = [
  'module.m',
  'io/SysAdmin.m', 'io/Pages.m', 'io/AnimatedGif.m', 'io/Video.m',
  'foundry/Vandercook.m',
  'pathmatics/gpc.c', 'pathmatics/pathmatics.m'
]
frameworks = ['AppKit', 'Foundation', 'Quartz', 'Security', 'AVFoundation', 'CoreMedia', 'CoreVideo', 'CoreText']
flags = sum((['-framework', fmwk] for fmwk in frameworks), [])
_plotdevice = Extension('_plotdevice', sources=sources, extra_link_args=flags)

setup (name = "_plotdevice",
       version = "1.0",
       author = "Christian Swinehart",
       description = "Typography, image/video export, and bezier math routines.",
       ext_modules = [_plotdevice])