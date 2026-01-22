import SwiftUI
import SwiftData

@main
struct VersionManagerApp: App {
    @StateObject private var appState = LocalAppState()

    var sharedModelContainer: ModelContainer = {
        let schema = Schema([
            ProjectModel.self,
            TrackedFileModel.self,
            VersionModel.self,
            TagModel.self,
            TagLinkModel.self,
            FileEventModel.self
        ])
        let modelConfiguration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)

        do {
            return try ModelContainer(for: schema, configurations: [modelConfiguration])
        } catch {
            fatalError("Could not create ModelContainer: \(error)")
        }
    }()

    var body: some Scene {
        WindowGroup {
            LocalContentView()
                .environmentObject(appState)
                .modelContainer(sharedModelContainer)
                .frame(minWidth: 900, minHeight: 600)
                .onAppear {
                    appState.setup(modelContext: sharedModelContainer.mainContext)
                }
        }
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Add File...") {
                    appState.showAddFileDialog = true
                }
                .keyboardShortcut("o", modifiers: .command)
            }
            CommandGroup(after: .newItem) {
                Button("Verify All") {
                    appState.verifyAllFiles()
                }
                .keyboardShortcut("r", modifiers: .command)
            }
        }
    }
}
