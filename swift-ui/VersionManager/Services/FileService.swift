import Foundation
import SwiftData
import CryptoKit
import AppKit
import UniformTypeIdentifiers

// MARK: - File Service
@MainActor
class FileService: ObservableObject {
    private let modelContext: ModelContext
    private let versionsDirectory: URL
    private let pinnedDirectory: URL

    init(modelContext: ModelContext) {
        self.modelContext = modelContext

        // Setup directories in Application Support
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let appDir = appSupport.appendingPathComponent("VersionManager", isDirectory: true)

        self.versionsDirectory = appDir.appendingPathComponent("versions", isDirectory: true)
        self.pinnedDirectory = appDir.appendingPathComponent("pinned", isDirectory: true)

        // Create directories if needed
        try? FileManager.default.createDirectory(at: versionsDirectory, withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: pinnedDirectory, withIntermediateDirectories: true)
    }

    // MARK: - File Operations

    func registerFile(at path: String, commitMessage: String, displayName: String? = nil) throws -> TrackedFileModel {
        let url = URL(fileURLWithPath: path)
        let fileManager = FileManager.default

        guard fileManager.fileExists(atPath: path) else {
            throw FileServiceError.fileNotFound
        }

        // Check if already tracked
        let descriptor = FetchDescriptor<TrackedFileModel>(predicate: #Predicate { $0.filePath == path })
        if let existing = try? modelContext.fetch(descriptor).first {
            throw FileServiceError.alreadyTracked(existing)
        }

        // Get file attributes
        let attrs = try fileManager.attributesOfItem(atPath: path)
        let fileSize = attrs[.size] as? Int64 ?? 0
        let modifiedTime = attrs[.modificationDate] as? Date ?? Date()

        // Calculate hash
        let fileHash = try calculateHash(for: url)

        // Create tracked file
        let name = displayName ?? url.lastPathComponent
        let trackedFile = TrackedFileModel(
            displayName: name,
            filePath: path,
            fileSize: fileSize,
            modifiedTime: modifiedTime,
            fileHash: fileHash
        )

        modelContext.insert(trackedFile)

        // Create initial version
        let version = try createVersionBackup(for: trackedFile, commitMessage: commitMessage)
        version.file = trackedFile

        try modelContext.save()

        return trackedFile
    }

    func deleteFile(_ file: TrackedFileModel) throws {
        // Delete version backups
        for version in file.versions ?? [] {
            if let backupPath = version.backupPath {
                try? FileManager.default.removeItem(atPath: backupPath)
            }
            if let pinnedPath = version.pinnedPath {
                try? FileManager.default.removeItem(atPath: pinnedPath)
            }
        }

        modelContext.delete(file)
        try modelContext.save()
    }

    // MARK: - Version Operations

    func createNewVersion(for file: TrackedFileModel, commitMessage: String) throws -> VersionModel {
        let version = try createVersionBackup(for: file, commitMessage: commitMessage)
        version.file = file

        // Update file status
        file.status = .ok
        let url = URL(fileURLWithPath: file.filePath)
        if let hash = try? calculateHash(for: url) {
            file.fileHash = hash
        }

        try modelContext.save()
        return version
    }

    private func createVersionBackup(for file: TrackedFileModel, commitMessage: String) throws -> VersionModel {
        let url = URL(fileURLWithPath: file.filePath)
        let fileManager = FileManager.default

        guard fileManager.fileExists(atPath: file.filePath) else {
            throw FileServiceError.fileNotFound
        }

        // Get current file info
        let attrs = try fileManager.attributesOfItem(atPath: file.filePath)
        let fileSize = attrs[.size] as? Int64 ?? 0
        let modifiedTime = attrs[.modificationDate] as? Date ?? Date()
        let fileHash = try calculateHash(for: url)

        // Create version
        let versionNumber = file.nextVersionNumber
        let version = VersionModel(
            versionNumber: versionNumber,
            commitMessage: commitMessage,
            fileSize: fileSize,
            modifiedTime: modifiedTime,
            fileHash: fileHash
        )

        // Create backup
        let fileDir = versionsDirectory.appendingPathComponent(file.id, isDirectory: true)
        try fileManager.createDirectory(at: fileDir, withIntermediateDirectories: true)

        let ext = url.pathExtension
        let backupName = "v\(versionNumber).\(ext)"
        let backupURL = fileDir.appendingPathComponent(backupName)

        try fileManager.copyItem(at: url, to: backupURL)
        version.backupPath = backupURL.path

        modelContext.insert(version)
        return version
    }

    func restoreVersion(_ version: VersionModel) throws {
        guard let file = version.file,
              let backupPath = version.backupPath else {
            throw FileServiceError.versionNotFound
        }

        let fileManager = FileManager.default
        let backupURL = URL(fileURLWithPath: backupPath)
        let targetURL = URL(fileURLWithPath: file.filePath)

        guard fileManager.fileExists(atPath: backupPath) else {
            throw FileServiceError.backupNotFound
        }

        // Remove current file and copy backup
        try? fileManager.removeItem(at: targetURL)
        try fileManager.copyItem(at: backupURL, to: targetURL)

        // Update file status
        file.status = .ok
        file.fileHash = version.fileHash

        // Create restore event
        let event = FileEventModel(eventType: .restore, description: "Restored to v\(version.versionNumber)")
        event.file = file

        try modelContext.save()
    }

    func togglePin(_ version: VersionModel) throws -> (isPinned: Bool, pinnedPath: String?) {
        guard let file = version.file,
              let backupPath = version.backupPath else {
            throw FileServiceError.versionNotFound
        }

        let fileManager = FileManager.default

        if version.isPinned {
            // Unpin
            if let pinnedPath = version.pinnedPath {
                try? fileManager.removeItem(atPath: pinnedPath)
            }
            version.isPinned = false
            version.pinnedPath = nil

            let event = FileEventModel(eventType: .unpin, description: "v\(version.versionNumber) unpinned")
            event.file = file
        } else {
            // Pin
            let backupURL = URL(fileURLWithPath: backupPath)
            let ext = backupURL.pathExtension
            let pinnedName = "\(file.displayName)_v\(version.versionNumber).\(ext)"
            let pinnedURL = pinnedDirectory.appendingPathComponent(pinnedName)

            try? fileManager.removeItem(at: pinnedURL)
            try fileManager.copyItem(at: backupURL, to: pinnedURL)

            version.isPinned = true
            version.pinnedPath = pinnedURL.path

            let event = FileEventModel(eventType: .pin, description: "v\(version.versionNumber) pinned")
            event.file = file
        }

        try modelContext.save()
        return (version.isPinned, version.pinnedPath)
    }

    // MARK: - Verification

    func verifyFile(_ file: TrackedFileModel) throws -> TrackedFileStatus {
        let fileManager = FileManager.default

        guard fileManager.fileExists(atPath: file.filePath) else {
            file.status = .missing
            let event = FileEventModel(eventType: .verifyMissing)
            event.file = file
            try modelContext.save()
            return .missing
        }

        let url = URL(fileURLWithPath: file.filePath)
        let currentHash = try calculateHash(for: url)

        if currentHash == file.fileHash {
            file.status = .ok
            let event = FileEventModel(eventType: .verifyOk)
            event.file = file
        } else {
            file.status = .modified
            let event = FileEventModel(eventType: .verifyModified)
            event.file = file
        }

        try modelContext.save()
        return file.status
    }

    func verifyAllFiles() throws -> [String: TrackedFileStatus] {
        let descriptor = FetchDescriptor<TrackedFileModel>()
        let files = try modelContext.fetch(descriptor)

        var results: [String: TrackedFileStatus] = [:]
        for file in files {
            results[file.id] = try verifyFile(file)
        }
        return results
    }

    // MARK: - Hash Calculation

    func calculateHash(for url: URL) throws -> String {
        let data = try Data(contentsOf: url)
        let hash = SHA256.hash(data: data)
        return hash.compactMap { String(format: "%02x", $0) }.joined()
    }

    // MARK: - Metadata Extraction

    func extractMetadata(for file: TrackedFileModel) -> [String: Any] {
        let url = URL(fileURLWithPath: file.filePath)
        var metadata: [String: Any] = [:]

        guard let uti = UTType(filenameExtension: url.pathExtension) else {
            return metadata
        }

        if uti.conforms(to: .image) {
            metadata = extractImageMetadata(from: url)
        } else if uti.conforms(to: .movie) || uti.conforms(to: .video) {
            metadata = extractVideoMetadata(from: url)
        }

        file.metadata = metadata
        try? modelContext.save()

        return metadata
    }

    private func extractImageMetadata(from url: URL) -> [String: Any] {
        var metadata: [String: Any] = [:]

        guard let imageSource = CGImageSourceCreateWithURL(url as CFURL, nil),
              let properties = CGImageSourceCopyPropertiesAtIndex(imageSource, 0, nil) as? [String: Any] else {
            return metadata
        }

        if let width = properties[kCGImagePropertyPixelWidth as String] as? Int,
           let height = properties[kCGImagePropertyPixelHeight as String] as? Int {
            metadata["width"] = width
            metadata["height"] = height
        }

        if let exif = properties[kCGImagePropertyExifDictionary as String] as? [String: Any] {
            if let dateString = exif[kCGImagePropertyExifDateTimeOriginal as String] as? String {
                metadata["dateTaken"] = dateString
            }
        }

        return metadata
    }

    private func extractVideoMetadata(from url: URL) -> [String: Any] {
        var metadata: [String: Any] = [:]

        // Use AVFoundation for video metadata
        // Note: Need to import AVFoundation and add async handling
        // For now, return basic file info
        metadata["type"] = "video"

        return metadata
    }

    // MARK: - File Actions

    func openFile(_ file: TrackedFileModel) {
        let url = URL(fileURLWithPath: file.filePath)
        NSWorkspace.shared.open(url)
    }

    func revealFile(_ file: TrackedFileModel) {
        let url = URL(fileURLWithPath: file.filePath)
        NSWorkspace.shared.selectFile(url.path, inFileViewerRootedAtPath: "")
    }

    func openVersion(_ version: VersionModel) {
        guard let backupPath = version.backupPath else { return }
        let url = URL(fileURLWithPath: backupPath)
        NSWorkspace.shared.open(url)
    }

    func revealVersion(_ version: VersionModel) {
        guard let backupPath = version.backupPath else { return }
        NSWorkspace.shared.selectFile(backupPath, inFileViewerRootedAtPath: "")
    }
}

// MARK: - Errors

enum FileServiceError: LocalizedError {
    case fileNotFound
    case alreadyTracked(TrackedFileModel)
    case versionNotFound
    case backupNotFound
    case hashMismatch

    var errorDescription: String? {
        switch self {
        case .fileNotFound:
            return "File not found"
        case .alreadyTracked(let file):
            return "File '\(file.displayName)' is already tracked"
        case .versionNotFound:
            return "Version not found"
        case .backupNotFound:
            return "Version backup file not found"
        case .hashMismatch:
            return "File hash does not match"
        }
    }
}
