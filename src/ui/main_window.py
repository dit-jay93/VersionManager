"""Main window for the Versioned File Manager application."""
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QFileDialog,
    QMessageBox, QMenuBar, QMenu, QApplication, QInputDialog
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from core import FileService
from core.job_queue import JobQueue, Job, JobType, JobStatus
from database import DatabaseManager, FileStatus, EventType
from ui.sidebar import Sidebar, FilterCategory
from ui.file_list import FileListWidget
from ui.inspector import InspectorPanel
from ui.dialogs import (
    CommitDialog,
    DeleteDialog,
    DeleteOption,
    JobQueueDialog,
    RelinkDialog,
    OpenWithDialog,
)
import json
from ui.theme import apply_dark_theme, apply_light_theme


class MainWindow(QMainWindow):
    """Main application window with 3-column layout."""

    def __init__(self, db_path: str):
        """Initialize the main window.

        Args:
            db_path: Path to the SQLite database.
        """
        super().__init__()

        # Initialize services
        self.db_manager = DatabaseManager(db_path)
        data_dir = str(Path(db_path).parent)

        # Load pin storage path from settings
        settings = QSettings("VersionedFileManager", "VFM")
        pin_storage_path = settings.value("pin_storage_path", None)
        if not pin_storage_path:
            # Default pin storage in app data directory
            pin_storage_path = str(Path(db_path).parent / "pinned")

        self.file_service = FileService(self.db_manager, data_dir, pin_storage_path)

        job_workers = settings.value("job_queue_max_workers", 1, type=int)
        self.job_queue = JobQueue(max_workers=job_workers)
        self._register_job_handlers()
        self.job_dialog: JobQueueDialog | None = None
        self._last_relink_root = settings.value("relink_root", None, type=str)
        self._last_relink_hash = settings.value("relink_use_hash", False, type=bool)
        self._last_relink_exts = settings.value("relink_exts", None, type=str)

        # Open-with preferences
        raw_open_with = settings.value("open_with_map", "{}", type=str)
        try:
            self._open_with_map: dict[str, str] = json.loads(raw_open_with)
        except Exception:
            self._open_with_map = {}

        self._compact_mode = False

        self._setup_window()
        self._setup_menu()
        self._load_settings()
        self._setup_ui()
        self._restore_layout()
        self._connect_signals()
        self._migrate_existing_files()
        self._load_files()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Toggle compact mode based on width threshold for a responsive feel
        compact = self.width() < 1100
        if compact != getattr(self, "_compact_mode", False):
            self._compact_mode = compact
            if self.dark_mode_action.isChecked():
                apply_dark_theme(QApplication.instance(), compact=compact)
            else:
                apply_light_theme(QApplication.instance(), compact=compact)

    def _save_open_with(self) -> None:
        settings = QSettings("VersionedFileManager", "VFM")
        settings.setValue("open_with_map", json.dumps(self._open_with_map))

    def _migrate_existing_files(self) -> None:
        """Migrate existing files to have version backups."""
        migrated = self.file_service.migrate_existing_files()
        if migrated > 0:
            print(f"Migrated {migrated} file(s) to include version backups")

    def _register_job_handlers(self) -> None:
        """Register job handlers for background operations."""

        def handle_verify_all(job: Job) -> None:
            files = self.db_manager.get_all_files(include_archived=False)
            total = max(len(files), 1)
            modified = 0
            missing = 0

            for idx, tracked_file in enumerate(files, start=1):
                if not self.job_queue.wait_if_paused_or_canceled(job):
                    return
                try:
                    status = self.file_service.verify_file(tracked_file.id)
                    if status == FileStatus.MODIFIED:
                        modified += 1
                        self.db_manager.create_event(
                            tracked_file.id,
                            EventType.VERIFY_MODIFIED,
                            "File has been modified since last version",
                        )
                    elif status == FileStatus.MISSING:
                        missing += 1
                        self.db_manager.create_event(
                            tracked_file.id,
                            EventType.VERIFY_MISSING,
                            "File is missing from disk",
                        )
                    else:
                        self.db_manager.create_event(
                            tracked_file.id,
                            EventType.VERIFY_OK,
                            "File integrity verified",
                        )
                except Exception as exc:  # pragma: no cover - defensive
                    job.status = JobStatus.FAILED
                    job.error = str(exc)
                    return

                job.progress = int((idx / total) * 100)
                self.job_queue.job_updated.emit(job)

            job.payload["summary"] = {"modified": modified, "missing": missing}

        def handle_pin_copy(job: Job) -> None:
            file_id = job.payload.get("file_id")
            version_number = job.payload.get("version_number")
            tracked_file = self.file_service.get_file(file_id) if file_id else None
            if not tracked_file:
                job.status = JobStatus.FAILED
                job.error = "File not found"
                return

            job.progress = 30
            self.job_queue.job_updated.emit(job)

            if not self.job_queue.wait_if_paused_or_canceled(job):
                return

            try:
                pinned_path = self.file_service.pin_version(file_id, version_number)
                job.payload["pinned_path"] = pinned_path
            except Exception as exc:  # pragma: no cover - defensive
                job.status = JobStatus.FAILED
                job.error = str(exc)
                return

            job.progress = 100
            self.job_queue.job_updated.emit(job)

        def handle_restore(job: Job) -> None:
            file_id = job.payload.get("file_id")
            version_number = job.payload.get("version_number")
            tracked_file = self.file_service.get_file(file_id) if file_id else None
            if not tracked_file:
                job.status = JobStatus.FAILED
                job.error = "File not found"
                return

            job.progress = 20
            self.job_queue.job_updated.emit(job)

            if not self.job_queue.wait_if_paused_or_canceled(job):
                return

            try:
                ok = self.file_service.restore_version(file_id, version_number)
                if not ok:
                    job.status = JobStatus.FAILED
                    job.error = "Restore failed"
                    return
                self.db_manager.create_event(
                    file_id, EventType.RESTORE, f"Restored to version {version_number}"
                )
            except Exception as exc:  # pragma: no cover - defensive
                job.status = JobStatus.FAILED
                job.error = str(exc)
                return

            job.progress = 100
            self.job_queue.job_updated.emit(job)

        def handle_relink_scan(job: Job) -> None:
            root_path = job.payload.get("root_path")
            use_hash = bool(job.payload.get("use_hash"))
            include_exts = job.payload.get("exts")
            max_size_mb = job.payload.get("max_size_mb")
            within_days = job.payload.get("within_days")
            if not root_path:
                job.status = JobStatus.FAILED
                job.error = "No root path provided"
                return

            job.progress = 10
            self.job_queue.job_updated.emit(job)

            if not self.job_queue.wait_if_paused_or_canceled(job):
                return

            try:
                summary = self.file_service.relink_missing_files(
                    root_path,
                    use_hash=use_hash,
                    include_exts=include_exts,
                    max_size_bytes=int(max_size_mb * 1024 * 1024) if max_size_mb else None,
                    modified_within_days=int(within_days) if within_days else None,
                )
                job.payload["summary"] = summary
            except Exception as exc:  # pragma: no cover - defensive
                job.status = JobStatus.FAILED
                job.error = str(exc)
                return

            job.progress = 100
            self.job_queue.job_updated.emit(job)

        self.job_queue.register_handler(JobType.VERIFY_ALL, handle_verify_all)
        self.job_queue.register_handler(JobType.PIN_COPY, handle_pin_copy)
        self.job_queue.register_handler(JobType.RESTORE, handle_restore)
        self.job_queue.register_handler(JobType.RELINK_SCAN, handle_relink_scan)

    def _on_job_completed(self, job: Job) -> None:
        """Refresh UI after a job finishes."""
        if job.job_type == JobType.VERIFY_ALL:
            files = self.file_service.get_all_files()
            self.file_list.set_files(files)
            selected_id = self.file_list.get_selected_file_id()
            if selected_id:
                self._on_file_selected(selected_id)
            if job.status == JobStatus.COMPLETED:
                summary = job.payload.get("summary", {}) if job.payload else {}
                modified = summary.get("modified", 0)
                missing = summary.get("missing", 0)
                if modified > 0 or missing > 0:
                    message = "Verification complete: "
                    parts = []
                    if modified:
                        parts.append(f"{modified} modified")
                    if missing:
                        parts.append(f"{missing} missing")
                    message += ", ".join(parts)
                else:
                    message = "All files OK"
                self.statusBar().showMessage(message, 5000)
            elif job.status == JobStatus.FAILED:
                self.statusBar().showMessage(f"Verification failed: {job.error}", 5000)
            elif job.status == JobStatus.CANCELED:
                self.statusBar().showMessage("Verification canceled", 3000)
        elif job.job_type == JobType.PIN_COPY:
            file_id = job.payload.get("file_id") if job.payload else None
            version_number = job.payload.get("version_number") if job.payload else None
            if job.status == JobStatus.COMPLETED and file_id and version_number is not None:
                pinned_path = job.payload.get("pinned_path")
                version = self.db_manager.get_version_by_number(file_id, version_number)
                if version:
                    self.inspector.update_version(version)
                self.db_manager.create_event(
                    file_id, EventType.PIN, f"Version {version_number} pinned to {pinned_path}"
                )
                events = self.db_manager.get_events(file_id)
                self.inspector.set_events(events)
                self.statusBar().showMessage(f"Version {version_number} pinned", 4000)
            elif job.status == JobStatus.FAILED:
                self.statusBar().showMessage(f"Pin failed: {job.error}", 5000)
            elif job.status == JobStatus.CANCELED:
                self.statusBar().showMessage("Pin canceled", 3000)
        elif job.job_type == JobType.RESTORE:
            file_id = job.payload.get("file_id") if job.payload else None
            version_number = job.payload.get("version_number") if job.payload else None
            if job.status == JobStatus.COMPLETED and file_id and version_number is not None:
                updated_file = self.file_service.get_file(file_id)
                if updated_file:
                    self.file_list.update_file(updated_file)
                    versions = self.file_service.get_versions(file_id)
                    tags = self.file_service.get_file_tags(file_id)
                    events = self.db_manager.get_events(file_id)
                    self.inspector.set_file(updated_file, versions, tags, events)
                self.statusBar().showMessage(f"Restored to version {version_number}", 4000)
            elif job.status == JobStatus.FAILED:
                self.statusBar().showMessage(f"Restore failed: {job.error}", 5000)
            elif job.status == JobStatus.CANCELED:
                self.statusBar().showMessage("Restore canceled", 3000)
        elif job.job_type == JobType.RELINK_SCAN:
            if job.status == JobStatus.COMPLETED:
                summary = job.payload.get("summary", {}) if job.payload else {}
                relinked = summary.get("relinked", 0)
                not_found = summary.get("not_found", 0)
                scanned = summary.get("scanned", 0)
                hash_checked = summary.get("hash_checked", 0)
                size_filtered = summary.get("size_filtered", 0)
                date_filtered = summary.get("date_filtered", 0)
                msg = f"Relink scan: {relinked} relinked"
                if not_found:
                    msg += f", {not_found} not found"
                msg += f" (scanned {scanned} files"
                if hash_checked:
                    msg += f", hash checked {hash_checked}"
                if size_filtered:
                    msg += f", size filtered {size_filtered}"
                if date_filtered:
                    msg += f", date filtered {date_filtered}"
                msg += ")"
                self._load_files()
                selected_id = self.file_list.get_selected_file_id()
                if selected_id:
                    self._on_file_selected(selected_id)
                self.statusBar().showMessage(msg, 5000)
                QMessageBox.information(self, "Relink Scan Results", msg)
            elif job.status == JobStatus.FAILED:
                self.statusBar().showMessage(f"Relink scan failed: {job.error}", 5000)
            elif job.status == JobStatus.CANCELED:
                self.statusBar().showMessage("Relink scan canceled", 3000)

    def _setup_window(self) -> None:
        """Configure the main window."""
        self.setWindowTitle("Versioned File Manager v0.1")
        self.setMinimumSize(960, 640)
        self.resize(1220, 760)

    def _setup_menu(self) -> None:
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        add_action = QAction("Add File...", self)
        add_action.setShortcut("Ctrl+O")
        add_action.triggered.connect(self._on_add_file)
        file_menu.addAction(add_action)

        file_menu.addSeparator()

        verify_action = QAction("Verify All", self)
        verify_action.setShortcut("Ctrl+R")
        verify_action.triggered.connect(self._on_verify_all)
        file_menu.addAction(verify_action)

        open_with_action = QAction("Open With...", self)
        open_with_action.triggered.connect(self._on_open_with)
        file_menu.addAction(open_with_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        find_action = QAction("Find...", self)
        find_action.setShortcut(QKeySequence.Find)  # Cmd+F / Ctrl+F
        find_action.triggered.connect(self._on_focus_search)
        edit_menu.addAction(find_action)

        edit_menu.addSeparator()

        self.delete_action = QAction("Remove File", self)
        self.delete_action.setShortcut(QKeySequence.Delete)  # Delete/Backspace
        self.delete_action.triggered.connect(self._on_delete_selected)
        self.delete_action.setEnabled(False)
        edit_menu.addAction(self.delete_action)

        # Also add Backspace as alternative shortcut
        backspace_shortcut = QShortcut(Qt.Key_Backspace, self)
        backspace_shortcut.activated.connect(self._on_delete_selected)

        # View menu
        view_menu = menubar.addMenu("View")

        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(False)
        self.dark_mode_action.triggered.connect(self._on_toggle_dark_mode)
        view_menu.addAction(self.dark_mode_action)

        # Jobs menu
        jobs_menu = menubar.addMenu("Jobs")
        show_jobs_action = QAction("Job Queue", self)
        show_jobs_action.triggered.connect(self._on_show_jobs)
        jobs_menu.addAction(show_jobs_action)

        relink_action = QAction("Relink Scan...", self)
        relink_action.triggered.connect(self._on_relink_scan)
        jobs_menu.addAction(relink_action)

        set_concurrency_action = QAction("Set Max Concurrent Jobs...", self)
        set_concurrency_action.triggered.connect(self._on_set_concurrency)
        jobs_menu.addAction(set_concurrency_action)

    def _on_toggle_dark_mode(self, checked: bool) -> None:
        """Toggle dark mode on/off."""
        app = QApplication.instance()
        if checked:
            apply_dark_theme(app, compact=self._compact_mode)
        else:
            apply_light_theme(app, compact=self._compact_mode)

        # Save setting
        settings = QSettings("VersionedFileManager", "VFM")
        settings.setValue("dark_mode", checked)

    def _load_settings(self) -> None:
        """Load saved settings."""
        settings = QSettings("VersionedFileManager", "VFM")

        # Dark mode
        dark_mode = settings.value("dark_mode", False, type=bool)
        if dark_mode:
            self.dark_mode_action.setChecked(True)
            apply_dark_theme(QApplication.instance(), compact=self._compact_mode)
        else:
            apply_light_theme(QApplication.instance(), compact=self._compact_mode)

    def _restore_layout(self) -> None:
        """Restore saved window and splitter layout."""
        settings = QSettings("VersionedFileManager", "VFM")

        # Window geometry
        geometry = settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Splitter state
        splitter_state = settings.value("splitter_state")
        if splitter_state:
            self.splitter.restoreState(splitter_state)

        # Sort option
        sort_index = settings.value("sort_index", 2, type=int)  # Default: Newest First
        self.file_list.sort_combo.setCurrentIndex(sort_index)

        # Sidebar filter
        filter_value = settings.value("sidebar_filter", "all", type=str)
        try:
            category = FilterCategory(filter_value)
            self.sidebar.set_filter(category)
            self.file_list.set_category_filter(category)
        except ValueError:
            pass  # Use default (ALL)

    def _save_settings(self) -> None:
        """Save current settings."""
        settings = QSettings("VersionedFileManager", "VFM")
        settings.setValue("window_geometry", self.saveGeometry())
        settings.setValue("splitter_state", self.splitter.saveState())
        settings.setValue("sort_index", self.file_list.sort_combo.currentIndex())

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        self._save_settings()
        self._save_open_with()
        self.job_queue.stop()
        super().closeEvent(event)

    def _setup_ui(self) -> None:
        """Set up the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create splitter for 3-column layout
        self.splitter = QSplitter(Qt.Horizontal)

        # Column 1: Sidebar
        self.sidebar = Sidebar()
        self.splitter.addWidget(self.sidebar)

        # Column 2: File list
        self.file_list = FileListWidget()
        self.splitter.addWidget(self.file_list)

        # Column 3: Inspector
        self.inspector = InspectorPanel()
        self.splitter.addWidget(self.inspector)

        # Set initial sizes (sidebar: 180, file list: 350, inspector: rest)
        self.splitter.setSizes([200, 420, 520])

        # Prevent sidebar from being too small
        self.splitter.setStretchFactor(0, 0)  # Sidebar doesn't stretch
        self.splitter.setStretchFactor(1, 1)  # File list stretches
        self.splitter.setStretchFactor(2, 1)  # Inspector stretches

        main_layout.addWidget(self.splitter)

    def _connect_signals(self) -> None:
        """Connect signals between components."""
        # Sidebar signals
        self.sidebar.filter_changed.connect(self._on_filter_changed)

        # File list signals
        self.file_list.file_selected.connect(self._on_file_selected)
        self.file_list.file_double_clicked.connect(self._on_file_double_clicked)
        self.file_list.add_file_requested.connect(self._on_add_file)
        self.file_list.verify_requested.connect(self._on_verify_all)
        self.file_list.files_dropped.connect(self._on_files_dropped)

        # Context menu signals
        self.file_list.open_file_requested.connect(self._on_file_double_clicked)
        self.file_list.show_in_finder_requested.connect(self._on_show_in_finder)
        self.file_list.new_version_requested.connect(self._on_new_version)
        self.file_list.delete_file_requested.connect(self._on_delete_file)
        self.file_list.verify_file_requested.connect(self._on_verify_file)
        self.file_list.toggle_favorite_requested.connect(self._on_toggle_favorite)
        self.file_list.rename_requested.connect(self._on_rename_file)
        self.file_list.unarchive_requested.connect(self._on_unarchive_file)

        # Inspector signals
        self.inspector.new_version_requested.connect(self._on_new_version)
        self.inspector.delete_file_requested.connect(self._on_delete_file)
        self.inspector.open_version_requested.connect(self._on_open_version)
        self.inspector.restore_version_requested.connect(self._on_restore_version)
        self.inspector.show_version_in_finder_requested.connect(self._on_show_version_in_finder)
        self.inspector.verify_version_requested.connect(self._on_verify_version)
        self.inspector.verify_all_versions_requested.connect(self._on_verify_all_versions)
        self.inspector.pin_version_requested.connect(self._on_pin_version)
        self.inspector.show_pinned_version_requested.connect(self._on_show_pinned_version)
        self.inspector.tag_added.connect(self._on_tag_added)
        self.inspector.tag_removed.connect(self._on_tag_removed)
        self.inspector.name_changed.connect(self._on_name_changed)
        self.inspector.metadata_requested.connect(self._on_metadata_requested)

        # Job queue signals
        self.job_queue.job_completed.connect(self._on_job_completed)

    def _on_filter_changed(self, category: FilterCategory) -> None:
        """Handle sidebar filter change.

        Args:
            category: The new FilterCategory.
        """
        self.file_list.set_category_filter(category)
        self.inspector.clear()
        self.delete_action.setEnabled(False)

        # Save filter setting
        settings = QSettings("VersionedFileManager", "VFM")
        settings.setValue("sidebar_filter", category.value)

    def _load_files(self) -> None:
        """Load all tracked files from the database."""
        # Include archived files so they can be shown in the Archived filter
        files = self.db_manager.get_all_files(include_archived=True)
        search_data = self.db_manager.get_all_files_search_data()
        self.file_list.set_files(files, search_data)

    def _on_file_selected(self, file_id: str) -> None:
        """Handle file selection.

        Args:
            file_id: The selected file's UUID.
        """
        tracked_file = self.file_service.get_file(file_id)
        if tracked_file:
            versions = self.file_service.get_versions(file_id)
            tags = self.file_service.get_file_tags(file_id)
            events = self.db_manager.get_events(file_id)
            metadata = self.db_manager.get_metadata(file_id)
            self.inspector.set_file(tracked_file, versions, tags, events, metadata)
            self.delete_action.setEnabled(True)
        else:
            self.delete_action.setEnabled(False)

    def _on_delete_selected(self) -> None:
        """Handle delete shortcut - delete currently selected file."""
        file_id = self.file_list.get_selected_file_id()
        if file_id:
            self._on_delete_file(file_id)

    def _on_focus_search(self) -> None:
        """Focus the search field."""
        self.file_list.search_field.setFocus()
        self.file_list.search_field.selectAll()

    def _on_file_double_clicked(self, file_id: str) -> None:
        """Handle file double-click to open the file.

        Args:
            file_id: The file's UUID.
        """
        app_path = self._open_with_map.get(file_id)
        if not self.file_service.open_file(file_id, app_path=app_path):
            QMessageBox.warning(
                self,
                "Cannot Open File",
                "The file could not be opened. It may be missing."
            )

    def _on_open_with(self, file_id: str | None = None) -> None:
        """Open selected file with chosen application, optionally saving preference."""
        if file_id is None:
            file_id = self.file_list.get_selected_file_id()
        if not file_id:
            QMessageBox.information(self, "Open With", "Select a file first.")
            return

        tracked_file = self.file_service.get_file(file_id)
        if not tracked_file:
            return

        last_app = self._open_with_map.get(file_id)
        choice = OpenWithDialog.get_choice(self, last_app=last_app, remember_checked=bool(last_app))
        if not choice:
            return

        if choice.always:
            self._open_with_map[file_id] = choice.app_path
            self._save_open_with()

        if not self.file_service.open_file(file_id, app_path=choice.app_path):
            QMessageBox.warning(self, "Cannot Open File", "The file could not be opened.")

    def _on_show_in_finder(self, file_id: str) -> None:
        """Handle show in Finder request.

        Args:
            file_id: The file's UUID.
        """
        if not self.file_service.show_in_finder(file_id):
            QMessageBox.warning(
                self,
                "Cannot Show File",
                "The file could not be revealed. It may be missing."
            )

    def _on_verify_file(self, file_id: str) -> None:
        """Handle verify single file request.

        Args:
            file_id: The file's UUID.
        """
        status = self.file_service.verify_file(file_id)
        tracked_file = self.file_service.get_file(file_id)

        if tracked_file:
            # Record event for non-OK status
            if status == FileStatus.MODIFIED:
                self.db_manager.create_event(
                    file_id, EventType.VERIFY_MODIFIED,
                    "File has been modified since last version"
                )
            elif status == FileStatus.MISSING:
                self.db_manager.create_event(
                    file_id, EventType.VERIFY_MISSING,
                    "File is missing from disk"
                )
            else:
                self.db_manager.create_event(
                    file_id, EventType.VERIFY_OK,
                    "File integrity verified"
                )

            self.file_list.update_file(tracked_file)
            # Update inspector if this file is selected
            if self.file_list.get_selected_file_id() == file_id:
                versions = self.file_service.get_versions(file_id)
                tags = self.file_service.get_file_tags(file_id)
                events = self.db_manager.get_events(file_id)
                self.inspector.set_file(tracked_file, versions, tags, events)

            status_text = {
                FileStatus.OK: "OK",
                FileStatus.MODIFIED: "Modified",
                FileStatus.MISSING: "Missing"
            }.get(status, status.value)
            self.statusBar().showMessage(f"Status: {status_text}", 3000)

    def _on_add_file(self) -> None:
        """Handle add file request."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Track",
            "",
            "All Files (*)"
        )

        if not file_path:
            return

        # Check if already tracked
        existing = self.db_manager.get_file_by_path(file_path)
        if existing:
            QMessageBox.information(
                self,
                "Already Tracked",
                f"This file is already being tracked as '{existing.display_name}'."
            )
            self.file_list.select_file(existing.id)
            return

        # Get commit message
        file_name = Path(file_path).name
        commit_message = CommitDialog.get_commit_message(
            parent=self,
            title="Add File",
            file_name=file_name,
            is_initial=True
        )

        if not commit_message:
            return

        try:
            tracked_file, version = self.file_service.register_file(
                file_path=file_path,
                commit_message=commit_message
            )
            self.file_list.add_file(tracked_file)
            # Update search data for the new file
            search_data = self.db_manager.get_file_search_data(tracked_file.id)
            self.file_list.update_search_data(tracked_file.id, search_data)
            self._on_file_selected(tracked_file.id)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to add file: {str(e)}"
            )

    def _on_files_dropped(self, file_paths: list[str]) -> None:
        """Handle files dropped onto the file list.

        Args:
            file_paths: List of dropped file paths.
        """
        added_count = 0
        skipped_count = 0
        last_added_file = None

        for file_path in file_paths:
            # Check if already tracked
            existing = self.db_manager.get_file_by_path(file_path)
            if existing:
                skipped_count += 1
                continue

            # Get commit message for each file
            file_name = Path(file_path).name
            commit_message = CommitDialog.get_commit_message(
                parent=self,
                title="Add File",
                file_name=file_name,
                is_initial=True
            )

            if not commit_message:
                # User cancelled, skip remaining files
                break

            try:
                tracked_file, version = self.file_service.register_file(
                    file_path=file_path,
                    commit_message=commit_message
                )
                self.file_list.add_file(tracked_file)
                # Update search data for the new file
                search_data = self.db_manager.get_file_search_data(tracked_file.id)
                self.file_list.update_search_data(tracked_file.id, search_data)
                last_added_file = tracked_file
                added_count += 1

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to add '{file_name}': {str(e)}"
                )

        # Show summary if multiple files were processed
        if added_count > 0:
            if last_added_file:
                self._on_file_selected(last_added_file.id)

            if added_count > 1 or skipped_count > 0:
                msg = f"Added {added_count} file(s)"
                if skipped_count > 0:
                    msg += f", {skipped_count} already tracked"
                self.statusBar().showMessage(msg, 3000)

    def _on_verify_all(self) -> None:
        """Handle verify all files request."""
        job = Job(job_type=JobType.VERIFY_ALL, description="Verify all files")
        self.job_queue.enqueue(job)
        self.statusBar().showMessage("Verification queued (Jobs ▸ Job Queue에서 확인)", 4000)

    def _on_show_jobs(self) -> None:
        """Show the job queue dialog (creates if not exists)."""
        if self.job_dialog is None:
            self.job_dialog = JobQueueDialog(self.job_queue, self)
        self.job_dialog.show()
        self.job_dialog.raise_()
        self.job_dialog.activateWindow()

    def _on_set_concurrency(self) -> None:
        """Prompt for max concurrent jobs and apply."""
        settings = QSettings("VersionedFileManager", "VFM")
        current = settings.value("job_queue_max_workers", 1, type=int)
        value, ok = QInputDialog.getInt(
            self,
            "Set Max Concurrent Jobs",
            "동시 실행 작업 수 (1-4):",
            value=current,
            min=1,
            max=4,
        )
        if not ok:
            return

        settings.setValue("job_queue_max_workers", value)
        self.job_queue.set_max_workers(value)
        self.statusBar().showMessage(f"Max concurrent jobs set to {value}", 3000)

    def _on_relink_scan(self) -> None:
        """Prompt for root folder and options, enqueue relink scan."""
        opts = RelinkDialog.get_options(
            parent=self,
            last_path=self._last_relink_root,
            last_use_hash=self._last_relink_hash,
            last_exts=self._last_relink_exts,
            last_max_size=settings.value("relink_max_size", None, type=str),
            last_within_days=settings.value("relink_within_days", None, type=str),
        )
        if not opts:
            return

        self._last_relink_root = opts.root_path
        self._last_relink_hash = opts.use_hash
        self._last_relink_exts = ",".join(opts.include_exts) if opts.include_exts else ""
        settings = QSettings("VersionedFileManager", "VFM")
        settings.setValue("relink_root", self._last_relink_root)
        settings.setValue("relink_use_hash", self._last_relink_hash)
        settings.setValue("relink_exts", self._last_relink_exts)
        settings.setValue("relink_max_size", str(opts.max_size_mb) if opts.max_size_mb else "")
        settings.setValue("relink_within_days", str(opts.modified_within_days) if opts.modified_within_days else "")

        job = Job(
            job_type=JobType.RELINK_SCAN,
            description=f"Relink scan • {opts.root_path}",
            payload={
                "root_path": opts.root_path,
                "use_hash": opts.use_hash,
                "exts": opts.include_exts,
                "max_size_mb": opts.max_size_mb,
                "within_days": opts.modified_within_days,
            },
        )
        self.job_queue.enqueue(job)
        self.statusBar().showMessage("Relink scan queued (Jobs ▸ Job Queue)", 4000)

    def _on_new_version(self, file_id: str) -> None:
        """Handle new version creation request.

        Args:
            file_id: The file's UUID.
        """
        tracked_file = self.file_service.get_file(file_id)
        if not tracked_file:
            return

        # Get commit message
        commit_message = CommitDialog.get_commit_message(
            parent=self,
            title="New Version",
            file_name=tracked_file.display_name,
            is_initial=False
        )

        if not commit_message:
            return

        try:
            version = self.file_service.create_new_version(
                file_id=file_id,
                commit_message=commit_message
            )

            # Refresh the file list and inspector
            updated_file = self.file_service.get_file(file_id)
            if updated_file:
                self.file_list.update_file(updated_file)
                # Update search data with new commit message
                search_data = self.db_manager.get_file_search_data(file_id)
                self.file_list.update_search_data(file_id, search_data)
                versions = self.file_service.get_versions(file_id)
                tags = self.file_service.get_file_tags(file_id)
                events = self.db_manager.get_events(file_id)
                self.inspector.set_file(updated_file, versions, tags, events)

            self.statusBar().showMessage(
                f"Created version {version.version_number}", 3000
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create version: {str(e)}"
            )

    def _on_delete_file(self, file_id: str) -> None:
        """Handle delete file request.

        Args:
            file_id: The file's UUID.
        """
        tracked_file = self.file_service.get_file(file_id)
        if not tracked_file:
            return

        # Get version count
        versions = self.file_service.get_versions(file_id)
        version_count = len(versions)

        # Check for saved default option
        settings = QSettings("VersionedFileManager", "VFM")
        saved_option = settings.value("default_delete_option", None)
        default_option = None
        if saved_option:
            try:
                default_option = DeleteOption(saved_option)
            except ValueError:
                pass

        # Show delete dialog
        option, remember = DeleteDialog.get_delete_option(
            tracked_file.display_name,
            version_count,
            self,
            default_option
        )

        if option is None:
            return  # Cancelled

        # Save preference if requested
        if remember:
            settings.setValue("default_delete_option", option.value)

        # Execute the selected action
        if option == DeleteOption.ARCHIVE:
            # Archive: hide from list but keep all data
            self.db_manager.set_archived(file_id, True)
            self.file_list.remove_file(file_id)
            self.inspector.clear()
            self.delete_action.setEnabled(False)
            self.statusBar().showMessage("File archived", 3000)

        elif option == DeleteOption.REMOVE:
            # Remove: delete from app, keep actual file
            self.file_service.delete_file(file_id)
            self.file_list.remove_file(file_id)
            self.inspector.clear()
            self.delete_action.setEnabled(False)
            self.statusBar().showMessage("File removed from tracking", 3000)

        elif option == DeleteOption.TRASH:
            # Trash: delete from app AND move actual file to trash
            import subprocess
            file_path = tracked_file.file_path

            # First delete from app
            self.file_service.delete_file(file_id)
            self.file_list.remove_file(file_id)
            self.inspector.clear()
            self.delete_action.setEnabled(False)

            # Then move to trash (macOS)
            try:
                subprocess.run(
                    ["osascript", "-e", f'tell application "Finder" to delete POSIX file "{file_path}"'],
                    check=True,
                    capture_output=True
                )
                self.statusBar().showMessage("File moved to Trash", 3000)
            except subprocess.CalledProcessError:
                self.statusBar().showMessage("File removed (could not move to Trash)", 3000)
            except FileNotFoundError:
                self.statusBar().showMessage("File removed (file was already missing)", 3000)

    def _on_open_version(self, file_id: str, version_number: int) -> None:
        """Handle open version request.

        Args:
            file_id: The file's UUID.
            version_number: The version number to open.
        """
        if not self.file_service.open_version(file_id, version_number):
            QMessageBox.warning(
                self,
                "Cannot Open Version",
                "The version backup file could not be opened."
            )

    def _on_restore_version(self, file_id: str, version_number: int) -> None:
        """Handle restore version request.

        Args:
            file_id: The file's UUID.
            version_number: The version number to restore.
        """
        tracked_file = self.file_service.get_file(file_id)
        if not tracked_file:
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Restore Version")
        msg_box.setText(f"Restore '{tracked_file.display_name}' to version {version_number}?")
        msg_box.setInformativeText(
            "This will overwrite the current file with the selected version.\n\n"
            "The current file state will be lost unless you create a new version first."
        )
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)

        if msg_box.exec() == QMessageBox.Yes:
            job = Job(
                job_type=JobType.RESTORE,
                description=f"Restore to v{version_number} • {tracked_file.display_name}",
                payload={"file_id": file_id, "version_number": version_number},
            )
            self.job_queue.enqueue(job)
            self.statusBar().showMessage("Restore queued (Jobs ▸ Job Queue)", 4000)

    def _on_show_version_in_finder(self, file_id: str, version_number: int) -> None:
        """Handle show version in Finder request.

        Args:
            file_id: The file's UUID.
            version_number: The version number to show.
        """
        if not self.file_service.show_version_in_finder(file_id, version_number):
            QMessageBox.warning(
                self,
                "Cannot Show Version",
                "The version backup file could not be revealed."
            )

    def _on_verify_version(self, file_id: str, version_number: int) -> None:
        """Handle verify version integrity request.

        Args:
            file_id: The file's UUID.
            version_number: The version number to verify.
        """
        result = self.file_service.verify_version_integrity(file_id, version_number)

        if result.is_valid:
            message = f"Version {version_number} integrity verified"
            self.inspector.show_verification_result(True, message)
            self.statusBar().showMessage(message, 3000)
        else:
            error_msg = result.error or "Unknown error"
            message = f"Version {version_number}: {error_msg}"
            self.inspector.show_verification_result(False, message)

    def _on_verify_all_versions(self, file_id: str) -> None:
        """Handle verify all versions request.

        Args:
            file_id: The file's UUID.
        """
        results = self.file_service.verify_all_versions(file_id)

        if not results:
            self.inspector.show_verification_result(False, "No versions to verify")
            return

        valid_count = sum(1 for r in results.values() if r.is_valid)
        total_count = len(results)

        if valid_count == total_count:
            message = f"All {total_count} version(s) verified successfully"
            self.inspector.show_verification_result(True, message)
            self.statusBar().showMessage(message, 3000)
        else:
            failed_versions = [v for v, r in results.items() if not r.is_valid]
            message = f"{valid_count}/{total_count} verified. Failed: v{', v'.join(map(str, failed_versions))}"
            self.inspector.show_verification_result(False, message)

    def _on_pin_version(self, file_id: str, version_number: int) -> None:
        """Handle pin/unpin version request.

        Args:
            file_id: The file's UUID.
            version_number: The version number to pin/unpin.
        """
        try:
            version = self.db_manager.get_version_by_number(file_id, version_number)
            if not version:
                raise ValueError("Version not found")

            if version.is_pinned:
                # Unpin is quick; do it inline
                success = self.file_service.unpin_version(file_id, version_number)
                if success:
                    updated_version = self.db_manager.get_version_by_number(file_id, version_number)
                    if updated_version:
                        self.inspector.update_version(updated_version)
                    self.db_manager.create_event(
                        file_id, EventType.UNPIN, f"Version {version_number} unpinned"
                    )
                    events = self.db_manager.get_events(file_id)
                    self.inspector.set_events(events)
                    self.statusBar().showMessage(f"Version {version_number} unpinned", 3000)
                else:
                    raise ValueError("Failed to unpin version")
            else:
                # Pin copy can be longer; queue it
                job = Job(
                    job_type=JobType.PIN_COPY,
                    description=f"Pin v{version_number} • {version.commit_message}",
                    payload={"file_id": file_id, "version_number": version_number},
                )
                self.job_queue.enqueue(job)
                self.statusBar().showMessage("Pin copy queued (Jobs ▸ Job Queue)", 4000)

        except ValueError as e:
            QMessageBox.warning(
                self,
                "Pin Failed",
                str(e)
            )
        except Exception as e:
            self.statusBar().showMessage(f"Failed to pin/unpin: {e}", 3000)

    def _on_show_pinned_version(self, file_id: str, version_number: int) -> None:
        """Handle show pinned version in Finder request.

        Args:
            file_id: The file's UUID.
            version_number: The version number to show.
        """
        if not self.file_service.show_pinned_version_in_finder(file_id, version_number):
            QMessageBox.warning(
                self,
                "Cannot Show Pinned Version",
                "The pinned file could not be revealed. It may have been moved or deleted."
            )

    def _on_tag_added(self, file_id: str, tag_name: str) -> None:
        """Handle tag added to a file.

        Args:
            file_id: The file's UUID.
            tag_name: The tag name to add.
        """
        try:
            self.file_service.add_tag_to_file(file_id, tag_name)
            # Refresh tags display
            tags = self.file_service.get_file_tags(file_id)
            self.inspector.set_tags(tags)
            # Update search data with new tag
            search_data = self.db_manager.get_file_search_data(file_id)
            self.file_list.update_search_data(file_id, search_data)
            self.statusBar().showMessage(f"Tag '{tag_name}' added", 2000)
        except Exception as e:
            self.statusBar().showMessage(f"Failed to add tag: {e}", 3000)

    def _on_tag_removed(self, file_id: str, tag_id: str) -> None:
        """Handle tag removed from a file.

        Args:
            file_id: The file's UUID.
            tag_id: The tag's UUID to remove.
        """
        try:
            self.file_service.remove_tag_from_file(file_id, tag_id)
            # Refresh tags display
            tags = self.file_service.get_file_tags(file_id)
            self.inspector.set_tags(tags)
            # Update search data with removed tag
            search_data = self.db_manager.get_file_search_data(file_id)
            self.file_list.update_search_data(file_id, search_data)
            self.statusBar().showMessage("Tag removed", 2000)
        except Exception as e:
            self.statusBar().showMessage(f"Failed to remove tag: {e}", 3000)

    def _on_metadata_requested(self, file_id: str) -> None:
        """Handle metadata extraction request."""
        try:
            meta = self.file_service.extract_metadata(file_id)
            self.inspector.set_metadata(meta)
            warning = meta.get("warning") if meta else None
            if warning:
                self.statusBar().showMessage(f"Metadata updated (note: {warning})", 4000)
            else:
                self.statusBar().showMessage("Metadata updated", 2000)
        except Exception as e:
            QMessageBox.warning(self, "Metadata", f"Failed to extract metadata: {e}")

    def _on_toggle_favorite(self, file_id: str) -> None:
        """Handle toggle favorite request.

        Args:
            file_id: The file's UUID.
        """
        try:
            is_favorite = self.db_manager.toggle_favorite(file_id)
            # Refresh the file in the list
            updated_file = self.file_service.get_file(file_id)
            if updated_file:
                self.file_list.update_file(updated_file)
                # Reapply filter in case we're in Favorites view
                self.file_list._apply_filter()

            status = "Added to" if is_favorite else "Removed from"
            self.statusBar().showMessage(f"{status} favorites", 2000)
        except Exception as e:
            self.statusBar().showMessage(f"Failed to update favorite: {e}", 3000)

    def _on_name_changed(self, file_id: str, new_name: str) -> None:
        """Handle file name change from inspector.

        Args:
            file_id: The file's UUID.
            new_name: The new display name.
        """
        try:
            self.db_manager.update_display_name(file_id, new_name)
            # Refresh the file in the list
            updated_file = self.file_service.get_file(file_id)
            if updated_file:
                self.file_list.update_file(updated_file)
            self.statusBar().showMessage(f"Renamed to '{new_name}'", 2000)
        except Exception as e:
            self.statusBar().showMessage(f"Failed to rename: {e}", 3000)

    def _on_rename_file(self, file_id: str, current_name: str) -> None:
        """Handle rename request from file list.

        Args:
            file_id: The file's UUID.
            current_name: The current display name.
        """
        new_name, ok = QInputDialog.getText(
            self,
            "Rename",
            "New name:",
            text=current_name
        )

        if ok and new_name.strip():
            new_name = new_name.strip()
            if new_name != current_name:
                self._on_name_changed(file_id, new_name)
                # Update inspector if this file is selected
                if self.file_list.get_selected_file_id() == file_id:
                    updated_file = self.file_service.get_file(file_id)
                    if updated_file:
                        self.inspector.name_edit.setText(new_name)

    def _on_unarchive_file(self, file_id: str) -> None:
        """Handle unarchive request from file list.

        Args:
            file_id: The file's UUID.
        """
        try:
            self.db_manager.unarchive_file(file_id)
            # Refresh file list to move the file out of Archived
            updated_file = self.file_service.get_file(file_id)
            if updated_file:
                # Update the file in the internal list
                self.file_list.update_file(updated_file)
                # Reapply filter to hide from Archived view
                self.file_list._apply_filter()
            self.inspector.clear()
            self.statusBar().showMessage("File restored from archive", 3000)
        except Exception as e:
            self.statusBar().showMessage(f"Failed to unarchive: {e}", 3000)
