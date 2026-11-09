# a stand-in library for testing ximport()
_ctx = None # set by ximport()

def chocolate():
    return _ctx.color('chocolate')
