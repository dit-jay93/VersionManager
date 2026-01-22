import Foundation
import SwiftData

// MARK: - Project Model
@Model
final class ProjectModel {
    @Attribute(.unique) var id: String
    var name: String
    var projectDescription: String?
    var color: String
    var createdAt: Date

    @Relationship(deleteRule: .nullify, inverse: \TrackedFileModel.project)
    var files: [TrackedFileModel]?

    init(name: String, description: String? = nil, color: String = "#007AFF") {
        self.id = UUID().uuidString
        self.name = name
        self.projectDescription = description
        self.color = color
        self.createdAt = Date()
    }

    var fileCount: Int {
        files?.count ?? 0
    }
}

// MARK: - File Status
enum TrackedFileStatus: String, Codable {
    case ok = "OK"
    case modified = "MODIFIED"
    case missing = "MISSING"
}

// MARK: - Tracked File Model
@Model
final class TrackedFileModel {
    @Attribute(.unique) var id: String
    var displayName: String
    var filePath: String
    var fileSize: Int64
    var modifiedTime: Date
    var status: TrackedFileStatus
    var createdAt: Date
    var fileHash: String?
    var isFavorite: Bool
    var isArchived: Bool

    var project: ProjectModel?

    @Relationship(deleteRule: .cascade, inverse: \VersionModel.file)
    var versions: [VersionModel]?

    @Relationship(deleteRule: .cascade, inverse: \TagLinkModel.file)
    var tagLinks: [TagLinkModel]?

    @Relationship(deleteRule: .cascade, inverse: \FileEventModel.file)
    var events: [FileEventModel]?

    var metadataJSON: String?

    init(displayName: String, filePath: String, fileSize: Int64, modifiedTime: Date, fileHash: String? = nil) {
        self.id = UUID().uuidString
        self.displayName = displayName
        self.filePath = filePath
        self.fileSize = fileSize
        self.modifiedTime = modifiedTime
        self.status = .ok
        self.createdAt = Date()
        self.fileHash = fileHash
        self.isFavorite = false
        self.isArchived = false
    }

    var metadata: [String: Any]? {
        get {
            guard let json = metadataJSON,
                  let data = json.data(using: .utf8),
                  let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                return nil
            }
            return dict
        }
        set {
            if let value = newValue,
               let data = try? JSONSerialization.data(withJSONObject: value),
               let json = String(data: data, encoding: .utf8) {
                metadataJSON = json
            } else {
                metadataJSON = nil
            }
        }
    }

    var sortedVersions: [VersionModel] {
        (versions ?? []).sorted { $0.versionNumber > $1.versionNumber }
    }

    var latestVersion: VersionModel? {
        sortedVersions.first
    }

    var nextVersionNumber: Int {
        (versions?.map { $0.versionNumber }.max() ?? 0) + 1
    }
}

// MARK: - Version Model
@Model
final class VersionModel {
    @Attribute(.unique) var id: String
    var versionNumber: Int
    var commitMessage: String
    var fileSize: Int64
    var modifiedTime: Date
    var createdAt: Date
    var fileHash: String?
    var isPinned: Bool
    var pinnedPath: String?
    var backupPath: String?

    var file: TrackedFileModel?

    init(versionNumber: Int, commitMessage: String, fileSize: Int64, modifiedTime: Date, fileHash: String? = nil, backupPath: String? = nil) {
        self.id = UUID().uuidString
        self.versionNumber = versionNumber
        self.commitMessage = commitMessage
        self.fileSize = fileSize
        self.modifiedTime = modifiedTime
        self.createdAt = Date()
        self.fileHash = fileHash
        self.isPinned = false
        self.backupPath = backupPath
    }
}

// MARK: - Tag Model
@Model
final class TagModel {
    @Attribute(.unique) var id: String
    @Attribute(.unique) var name: String
    var createdAt: Date

    @Relationship(deleteRule: .cascade, inverse: \TagLinkModel.tag)
    var tagLinks: [TagLinkModel]?

    init(name: String) {
        self.id = UUID().uuidString
        self.name = name.lowercased().replacingOccurrences(of: "#", with: "").trimmingCharacters(in: .whitespaces)
        self.createdAt = Date()
    }
}

// MARK: - Tag Link Model (Many-to-Many)
@Model
final class TagLinkModel {
    @Attribute(.unique) var id: String
    var createdAt: Date

    var tag: TagModel?
    var file: TrackedFileModel?

    init(tag: TagModel, file: TrackedFileModel) {
        self.id = UUID().uuidString
        self.createdAt = Date()
        self.tag = tag
        self.file = file
    }
}

// MARK: - Event Type
enum FileEventType: String, Codable {
    case restore = "RESTORE"
    case pin = "PIN"
    case unpin = "UNPIN"
    case delete = "DELETE"
    case verifyOk = "VERIFY_OK"
    case verifyModified = "VERIFY_MODIFIED"
    case verifyMissing = "VERIFY_MISSING"
    case relink = "RELINK"
}

// MARK: - File Event Model
@Model
final class FileEventModel {
    @Attribute(.unique) var id: String
    var eventType: FileEventType
    var eventDescription: String?
    var createdAt: Date

    var file: TrackedFileModel?

    init(eventType: FileEventType, description: String? = nil) {
        self.id = UUID().uuidString
        self.eventType = eventType
        self.eventDescription = description
        self.createdAt = Date()
    }
}
