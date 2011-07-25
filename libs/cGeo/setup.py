from distutils.core import setup, Extension

cGeo = Extension("cGeo", sources = ["cGeo.c"])

setup (name = "cGeo",
       version = "0.1",
       author = "Tom De Smedt",
       description = "Fast geometric functionality.",
       ext_modules = [cGeo])