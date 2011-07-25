from AppKit import NSBezierPath, NSFont, NSApplication

# Force NSApp initialisation.
NSApplication.sharedApplication().activateIgnoringOtherApps_(0)

p1 = NSBezierPath.bezierPathWithOvalInRect_(((0, 0), (100, 100)))
p2 = NSBezierPath.bezierPathWithOvalInRect_(((40, 40), (100, 100)))

# Outside of bounding box
p3 = NSBezierPath.bezierPathWithOvalInRect_(((110, 0), (100, 100)))

# In bounding box, doesn't intersect
p4 = NSBezierPath.bezierPathWithOvalInRect_(((72, 72), (100, 100)))



from cPolymagic import *

print intersects(p1, p4)

f = NSFont.fontWithName_size_("Helvetica", 72)
fp1 = NSBezierPath.bezierPath()
fp1.moveToPoint_((100, 100))
fp1.appendBezierPathWithGlyph_inFont_(68, f)

fp2 = NSBezierPath.bezierPath()
fp2.moveToPoint_((110, 100))
fp2.appendBezierPathWithGlyph_inFont_(68, f)

print intersects(fp1, fp2)

# Some other thing inside of the function perhaps?

print intersects(fp2, fp2)

p = union(fp1, fp2)
print p.elementCount()

p =  intersect(fp1, fp2)
print p.elementCount()

p =  difference(fp1, fp2)
print p.elementCount()

p = xor(fp1, fp2)
print p.elementCount()

