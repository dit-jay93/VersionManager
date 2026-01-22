"""File list component for displaying tracked files."""
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMenu, QApplication, QLineEdit, QComboBox
)
from PySide6.QtCore import Signal, Qt, QMimeData, QPoint, QEvent
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QAction, QClipboard, QKeyEvent

from database.models import TrackedFile, FileStatus
from ui.sidebar import FilterCategory


class FileListItem(QListWidgetItem):
    """Custom list item that holds TrackedFile data."""

    def __init__(self, tracked_file: TrackedFile):
        """Initialize the file list item.

        Args:
            tracked_file: The TrackedFile to display.
        """
        super().__init__()
        self.tracked_file = tracked_file
        self._update_display()

    def _update_display(self) -> None:
        """Update the item display text."""
        status_indicator = self._get_status_indicator()
        favorite_indicator = "⭐ " if self.tracked_file.is_favorite else ""
        type_icon = self._get_type_icon()
        self.setText(f"{status_indicator} {favorite_indicator}{type_icon}{self.tracked_file.display_name}")

    def _get_status_indicator(self) -> str:
        """Get status indicator symbol."""
        status_map = {
            FileStatus.OK: "●",
            FileStatus.MODIFIED: "◐",
            FileStatus.MISSING: "○"
        }
        return status_map.get(self.tracked_file.status, "?")

    def _get_type_icon(self) -> str:
        """Return a lightweight icon based on file extension."""
        name = self.tracked_file.file_path.lower()
        if name.endswith((".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm")):
            return "🎬 "
        if name.endswith((".mp3", ".wav", ".flac", ".aac")):
            return "🎵 "
        if name.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp")):
            return "🖼️ "
        if name.endswith((".psd", ".ai", ".fig")):
            return "🎨 "
        if name.endswith((".txt", ".md", ".rtf")):
            return "📄 "
        if name.endswith((".pdf",)):
            return "📕 "
        if name.endswith((".zip", ".tar", ".gz", ".7z", ".rar")):
            return "🗜️ "
        return ""

    def update_file(self, tracked_file: TrackedFile) -> None:
        """Update the tracked file data.

        Args:
            tracked_file: Updated TrackedFile.
        """
        self.tracked_file = tracked_file
        self._update_display()


