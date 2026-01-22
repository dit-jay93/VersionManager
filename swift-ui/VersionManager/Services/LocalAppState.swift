import Foundation
import SwiftUI
import SwiftData

@MainActor
class LocalAppState: ObservableObject {
    // MARK: - Published Properties
    @Published var files: [TrackedFileModel] = []
    @Published var selectedFileId: String?
    @Published var selectedFilter: FilterCategory = .all
    @Published var searchText: String = ""
    @Published var sortOption: SortOption = .newestFirst

    @Published var projects: [ProjectModel] = []
    @Published var selectedProjectId: String? = nil

    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var statusMessage: String?

    @Published var showAddFileDialog: Bool = false
    @Published var showNewVersionDialog: Bool = false
    @Published var showNewProjectDialog: Bool = false

    // MARK: - Services
    private var modelContext: ModelContext?
    private var fileService: FileService?

    // MARK: - Computed Properties

    var filteredFiles: [TrackedFileModel] {
        var result = files

        // Apply project filter
        if let projectId = selectedProjectId {
            result = result.filter { $0.project?.id == projectId }
        }

        // Apply category filter
        switch selectedFilter {
        case .all:
            result = result.filter { !$0.isArchived }
        case .favorites:
            result = result.filter { $0.isFavorite && !$0.isArchived }
        case .recent:
            let cutoff = Date().addingTimeInterval(-7 * 24 * 60 * 60)
            result = result.filter { !$0.isArchived && $0.createdAt >= cutoff }
        case .modified:
            result = result.filter { ($0.status == .modified || $0.status == .missing) && !$0.isArchived }
        case .archived:
            result = result.filter { $0.isArchived }
        }

        // Apply search filter
        if !searchText.isEmpty {
            let query = searchText.lowercased()
            result = result.filter {
                $0.displayName.lowercased().contains(query) ||
                $0.filePath.lowercased().contains(query)
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
                let order: [TrackedFileStatus: Int] = [.modified: 0, .missing: 1, .ok: 2]
                return (order[$0.status] ?? 3) < (order[$1.status] ?? 3)
            }
        }

        return result
    }

    var selectedFile: TrackedFileModel? {
        guard let id = selectedFileId else { return nil }
        return files.first { $0.id == id }
    }

    // MARK: - Setup

    func setup(modelContext: ModelContext) {
        self.modelContext = modelContext
        self.fileService = FileService(modelContext: modelContext)
        loadData()
    }

    // MARK: - Data Loading

    func loadData() {
        guard let context = modelContext else { return }

        do {
            let fileDescriptor = FetchDescriptor<TrackedFileModel>(sortBy: [SortDescriptor(\.createdAt, order: .reverse)])
            files = try context.fetch(fileDescriptor)

            let projectDescriptor = FetchDescriptor<ProjectModel>(sortBy: [SortDescriptor(\.name)])
            projects = try context.fetch(projectDescriptor)
        } catch {
            errorMessage = "Failed to load data: \(error.localizedDescription)"
        }
    }

    // MARK: - File Operations

