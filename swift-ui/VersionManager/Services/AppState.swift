import Foundation
import SwiftUI

@MainActor
class AppState: ObservableObject {
    // MARK: - Published Properties
    @Published var files: [TrackedFile] = []
    @Published var selectedFileId: String?
    @Published var selectedFilter: FilterCategory = .all
    @Published var searchText: String = ""
    @Published var sortOption: SortOption = .newestFirst

    @Published var projects: [Project] = []
    @Published var selectedProjectId: String? = nil  // nil means "All Projects"

    @Published var versions: [Version] = []
    @Published var tags: [Tag] = []
    @Published var events: [FileEvent] = []
    @Published var metadata: [String: Any]? = nil

    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var statusMessage: String?

    @Published var showAddFileDialog: Bool = false
    @Published var showNewVersionDialog: Bool = false
    @Published var showRenameDialog: Bool = false
    @Published var showDeleteConfirmation: Bool = false
    @Published var showNewProjectDialog: Bool = false

    // MARK: - Computed Properties

    var filteredFiles: [TrackedFile] {
        var result = files

        // Apply project filter first
        if let projectId = selectedProjectId {
            result = result.filter { $0.projectId == projectId }
        }

        // Apply category filter
        switch selectedFilter {
        case .all:
            result = result.filter { !$0.isArchived }
        case .favorites:
            result = result.filter { $0.isFavorite && !$0.isArchived }
        case .recent:
            let cutoff = Date().addingTimeInterval(-7 * 24 * 60 * 60)
            result = result.filter { file in
                if file.isArchived { return false }
                if let date = ISO8601DateFormatter().date(from: file.createdAt) {
                    return date >= cutoff
                }
                return false
            }
        case .modified:
            result = result.filter { ($0.status == .modified || $0.status == .missing) && !$0.isArchived }
        case .archived:
            result = result.filter { $0.isArchived }
        }

        // Apply search filter
        if !searchText.isEmpty {
            let query = searchText.lowercased()
            result = result.filter { file in
                file.displayName.lowercased().contains(query) ||
                file.filePath.lowercased().contains(query)
            }
        }

        // Apply sorting
        switch sortOption {
        case .nameAsc:
            result.sort { $0.displayName.lowercased() < $1.displayName.lowercased() }
        case .nameDesc:
            result.sort { $0.displayName.lowercased() > $1.displayName.lowercased() }
        case .newestFirst:
            result.sort { $0.createdAt > $1.createdAt }
        case .oldestFirst:
            result.sort { $0.createdAt < $1.createdAt }
        case .status:
            result.sort {
                let order: [FileStatus: Int] = [.modified: 0, .missing: 1, .ok: 2]
                return (order[$0.status] ?? 3) < (order[$1.status] ?? 3)
            }
        }

        return result
    }

    var selectedFile: TrackedFile? {
        guard let id = selectedFileId else { return nil }
        return files.first { $0.id == id }
    }

    // MARK: - File Operations

    func loadFiles() async {
        isLoading = true
        errorMessage = nil

        do {
            async let filesTask = APIService.shared.getFiles(includeArchived: true)
            async let projectsTask = APIService.shared.getProjects()

            files = try await filesTask
            projects = try await projectsTask
        } catch {
            errorMessage = "Failed to load files: \(error.localizedDescription)"
        }

        isLoading = false
    }

    // MARK: - Project Operations

    func loadProjects() async {
        do {
            projects = try await APIService.shared.getProjects()
        } catch {
            errorMessage = "Failed to load projects: \(error.localizedDescription)"
        }
    }

    func createProject(name: String, description: String?, color: String) async {
        do {
            let project = try await APIService.shared.createProject(name: name, description: description, color: color)
            projects.append(project)
            statusMessage = "Project '\(name)' created"
        } catch {
            errorMessage = "Failed to create project: \(error.localizedDescription)"
        }
    }

    func updateProject(_ id: String, name: String?, description: String?, color: String?) async {
        do {
            let updated = try await APIService.shared.updateProject(id: id, name: name, description: description, color: color)
            if let index = projects.firstIndex(where: { $0.id == id }) {
                projects[index] = updated
            }
            statusMessage = "Project updated"
        } catch {
            errorMessage = "Failed to update project: \(error.localizedDescription)"
        }
    }

    func deleteProject(_ id: String) async {
        do {
            try await APIService.shared.deleteProject(id: id)
            projects.removeAll { $0.id == id }
            if selectedProjectId == id {
                selectedProjectId = nil
            }
            statusMessage = "Project deleted"
            // Reload files to update their project_id
            await loadFiles()
        } catch {
            errorMessage = "Failed to delete project: \(error.localizedDescription)"
        }
    }

