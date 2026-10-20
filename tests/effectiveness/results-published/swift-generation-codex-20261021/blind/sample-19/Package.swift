// swift-tools-version: 6.0
import PackageDescription
let package = Package(name: "CedarStore", products: [.library(name: "CedarStore", targets: ["CedarStore"])], targets: [
    .target(name: "CedarStore"),
    .testTarget(name: "CedarStoreTests", dependencies: ["CedarStore"])
])
