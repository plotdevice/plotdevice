# all the NSBits and NSPieces

from Quartz import CALayer, CGBitmapContextCreate, CGBitmapContextCreateImage, CGColorCreate, CGColorCreateCopyByMatchingToColorSpace, \
                   CGColorSpaceCreateDeviceCMYK, CGColorSpaceCreateDeviceRGB, CGColorSpaceCreateWithName, kCGColorSpaceDisplayP3, \
                   CGColorSpaceCopyICCData, CGColorSpaceCreateWithICCData, \
                   CGColorRef, CGColorGetColorSpace, CGColorGetComponents, CGColorGetNumberOfComponents, CGColorSpaceCopyName, \
                   kCGColorSpaceExtendedDisplayP3, kCGColorSpaceExtendedSRGB, kCGColorSpaceGenericCMYK, kCGColorSpaceSRGB, \
                   kCGColorSpaceModelCMYK, \
                   CGContextAddPath, CGContextAddRect, \
                   CGAffineTransformConcat, CGAffineTransformInvert, CGRectApplyAffineTransform, \
                   CGAffineTransformMakeScale, CGAffineTransformMakeTranslation, CGBitmapContextGetAlphaInfo, CGBitmapContextGetColorSpace, \
                   CGBitmapContextGetHeight, CGBitmapContextGetWidth, CGColorCreateCopyWithAlpha, CGColorGetAlpha, \
                   CGColorSpaceGetModel, CGContextConcatCTM, CGContextDrawImage, CGContextSetInterpolationQuality, \
                   CGRectInset, CGRectIntegral, CGRectIntersection, CGRectIsEmpty, kCGColorSpaceModelRGB, \
                   kCGImageAlphaNone, kCGImageAlphaNoneSkipFirst, kCGImageAlphaNoneSkipLast, kCGInterpolationHigh, \
                   CGContextBeginPath, CGContextBeginTransparencyLayer, CGContextBeginTransparencyLayerWithRect, \
                   CGContextClearRect, CGContextClearRect, CGContextClip, CGContextClipToMask, CGContextClipToRect, CGContextGetClipBoundingBox, CGContextDrawPath, \
                   CGContextEndTransparencyLayer, CGContextEOClip, CGContextFlush, CGContextGetCTM, CGContextRestoreGState, CGContextSaveGState, CGContextScaleCTM, \
                   CGContextSetAlpha, CGContextSetBlendMode, CGContextSetFillColorWithColor, CGContextSetLineCap, \
                   CGContextSetLineDash, CGContextSetLineJoin, CGContextSetLineWidth, CGContextSetShadowWithColor, \
                   CGContextSetStrokeColorWithColor, CGContextTranslateCTM, CGDataConsumerCreateWithCFData, CGImageDestinationAddImage, \
                   CGImageDestinationCreateWithData, CGImageDestinationFinalize, CGImageDestinationSetProperties, \
                   CGImageGetBitsPerComponent, CGImageGetBitsPerPixel, CGImageGetBytesPerRow, CGImageGetDataProvider, \
                   CGImageCreateCopyWithColorSpace, CGImageGetColorSpace, \
                   CGImageGetHeight, CGImageGetWidth, CGImageMaskCreate, CGPathAddCurveToPoint, CGPathAddLineToPoint, \
                   CGPathCloseSubpath, CGPathCreateCopy, CGPathCreateMutable, CGPathMoveToPoint, CGPathRelease, \
                   CGPDFContextBeginPage, CGPDFContextClose, CGPDFContextCreate, CGPDFContextEndPage, CGRectMake, \
                   CGContextBeginPage, CGContextEndPage, CGPDFContextCreateWithURL, \
                   CGSizeMake, kCGBitmapByteOrder32Host, kCGBlendModeClear, kCGBlendModeColor, kCGBlendModeColorBurn, \
                   kCGBlendModeColorDodge, kCGBlendModeCopy, kCGBlendModeDarken, kCGBlendModeDestinationAtop, \
                   kCGBlendModeDestinationIn, kCGBlendModeDestinationOut, kCGBlendModeDestinationOver, \
                   kCGBlendModeDifference, kCGBlendModeExclusion, kCGBlendModeHardLight, kCGBlendModeHue, \
                   kCGBlendModeLighten, kCGBlendModeLuminosity, kCGBlendModeMultiply, kCGBlendModeNormal, \
                   kCGBlendModeOverlay, kCGBlendModePlusDarker, kCGBlendModePlusLighter, kCGBlendModeSaturation, \
                   kCGBlendModeScreen, kCGBlendModeSoftLight, kCGBlendModeSourceAtop, kCGBlendModeSourceIn, \
                   kCGBlendModeSourceOut, kCGBlendModeXOR, kCGImageAlphaNone, kCGImageAlphaNoneSkipFirst, \
                   kCGImageAlphaPremultipliedFirst, kCGImageDestinationLossyCompressionQuality, \
                   kCGImagePropertyDPIHeight, kCGImagePropertyDPIWidth, kCGLineCapButt, kCGLineCapRound, \
                   kCGLineCapSquare, kCGLineJoinBevel, kCGLineJoinMiter, kCGLineJoinRound, kCGPathFill, \
                   kCGPathFillStroke, kCGPathStroke, kCGRenderingIntentDefault, kCAGravityCenter, kCAGravityResize, kCAGravityResizeAspect, kCIInputImageKey