    func setFileProject(_ fileId: String, projectId: String?) async {
        do {
            try await APIService.shared.setFileProject(fileId: fileId, projectId: projectId)
            if let index = files.firstIndex(where: { $0.id == fileId }) {
                files[index].projectId = projectId
            }
            // Update project file counts
            await loadProjects()
            statusMessage = projectId != nil ? "File moved to project" : "File removed from project"
        } catch {
            errorMessage = "Failed to update file project: \(error.localizedDescription)"
        }
    }

    func selectProject(_ projectId: String?) {
        selectedProjectId = projectId
    }

    func selectFile(_ id: String?) async {
        selectedFileId = id

        guard let fileId = id else {
            versions = []
            tags = []
            events = []
            metadata = nil
            return
        }

        do {
            async let versionsTask = APIService.shared.getVersions(fileId: fileId)
            async let tagsTask = APIService.shared.getTags(fileId: fileId)
            async let eventsTask = APIService.shared.getEvents(fileId: fileId)
            async let metadataTask = APIService.shared.getMetadata(fileId: fileId)

            versions = try await versionsTask
            tags = try await tagsTask
            events = try await eventsTask
            metadata = try? await metadataTask
        } catch {
            errorMessage = "Failed to load file details: \(error.localizedDescription)"
        }
    }

    func registerFile(path: String, commitMessage: String) async {
        isLoading = true

        do {
            let newFile = try await APIService.shared.registerFile(path: path, commitMessage: commitMessage)
            files.insert(newFile, at: 0)
            await selectFile(newFile.id)
            statusMessage = "File added successfully"
        } catch {
            errorMessage = "Failed to add file: \(error.localizedDescription)"
        }

        isLoading = false
    }

    func deleteFile(_ id: String) async {
        do {
            try await APIService.shared.deleteFile(id: id)
            files.removeAll { $0.id == id }
            if selectedFileId == id {
                await selectFile(nil)
            }
            statusMessage = "File removed"
        } catch {
            errorMessage = "Failed to delete file: \(error.localizedDescription)"
        }
    }

    func archiveFile(_ id: String) async {
        do {
            try await APIService.shared.setArchived(id: id, archived: true)
            if let index = files.firstIndex(where: { $0.id == id }) {
                files[index].isArchived = true
            }
            statusMessage = "File archived"
        } catch {
            errorMessage = "Failed to archive file: \(error.localizedDescription)"
        }
    }

    func unarchiveFile(_ id: String) async {
        do {
            try await APIService.shared.setArchived(id: id, archived: false)
            if let index = files.firstIndex(where: { $0.id == id }) {
                files[index].isArchived = false
            }
            statusMessage = "File unarchived"
        } catch {
            errorMessage = "Failed to unarchive file: \(error.localizedDescription)"
        }
    }

    func verifyFile(_ id: String) async {
        do {
            let updatedFile = try await APIService.shared.verifyFile(id: id)
            if let index = files.firstIndex(where: { $0.id == id }) {
                files[index] = updatedFile
            }
            // Refresh events
            events = try await APIService.shared.getEvents(fileId: id)
            statusMessage = "Status: \(updatedFile.status.displayName)"
        } catch {
            errorMessage = "Failed to verify file: \(error.localizedDescription)"
        }
    }

    func verifyAllFiles() async {
        isLoading = true

        do {
            let result = try await APIService.shared.verifyAllFiles()
            await loadFiles()

            if result.modified > 0 || result.missing > 0 {
                statusMessage = "\(result.modified) modified, \(result.missing) missing"
            } else {
                statusMessage = "All files OK"
            }
        } catch {
            errorMessage = "Failed to verify files: \(error.localizedDescription)"
        }

        isLoading = false
    }

    func openFile(_ id: String) async {
        do {
            try await APIService.shared.openFile(id: id)
        } catch {
            errorMessage = "Failed to open file: \(error.localizedDescription)"
        }
    }

    func revealFile(_ id: String) async {
        do {
            try await APIService.shared.revealFile(id: id)
        } catch {
            errorMessage = "Failed to reveal file: \(error.localizedDescription)"
        }
    }

    func toggleFavorite(_ id: String) async {
        do {
            let isFavorite = try await APIService.shared.toggleFavorite(id: id)
            if let index = files.firstIndex(where: { $0.id == id }) {
                files[index].isFavorite = isFavorite
            }
            statusMessage = isFavorite ? "Added to favorites" : "Removed from favorites"
        } catch {
            errorMessage = "Failed to update favorite: \(error.localizedDescription)"
        }
    }

    func renameFile(_ id: String, newName: String) async {
        do {
            try await APIService.shared.updateName(id: id, name: newName)
            if let index = files.firstIndex(where: { $0.id == id }) {
                files[index].displayName = newName
            }
            statusMessage = "Renamed to '\(newName)'"
        } catch {
            errorMessage = "Failed to rename file: \(error.localizedDescription)"
        }
    }

