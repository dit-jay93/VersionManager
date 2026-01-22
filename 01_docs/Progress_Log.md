## Progress Log

### 2026-01-22
- Added Job Queue with background handlers (Verify All, Pin Copy, Restore, Relink) and monitoring dialog.
- Added Relink options dialog, hash-based matching, extension filters, and mtime heuristic fallback for missing files.
- Enhanced Job Queue UI with progress bars, hide/clear completed controls, and concurrency setting.
- Added Open With support: menu action, per-file preferred app stored in settings, and fallback to default open.
- Added Relink filters (max size, modified-within-days) and result stats (size/date filtered counts).
- Added metadata extraction (Pillow) with inspector view and refresh, metadata table in DB.
- Added optional video metadata via ffprobe (if available) and display in Inspector.
- Added ffprobe absence warning surfaced in metadata UI/status when not installed.
- Added file type icons in file list (video/audio/image/doc/archive cues).
- Added Inspector type badge (Video/Image/extension) sourced from metadata.
- Refreshed UI theme to SwiftUI-like light/dark style (rounded cards, gradients, accent blue); light theme now applied by default.
- Added responsive compact mode: auto-toggles reduced padding/radius when window width < 1100px.
- Button text contrast: pressed/checked states keep text color consistent.
