import SwiftUI
import UniformTypeIdentifiers

struct FileListView: View {
    @EnvironmentObject var appState: AppState
    @State private var isTargeted = false
    var isCompact: Bool = false

    var body: some View {
        VStack(spacing: 0) {
            // Search and Sort Bar
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)
                TextField(isCompact ? "Search..." : "Search name, path...", text: $appState.searchText)
                    .textFieldStyle(.plain)

                if !isCompact {
                    Divider()
                        .frame(height: 16)

                    Picker("Sort", selection: $appState.sortOption) {
                        ForEach(SortOption.allCases, id: \.self) { option in
                            Text(option.rawValue).tag(option)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(width: 130)
                }
            }
            .padding(.horizontal, isCompact ? 8 : 12)
            .padding(.vertical, isCompact ? 6 : 8)
            .background(Color(nsColor: .controlBackgroundColor))

            Divider()

            // File List
            if appState.filteredFiles.isEmpty {
                emptyStateView
            } else {
                List(appState.filteredFiles, selection: $appState.selectedFileId) { file in
                    FileRowView(file: file)
                        .tag(file.id)
                        .contextMenu {
                            fileContextMenu(for: file)
                        }
                }
                .listStyle(.plain)
                .onChange(of: appState.selectedFileId) { oldValue, newValue in
                    Task {
                        await appState.selectFile(newValue)
                    }
                }
            }

            Divider()

            // Status Bar
            HStack {
                Text(statusText)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()

                if isCompact {
                    // 컴팩트 모드: 정렬 메뉴 여기로
                    Menu {
                        ForEach(SortOption.allCases, id: \.self) { option in
                            Button(option.rawValue) {
                                appState.sortOption = option
                            }
                        }
                    } label: {
                        Image(systemName: "arrow.up.arrow.down")
                    }
                    .menuStyle(.borderlessButton)
                }

                Button {
                    appState.showAddFileDialog = true
                } label: {
                    Image(systemName: "plus")
                }
                .buttonStyle(.plain)
                .help("Add File")
            }
            .padding(.horizontal, isCompact ? 8 : 12)
            .padding(.vertical, isCompact ? 4 : 6)
            .background(Color(nsColor: .controlBackgroundColor))
        }
        .navigationTitle(isCompact ? "" : "Files")
        .onDrop(of: [UTType.fileURL], isTargeted: $isTargeted) { providers in
            handleDrop(providers: providers)
        }
        .overlay {
            if isTargeted {
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.accentColor, lineWidth: 2)
                    .background(Color.accentColor.opacity(0.1))
            }
        }
    }

    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "doc.badge.plus")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
            Text("No Files")
                .font(.headline)
            Text("Drag files here or click + to add")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var statusText: String {
        let filtered = appState.filteredFiles.count
        let total = appState.files.count
        if filtered == total {
            return "\(total) file\(total == 1 ? "" : "s")"
        } else {
            return "\(filtered) of \(total) files"
        }
    }

    @ViewBuilder
    private func fileContextMenu(for file: TrackedFile) -> some View {
        Button("Open") {
            Task { await appState.openFile(file.id) }
        }
        Button("Show in Finder") {
            Task { await appState.revealFile(file.id) }
        }

        Divider()

        Button("Verify") {
            Task { await appState.verifyFile(file.id) }
        }

        if file.status == .modified {
            Button("New Version...") {
                appState.selectedFileId = file.id
                appState.showNewVersionDialog = true
            }
        }

        Divider()

        Button(file.isFavorite ? "Remove from Favorites" : "Add to Favorites") {
            Task { await appState.toggleFavorite(file.id) }
        }

        Divider()

        // Move to Project
        Menu("Move to Project") {
            Button("No Project") {
                Task { await appState.setFileProject(file.id, projectId: nil) }
            }
            Divider()
            ForEach(appState.projects) { project in
                Button {
                    Task { await appState.setFileProject(file.id, projectId: project.id) }
                } label: {
                    HStack {
                        Circle()
                            .fill(project.swiftUIColor)
                            .frame(width: 8, height: 8)
                        Text(project.name)
                    }
                }
            }
        }

        Divider()

        if file.isArchived {
            Button("Unarchive") {
                Task { await appState.unarchiveFile(file.id) }
            }
        } else {
            Button("Archive") {
                Task { await appState.archiveFile(file.id) }
            }
            Button("Remove", role: .destructive) {
                Task { await appState.deleteFile(file.id) }
            }
        }
    }

    private func handleDrop(providers: [NSItemProvider]) -> Bool {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, error in
                guard let data = item as? Data,
                      let url = URL(dataRepresentation: data, relativeTo: nil) else { return }

                DispatchQueue.main.async {
                    // For simplicity, auto-generate commit message
                    Task {
                        await appState.registerFile(path: url.path, commitMessage: "Initial version")
                    }
                }
            }
        }
        return true
    }
}