    // MARK: - Version Operations

    func createVersion(commitMessage: String) async {
        guard let fileId = selectedFileId else { return }

        do {
            let newVersion = try await APIService.shared.createVersion(fileId: fileId, commitMessage: commitMessage)
            versions.insert(newVersion, at: 0)

            // Refresh file status
            let updatedFile = try await APIService.shared.getFile(id: fileId)
            if let index = files.firstIndex(where: { $0.id == fileId }) {
                files[index] = updatedFile
            }

            statusMessage = "Created version \(newVersion.versionNumber)"
        } catch {
            errorMessage = "Failed to create version: \(error.localizedDescription)"
        }
    }

    func restoreVersion(_ versionNumber: Int) async {
        guard let fileId = selectedFileId else { return }

        do {
            try await APIService.shared.restoreVersion(fileId: fileId, versionNumber: versionNumber)

            // Refresh file and events
            let updatedFile = try await APIService.shared.getFile(id: fileId)
            if let index = files.firstIndex(where: { $0.id == fileId }) {
                files[index] = updatedFile
            }
            events = try await APIService.shared.getEvents(fileId: fileId)

            statusMessage = "Restored to version \(versionNumber)"
        } catch {
            errorMessage = "Failed to restore version: \(error.localizedDescription)"
        }
    }

    func openVersion(_ versionNumber: Int) async {
        guard let fileId = selectedFileId else { return }

        do {
            try await APIService.shared.openVersion(fileId: fileId, versionNumber: versionNumber)
        } catch {
            errorMessage = "Failed to open version: \(error.localizedDescription)"
        }
    }

    func revealVersion(_ versionNumber: Int) async {
        guard let fileId = selectedFileId else { return }

        do {
            try await APIService.shared.revealVersion(fileId: fileId, versionNumber: versionNumber)
        } catch {
            errorMessage = "Failed to reveal version: \(error.localizedDescription)"
        }
    }

    func verifyVersion(_ versionNumber: Int) async -> VerificationResult? {
        guard let fileId = selectedFileId else { return nil }

        do {
            return try await APIService.shared.verifyVersion(fileId: fileId, versionNumber: versionNumber)
        } catch {
            errorMessage = "Failed to verify version: \(error.localizedDescription)"
            return nil
        }
    }

    func togglePin(_ versionNumber: Int) async {
        guard let fileId = selectedFileId else { return }

        do {
            let result = try await APIService.shared.togglePin(fileId: fileId, versionNumber: versionNumber)

            // Update local version state
            if let index = versions.firstIndex(where: { $0.versionNumber == versionNumber }) {
                versions[index].isPinned = result.isPinned
                versions[index].pinnedPath = result.pinnedPath
            }

            // Refresh events
            events = try await APIService.shared.getEvents(fileId: fileId)

            statusMessage = result.isPinned ? "Version pinned" : "Version unpinned"
        } catch {
            errorMessage = "Failed to toggle pin: \(error.localizedDescription)"
        }
    }

    func revealPinnedVersion(_ versionNumber: Int) async {
        guard let fileId = selectedFileId else { return }

        do {
            try await APIService.shared.revealPinnedVersion(fileId: fileId, versionNumber: versionNumber)
        } catch {
            errorMessage = "Failed to reveal pinned version: \(error.localizedDescription)"
        }
    }

    // MARK: - Tag Operations

    func addTag(_ tagName: String) async {
        guard let fileId = selectedFileId else { return }

        do {
            let newTag = try await APIService.shared.addTag(fileId: fileId, tagName: tagName)
            tags.append(newTag)
            statusMessage = "Tag added"
        } catch {
            errorMessage = "Failed to add tag: \(error.localizedDescription)"
        }
    }

    func removeTag(_ tagId: String) async {
        guard let fileId = selectedFileId else { return }

        do {
            try await APIService.shared.removeTag(fileId: fileId, tagId: tagId)
            tags.removeAll { $0.id == tagId }
            statusMessage = "Tag removed"
        } catch {
            errorMessage = "Failed to remove tag: \(error.localizedDescription)"
        }
    }

    // MARK: - Metadata Operations

    func extractMetadata() async {
        guard let fileId = selectedFileId else { return }

        do {
            metadata = try await APIService.shared.extractMetadata(fileId: fileId)
            statusMessage = "Metadata extracted"
        } catch {
            errorMessage = "Failed to extract metadata: \(error.localizedDescription)"
        }
    }
}

// MARK: - Sort Option

enum SortOption: String, CaseIterable {
    case nameAsc = "Name (A-Z)"
    case nameDesc = "Name (Z-A)"
    case newestFirst = "Newest First"
    case oldestFirst = "Oldest First"
    case status = "Status"
}