class FileListWidget(QWidget):
    """Widget for displaying and managing the file list."""

    # Signals
    file_selected = Signal(str)  # Emits file_id
    file_double_clicked = Signal(str)  # Emits file_id
    add_file_requested = Signal()
    verify_requested = Signal()
    files_dropped = Signal(list)  # Emits list of file paths
    # Context menu signals
    open_file_requested = Signal(str)  # Emits file_id
    show_in_finder_requested = Signal(str)  # Emits file_id
    new_version_requested = Signal(str)  # Emits file_id
    delete_file_requested = Signal(str)  # Emits file_id
    verify_file_requested = Signal(str)  # Emits file_id
    toggle_favorite_requested = Signal(str)  # Emits file_id
    rename_requested = Signal(str, str)  # Emits (file_id, current_name)
    unarchive_requested = Signal(str)  # Emits file_id

    def __init__(self, parent=None):
        """Initialize the file list widget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._all_files: list[TrackedFile] = []  # Store all files for filtering
        self._category_filter = FilterCategory.ALL  # Current category filter
        self._search_data: dict[str, dict] = {}  # Extended search data (commit messages, tags)
        self._setup_ui()
        self._setup_context_menu()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the file list UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header with title and buttons
        header = QHBoxLayout()

        title = QLabel("Files")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title)

        header.addStretch()

        # Verify button
        self.verify_btn = QPushButton("Verify")
        self.verify_btn.setToolTip("Check all files for changes")
        header.addWidget(self.verify_btn)

        # Add file button
        self.add_btn = QPushButton("+ Add")
        self.add_btn.setToolTip("Add a file to track")
        header.addWidget(self.add_btn)

        layout.addLayout(header)

        # Search and sort row
        search_sort_row = QHBoxLayout()

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search name, path, commit, tag...")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self._on_search_changed)
        self.search_field.installEventFilter(self)
        search_sort_row.addWidget(self.search_field, stretch=1)

        sort_label = QLabel("Sort:")
        sort_label.setStyleSheet("color: gray;")
        search_sort_row.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Name (A-Z)", "name_asc")
        self.sort_combo.addItem("Name (Z-A)", "name_desc")
        self.sort_combo.addItem("Newest First", "date_desc")
        self.sort_combo.addItem("Oldest First", "date_asc")
        self.sort_combo.addItem("Status", "status")
        self.sort_combo.setCurrentIndex(2)  # Default to "Newest First"
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        search_sort_row.addWidget(self.sort_combo)

        layout.addLayout(search_sort_row)

        # File list
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_widget)

        # Status bar
        self.status_label = QLabel("No files")
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        self.add_btn.clicked.connect(self.add_file_requested.emit)
        self.verify_btn.clicked.connect(self.verify_requested.emit)
        self.list_widget.installEventFilter(self)

    def _setup_context_menu(self) -> None:
        """Set up the context menu."""
        self.context_menu = QMenu(self)

        self.open_action = QAction("Open", self)
        self.open_action.triggered.connect(self._on_context_open)
        self.context_menu.addAction(self.open_action)

        self.show_in_finder_action = QAction("Show in Finder", self)
        self.show_in_finder_action.triggered.connect(self._on_context_show_in_finder)
        self.context_menu.addAction(self.show_in_finder_action)

        self.copy_path_action = QAction("Copy Path", self)
        self.copy_path_action.triggered.connect(self._on_context_copy_path)
        self.context_menu.addAction(self.copy_path_action)

        self.context_menu.addSeparator()

        self.rename_action = QAction("Rename", self)
        self.rename_action.setShortcut("F2")
        self.rename_action.triggered.connect(self._on_context_rename)
        self.context_menu.addAction(self.rename_action)

        self.favorite_action = QAction("Add to Favorites", self)
        self.favorite_action.triggered.connect(self._on_context_toggle_favorite)
        self.context_menu.addAction(self.favorite_action)

        self.context_menu.addSeparator()

        self.verify_action = QAction("Verify", self)
        self.verify_action.triggered.connect(self._on_context_verify)
        self.context_menu.addAction(self.verify_action)

        self.new_version_action = QAction("New Version...", self)
        self.new_version_action.triggered.connect(self._on_context_new_version)
        self.context_menu.addAction(self.new_version_action)

        self.context_menu.addSeparator()

        self.unarchive_action = QAction("Unarchive", self)
        self.unarchive_action.triggered.connect(self._on_context_unarchive)
        self.context_menu.addAction(self.unarchive_action)

        self.delete_action = QAction("Remove", self)
        self.delete_action.triggered.connect(self._on_context_delete)
        self.context_menu.addAction(self.delete_action)

    def _show_context_menu(self, position: QPoint) -> None:
        """Show context menu at the given position."""
        item = self.list_widget.itemAt(position)
        if not isinstance(item, FileListItem):
            return

        # Update action states based on file status
        tracked_file = item.tracked_file
        is_archived = tracked_file.is_archived

        # Show/hide actions based on archived state
        self.unarchive_action.setVisible(is_archived)
        self.delete_action.setVisible(not is_archived)
        self.new_version_action.setVisible(not is_archived)
        self.favorite_action.setVisible(not is_archived)
        self.verify_action.setVisible(not is_archived)
        self.rename_action.setVisible(not is_archived)

        # Allow creating a new version unless the file is missing
        self.new_version_action.setEnabled(tracked_file.status != FileStatus.MISSING)

        # Update favorite action text
        if tracked_file.is_favorite:
            self.favorite_action.setText("Remove from Favorites")
        else:
            self.favorite_action.setText("Add to Favorites")

        # Store the file info for the context menu actions
        self._context_file_id = tracked_file.id
        self._context_file_path = tracked_file.file_path
        self._context_file_name = tracked_file.display_name

        # Show menu at cursor position
        self.context_menu.exec(self.list_widget.mapToGlobal(position))

    def _on_context_open(self) -> None:
        """Handle open action from context menu."""
        if hasattr(self, '_context_file_id'):
            self.open_file_requested.emit(self._context_file_id)

    def _on_context_show_in_finder(self) -> None:
        """Handle show in Finder action from context menu."""
        if hasattr(self, '_context_file_id'):
            self.show_in_finder_requested.emit(self._context_file_id)

    def _on_context_copy_path(self) -> None:
        """Handle copy path action from context menu."""
        if hasattr(self, '_context_file_path'):
            clipboard = QApplication.clipboard()
            clipboard.setText(self._context_file_path)

    def _on_context_verify(self) -> None:
        """Handle verify action from context menu."""
        if hasattr(self, '_context_file_id'):
            self.verify_file_requested.emit(self._context_file_id)

    def _on_context_new_version(self) -> None:
        """Handle new version action from context menu."""
        if hasattr(self, '_context_file_id'):
            self.new_version_requested.emit(self._context_file_id)

    def _on_context_delete(self) -> None:
        """Handle delete action from context menu."""
        if hasattr(self, '_context_file_id'):
            self.delete_file_requested.emit(self._context_file_id)

    def _on_context_toggle_favorite(self) -> None:
        """Handle toggle favorite action from context menu."""
        if hasattr(self, '_context_file_id'):
            self.toggle_favorite_requested.emit(self._context_file_id)

    def _on_context_rename(self) -> None:
        """Handle rename action from context menu."""
        if hasattr(self, '_context_file_id') and hasattr(self, '_context_file_name'):
            self.rename_requested.emit(self._context_file_id, self._context_file_name)

    def _on_context_unarchive(self) -> None:
        """Handle unarchive action from context menu."""
        if hasattr(self, '_context_file_id'):
            self.unarchive_requested.emit(self._context_file_id)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """Handle selection change."""
        if current and isinstance(current, FileListItem):
            self.file_selected.emit(current.tracked_file.id)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        """Handle double click."""
        if isinstance(item, FileListItem):
            self.file_double_clicked.emit(item.tracked_file.id)

    def set_files(self, files: list[TrackedFile], search_data: dict[str, dict] = None) -> None:
        """Set the list of files to display.

        Args:
            files: List of TrackedFile objects.
            search_data: Optional dict mapping file_id to search data.
        """
        self._all_files = list(files)
        if search_data is not None:
            self._search_data = search_data
        self._apply_filter()

    def set_search_data(self, search_data: dict[str, dict]) -> None:
        """Set the extended search data.

        Args:
            search_data: Dict mapping file_id to search data
                        (with 'commit_messages' and 'tags' keys).
        """
        self._search_data = search_data

    def update_search_data(self, file_id: str, data: dict) -> None:
        """Update search data for a specific file.

        Args:
            file_id: The file's UUID.
            data: Search data dict with 'commit_messages' and 'tags' keys.
        """
        self._search_data[file_id] = data

    def _on_search_changed(self, text: str) -> None:
        """Handle search text change."""
        self._apply_filter()

    def _on_sort_changed(self, index: int) -> None:
        """Handle sort option change."""
        self._apply_filter()

    def _sort_files(self, files: list[TrackedFile]) -> list[TrackedFile]:
        """Sort files based on current sort option."""
        sort_key = self.sort_combo.currentData()

        if sort_key == "name_asc":
            return sorted(files, key=lambda f: f.display_name.lower())
        elif sort_key == "name_desc":
            return sorted(files, key=lambda f: f.display_name.lower(), reverse=True)
        elif sort_key == "date_desc":
            return sorted(files, key=lambda f: f.created_at, reverse=True)
        elif sort_key == "date_asc":
            return sorted(files, key=lambda f: f.created_at)
        elif sort_key == "status":
            # Sort by status: MODIFIED first, then MISSING, then OK
            status_order = {FileStatus.MODIFIED: 0, FileStatus.MISSING: 1, FileStatus.OK: 2}
            return sorted(files, key=lambda f: (status_order.get(f.status, 3), f.display_name.lower()))
        return files

    def _apply_filter(self) -> None:
        """Apply the current search filter, category filter, and sort to the file list."""
        search_text = self.search_field.text().lower().strip()
        self.list_widget.clear()

        # Apply category filter first
        category_filtered = self._filter_by_category(self._all_files)

        # Apply search filter
        filtered_files = []
        for tracked_file in category_filtered:
            if not search_text or self._matches_search(tracked_file, search_text):
                filtered_files.append(tracked_file)

        # Sort files
        sorted_files = self._sort_files(filtered_files)

        # Add to list widget
        for tracked_file in sorted_files:
            item = FileListItem(tracked_file)
            self.list_widget.addItem(item)

        self._update_status_label(len(filtered_files), len(self._all_files))

    def _matches_search(self, tracked_file: TrackedFile, search_text: str) -> bool:
        """Check if a file matches the search text.

        Searches across display name, file path, commit messages, and tags.

        Args:
            tracked_file: The file to check.
            search_text: The search text (lowercase).

        Returns:
            True if the file matches the search text.
        """
        # Check display name
        if search_text in tracked_file.display_name.lower():
            return True

        # Check file path
        if search_text in tracked_file.file_path.lower():
            return True

        # Check extended search data (commit messages and tags)
        file_data = self._search_data.get(tracked_file.id, {})

        # Check commit messages
        for message in file_data.get('commit_messages', []):
            if search_text in message.lower():
                return True

        # Check tags (support searching with or without #)
        search_tag = search_text.lstrip('#')
        for tag in file_data.get('tags', []):
            if search_tag in tag.lower():
                return True

        return False

    def _filter_by_category(self, files: list[TrackedFile]) -> list[TrackedFile]:
        """Filter files by the current category.

        Args:
            files: List of TrackedFile objects.

        Returns:
            Filtered list of TrackedFile objects.
        """
        if self._category_filter == FilterCategory.ALL:
            # Exclude archived files from "All Files"
            return [f for f in files if not f.is_archived]
        elif self._category_filter == FilterCategory.FAVORITES:
            # Show only favorite files (excluding archived)
            return [f for f in files if f.is_favorite and not f.is_archived]
        elif self._category_filter == FilterCategory.MODIFIED:
            # Show files with MODIFIED or MISSING status (excluding archived)
            return [f for f in files if f.status in (FileStatus.MODIFIED, FileStatus.MISSING) and not f.is_archived]
        elif self._category_filter == FilterCategory.RECENT:
            # Show files created or modified in the last 7 days (excluding archived)
            cutoff = datetime.now() - timedelta(days=7)
            recent_files = []
            for f in files:
                if f.is_archived:
                    continue
                try:
                    created = datetime.fromisoformat(f.created_at.replace('Z', '+00:00'))
                    # Remove timezone info for comparison
                    if created.tzinfo:
                        created = created.replace(tzinfo=None)
                    if created >= cutoff:
                        recent_files.append(f)
                except (ValueError, AttributeError):
                    # If parsing fails, include the file
                    recent_files.append(f)
            return recent_files
        elif self._category_filter == FilterCategory.ARCHIVED:
            # Show only archived files
            return [f for f in files if f.is_archived]
        return files

    def set_category_filter(self, category: FilterCategory) -> None:
        """Set the category filter.

        Args:
            category: The FilterCategory to filter by.
        """
        if category != self._category_filter:
            self._category_filter = category
            self._apply_filter()

    def update_file(self, tracked_file: TrackedFile) -> None:
        """Update a single file in the list.

        Args:
            tracked_file: Updated TrackedFile.
        """
        # Update in _all_files
        for i, f in enumerate(self._all_files):
            if f.id == tracked_file.id:
                self._all_files[i] = tracked_file
                break

        # Update in visible list
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if isinstance(item, FileListItem) and item.tracked_file.id == tracked_file.id:
                item.update_file(tracked_file)
                break

    def add_file(self, tracked_file: TrackedFile) -> None:
        """Add a new file to the list.

        Args:
            tracked_file: The TrackedFile to add.
        """
        # Add to _all_files
        self._all_files.insert(0, tracked_file)

        # Add to visible list if matches filter
        search_text = self.search_field.text().lower().strip()
        if not search_text or search_text in tracked_file.display_name.lower():
            item = FileListItem(tracked_file)
            self.list_widget.insertItem(0, item)
            self.list_widget.setCurrentItem(item)

        self._update_status_label(self.list_widget.count(), len(self._all_files))

    def remove_file(self, file_id: str) -> None:
        """Remove a file from the list.

        Args:
            file_id: The file's UUID.
        """
        # Remove from _all_files
        self._all_files = [f for f in self._all_files if f.id != file_id]

        # Remove from visible list
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if isinstance(item, FileListItem) and item.tracked_file.id == file_id:
                self.list_widget.takeItem(i)
                break

        self._update_status_label(self.list_widget.count(), len(self._all_files))

    def get_selected_file_id(self) -> str | None:
        """Get the currently selected file ID.

        Returns:
            The selected file's UUID or None.
        """
        current = self.list_widget.currentItem()
        if isinstance(current, FileListItem):
            return current.tracked_file.id
        return None

    def select_file(self, file_id: str) -> None:
        """Select a file by ID.

        Args:
            file_id: The file's UUID.
        """
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if isinstance(item, FileListItem) and item.tracked_file.id == file_id:
                self.list_widget.setCurrentItem(item)
                break

    def _update_status_label(self, visible_count: int, total_count: int = None) -> None:
        """Update the status label with file count."""
        if total_count is None:
            total_count = visible_count

        if total_count == 0:
            self.status_label.setText("No files - drag files here to add")
        elif visible_count == total_count:
            if total_count == 1:
                self.status_label.setText("1 file")
            else:
                self.status_label.setText(f"{total_count} files")
        else:
            self.status_label.setText(f"{visible_count} of {total_count} files")

    def eventFilter(self, obj, event: QEvent) -> bool:
        """Handle events for filtered objects."""
        # Check for search_field events
        if hasattr(self, 'search_field') and obj == self.search_field and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_Escape:
                if self.search_field.text():
                    self.search_field.clear()
                else:
                    if hasattr(self, 'list_widget'):
                        self.list_widget.setFocus()
                return True
        # Check for list_widget events
        elif hasattr(self, 'list_widget') and obj == self.list_widget and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_F2:
                current = self.list_widget.currentItem()
                if isinstance(current, FileListItem):
                    self.rename_requested.emit(
                        current.tracked_file.id,
                        current.tracked_file.display_name
                    )
                return True
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            # Check if any URL is a file (not directory)
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        """Handle drag move event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop event."""
        file_paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                # Only accept files, not directories
                import os
                if os.path.isfile(path):
                    file_paths.append(path)

        if file_paths:
            event.acceptProposedAction()
            self.files_dropped.emit(file_paths)
        else:
            event.ignore()
