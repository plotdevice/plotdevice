# all the NSBits and NSPieces

from Quartz import CALayer, CGAffineTransformConcat, CGAffineTransformInvert, CGAffineTransformMakeScale, \
                   CGAffineTransformMakeTranslation, CGBitmapContextCreate, CGBitmapContextCreateImage, \
                   CGBitmapContextGetAlphaInfo, CGBitmapContextGetColorSpace, CGBitmapContextGetHeight, \
                   CGBitmapContextGetWidth, CGColorCreate, CGColorCreateCopyByMatchingToColorSpace, \
                   CGColorCreateCopyWithAlpha, CGColorGetColorSpace, CGColorGetComponents, \
                   CGColorGetNumberOfComponents, CGColorRef, CGColorSpaceCopyICCData, CGColorSpaceCopyName, \
                   CGColorSpaceCreateDeviceCMYK, CGColorSpaceCreateDeviceRGB, CGColorSpaceCreateWithICCData, \
                   CGColorSpaceCreateWithName, CGColorSpaceGetModel, CGColorSpaceGetNumberOfComponents, \
                   CGContextAddPath, CGContextAddRect, CGContextBeginPage, CGContextBeginPath, \
                   CGContextBeginTransparencyLayer, CGContextBeginTransparencyLayerWithRect, CGContextClearRect, \
                   CGContextClip, CGContextClipToMask, CGContextClipToRect, CGContextConcatCTM, CGContextDrawImage, \
                   CGContextDrawPath, CGContextEndPage, CGContextEndTransparencyLayer, CGContextEOClip, \
                   CGContextFlush, CGContextGetClipBoundingBox, CGContextGetCTM, CGContextGetPathBoundingBox, \
                   CGContextReplacePathWithStrokedPath, CGContextRestoreGState, CGContextSaveGState, \
                   CGContextScaleCTM, CGContextSetAlpha, CGContextSetBlendMode, CGContextSetFillColorWithColor, \
                   CGContextSetInterpolationQuality, CGContextSetLineCap, CGContextSetLineDash, \
                   CGContextSetLineJoin, CGContextSetLineWidth, CGContextSetRenderingIntent, \
                   CGContextSetShadowWithColor, CGContextSetStrokeColorWithColor, CGContextTranslateCTM, \
                   CGDataConsumerCreateWithCFData, CGImageCreateCopyWithColorSpace, CGImageDestinationAddImage, \
                   CGImageDestinationCreateWithData, CGImageDestinationFinalize, CGImageDestinationSetProperties, \
                   CGImageGetBitsPerComponent, CGImageGetBitsPerPixel, CGImageGetBytesPerRow, CGImageGetColorSpace, \
                   CGImageGetDataProvider, CGImageGetHeight, CGImageGetWidth, CGImageMaskCreate, \
                   CGPathAddCurveToPoint, CGPathAddLineToPoint, CGPathCloseSubpath, CGPathCreateCopy, \
                   CGPathCreateMutable, CGPathMoveToPoint, CGPathRelease, CGPDFContextBeginPage, CGPDFContextClose, \
                   CGPDFContextCreate, CGPDFContextCreateWithURL, CGPDFContextEndPage, CGRectApplyAffineTransform, \
                   CGRectInset, CGRectIntegral, CGRectIntersection, CGRectIsEmpty, CGRectMake, CGSizeMake, \
                   kCAGravityCenter, kCAGravityResize, kCAGravityResizeAspect, kCGBitmapByteOrder32Host, \
                   kCGBlendModeClear, kCGBlendModeColor, kCGBlendModeColorBurn, kCGBlendModeColorDodge, \
                   kCGBlendModeCopy, kCGBlendModeDarken, kCGBlendModeDestinationAtop, kCGBlendModeDestinationIn, \
                   kCGBlendModeDestinationOut, kCGBlendModeDestinationOver, kCGBlendModeDifference, \
                   kCGBlendModeExclusion, kCGBlendModeHardLight, kCGBlendModeHue, kCGBlendModeLighten, \
                   kCGBlendModeLuminosity, kCGBlendModeMultiply, kCGBlendModeNormal, kCGBlendModeOverlay, \
                   kCGBlendModePlusDarker, kCGBlendModePlusLighter, kCGBlendModeSaturation, kCGBlendModeScreen, \
                   kCGBlendModeSoftLight, kCGBlendModeSourceAtop, kCGBlendModeSourceIn, kCGBlendModeSourceOut, \
                   kCGBlendModeXOR, kCGColorSpaceDisplayP3, kCGColorSpaceExtendedDisplayP3, \
                   kCGColorSpaceExtendedSRGB, kCGColorSpaceGenericCMYK, kCGColorSpaceModelCMYK, \
                   kCGColorSpaceModelRGB, kCGColorSpaceSRGB, kCGImageAlphaNone, kCGImageAlphaNoneSkipFirst, \
                   kCGImageAlphaNoneSkipLast, kCGImageAlphaPremultipliedFirst, kCGImageAlphaPremultipliedLast, \
                   kCGImageDestinationLossyCompressionQuality, kCGImagePropertyDPIHeight, kCGImagePropertyDPIWidth, \
                   kCGInterpolationHigh, kCGLineCapButt, kCGLineCapRound, kCGLineCapSquare, kCGLineJoinBevel, \
                   kCGLineJoinMiter, kCGLineJoinRound, kCGPathFill, kCGPathFillStroke, kCGPathStroke, \
                   kCGRenderingIntentDefault, kCGRenderingIntentRelativeColorimetric, kCIInputImageKey
