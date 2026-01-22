import SwiftUI
import SwiftData

struct LocalContentView: View {
    @EnvironmentObject var appState: LocalAppState
    @Environment(\.colorScheme) var colorScheme
    @State private var windowSize: CGSize = .zero

    private var isCompact: Bool {
        windowSize.width < 900
    }

    private var isNarrow: Bool {
        windowSize.width < 700
    }

    var body: some View {
        GeometryReader { geometry in
            Group {
                if isNarrow {
                    NavigationSplitView {
                        LocalFileListView(isCompact: isCompact)
                            .frame(minWidth: 280)
                    } detail: {
                        LocalInspectorView(isCompact: isCompact)
                    }
                } else {
                    NavigationSplitView {
                        LocalSidebarView()
                            .frame(minWidth: isCompact ? 140 : 180)
                    } content: {
                        LocalFileListView(isCompact: isCompact)
                            .frame(minWidth: isCompact ? 250 : 300)
                    } detail: {
                        LocalInspectorView(isCompact: isCompact)
                            .frame(minWidth: isCompact ? 280 : 320)
                    }
                }
            }
            .onChange(of: geometry.size) { oldSize, newSize in
                windowSize = newSize
            }
            .onAppear {
                windowSize = geometry.size
            }
        }
        .alert("Error", isPresented: .constant(appState.errorMessage != nil)) {
            Button("OK") {
                appState.errorMessage = nil
            }
        } message: {
            Text(appState.errorMessage ?? "")
        }
        .sheet(isPresented: $appState.showAddFileDialog) {
            LocalAddFileSheet()
        }
        .sheet(isPresented: $appState.showNewVersionDialog) {
            LocalNewVersionSheet()
        }
        .sheet(isPresented: $appState.showNewProjectDialog) {
            LocalNewProjectSheet()
        }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Button {
                    appState.showAddFileDialog = true
                } label: {
                    Label("Add", systemImage: "plus")
                }
                .help("Add File (⌘O)")

                Button {
                    appState.verifyAllFiles()
                } label: {
                    Label("Verify", systemImage: "checkmark.shield")
                }
                .help("Verify All Files (⌘R)")

                if appState.selectedFile != nil {
                    Button {
                        appState.showNewVersionDialog = true
                    } label: {
                        Label("Version", systemImage: "plus.square.on.square")
                    }
                    .help("Create New Version")
                }
            }

            ToolbarItem(placement: .status) {
                if appState.isLoading {
                    ProgressView()
                        .scaleEffect(0.6)
                } else if let message = appState.statusMessage {
                    Text(message)
                        .foregroundColor(.secondary)
                        .font(.caption)
                        .onAppear {
                            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                                if appState.statusMessage == message {
                                    appState.statusMessage = nil
                                }
                            }
                        }
                }
            }
        }
    }
}

// MARK: - Local Sidebar View

struct LocalSidebarView: View {
    @EnvironmentObject var appState: LocalAppState
    @State private var isProjectsExpanded = true

