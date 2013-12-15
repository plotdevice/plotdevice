from os.path import dirname, abspath
__version__='1.9.7rc2'

def get_version():
    return __version__

def get_bundle_path(subpath=''):
  bundle_path = dirname(abspath('%s/../../../..'%__file__))
  if subpath:
    return '%s/%s'%(bundle_path, subpath)
  return bundle_path