from AppKit import NSAlert, NSAlternateKeyMask, NSApp, NSAppearance, NSApplication, \
                   NSApplicationActivationPolicyAccessory, NSApplicationActivationPolicyRegular, \
                   NSApplicationPresentationAutoHideMenuBar, NSApplicationPresentationAutoHideToolbar, \
                   NSApplicationPresentationFullScreen, NSBackingStoreBuffered, NSBeep, NSBezierPath, \
                   NSBitmapImageRep, NSBorderlessWindowMask, NSButton, NSCenterTextAlignment, NSChangeAutosaved, \
                   NSChangeCleared, NSChangeDone, NSChangeReadOtherContents, NSChangeRedone, NSChangeUndone, \
                   NSClipView, NSClosePathBezierPathElement, NSColor, NSColorSpace, NSCommandKeyMask, \
                   NSCompositeCopy, NSCompositeSourceOver, NSContentsCellMask, NSCriticalAlertStyle, NSCursor, \
                   NSCurveToBezierPathElement, NSDeviceCMYKColorSpace, NSDeviceIndependentModifierFlagsMask, \
                   NSDeviceRGBColorSpace, NSDocument, NSDocumentController, NSDragOperationCopy, NSEventTypeKeyDown, \
                   NSFindPboard, NSFixedPitchFontMask, NSFocusRingTypeExterior, NSFont, NSFontDescriptor, \
                   NSFontManager, NSForegroundColorAttributeName, NSGIFFileType, NSGradient, NSGraphicsContext, \
                   NSGraphiteControlTint, NSImage, NSImageCacheNever, NSImageCompressionFactor, \
                   NSImageInterpolationHigh, NSItalicFontMask, NSJPEGFileType, NSJustifiedTextAlignment, \
                   NSKernAttributeName, NSKeyValueObservingOptionNew, NSLayoutConstraint, NSLayoutManager, \
                   NSLeftTextAlignment, NSLineBreakByWordWrapping, NSLineToBezierPathElement, NSLinkAttributeName, \
                   NSMenu, NSMenuItem, NSMiniControlSize, NSMoveToBezierPathElement, NSMutableParagraphStyle, NSNib, \
                   NSOffState, NSOnState, NSParagraphStyleAttributeName, NSPasteboard, NSPasteboardTypePDF, \
                   NSPasteboardTypeTIFF, NSPasteboardURLReadingContentsConformToTypesKey, \
                   NSPasteboardURLReadingFileURLsOnlyKey, NSPDFImageRep, NSPNGFileType, NSPrintOperation, \
                   NSRectFill, NSRectFillUsingOperation, NSResponder, NSRightTextAlignment, NSSavePanel, NSScreen, \
                   NSScrollElasticityAllowed, NSScrollElasticityNone, NSScrollViewDidEndLiveMagnifyNotification, \
                   NSScrollViewWillStartLiveMagnifyNotification, NSShadow, NSSlider, NSSmallControlSize, \
                   NSSplitView, NSStringPboardType, NSSwitch, NSTerminateLater, NSTerminateNow, NSTextContainer, \
                   NSTextField, NSTextFinder, NSTextStorage, NSTextView, NSTIFFFileType, NSToolbarItem, \
                   NSTrackingActiveInActiveApp, NSTrackingActiveInKeyWindow, NSTrackingArea, \
                   NSTrackingMouseEnteredAndExited, NSTrackingMouseMoved, NSUnboldFontMask, NSUnionRect, \
                   NSUnitalicFontMask, NSView, NSViewBoundsDidChangeNotification, NSViewFrameDidChangeNotification, \
                   NSViewMinXMargin, NSViewWidthSizable, NSVisualEffectMaterialHUDWindow, \
                   NSVisualEffectMaterialTitlebar, NSVisualEffectMaterialUnderWindowBackground, NSVisualEffectView, \
                   NSWindow, NSWindowBackingLocationVideoMemory, NSWindowController, \
                   NSWindowStyleMaskFullSizeContentView, NSWindowTabbingModeAutomatic, NSWindowTabbingModePreferred, \
                   NSWorkspace
from Foundation import CIAffineTransform, CIColorMatrix, CIContext, CIFilter, CIImage, CIVector, Foundation, NO, \
                       NSAffineTransform, NSAffineTransformStruct, NSArray, NSAttributedString, NSAutoreleasePool, \
                       NSBundle, NSCharacterSet, NSData, NSDate, NSDateFormatter, NSDictionary, NSFileCoordinator, \
                       NSFileHandle, NSFileHandleDataAvailableNotification, NSHeight, NSInsetRect, \
                       NSIntersectionRange, NSIntersectionRect, NSLocale, NSLog, NSMacOSRomanStringEncoding, \
                       NSMakeRange, NSMidX, NSMidY, NSMutableAttributedString, NSMutableData, NSNotFound, \
                       NSNotificationCenter, NSObject, NSOffsetRect, NSOperationQueue, NSPoint, NSPointInRect, \
                       NSRect, NSRectFromString, NSSelectorFromString, NSSize, NSString, NSStringFromRect, NSTimer, \
                       NSTimeZone, NSURL, NSUserDefaults, NSUTF8StringEncoding, NSWidth, NSZeroRect
from WebKit import WKUserScript, WKUserScriptInjectionTimeAtDocumentStart, WKWebView, WKWebViewConfiguration
from ColorSync import ColorSyncProfileCreate, ColorSyncProfileCreateWithName, ColorSyncTransformConvert, \
                      ColorSyncTransformCreate, kColorSync16BitInteger, kColorSyncAlphaNone, \
                      kColorSyncBlackPointCompensation, kColorSyncDisplayP3Profile, kColorSyncProfile, \
                      kColorSyncRenderingIntent, kColorSyncRenderingIntentRelative, kColorSyncTransformDeviceToPCS, \
                      kColorSyncTransformPCSToDevice, kColorSyncTransformTag
from objc import IBAction, IBOutlet
