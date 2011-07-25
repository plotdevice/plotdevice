from distutils.core import setup, Extension

cPathmatics = Extension("cPathmatics", sources = ["pathmatics.c"])

setup (name = "pathmatics",
       version = "1.0",
       author = "Tom De Smedt and Frederik De Bleser",
       description = "Inner looping functions for calculating bezier operations.",
       ext_modules = [cPathmatics])