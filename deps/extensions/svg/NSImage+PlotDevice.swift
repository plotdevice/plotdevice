import AppKit
import CoreGraphics

public extension NSImage {

  convenience init?(svgData data: Data) {
    guard let image = Image(data: data) else { return nil }

    self.init(size: image.size, flipped: true) { rect in
      guard let ctx = NSGraphicsContext.current?.cgContext else { return false }
      ctx.draw(image, in: CGRect(x: 0, y: 0, width: rect.size.width, height: rect.size.height))
      return true
    }
  }

  convenience init?(svgFileURL url: URL) {
    guard let image = Image(fileURL: url) else { return nil }

    self.init(size: image.size, flipped: true) { rect in
      guard let ctx = NSGraphicsContext.current?.cgContext else { return false }
      ctx.draw(image, in: CGRect(x: 0, y: 0, width: rect.size.width, height: rect.size.height))
      return true
    }
  }

  @objc
  static func svgFromData(_ data: Data) -> NSImage? {
      NSImage(svgData: data)
  }

  @objc
  static func svgFromURL(_ url: URL) -> NSImage? {
      NSImage(svgFileURL: url)
  }
}