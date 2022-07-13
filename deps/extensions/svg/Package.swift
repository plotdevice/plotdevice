// swift-tools-version:5.4

import PackageDescription

let package = Package(
    name: "SwiftDraw",
    platforms: [
         .macOS(.v10_12),
      ],
    targets: [
        .target(
            name: "SwiftDraw",
            dependencies: [],
      path: "SwiftDraw"
    )]
)
