import Foundation
import SwiftUI

// MARK: - Project
struct Project: Identifiable, Codable, Equatable {
    let id: String
    var name: String
    var description: String?
    var color: String
    let createdAt: String
    var fileCount: Int

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case description
        case color
        case createdAt = "created_at"
        case fileCount = "file_count"
    }

    var swiftUIColor: Color {
        Color(hex: color) ?? .blue
    }
}

extension Color {
    init?(hex: String) {
        var hexSanitized = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        hexSanitized = hexSanitized.replacingOccurrences(of: "#", with: "")

        var rgb: UInt64 = 0
        guard Scanner(string: hexSanitized).scanHexInt64(&rgb) else { return nil }

        let r = Double((rgb & 0xFF0000) >> 16) / 255.0
        let g = Double((rgb & 0x00FF00) >> 8) / 255.0
        let b = Double(rgb & 0x0000FF) / 255.0

        self.init(red: r, green: g, blue: b)
    }
}

// MARK: - File Status
enum FileStatus: String, Codable, CaseIterable {
    case ok = "OK"
    case modified = "MODIFIED"
    case missing = "MISSING"

    var displayName: String {
        switch self {
        case .ok: return "OK"
        case .modified: return "Modified"
        case .missing: return "Missing"
        }
    }

    var icon: String {
        switch self {
        case .ok: return "●"
        case .modified: return "◐"
        case .missing: return "○"
        }
    }

    var color: String {
        switch self {
        case .ok: return "green"
        case .modified: return "orange"
        case .missing: return "red"
        }
    }
}

// MARK: - Tracked File
struct TrackedFile: Identifiable, Codable, Equatable {
    let id: String
    var displayName: String
    let filePath: String
    let fileSize: Int
    let modifiedTime: Double
    var status: FileStatus
    let createdAt: String
    var fileHash: String?
    var isFavorite: Bool
    var isArchived: Bool
    var projectId: String?

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case filePath = "file_path"
        case fileSize = "file_size"
        case modifiedTime = "modified_time"
        case status
        case createdAt = "created_at"
        case fileHash = "file_hash"
        case isFavorite = "is_favorite"
        case isArchived = "is_archived"
        case projectId = "project_id"
    }

    var formattedSize: String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(fileSize))
    }

    var formattedDate: String {
        if let date = ISO8601DateFormatter().date(from: createdAt) {
            let formatter = DateFormatter()
            formatter.dateStyle = .medium
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
        return createdAt
    }
}

// MARK: - Version
struct Version: Identifiable, Codable, Equatable {
    let id: String
    let fileId: String
    let versionNumber: Int
    let commitMessage: String
    let fileSize: Int
    let modifiedTime: Double
    let createdAt: String
    var fileHash: String?
    var isPinned: Bool
    var pinnedPath: String?

    enum CodingKeys: String, CodingKey {
        case id
        case fileId = "file_id"
        case versionNumber = "version_number"
        case commitMessage = "commit_message"
        case fileSize = "file_size"
        case modifiedTime = "modified_time"
        case createdAt = "created_at"
        case fileHash = "file_hash"
        case isPinned = "is_pinned"
        case pinnedPath = "pinned_path"
    }

    var formattedSize: String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(fileSize))
    }

    var formattedDate: String {
        if let date = ISO8601DateFormatter().date(from: createdAt) {
            let formatter = DateFormatter()
            formatter.dateStyle = .medium
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
        return createdAt
    }
}

// MARK: - Tag
struct Tag: Identifiable, Codable, Equatable {
    let id: String
    let name: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case createdAt = "created_at"
    }

    var displayName: String {
        "#\(name)"
    }
}

// MARK: - Event
struct FileEvent: Identifiable, Codable, Equatable {
    let id: String
    let fileId: String
    let eventType: String
    let description: String?
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case fileId = "file_id"
        case eventType = "event_type"
        case description
        case createdAt = "created_at"
    }

    var icon: String {
        switch eventType {
        case "RESTORE": return "↩"
        case "PIN": return "📌"
        case "UNPIN": return "📍"
        case "DELETE": return "🗑"
        case "VERIFY_OK": return "✓"
        case "VERIFY_MODIFIED": return "⚠"
        case "VERIFY_MISSING": return "✗"
        default: return "•"
        }
    }

    var displayName: String {
        switch eventType {
        case "RESTORE": return "Restored"
        case "PIN": return "Pinned"
        case "UNPIN": return "Unpinned"
        case "DELETE": return "Deleted"
        case "VERIFY_OK": return "Verified OK"
        case "VERIFY_MODIFIED": return "Modified Detected"
        case "VERIFY_MISSING": return "Missing Detected"
        default: return eventType
        }
    }

    var formattedDate: String {
        if let date = ISO8601DateFormatter().date(from: createdAt) {
            let formatter = DateFormatter()
            formatter.dateStyle = .short
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
        return createdAt
    }
}

// MARK: - Filter Category
enum FilterCategory: String, CaseIterable {
    case all = "All Files"
    case favorites = "Favorites"
    case recent = "Recent"
    case modified = "Modified"
    case archived = "Archived"

    var icon: String {
        switch self {
        case .all: return "folder"
        case .favorites: return "star.fill"
        case .recent: return "clock"
        case .modified: return "exclamationmark.triangle"
        case .archived: return "archivebox"
        }
    }
}

// MARK: - API Responses
struct VerificationResult: Codable {
    let isValid: Bool
    let message: String

    enum CodingKeys: String, CodingKey {
        case isValid = "is_valid"
        case message
    }
}

struct VerifyAllResponse: Codable {
    let total: Int
    let ok: Int
    let modified: Int
    let missing: Int
}

struct PinResponse: Codable {
    let isPinned: Bool
    let pinnedPath: String?

    enum CodingKeys: String, CodingKey {
        case isPinned = "is_pinned"
        case pinnedPath = "pinned_path"
    }
}
