import SwiftUI

struct ContentView: View {
    @EnvironmentObject var appState: AppState
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
                    // 좁은 화면: 2컬럼 (사이드바 숨김)
                    NavigationSplitView {
                        FileListView(isCompact: isCompact)
                            .frame(minWidth: 280)
                    } detail: {
                        InspectorView(isCompact: isCompact)
                    }
                } else {
                    // 넓은 화면: 3컬럼
                    NavigationSplitView {
                        SidebarView()
                            .frame(minWidth: isCompact ? 140 : 180)
                    } content: {
                        FileListView(isCompact: isCompact)
                            .frame(minWidth: isCompact ? 250 : 300)
                    } detail: {
                        InspectorView(isCompact: isCompact)
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
        .task {
            await appState.loadFiles()
        }
        .alert("Error", isPresented: .constant(appState.errorMessage != nil)) {
            Button("OK") {
                appState.errorMessage = nil
            }
        } message: {
            Text(appState.errorMessage ?? "")
        }
        .sheet(isPresented: $appState.showAddFileDialog) {
            AddFileSheet()
        }
        .sheet(isPresented: $appState.showNewVersionDialog) {
            NewVersionSheet()
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
                    Task { await appState.verifyAllFiles() }
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
