import SwiftUI
import AppKit

struct AddFileSheet: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) var dismiss

    @State private var selectedPath: String = ""
    @State private var commitMessage: String = ""

    var body: some View {
        VStack(spacing: 20) {
            Text("Add File")
                .font(.headline)

            VStack(alignment: .leading, spacing: 8) {
                Text("File Path")
                    .font(.caption)
                    .foregroundColor(.secondary)

                HStack {
                    TextField("Select a file...", text: $selectedPath)
                        .textFieldStyle(.roundedBorder)
                        .disabled(true)

                    Button("Browse...") {
                        selectFile()
                    }
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Commit Message")
                    .font(.caption)
                    .foregroundColor(.secondary)

                TextField("Initial version", text: $commitMessage)
                    .textFieldStyle(.roundedBorder)
            }

            HStack {
                Button("Cancel") {
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)

                Spacer()

                Button("Add") {
                    addFile()
                }
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
        panel.allowsMultipleSelection = false

        if panel.runModal() == .OK, let url = panel.url {
            selectedPath = url.path
            if commitMessage.isEmpty {
                commitMessage = "Initial version"
            }
        }
    }

    private func addFile() {
        Task {
            await appState.registerFile(path: selectedPath, commitMessage: commitMessage)
            dismiss()
        }
    }
}

struct NewVersionSheet: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) var dismiss

    @State private var commitMessage: String = ""

    var body: some View {
        VStack(spacing: 20) {
            Text("New Version")
                .font(.headline)

            if let file = appState.selectedFile {
                HStack {
                    Image(systemName: "doc.fill")
                        .foregroundColor(.secondary)
                    Text(file.displayName)
                        .lineLimit(1)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color(nsColor: .controlBackgroundColor))
                .cornerRadius(8)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("What changed?")
                    .font(.caption)
                    .foregroundColor(.secondary)

                TextField("Describe the changes...", text: $commitMessage, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(3...5)
            }

            HStack {
                Button("Cancel") {
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)

                Spacer()

                Button("Create Version") {
                    createVersion()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(commitMessage.isEmpty)
            }
        }
        .padding(24)
        .frame(width: 400)
    }

    private func createVersion() {
        Task {
            await appState.createVersion(commitMessage: commitMessage)
            dismiss()
        }
    }
}