struct FileRowView: View {
    let file: TrackedFile

    var body: some View {
        HStack(spacing: 8) {
            // File type icon
            Image(systemName: fileTypeIcon)
                .foregroundColor(fileTypeColor)
                .font(.system(size: 16))
                .frame(width: 20)

            // File info
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Text(file.displayName)
                        .lineLimit(1)

                    // Status indicator
                    Circle()
                        .fill(statusColor)
                        .frame(width: 8, height: 8)

                    // Favorite indicator
                    if file.isFavorite {
                        Image(systemName: "star.fill")
                            .foregroundColor(.yellow)
                            .font(.system(size: 10))
                    }
                }

                HStack {
                    Text(file.formattedSize)
                    Text("•")
                    Text(fileExtension.uppercased())
                }
                .font(.caption)
                .foregroundColor(.secondary)
            }

            Spacer()

            // Archive indicator
            if file.isArchived {
                Image(systemName: "archivebox")
                    .foregroundColor(.secondary)
                    .font(.caption)
            }
        }
        .padding(.vertical, 4)
    }

    private var fileExtension: String {
        let ext = (file.filePath as NSString).pathExtension.lowercased()
        return ext.isEmpty ? "file" : ext
    }

    private var fileTypeIcon: String {
        let ext = fileExtension
        switch ext {
        case "mp4", "mov", "avi", "mkv", "webm", "m4v":
            return "film"
        case "mp3", "wav", "aac", "flac", "m4a", "ogg":
            return "waveform"
        case "jpg", "jpeg", "png", "gif", "webp", "tiff", "heic", "bmp":
            return "photo"
        case "pdf":
            return "doc.richtext"
        case "doc", "docx", "txt", "rtf", "md":
            return "doc.text"
        case "xls", "xlsx", "csv":
            return "tablecells"
        case "ppt", "pptx", "key":
            return "slider.horizontal.below.rectangle"
        case "zip", "rar", "7z", "tar", "gz":
            return "archivebox"
        case "psd", "ai", "sketch", "fig":
            return "paintbrush"
        case "swift", "py", "js", "ts", "html", "css", "json":
            return "chevron.left.forwardslash.chevron.right"
        default:
            return "doc"
        }
    }

    private var fileTypeColor: Color {
        let ext = fileExtension
        switch ext {
        case "mp4", "mov", "avi", "mkv", "webm", "m4v":
            return .purple
        case "mp3", "wav", "aac", "flac", "m4a", "ogg":
            return .pink
        case "jpg", "jpeg", "png", "gif", "webp", "tiff", "heic", "bmp":
            return .blue
        case "pdf":
            return .red
        case "psd", "ai", "sketch", "fig":
            return .orange
        default:
            return .secondary
        }
    }

    private var statusColor: Color {
        switch file.status {
        case .ok: return .green
        case .modified: return .orange
        case .missing: return .red
        }
    }
}