from AppKit import NSAlert, NSAlternateKeyMask, NSApp, NSAppearance, NSApplication, NSApplicationActivationPolicyAccessory, \
                   NSApplicationActivationPolicyRegular, \
                   NSApplicationPresentationAutoHideMenuBar, NSApplicationPresentationAutoHideToolbar, \
                   NSApplicationPresentationFullScreen, \
                   NSBackingStoreBuffered, NSBeep, NSBezierPath, NSBitmapImageRep, NSBorderlessWindowMask, NSButton, \
                   NSCenterTextAlignment, NSChangeAutosaved, NSChangeCleared, NSChangeDone, NSChangeReadOtherContents, \
                   NSChangeRedone, NSChangeUndone, NSClipView, NSClosePathBezierPathElement, NSColor, NSColorSpace, \
                   NSCommandKeyMask, NSCompositeCopy, NSCompositeSourceOver, NSContentsCellMask, NSCriticalAlertStyle, NSCursor, \
                   NSCurveToBezierPathElement, NSDeviceCMYKColorSpace, NSDeviceIndependentModifierFlagsMask, NSDeviceRGBColorSpace, NSDocument, \
                   NSDocumentController, NSDragOperationCopy, NSEventTypeKeyDown, NSFindPboard, NSFixedPitchFontMask, NSFocusRingTypeExterior, NSFont, \
                   NSFontDescriptor, NSFontManager, NSForegroundColorAttributeName, NSGIFFileType, NSGradient, \
                   NSGraphicsContext, NSGraphiteControlTint, NSImage, NSImageCacheNever, NSImageCompressionFactor, \
                   NSImageInterpolationHigh, NSItalicFontMask, NSJPEGFileType, NSJustifiedTextAlignment, \
                   NSKernAttributeName, NSKeyValueObservingOptionNew, NSLayoutConstraint, NSLayoutManager, NSLeftTextAlignment, \
                   NSLineBreakByWordWrapping, NSLineToBezierPathElement, NSLinkAttributeName, NSMenu, NSMenuItem, NSMiniControlSize, \
                   NSMoveToBezierPathElement, NSMutableParagraphStyle, NSNib, NSOffState, NSOnState, \
                   NSParagraphStyleAttributeName, NSPasteboard, NSPasteboardTypePDF, NSPasteboardTypeTIFF, \
                   NSPasteboardURLReadingContentsConformToTypesKey, NSPasteboardURLReadingFileURLsOnlyKey, \
                   NSPDFImageRep, NSPNGFileType, NSPrintOperation, NSRectFill, NSRectFillUsingOperation, NSResponder, \
                   NSRightTextAlignment, NSSavePanel, NSScreen, NSScrollViewDidEndLiveMagnifyNotification, \
                   NSScrollViewWillStartLiveMagnifyNotification, \
                   NSScrollElasticityAllowed, NSScrollElasticityNone, NSShadow, NSSlider, NSSmallControlSize, NSSplitView, \
                   NSStringPboardType, NSSwitch, NSTextContainer, NSTextField, NSTextFinder, NSTextStorage, \
                   NSTerminateLater, NSTerminateNow, NSTextView, NSTIFFFileType, NSToolbarItem, NSTrackingActiveInActiveApp, \
                   NSTrackingActiveInKeyWindow, NSTrackingArea, NSTrackingArea, NSTrackingMouseEnteredAndExited, \
                   NSTrackingMouseMoved, NSUnboldFontMask, NSUnionRect, NSUnitalicFontMask, NSView, \
                   NSViewBoundsDidChangeNotification, NSViewFrameDidChangeNotification, NSViewMinXMargin, NSViewWidthSizable, \
                   NSVisualEffectMaterialHUDWindow, NSVisualEffectMaterialTitlebar, NSVisualEffectMaterialUnderWindowBackground, \
                   NSVisualEffectView, NSWindow, \
                   NSWindowBackingLocationVideoMemory, NSWindowController, NSWindowStyleMaskFullSizeContentView, \
                   NSWindowTabbingModeAutomatic, \
                   NSWindowTabbingModePreferred, NSWorkspace
from Foundation import CIAffineTransform, CIColorMatrix, CIContext, CIFilter, CIImage, CIVector, Foundation, NO, \
                       NSAffineTransform, NSAffineTransformStruct, NSArray, NSAttributedString, NSAutoreleasePool, \
                       NSBundle, NSCharacterSet, NSData, NSDate, NSDateFormatter, NSDictionary, NSFileCoordinator, NSFileHandle, \
                       NSFileHandleDataAvailableNotification, NSHeight, NSInsetRect, NSIntersectionRange, \
                       NSIntersectionRect, NSLocale, NSLog, NSMacOSRomanStringEncoding, NSMakeRange, NSMidX, NSMidY, \
                       NSMutableAttributedString, NSMutableData, NSNotFound, NSNotificationCenter, NSObject, NSOffsetRect, \
                       NSOperationQueue, NSPoint, NSPointInRect, NSRect, NSRectFromString, NSSelectorFromString, NSSize, NSString, \
                       NSStringFromRect, NSTimer, NSTimeZone, NSURL, NSUserDefaults, NSUTF8StringEncoding, NSWidth, \
                       NSZeroRect
from CoreServices import kUTTypePNG, kUTTypeJPEG, kUTTypeGIF, kUTTypeTIFF
from WebKit import WKWebView, WKWebViewConfiguration, WKUserScript, WKUserScriptInjectionTimeAtDocumentStart
from objc import IBOutlet, IBAction
