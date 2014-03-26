# encoding: utf-8
from .context import Context, Canvas
from . import grobs, effects, colors, typography, bezier, transform

# pull every submodule's __all__ into our own
modules = grobs, effects, colors, typography, bezier, transform
ns = {"Context":Context}
for module in modules:
  ns.update( (a,getattr(module,a)) for a in module.__all__  )
globals().update(ns)
__all__ = ns.keys()

# called by a Context to do the dependency injection™
def activate(ctx):
  for module in modules:
    setattr(module, '_ctx', ctx)
