import SwiftUI

@main
struct VersionManagerApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .frame(minWidth: 900, minHeight: 600)
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
                    Task {
                        await appState.verifyAllFiles()
                    }
                }
                .keyboardShortcut("r", modifiers: .command)
            }
        }
    }
}
