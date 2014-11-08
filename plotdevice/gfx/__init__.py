# encoding: utf-8
from contextlib import contextmanager
from ..lib.cocoa import *

### graphics context mgmt ###

def _save():
    NSGraphicsContext.currentContext().saveGraphicsState()

def _restore():
    NSGraphicsContext.currentContext().restoreGraphicsState()

@contextmanager
def _ns_context():
    ctx = NSGraphicsContext.currentContext()
    ctx.saveGraphicsState()
    yield ctx
    ctx.restoreGraphicsState()

@contextmanager
def _cg_context():
    port = NSGraphicsContext.currentContext().graphicsPort()
    CGContextSaveGState(port)
    yield port
    CGContextRestoreGState(port)

@contextmanager
def _cg_layer():
    # CGContextBeginTransparencyLayerWithRect(_cg_port(), <bounds>, None)
    CGContextBeginTransparencyLayer(_cg_port(), None)
    yield
    CGContextEndTransparencyLayer(_cg_port())

def _cg_port():
    return NSGraphicsContext.currentContext().graphicsPort()

### submodule init ###

# pool the submodules' __all__ namespaces into our own
from . import atoms, effects, colors, text, typography, bezier, image, geometry
modules = atoms, effects, colors, text, typography, bezier, image, geometry
ns = {}
for module in modules:
  ns.update( (a,getattr(module,a)) for a in module.__all__  )
globals().update(ns)
__all__ = ns.keys()

# called by a Context to do the dependency injection™
def bind(ctx):
  for module in modules:
    # all of the gfx.* submodules refer to a global called _ctx to access the
    # parent context. before a user script is interpreted, the sandbox resets the
    # context which calls this method as a side-effect.
    setattr(module, '_ctx', ctx)

