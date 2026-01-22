import SwiftUI

struct InspectorView: View {
    @EnvironmentObject var appState: AppState
    @State private var newTagText = ""
    @State private var selectedVersionNumber: Int?
    @State private var verificationResult: VerificationResult?
    var isCompact: Bool = false

    private var spacing: CGFloat { isCompact ? 12 : 20 }
    private var padding: CGFloat { isCompact ? 12 : 16 }

    var body: some View {
        if let file = appState.selectedFile {
            ScrollView {
                VStack(alignment: .leading, spacing: spacing) {
                    fileInfoSection(file)
                    metadataSection
                    tagsSection
                    versionsSection
                    if !isCompact {
                        eventsSection
                    }
                    actionsSection(file)
                }
                .padding(padding)
            }
            .navigationTitle(isCompact ? "" : "Inspector")
        } else {
            VStack(spacing: 12) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.system(size: isCompact ? 36 : 48))
                    .foregroundColor(.secondary)
                Text(isCompact ? "Select a file" : "Select a file to view details")
                    .foregroundColor(.secondary)
                    .font(isCompact ? .caption : .body)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    // MARK: - File Info Section

    @ViewBuilder
    private func fileInfoSection(_ file: TrackedFile) -> some View {
        GroupBox("File Information") {
            VStack(alignment: .leading, spacing: 12) {
                LabeledContent("Name") {
                    Text(file.displayName)
                        .lineLimit(1)
                }

                LabeledContent("Path") {
                    Text(file.filePath)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }

                LabeledContent("Status") {
                    HStack(spacing: 4) {
                        Text(file.status.icon)
                        Text(file.status.displayName)
                    }
                    .foregroundColor(statusColor(for: file.status))
                }

                LabeledContent("Size") {
                    Text(file.formattedSize)
                }

                LabeledContent("Added") {
                    Text(file.formattedDate)
                }

                if let hash = file.fileHash {
                    LabeledContent("Hash") {
                        Text(String(hash.prefix(16)) + "...")
                            .font(.caption.monospaced())
                            .foregroundColor(.secondary)
                            .help(hash)
                    }
                }
            }
            .padding(.vertical, 4)
        }
    }

    private func statusColor(for status: FileStatus) -> Color {
        switch status {
        case .ok: return .green
        case .modified: return .orange
        case .missing: return .red
        }
    }

    // MARK: - Tags Section

    @ViewBuilder
    private var tagsSection: some View {
        GroupBox("Tags") {
            VStack(alignment: .leading, spacing: 8) {
                // Tag chips
                FlowLayout(spacing: 4) {
                    ForEach(appState.tags) { tag in
                        TagChipView(tag: tag) {
                            Task { await appState.removeTag(tag.id) }
                        }
                    }
                }

                // Add tag input
                HStack {
                    TextField("Add tag (e.g. #final)", text: $newTagText)
                        .textFieldStyle(.roundedBorder)
                        .onSubmit {
                            addTag()
                        }
                    Button(action: addTag) {
                        Image(systemName: "plus.circle.fill")
                    }
                    .disabled(newTagText.isEmpty)
                }
            }
            .padding(.vertical, 4)
        }
    }

    private func addTag() {
        guard !newTagText.isEmpty else { return }
        Task {
            await appState.addTag(newTagText)
            newTagText = ""
        }
    }

    // MARK: - Versions Section

    @ViewBuilder
    private var versionsSection: some View {
        GroupBox(isCompact ? "Versions" : "Version History") {
            VStack(alignment: .leading, spacing: isCompact ? 4 : 8) {
                // Version list
                List(appState.versions, selection: $selectedVersionNumber) { version in
                    VersionRowView(version: version, isCompact: isCompact)
                        .tag(version.versionNumber)
                        .contextMenu {
                            versionContextMenu(for: version)
                        }
                }
                .listStyle(.plain)
                .frame(height: min(CGFloat(appState.versions.count) * (isCompact ? 40 : 50) + 20, isCompact ? 150 : 200))

                // Selected version actions
                if let versionNumber = selectedVersionNumber,
                   let version = appState.versions.first(where: { $0.versionNumber == versionNumber }) {
                    Divider()

                    Text(version.commitMessage)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(isCompact ? 1 : 2)
                        .padding(.vertical, isCompact ? 2 : 4)

                    if isCompact {
                        // 컴팩트: 2줄로 버튼 배치
                        VStack(spacing: 4) {
                            HStack {
                                Button("Open") {
                                    Task { await appState.openVersion(versionNumber) }
                                }
                                Button("Restore") {
                                    Task { await appState.restoreVersion(versionNumber) }
                                }
                                Spacer()
                            }
                            HStack {
                                Button("Verify") {
                                    Task {
                                        verificationResult = await appState.verifyVersion(versionNumber)
                                    }
                                }
                                Button(version.isPinned ? "Unpin" : "Pin") {
                                    Task { await appState.togglePin(versionNumber) }
                                }
                                Spacer()
                            }
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                    } else {
                        HStack {
                            Button("Open") {
                                Task { await appState.openVersion(versionNumber) }
                            }
                            Button("Restore") {
                                Task { await appState.restoreVersion(versionNumber) }
                            }
                            Button("Verify") {
                                Task {
                                    verificationResult = await appState.verifyVersion(versionNumber)
                                }
                            }

                            Spacer()

                            Button(version.isPinned ? "Unpin" : "Pin") {
                                Task { await appState.togglePin(versionNumber) }
                            }
                        }
                        .buttonStyle(.bordered)
                    }

                    if let result = verificationResult {
                        HStack {
                            Image(systemName: result.isValid ? "checkmark.circle.fill" : "xmark.circle.fill")
                                .foregroundColor(result.isValid ? .green : .red)
                            Text(result.message)
                                .font(.caption)
                                .lineLimit(1)
                        }
                        .padding(.top, isCompact ? 2 : 4)
                    }
                }
            }
            .padding(.vertical, isCompact ? 2 : 4)
        }
    }

    @ViewBuilder
    private func versionContextMenu(for version: Version) -> some View {
        Button("Open Version") {
            Task { await appState.openVersion(version.versionNumber) }
        }
        Button("Show in Finder") {
            Task { await appState.revealVersion(version.versionNumber) }
        }

        Divider()

        Button(version.isPinned ? "Unpin" : "Pin") {
            Task { await appState.togglePin(version.versionNumber) }
        }

        if version.isPinned {
            Button("Show Pinned in Finder") {
                Task { await appState.revealPinnedVersion(version.versionNumber) }
            }
        }

        Divider()

        Button("Verify Integrity") {
            Task {
                verificationResult = await appState.verifyVersion(version.versionNumber)
            }
        }

        Divider()

        Button("Restore to This Version") {
            Task { await appState.restoreVersion(version.versionNumber) }
        }
    }

    // MARK: - Events Section

    @ViewBuilder
    private var eventsSection: some View {
        GroupBox("Events Timeline") {
            if appState.events.isEmpty {
                Text("No events recorded")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.vertical, 8)
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(appState.events.prefix(10)) { event in
                        HStack {
                            Text(event.icon)
                            Text(event.displayName)
                                .font(.caption)
                            Spacer()
                            Text(event.formattedDate)
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.vertical, 4)
            }
        }
    }

    // MARK: - Metadata Section

    @ViewBuilder
    private var metadataSection: some View {
        GroupBox("Metadata") {
            if let metadata = appState.metadata, !metadata.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    if let width = metadata["width"] as? Int,
                       let height = metadata["height"] as? Int {
                        LabeledContent("Dimensions") {
                            Text("\(width) × \(height)")
                        }
                    }
                    if let duration = metadata["duration"] as? Double {
                        LabeledContent("Duration") {
                            Text(formatDuration(duration))
                        }
                    }
                    if let codec = metadata["codec"] as? String {
                        LabeledContent("Codec") {
                            Text(codec)
                        }
                    }
                    if let warning = metadata["warning"] as? String {
                        HStack {
                            Image(systemName: "exclamationmark.triangle")
                                .foregroundColor(.orange)
                            Text(warning)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.vertical, 4)
            } else {
                HStack {
                    Text("No metadata available")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                    Button("Extract") {
                        Task { await appState.extractMetadata() }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
                .padding(.vertical, 4)
            }
        }
    }

    private func formatDuration(_ seconds: Double) -> String {
        let mins = Int(seconds) / 60
        let secs = Int(seconds) % 60
        return String(format: "%d:%02d", mins, secs)
    }

    // MARK: - Actions Section

    @ViewBuilder
    private func actionsSection(_ file: TrackedFile) -> some View {
        if isCompact {
            VStack(spacing: 8) {
                HStack {
                    Button("New Version") {
                        appState.showNewVersionDialog = true
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)

                    Button("Open") {
                        Task { await appState.openFile(file.id) }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)

                    Button("Reveal") {
                        Task { await appState.revealFile(file.id) }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)

                    Spacer()
                }

                HStack {
                    Spacer()
                    if file.isArchived {
                        Button("Unarchive") {
                            Task { await appState.unarchiveFile(file.id) }
                        }
                        .controlSize(.small)
                    } else {
                        Button("Remove", role: .destructive) {
                            Task { await appState.deleteFile(file.id) }
                        }
                        .controlSize(.small)
                    }
                }
            }
        } else {
            HStack {
                Button("New Version") {
                    appState.showNewVersionDialog = true
                }
                .buttonStyle(.borderedProminent)

                Button("Open") {
                    Task { await appState.openFile(file.id) }
                }
                .buttonStyle(.bordered)

                Button("Reveal") {
                    Task { await appState.revealFile(file.id) }
                }
                .buttonStyle(.bordered)

                Spacer()

                if file.isArchived {
                    Button("Unarchive") {
                        Task { await appState.unarchiveFile(file.id) }
                    }
                } else {
                    Button("Remove", role: .destructive) {
                        Task { await appState.deleteFile(file.id) }
                    }
                }
            }
        }
    }
}

// MARK: - Supporting Views

struct TagChipView: View {
    let tag: Tag
    let onRemove: () -> Void

    var body: some View {
        HStack(spacing: 4) {
            Text(tag.displayName)
                .font(.caption)
                .foregroundColor(.blue)
            Button(action: onRemove) {
                Image(systemName: "xmark.circle.fill")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color.blue.opacity(0.1))
        .cornerRadius(12)
    }
}

struct VersionRowView: View {
    let version: Version
    var isCompact: Bool = false

    var body: some View {
        HStack {
            if version.isPinned {
                Text("📌")
                    .font(isCompact ? .caption : .body)
            }
            VStack(alignment: .leading, spacing: isCompact ? 1 : 2) {
                Text("v\(version.versionNumber)")
                    .fontWeight(.medium)
                    .font(isCompact ? .caption : .body)
                if !isCompact {
                    Text(version.formattedDate)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            Spacer()
            Text(version.formattedSize)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, isCompact ? 2 : 4)
    }
}

// MARK: - Flow Layout

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = FlowResult(in: proposal.width ?? 0, subviews: subviews, spacing: spacing)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = FlowResult(in: bounds.width, subviews: subviews, spacing: spacing)
        for (index, subview) in subviews.enumerated() {
            subview.place(at: CGPoint(x: bounds.minX + result.positions[index].x,
                                      y: bounds.minY + result.positions[index].y),
                         proposal: .unspecified)
        }
    }

    struct FlowResult {
        var size: CGSize = .zero
        var positions: [CGPoint] = []

        init(in maxWidth: CGFloat, subviews: Subviews, spacing: CGFloat) {
            var x: CGFloat = 0
            var y: CGFloat = 0
            var rowHeight: CGFloat = 0

            for subview in subviews {
                let size = subview.sizeThatFits(.unspecified)

                if x + size.width > maxWidth && x > 0 {
                    x = 0
                    y += rowHeight + spacing
                    rowHeight = 0
                }

                positions.append(CGPoint(x: x, y: y))
                rowHeight = max(rowHeight, size.height)
                x += size.width + spacing
            }

            self.size = CGSize(width: maxWidth, height: y + rowHeight)
        }
    }
}
