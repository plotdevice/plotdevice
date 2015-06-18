# all the NSBits and NSPieces

from Quartz import CALayer, CGColorCreate, CGContextAddPath, CGContextAddRect, CGContextBeginPath, \
                   CGContextBeginTransparencyLayer, CGContextBeginTransparencyLayerWithRect, \
                   CGContextClip, CGContextClipToMask, CGContextDrawPath, CGContextEOClip, \
                   CGContextEndTransparencyLayer, CGContextRestoreGState, CGContextSaveGState, \
                   CGContextSetAlpha, CGContextSetBlendMode, CGContextSetFillColorWithColor, \
                   CGContextSetLineCap, CGContextSetLineDash, CGContextSetLineJoin, CGContextSetLineWidth, \
                   CGContextSetStrokeColorWithColor, CGImageGetBitsPerComponent, CGImageGetBitsPerPixel, \
                   CGImageGetBytesPerRow, CGImageGetDataProvider, CGImageGetHeight, CGImageGetWidth, \
                   CGImageMaskCreate, CGPathAddCurveToPoint, CGPathAddLineToPoint, CGPathCloseSubpath, \
                   CGPathCreateCopy, CGPathCreateMutable, CGPathRelease, CGPathMoveToPoint, kCGBlendModeClear, \
                   kCGBlendModeColor, kCGBlendModeColorBurn, kCGBlendModeColorDodge, kCGBlendModeCopy, \
                   kCGBlendModeDarken, kCGBlendModeDestinationAtop, kCGBlendModeDestinationIn, \
                   kCGBlendModeDestinationOut, kCGBlendModeDestinationOver, kCGBlendModeDifference, \
                   kCGBlendModeExclusion, kCGBlendModeHardLight, kCGBlendModeHue, kCGBlendModeLighten, \
                   kCGBlendModeLuminosity, kCGBlendModeMultiply, kCGBlendModeNormal, kCGBlendModeOverlay, \
                   kCGBlendModePlusDarker, kCGBlendModePlusLighter, kCGBlendModeSaturation, \
                   kCGBlendModeScreen, kCGBlendModeSoftLight, kCGBlendModeSourceAtop, kCGBlendModeSourceIn, \
                   kCGBlendModeSourceOut, kCGBlendModeXOR, kCGLineCapButt, kCGLineCapRound, kCGLineCapSquare, \
                   kCGLineJoinBevel, kCGLineJoinMiter, kCGLineJoinRound, kCGPathFill, kCGPathFillStroke, \
                   kCGPathStroke, kCIInputImageKey
from AppKit import NSAlert, NSApp, NSApplication, NSApplicationActivationPolicyAccessory, \
                   NSBackingStoreBuffered, NSBeep, NSBezierPath, NSBitmapImageRep, NSBorderlessWindowMask, \
                   NSButton, NSCenterTextAlignment, NSChangeAutosaved, NSChangeCleared, NSChangeDone, \
                   NSChangeReadOtherContents, NSChangeRedone, NSChangeUndone, NSClipView, \
                   NSClosePathBezierPathElement, NSColor, NSColorSpace, NSCompositeCopy, \
                   NSCompositeSourceOver, NSContentsCellMask, NSCriticalAlertStyle, NSCursor, \
                   NSCurveToBezierPathElement, NSDeviceCMYKColorSpace, NSDeviceRGBColorSpace, NSDocument, \
                   NSDocumentController, NSFindPboard, NSFixedPitchFontMask, NSFocusRingTypeExterior, \
                   NSFont, NSFontDescriptor, NSFontManager, NSForegroundColorAttributeName, NSGIFFileType, \
                   NSGradient, NSGraphicsContext, NSGraphiteControlTint, NSImage, NSImageCacheNever, \
                   NSImageCompressionFactor, NSImageInterpolationHigh, NSItalicFontMask, NSJPEGFileType, \
                   NSJustifiedTextAlignment, NSLayoutManager, NSLeftTextAlignment, NSLineBreakByWordWrapping, \
                   NSLineToBezierPathElement, NSMenu, NSMenuItem, NSMiniControlSize, NSMoveToBezierPathElement, \
                   NSMutableParagraphStyle, NSNib, NSOffState, NSOnState, NSPDFPboardType, NSPNGFileType, \
                   NSParagraphStyleAttributeName, NSPasteboard, NSPasteboardURLReadingContentsConformToTypesKey, \
                   NSPasteboardURLReadingFileURLsOnlyKey, NSPostScriptPboardType, NSPrintOperation, NSRectFill, \
                   NSRectFillUsingOperation, NSResponder, NSRightTextAlignment, NSSavePanel, NSScreen, NSShadow, \
                   NSSlider, NSSmallControlSize, NSSplitView, NSStringPboardType, NSSwitchButton, NSTIFFFileType, \
                   NSTIFFPboardType, NSTextContainer, NSTextField, NSTextFinder, NSTextStorage, NSTextView, \
                   NSTrackingActiveInActiveApp, NSTrackingArea, NSTrackingMouseEnteredAndExited, NSUnboldFontMask, \
                   NSUnitalicFontMask, NSUnionRect, NSView, NSViewFrameDidChangeNotification, NSWindow, \
                   NSWindowBackingLocationVideoMemory, NSWindowController, NSWorkspace, NSKernAttributeName
from Foundation import CIAffineTransform, CIColorMatrix, CIContext, CIFilter, CIImage, \
                   CIVector, Foundation, NO, NSAffineTransform, NSAffineTransformStruct, \
                   NSAttributedString, NSAutoreleasePool, NSBundle, NSData, NSDate, NSDateFormatter, \
                   NSFileCoordinator, NSFileHandle, NSFileHandleDataAvailableNotification, NSIntersectionRange, \
                   NSHeight, NSInsetRect, NSIntersectionRect, NSLocale, NSLog, NSMacOSRomanStringEncoding, \
                   NSMakeRange, NSMidX, NSMidY, NSMutableAttributedString, NSNotificationCenter, NSObject,\
                   NSOffsetRect, NSOperationQueue, NSPoint, NSRect, NSRectFromString, NSSelectorFromString, \
                   NSSize, NSString, NSStringFromRect, NSTimeZone, NSTimer, NSURL, NSUserDefaults, \
                   NSUTF8StringEncoding, NSWidth
from WebKit import WebView
from objc import IBOutlet, IBAction