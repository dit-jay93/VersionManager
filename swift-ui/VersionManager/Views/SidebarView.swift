import SwiftUI

struct SidebarView: View {
    @EnvironmentObject var appState: AppState
    @State private var isProjectsExpanded = true

    var body: some View {
        List {
            // Projects Section
            Section {
                DisclosureGroup(isExpanded: $isProjectsExpanded) {
                    // All Projects
                    Button {
                        appState.selectProject(nil)
                    } label: {
                        Label("All Projects", systemImage: "tray.2")
                    }
                    .buttonStyle(.plain)
                    .padding(.vertical, 2)
                    .background(appState.selectedProjectId == nil ? Color.accentColor.opacity(0.15) : Color.clear)
                    .cornerRadius(4)

                    // Project List
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
                            Button("Rename...") {
                                // TODO: Implement rename
                            }
                            Divider()
                            Button("Delete", role: .destructive) {
                                Task { await appState.deleteProject(project.id) }
                            }
                        }
                    }

                    // New Project Button
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

            // Filter Section
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
        .sheet(isPresented: $appState.showNewProjectDialog) {
            NewProjectSheet()
        }
    }
}

struct NewProjectSheet: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) var dismiss

    @State private var projectName = ""
    @State private var projectDescription = ""
    @State private var selectedColor = "#007AFF"

    private let colorOptions = [
        "#007AFF", // Blue
        "#34C759", // Green
        "#FF9500", // Orange
        "#FF3B30", // Red
        "#AF52DE", // Purple
        "#FF2D55", // Pink
        "#5856D6", // Indigo
        "#00C7BE", // Teal
    ]

    var body: some View {
        VStack(spacing: 20) {
            Text("New Project")
                .font(.headline)

            VStack(alignment: .leading, spacing: 8) {
                Text("Name")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextField("Project name", text: $projectName)
                    .textFieldStyle(.roundedBorder)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Description (Optional)")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextField("Description", text: $projectDescription)
                    .textFieldStyle(.roundedBorder)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Color")
                    .font(.caption)
                    .foregroundColor(.secondary)
                HStack(spacing: 8) {
                    ForEach(colorOptions, id: \.self) { color in
                        Circle()
                            .fill(Color(hex: color) ?? .blue)
                            .frame(width: 24, height: 24)
                            .overlay(
                                Circle()
                                    .stroke(Color.primary, lineWidth: selectedColor == color ? 2 : 0)
                            )
                            .onTapGesture {
                                selectedColor = color
                            }
                    }
                }
            }

            HStack {
                Button("Cancel") {
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)

                Spacer()

                Button("Create") {
                    createProject()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(projectName.isEmpty)
            }
        }
        .padding(24)
        .frame(width: 350)
    }

    private func createProject() {
        Task {
            await appState.createProject(
                name: projectName,
                description: projectDescription.isEmpty ? nil : projectDescription,
                color: selectedColor
            )
            dismiss()
        }
    }
}
