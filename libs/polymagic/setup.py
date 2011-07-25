from distutils.core import setup, Extension

CFLAGS=[]

cPolymagic = Extension("cPolymagic", sources = ["gpc.c", "polymagic.m"], extra_compile_args=CFLAGS)

setup (name = "polymagic",
       version = "0.1",
       author = "Frederik De Bleser",
       description = "Additional utility functions for NSBezierPath using GPC.",
       ext_modules = [cPolymagic])