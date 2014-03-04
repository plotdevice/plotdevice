from setuptools import setup, find_packages
from setuptools.extension import Extension

quiet = {"extra_compile_args":['-Qunused-arguments']}
cPathmatics = Extension("cPathmatics", sources = ["pathmatics.c"], **quiet)

setup (name = "pathmatics",
       version = "1.0",
       author = "Tom De Smedt and Frederik De Bleser",
       description = "Inner looping functions for calculating bezier operations.",
       ext_modules = [cPathmatics])