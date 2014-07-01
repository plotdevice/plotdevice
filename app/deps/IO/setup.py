# from distutils.core import setup, Extension
from setuptools import setup, find_packages
from setuptools.extension import Extension

quiet = {"extra_compile_args":['-Qunused-arguments']}
cIO = Extension('cIO', sources=['module.m', 'SysAdmin.m', 'Pages.m', 'AnimatedGif.m', 'Video.m'], extra_link_args=['-framework', 'AppKit', '-framework', 'Foundation', '-framework', 'Quartz', '-framework', 'Security', '-framework', 'AVFoundation', '-framework', 'CoreMedia', '-framework', 'CoreVideo'], **quiet)

setup (name = "cIO",
       version = "1.0",
       author = "Christian Swinehart",
       description = "Image and video export routines.",
       ext_modules = [cIO])