__all__ = ["AnimatedGif", "ImageSequence", "SysAdmin", "Video"]
import objc, cIO
for cls in __all__:
    globals()[cls] = objc.lookUpClass(cls)
