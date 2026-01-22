// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "VersionManager",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "VersionManager", targets: ["VersionManager"])
    ],
    targets: [
        .executableTarget(
            name: "VersionManager",
            path: "VersionManager"
        )
    ]
)