    func registerFile(path: String, commitMessage: String) {
        guard let service = fileService else { return }

        isLoading = true
        do {
            let file = try service.registerFile(at: path, commitMessage: commitMessage)
            files.insert(file, at: 0)
            selectedFileId = file.id
            statusMessage = "File added successfully"
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func deleteFile(_ id: String) {
        guard let file = files.first(where: { $0.id == id }),
              let service = fileService else { return }

        do {
            try service.deleteFile(file)
            files.removeAll { $0.id == id }
            if selectedFileId == id {
                selectedFileId = nil
            }
            statusMessage = "File removed"
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func verifyFile(_ id: String) {
        guard let file = files.first(where: { $0.id == id }),
              let service = fileService else { return }

        do {
            let status = try service.verifyFile(file)
            statusMessage = "Status: \(status.rawValue)"
            loadData() // Refresh
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func verifyAllFiles() {
        guard let service = fileService else { return }

        isLoading = true
        do {
            let results = try service.verifyAllFiles()
            let modified = results.values.filter { $0 == .modified }.count
            let missing = results.values.filter { $0 == .missing }.count

            if modified > 0 || missing > 0 {
                statusMessage = "\(modified) modified, \(missing) missing"
            } else {
                statusMessage = "All files OK"
            }
            loadData()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func openFile(_ id: String) {
        guard let file = files.first(where: { $0.id == id }),
              let service = fileService else { return }
        service.openFile(file)
    }

    func revealFile(_ id: String) {
        guard let file = files.first(where: { $0.id == id }),
              let service = fileService else { return }
        service.revealFile(file)
    }

    func toggleFavorite(_ id: String) {
        guard let file = files.first(where: { $0.id == id }) else { return }

        file.isFavorite.toggle()
        try? modelContext?.save()
        statusMessage = file.isFavorite ? "Added to favorites" : "Removed from favorites"
    }

    func archiveFile(_ id: String) {
        guard let file = files.first(where: { $0.id == id }) else { return }

        file.isArchived = true
        try? modelContext?.save()
        statusMessage = "File archived"
    }

    func unarchiveFile(_ id: String) {
        guard let file = files.first(where: { $0.id == id }) else { return }

        file.isArchived = false
        try? modelContext?.save()
        statusMessage = "File unarchived"
    }

    // MARK: - Version Operations

    func createVersion(commitMessage: String) {
        guard let file = selectedFile,
              let service = fileService else { return }

        do {
            let version = try service.createNewVersion(for: file, commitMessage: commitMessage)
            statusMessage = "Created version \(version.versionNumber)"
            loadData()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func restoreVersion(_ version: VersionModel) {
        guard let service = fileService else { return }

        do {
            try service.restoreVersion(version)
            statusMessage = "Restored to version \(version.versionNumber)"
            loadData()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func openVersion(_ version: VersionModel) {
        fileService?.openVersion(version)
    }

    func revealVersion(_ version: VersionModel) {
        fileService?.revealVersion(version)
    }

    func togglePin(_ version: VersionModel) {
        guard let service = fileService else { return }

        do {
            let (isPinned, _) = try service.togglePin(version)
            statusMessage = isPinned ? "Version pinned" : "Version unpinned"
            loadData()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    // MARK: - Tag Operations

    func addTag(_ tagName: String) {
        guard let file = selectedFile,
              let context = modelContext else { return }

        // Find or create tag
        let normalized = tagName.lowercased().replacingOccurrences(of: "#", with: "").trimmingCharacters(in: .whitespaces)
        let descriptor = FetchDescriptor<TagModel>(predicate: #Predicate { $0.name == normalized })

        let tag: TagModel
        if let existing = try? context.fetch(descriptor).first {
            tag = existing
        } else {
            tag = TagModel(name: tagName)
            context.insert(tag)
        }

        // Create link
        let link = TagLinkModel(tag: tag, file: file)
        context.insert(link)

        try? context.save()
        statusMessage = "Tag added"
    }

    func removeTag(_ tagLink: TagLinkModel) {
        modelContext?.delete(tagLink)
        try? modelContext?.save()
        statusMessage = "Tag removed"
    }

    // MARK: - Project Operations

    func createProject(name: String, description: String?, color: String) {
        guard let context = modelContext else { return }

        let project = ProjectModel(name: name, description: description, color: color)
        context.insert(project)

        do {
            try context.save()
            projects.append(project)
            statusMessage = "Project '\(name)' created"
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func deleteProject(_ id: String) {
        guard let project = projects.first(where: { $0.id == id }),
              let context = modelContext else { return }

        context.delete(project)

        do {
            try context.save()
            projects.removeAll { $0.id == id }
            if selectedProjectId == id {
                selectedProjectId = nil
            }
            statusMessage = "Project deleted"
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func setFileProject(_ fileId: String, projectId: String?) {
        guard let file = files.first(where: { $0.id == fileId }) else { return }

        if let projectId = projectId {
            file.project = projects.first { $0.id == projectId }
        } else {
            file.project = nil
        }

        try? modelContext?.save()
        loadData()
        statusMessage = projectId != nil ? "File moved to project" : "File removed from project"
    }

    func selectProject(_ projectId: String?) {
        selectedProjectId = projectId
    }

    // MARK: - Metadata

    func extractMetadata() {
        guard let file = selectedFile,
              let service = fileService else { return }

        _ = service.extractMetadata(for: file)
        statusMessage = "Metadata extracted"
    }
}
