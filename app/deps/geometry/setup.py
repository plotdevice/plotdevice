# from distutils.core import setup, Extension
from setuptools import setup, find_packages
from setuptools.extension import Extension

quiet = {"extra_compile_args":['-Qunused-arguments']}
cGeometry = Extension("cGeometry", ["cGeometry.c"], **quiet)

setup (name = "cGeometry",
       version = "0.1",
       author = "Tom De Smedt",
       description = "Fast geometric functionality.",
       ext_modules = [cGeometry])