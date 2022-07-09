# all the NSBits and NSPieces

from Quartz import CALayer, CGBitmapContextCreate, CGBitmapContextCreateImage, CGColorCreate, \
                   CGColorSpaceCreateDeviceRGB, CGContextAddPath, CGContextAddRect, CGContextBeginPath, \
                   CGContextBeginTransparencyLayer, CGContextBeginTransparencyLayerWithRect, CGContextClearRect, \
                   CGContextClip, CGContextClipToMask, CGContextDrawPath, CGContextEndTransparencyLayer, \
                   CGContextEOClip, CGContextRestoreGState, CGContextSaveGState, CGContextSetAlpha, \
                   CGContextSetBlendMode, CGContextSetFillColorWithColor, CGContextSetLineCap, CGContextSetLineDash, \
                   CGContextSetLineJoin, CGContextSetLineWidth, CGContextSetStrokeColorWithColor, \
                   CGDataConsumerCreateWithCFData, CGImageDestinationAddImage, CGImageDestinationCreateWithData, \
                   CGImageDestinationFinalize, CGImageDestinationSetProperties, CGImageGetBitsPerComponent, \
                   CGImageGetBitsPerPixel, CGImageGetBytesPerRow, CGImageGetDataProvider, CGImageGetHeight, \
                   CGImageGetWidth, CGImageMaskCreate, CGPathAddCurveToPoint, CGPathAddLineToPoint, \
                   CGPathCloseSubpath, CGPathCreateCopy, CGPathCreateMutable, CGPathMoveToPoint, CGPathRelease, \
                   CGPDFContextBeginPage, CGPDFContextClose, CGPDFContextCreate, CGPDFContextEndPage, CGRectMake, \
                   CGSizeMake, kCGBitmapByteOrder32Host, kCGBlendModeClear, kCGBlendModeColor, kCGBlendModeColorBurn, \
                   kCGBlendModeColorDodge, kCGBlendModeCopy, kCGBlendModeDarken, kCGBlendModeDestinationAtop, \
                   kCGBlendModeDestinationIn, kCGBlendModeDestinationOut, kCGBlendModeDestinationOver, \
                   kCGBlendModeDifference, kCGBlendModeExclusion, kCGBlendModeHardLight, kCGBlendModeHue, \
                   kCGBlendModeLighten, kCGBlendModeLuminosity, kCGBlendModeMultiply, kCGBlendModeNormal, \
                   kCGBlendModeOverlay, kCGBlendModePlusDarker, kCGBlendModePlusLighter, kCGBlendModeSaturation, \
                   kCGBlendModeScreen, kCGBlendModeSoftLight, kCGBlendModeSourceAtop, kCGBlendModeSourceIn, \
                   kCGBlendModeSourceOut, kCGBlendModeXOR, kCGImageAlphaNoneSkipFirst, \
                   kCGImageAlphaPremultipliedFirst, kCGImageDestinationLossyCompressionQuality, kCGLineCapButt, \
                   kCGLineCapRound, kCGLineCapSquare, kCGLineJoinBevel, kCGLineJoinMiter, kCGLineJoinRound, \
                   kCGPathFill, kCGPathFillStroke, kCGPathStroke, kCIInputImageKey, kCGImageAlphaNone, CGColorSpaceCreateDeviceCMYK, CGContextClearRect
from AppKit import NSAlert, NSApp, NSAppearance, NSApplication, NSApplicationActivationPolicyAccessory, \
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
                   NSJustifiedTextAlignment, NSKeyValueObservingOptionNew, NSLayoutManager, NSLeftTextAlignment, \
                   NSLineBreakByWordWrapping, NSLineToBezierPathElement, NSMenu, NSMenuItem, NSMiniControlSize, \
                   NSMoveToBezierPathElement, NSMutableParagraphStyle, NSNib, NSOffState, NSOnState, NSPNGFileType, \
                   NSParagraphStyleAttributeName, NSPasteboard, NSPasteboardTypePDF, NSPasteboardURLReadingContentsConformToTypesKey, \
                   NSPasteboardURLReadingFileURLsOnlyKey, NSPasteboardTypeTIFF, NSPrintOperation, NSRectFill, \
                   NSRectFillUsingOperation, NSResponder, NSRightTextAlignment, NSSavePanel, NSScreen, NSShadow, \
                   NSSlider, NSSmallControlSize, NSSplitView, NSStringPboardType, NSSwitch, \
                   NSTIFFFileType, NSTextContainer, NSTextField, NSTextFinder, NSTextStorage, NSTextView, \
                   NSToolbarItem, NSTrackingActiveInActiveApp, NSTrackingArea, NSTrackingMouseEnteredAndExited, \
                   NSUnboldFontMask, NSUnitalicFontMask, NSUnionRect, NSView, NSViewMinXMargin, NSViewWidthSizable,  \
                   NSViewFrameDidChangeNotification, NSWindow, NSWindowBackingLocationVideoMemory, \
                   NSWindowController, NSWindowTabbingModeAutomatic, NSWindowTabbingModePreferred, NSWorkspace, NSKernAttributeName
from Foundation import CIAffineTransform, CIColorMatrix, CIContext, CIFilter, CIImage, \
                   CIVector, Foundation, NO, NSAffineTransform, NSAffineTransformStruct, \
                   NSAttributedString, NSAutoreleasePool, NSBundle, NSData, NSDate, NSDateFormatter, \
                   NSFileCoordinator, NSFileHandle, NSFileHandleDataAvailableNotification, NSIntersectionRange, \
                   NSHeight, NSInsetRect, NSIntersectionRect, NSLocale, NSLog, NSMacOSRomanStringEncoding, \
                   NSMakeRange, NSMidX, NSMidY, NSMutableAttributedString, NSMutableData, NSNotificationCenter, NSObject,\
                   NSOffsetRect, NSOperationQueue, NSPoint, NSRect, NSRectFromString, NSSelectorFromString, \
                   NSSize, NSString, NSStringFromRect, NSTimeZone, NSTimer, NSURL, NSUserDefaults, \
                   NSUTF8StringEncoding, NSWidth
from LaunchServices import kUTTypePNG, kUTTypeJPEG, kUTTypeGIF, kUTTypeTIFF
from WebKit import WebView
from objc import IBOutlet, IBAction