    var body: some View {
        List {
            Section {
                DisclosureGroup(isExpanded: $isProjectsExpanded) {
                    Button {
                        appState.selectProject(nil)
                    } label: {
                        Label("All Projects", systemImage: "tray.2")
                    }
                    .buttonStyle(.plain)
                    .padding(.vertical, 2)
                    .background(appState.selectedProjectId == nil ? Color.accentColor.opacity(0.15) : Color.clear)
                    .cornerRadius(4)

                    ForEach(appState.projects) { project in
                        Button {
                            appState.selectProject(project.id)
                        } label: {
                            HStack {
                                Circle()
                                    .fill(project.swiftUIColor)
                                    .frame(width: 10, height: 10)
                                Text(project.name)
                                    .lineLimit(1)
                                Spacer()
                                Text("\(project.fileCount)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .buttonStyle(.plain)
                        .padding(.vertical, 2)
                        .background(appState.selectedProjectId == project.id ? Color.accentColor.opacity(0.15) : Color.clear)
                        .cornerRadius(4)
                        .contextMenu {
                            Button("Delete", role: .destructive) {
                                appState.deleteProject(project.id)
                            }
                        }
                    }

                    Button {
                        appState.showNewProjectDialog = true
                    } label: {
                        Label("New Project", systemImage: "plus")
                            .foregroundColor(.accentColor)
                    }
                    .buttonStyle(.plain)
                    .padding(.vertical, 2)
                } label: {
                    Label("Projects", systemImage: "folder")
                        .font(.headline)
                }
            }

            Section("Filters") {
                ForEach(FilterCategory.allCases, id: \.self) { category in
                    Button {
                        appState.selectedFilter = category
                    } label: {
                        Label(category.rawValue, systemImage: category.icon)
                    }
                    .buttonStyle(.plain)
                    .padding(.vertical, 2)
                    .background(appState.selectedFilter == category ? Color.accentColor.opacity(0.15) : Color.clear)
                    .cornerRadius(4)
                }
            }
        }
        .listStyle(.sidebar)
        .navigationTitle("Library")
    }
}

// MARK: - Project Color Extension

extension ProjectModel {
    var swiftUIColor: Color {
        Color(hex: color) ?? .blue
    }
}

// MARK: - Local File List View

struct LocalFileListView: View {
    @EnvironmentObject var appState: LocalAppState
    @State private var isTargeted = false
    var isCompact: Bool = false

    var body: some View {
        VStack(spacing: 0) {
            // Search Bar
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)
                TextField(isCompact ? "Search..." : "Search name, path...", text: $appState.searchText)
                    .textFieldStyle(.plain)

                if !isCompact {
                    Divider().frame(height: 16)
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
            } else {
                List(appState.filteredFiles, id: \.id, selection: $appState.selectedFileId) { file in
                    LocalFileRowView(file: file)
                        .tag(file.id)
                        .contextMenu {
                            fileContextMenu(for: file)
                        }
                }
                .listStyle(.plain)
            }

            Divider()

            // Status Bar
            HStack {
                Text("\(appState.filteredFiles.count) files")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                Button {
                    appState.showAddFileDialog = true
                } label: {
                    Image(systemName: "plus")
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, isCompact ? 8 : 12)
            .padding(.vertical, isCompact ? 4 : 6)
            .background(Color(nsColor: .controlBackgroundColor))
        }
        .navigationTitle(isCompact ? "" : "Files")
        .onDrop(of: [.fileURL], isTargeted: $isTargeted) { providers in
            handleDrop(providers: providers)
        }
    }

    @ViewBuilder
    private func fileContextMenu(for file: TrackedFileModel) -> some View {
        Button("Open") { appState.openFile(file.id) }
        Button("Show in Finder") { appState.revealFile(file.id) }
        Divider()
        Button("Verify") { appState.verifyFile(file.id) }
        if file.status == .modified {
            Button("New Version...") {
                appState.selectedFileId = file.id
                appState.showNewVersionDialog = true
            }
        }
        Divider()
        Button(file.isFavorite ? "Remove from Favorites" : "Add to Favorites") {
            appState.toggleFavorite(file.id)
        }
        Divider()
        Menu("Move to Project") {
            Button("No Project") { appState.setFileProject(file.id, projectId: nil) }
            Divider()
            ForEach(appState.projects) { project in
                Button(project.name) { appState.setFileProject(file.id, projectId: project.id) }
            }
        }
        Divider()
        if file.isArchived {
            Button("Unarchive") { appState.unarchiveFile(file.id) }
        } else {
            Button("Archive") { appState.archiveFile(file.id) }
            Button("Remove", role: .destructive) { appState.deleteFile(file.id) }
        }
    }

    private func handleDrop(providers: [NSItemProvider]) -> Bool {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: "public.file-url", options: nil) { item, _ in
                guard let data = item as? Data,
                      let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
                DispatchQueue.main.async {
                    appState.registerFile(path: url.path, commitMessage: "Initial version")
                }
            }
        }
        return true
    }
}

// MARK: - Local File Row View

struct LocalFileRowView: View {
    let file: TrackedFileModel

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: fileTypeIcon)
                .foregroundColor(fileTypeColor)
                .font(.system(size: 16))
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Text(file.displayName)
                        .lineLimit(1)
                    Circle()
                        .fill(statusColor)
                        .frame(width: 8, height: 8)
                    if file.isFavorite {
                        Image(systemName: "star.fill")
                            .foregroundColor(.yellow)
                            .font(.system(size: 10))
                    }
                }

                HStack {
                    Text(formattedSize)
                    Text("•")
                    Text(fileExtension.uppercased())
                }
                .font(.caption)
                .foregroundColor(.secondary)
            }

            Spacer()

            if file.isArchived {
                Image(systemName: "archivebox")
                    .foregroundColor(.secondary)
                    .font(.caption)
            }
        }
        .padding(.vertical, 4)
    }

    private var fileExtension: String {
        URL(fileURLWithPath: file.filePath).pathExtension.lowercased()
    }

    private var formattedSize: String {
        ByteCountFormatter.string(fromByteCount: file.fileSize, countStyle: .file)
    }

    private var fileTypeIcon: String {
        switch fileExtension {
        case "mp4", "mov", "avi", "mkv", "webm": return "film"
        case "mp3", "wav", "aac", "flac", "m4a": return "waveform"
        case "jpg", "jpeg", "png", "gif", "webp", "heic": return "photo"
        case "pdf": return "doc.richtext"
        case "doc", "docx", "txt", "rtf", "md": return "doc.text"
        case "zip", "rar", "7z": return "archivebox"
        default: return "doc"
        }
    }

    private var fileTypeColor: Color {
        switch fileExtension {
        case "mp4", "mov", "avi", "mkv", "webm": return .purple
        case "mp3", "wav", "aac", "flac", "m4a": return .pink
        case "jpg", "jpeg", "png", "gif", "webp", "heic": return .blue
        case "pdf": return .red
        default: return .secondary
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

// MARK: - Local Inspector View

struct LocalInspectorView: View {
    @EnvironmentObject var appState: LocalAppState
    @State private var selectedVersion: VersionModel?
    var isCompact: Bool = false

    var body: some View {
        if let file = appState.selectedFile {
            ScrollView {
                VStack(alignment: .leading, spacing: isCompact ? 12 : 20) {
                    fileInfoSection(file)
                    versionsSection(file)
                    actionsSection(file)
                }
                .padding(isCompact ? 12 : 16)
            }
            .navigationTitle(isCompact ? "" : "Inspector")
        } else {
            VStack(spacing: 12) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.system(size: isCompact ? 36 : 48))
                    .foregroundColor(.secondary)
                Text(isCompact ? "Select a file" : "Select a file to view details")
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    @ViewBuilder
    private func fileInfoSection(_ file: TrackedFileModel) -> some View {
        GroupBox("File Information") {
            VStack(alignment: .leading, spacing: 12) {
                LabeledContent("Name") { Text(file.displayName).lineLimit(1) }
                LabeledContent("Path") {
                    Text(file.filePath)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }
                LabeledContent("Status") {
                    HStack(spacing: 4) {
                        Circle().fill(statusColor(file.status)).frame(width: 8, height: 8)
                        Text(file.status.rawValue)
                    }
                }
                LabeledContent("Size") {
                    Text(ByteCountFormatter.string(fromByteCount: file.fileSize, countStyle: .file))
                }
            }
            .padding(.vertical, 4)
        }
    }

    @ViewBuilder
    private func versionsSection(_ file: TrackedFileModel) -> some View {
        GroupBox("Versions") {
            VStack(alignment: .leading, spacing: 8) {
                ForEach(file.sortedVersions) { version in
                    HStack {
                        if version.isPinned { Text("📌") }
                        Text("v\(version.versionNumber)")
                            .fontWeight(.medium)
                        Text(version.commitMessage)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                        Spacer()
                        Text(ByteCountFormatter.string(fromByteCount: version.fileSize, countStyle: .file))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 4)
                    .background(selectedVersion?.id == version.id ? Color.accentColor.opacity(0.1) : Color.clear)
                    .cornerRadius(4)
                    .onTapGesture { selectedVersion = version }
                    .contextMenu {
                        Button("Open") { appState.openVersion(version) }
                        Button("Show in Finder") { appState.revealVersion(version) }
                        Divider()
                        Button(version.isPinned ? "Unpin" : "Pin") { appState.togglePin(version) }
                        Divider()
                        Button("Restore") { appState.restoreVersion(version) }
                    }
                }

                if let version = selectedVersion {
                    Divider()
                    HStack {
                        Button("Open") { appState.openVersion(version) }
                        Button("Restore") { appState.restoreVersion(version) }
                        Spacer()
                        Button(version.isPinned ? "Unpin" : "Pin") { appState.togglePin(version) }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
            }
            .padding(.vertical, 4)
        }
    }

    @ViewBuilder
    private func actionsSection(_ file: TrackedFileModel) -> some View {
        HStack {
            Button("New Version") { appState.showNewVersionDialog = true }
                .buttonStyle(.borderedProminent)
            Button("Open") { appState.openFile(file.id) }
                .buttonStyle(.bordered)
            Button("Reveal") { appState.revealFile(file.id) }
                .buttonStyle(.bordered)
            Spacer()
            if file.isArchived {
                Button("Unarchive") { appState.unarchiveFile(file.id) }
            } else {
                Button("Remove", role: .destructive) { appState.deleteFile(file.id) }
            }
        }
    }

    private func statusColor(_ status: TrackedFileStatus) -> Color {
        switch status {
        case .ok: return .green
        case .modified: return .orange
        case .missing: return .red
        }
    }
}

// MARK: - Sheets

struct LocalAddFileSheet: View {
    @EnvironmentObject var appState: LocalAppState
    @Environment(\.dismiss) var dismiss
    @State private var selectedPath = ""
    @State private var commitMessage = ""

    var body: some View {
        VStack(spacing: 20) {
            Text("Add File").font(.headline)

            VStack(alignment: .leading, spacing: 8) {
                Text("File Path").font(.caption).foregroundColor(.secondary)
                HStack {
                    TextField("Select a file...", text: $selectedPath)
                        .textFieldStyle(.roundedBorder)
                        .disabled(true)
                    Button("Browse...") { selectFile() }
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Commit Message").font(.caption).foregroundColor(.secondary)
                TextField("Initial version", text: $commitMessage)
                    .textFieldStyle(.roundedBorder)
            }

            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button("Add") { addFile() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(selectedPath.isEmpty || commitMessage.isEmpty)
            }
        }
        .padding(24)
        .frame(width: 400)
    }

    private func selectFile() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        if panel.runModal() == .OK, let url = panel.url {
            selectedPath = url.path
            if commitMessage.isEmpty { commitMessage = "Initial version" }
        }
    }

    private func addFile() {
        appState.registerFile(path: selectedPath, commitMessage: commitMessage)
        dismiss()
    }
}

struct LocalNewVersionSheet: View {
    @EnvironmentObject var appState: LocalAppState
    @Environment(\.dismiss) var dismiss
    @State private var commitMessage = ""

    var body: some View {
        VStack(spacing: 20) {
            Text("New Version").font(.headline)

            if let file = appState.selectedFile {
                HStack {
                    Image(systemName: "doc.fill").foregroundColor(.secondary)
                    Text(file.displayName).lineLimit(1)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color(nsColor: .controlBackgroundColor))
                .cornerRadius(8)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("What changed?").font(.caption).foregroundColor(.secondary)
                TextField("Describe the changes...", text: $commitMessage, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(3...5)
            }

            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button("Create Version") { createVersion() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(commitMessage.isEmpty)
            }
        }
        .padding(24)
        .frame(width: 400)
    }

    private func createVersion() {
        appState.createVersion(commitMessage: commitMessage)
        dismiss()
    }
}

struct LocalNewProjectSheet: View {
    @EnvironmentObject var appState: LocalAppState
    @Environment(\.dismiss) var dismiss
    @State private var projectName = ""
    @State private var projectDescription = ""
    @State private var selectedColor = "#007AFF"

    private let colorOptions = ["#007AFF", "#34C759", "#FF9500", "#FF3B30", "#AF52DE", "#FF2D55", "#5856D6", "#00C7BE"]

    var body: some View {
        VStack(spacing: 20) {
            Text("New Project").font(.headline)

            VStack(alignment: .leading, spacing: 8) {
                Text("Name").font(.caption).foregroundColor(.secondary)
                TextField("Project name", text: $projectName).textFieldStyle(.roundedBorder)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Description (Optional)").font(.caption).foregroundColor(.secondary)
                TextField("Description", text: $projectDescription).textFieldStyle(.roundedBorder)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Color").font(.caption).foregroundColor(.secondary)
                HStack(spacing: 8) {
                    ForEach(colorOptions, id: \.self) { color in
                        Circle()
                            .fill(Color(hex: color) ?? .blue)
                            .frame(width: 24, height: 24)
                            .overlay(Circle().stroke(Color.primary, lineWidth: selectedColor == color ? 2 : 0))
                            .onTapGesture { selectedColor = color }
                    }
                }
            }

            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button("Create") { createProject() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(projectName.isEmpty)
            }
        }
        .padding(24)
        .frame(width: 350)
    }

    private func createProject() {
        appState.createProject(
            name: projectName,
            description: projectDescription.isEmpty ? nil : projectDescription,
            color: selectedColor
        )
        dismiss()
    }
}
