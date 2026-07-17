import AppKit
import CoreGraphics
import ObjectiveC

public extension NSImage {

  convenience init?(svgData data: Data) {
    guard let image = Image(data: data) else { return nil }

    self.init(size: image.size, flipped: true) { rect in
      guard let ctx = NSGraphicsContext.current?.cgContext else { return false }
      ctx.draw(image, in: CGRect(x: 0, y: 0, width: rect.size.width, height: rect.size.height))
      return true
    }
    objc_setAssociatedObject(self, &plotdeviceSVGKey, image, .OBJC_ASSOCIATION_RETAIN)
  }

  convenience init?(svgFileURL url: URL) {
    guard let image = Image(fileURL: url) else { return nil }

    self.init(size: image.size, flipped: true) { rect in
      guard let ctx = NSGraphicsContext.current?.cgContext else { return false }
      ctx.draw(image, in: CGRect(x: 0, y: 0, width: rect.size.width, height: rect.size.height))
      return true
    }
    objc_setAssociatedObject(self, &plotdeviceSVGKey, image, .OBJC_ASSOCIATION_RETAIN)
  }

  @objc
  static func svgFromData(_ data: Data) -> NSImage? {
      NSImage(svgData: data)
  }

  @objc
  static func svgFromURL(_ url: URL) -> NSImage? {
      NSImage(svgFileURL: url)
  }

  // Traces the union of every shape in the SVG into a single NSBezierPath, for
  // use as a vector clip()/mask() outline (as opposed to a rasterized one).
  // Computed lazily on first access and cached, since most SVGs are only ever
  // drawn, not traced. Returns nil for images that weren't loaded via
  // svgFromData_/svgFromURL_.
  @objc
  func plotdeviceOutline() -> NSBezierPath? {
    if let cached = objc_getAssociatedObject(self, &plotdeviceOutlineKey) as? NSBezierPath {
      return cached
    }
    guard let svg = objc_getAssociatedObject(self, &plotdeviceSVGKey) as? Image else {
      return nil
    }
    let outline = svg.plotdeviceOutlinePath()
    objc_setAssociatedObject(self, &plotdeviceOutlineKey, outline, .OBJC_ASSOCIATION_RETAIN)
    return outline
  }
}

private var plotdeviceSVGKey: UInt8 = 0
private var plotdeviceOutlineKey: UInt8 = 0

private extension Image {

  // Walks the flat list of draw commands SwiftDraw generated from the SVG
  // (see Image.swift/Renderer.swift), tracking a CTM stack the same way a
  // real CGContext-backed renderer would (see CGRenderer in
  // Renderer.CoreGraphics.swift), and merges every filled/stroked shape's
  // path -- transformed into its final position -- into one accumulated
  // path. Stroked shapes are converted to their equivalent fill outline
  // (via the current line width/cap/join/miter, tracked the same way the
  // ctm is) before being merged in, so their painted-ink area actually
  // contributes to the union rather than a zero-width centerline.
  func plotdeviceOutlinePath() -> NSBezierPath {
    var ctm = CGAffineTransform.identity
    var stack: [CGAffineTransform] = []
    let accumulated = CGMutablePath()

    var lineWidth: CGFloat = 1.0
    var lineCap: CGLineCap = .butt
    var lineJoin: CGLineJoin = .miter
    var miterLimit: CGFloat = 10.0

    for command in commands {
      switch command {
      case .pushState:
        stack.append(ctm)
      case .popState:
        if let restored = stack.popLast() {
          ctm = restored
        }
      case .concatenate(let transform):
        ctm = transform.concatenating(ctm)
      case .translate(let tx, let ty):
        ctm = CGAffineTransform(translationX: tx, y: ty).concatenating(ctm)
      case .rotate(let angle):
        ctm = CGAffineTransform(rotationAngle: angle).concatenating(ctm)
      case .scale(let sx, let sy):
        ctm = CGAffineTransform(scaleX: sx, y: sy).concatenating(ctm)
      case .setLine(let width):
        lineWidth = width
      case .setLineCap(let cap):
        lineCap = cap
      case .setLineJoin(let join):
        lineJoin = join
      case .setLineMiter(let limit):
        miterLimit = limit
      case .fill(let path, _):
        accumulated.addPath(path, transform: ctm)
      case .stroke(let path):
        let stroked = path.copy(strokingWithWidth: lineWidth, lineCap: lineCap,
                                 lineJoin: lineJoin, miterLimit: miterLimit)
        accumulated.addPath(stroked, transform: ctm)
      default:
        break
      }
    }

    return accumulated.plotdeviceBezierPath()
  }
}

private extension CGPath {

  // Replays this path's segments onto a fresh NSBezierPath. Manual segment
  // replay (rather than the macOS 14+ NSBezierPath(cgPath:) initializer) so
  // this keeps working on the package's older deployment target; quadratic
  // segments are elevated to cubic since NSBezierPath has no quad primitive
  // prior to macOS 14 either.
  func plotdeviceBezierPath() -> NSBezierPath {
    let path = NSBezierPath()
    var current = CGPoint.zero

    for segment in segments() {
      switch segment {
      case .move(let p):
        path.move(to: p)
        current = p
      case .line(let p):
        path.line(to: p)
        current = p
      case .quad(let c, let p):
        let c1 = CGPoint(x: current.x + (c.x - current.x) * (2.0/3.0),
                          y: current.y + (c.y - current.y) * (2.0/3.0))
        let c2 = CGPoint(x: p.x + (c.x - p.x) * (2.0/3.0),
                          y: p.y + (c.y - p.y) * (2.0/3.0))
        path.curve(to: p, controlPoint1: c1, controlPoint2: c2)
        current = p
      case .cubic(let c1, let c2, let p):
        path.curve(to: p, controlPoint1: c1, controlPoint2: c2)
        current = p
      case .close:
        path.close()
      }
    }

    return path
  }
}
