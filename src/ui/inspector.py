"""Inspector panel for displaying file details and version history."""
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QGroupBox, QFormLayout, QScrollArea, QMenu, QLineEdit,
    QFrame, QSizePolicy, QTextEdit
)
from PySide6.QtCore import Signal, Qt, QPoint
from PySide6.QtGui import QAction

from database.models import TrackedFile, Version, FileStatus, Tag, Event


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def format_datetime(iso_string: str) -> str:
    """Format ISO datetime string for display."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_string


class TagChip(QFrame):
    """A clickable tag chip widget."""

    remove_clicked = Signal(str)  # Emits tag_id

    def __init__(self, tag: Tag, parent=None):
        """Initialize the tag chip."""
        super().__init__(parent)
        self.tag = tag
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the chip UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)

        # Tag name label
        self.label = QLabel(self.tag.display_name)
        self.label.setStyleSheet("color: #1976d2; font-size: 11px;")
        layout.addWidget(self.label)

        # Remove button
        self.remove_btn = QPushButton("×")
        self.remove_btn.setFixedSize(14, 14)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #666;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #d32f2f;
            }
        """)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        layout.addWidget(self.remove_btn)

        # Chip styling
        self.setStyleSheet("""
            TagChip {
                background-color: #e3f2fd;
                border: 1px solid #90caf9;
                border-radius: 10px;
            }
        """)
        self.setFixedHeight(22)

    def _on_remove_clicked(self) -> None:
        """Handle remove button click."""
        self.remove_clicked.emit(self.tag.id)


class TagsWidget(QWidget):
    """Widget for displaying and managing tags."""

    tag_added = Signal(str)  # Emits tag_name
    tag_removed = Signal(str)  # Emits tag_id

    def __init__(self, parent=None):
        """Initialize the tags widget."""
        super().__init__(parent)
        self._tags: list[Tag] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Tags container (flow layout simulation)
        self.tags_container = QWidget()
        self.tags_layout = QHBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(4)
        self.tags_layout.addStretch()
        layout.addWidget(self.tags_container)

        # Add tag input
        input_layout = QHBoxLayout()
        input_layout.setSpacing(4)

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Add tag (e.g. #final)")
        self.tag_input.setMaximumHeight(24)
        self.tag_input.returnPressed.connect(self._on_add_tag)
        input_layout.addWidget(self.tag_input)

        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(24, 24)
        self.add_btn.setToolTip("Add tag")
        self.add_btn.clicked.connect(self._on_add_tag)
        input_layout.addWidget(self.add_btn)

        layout.addLayout(input_layout)

    def set_tags(self, tags: list[Tag]) -> None:
        """Set the tags to display."""
        self._tags = tags
        self._rebuild_chips()

    def _rebuild_chips(self) -> None:
        """Rebuild the tag chips."""
        # Clear existing chips
        while self.tags_layout.count() > 1:  # Keep the stretch
            item = self.tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new chips
        for tag in self._tags:
            chip = TagChip(tag)
            chip.remove_clicked.connect(self._on_tag_remove)
            self.tags_layout.insertWidget(self.tags_layout.count() - 1, chip)

    def _on_add_tag(self) -> None:
        """Handle add tag action."""
        tag_name = self.tag_input.text().strip()
        if tag_name:
            self.tag_added.emit(tag_name)
            self.tag_input.clear()

    def _on_tag_remove(self, tag_id: str) -> None:
        """Handle tag removal."""
        self.tag_removed.emit(tag_id)

    def clear(self) -> None:
        """Clear all tags."""
        self._tags = []
        self._rebuild_chips()
        self.tag_input.clear()


class EditableLabel(QWidget):
    """A label that becomes editable on double-click."""

    text_changed = Signal(str)  # Emits new text when editing is confirmed

    def __init__(self, parent=None):
        """Initialize the editable label."""
        super().__init__(parent)
        self._setup_ui()
        self._editing = False

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Display label (shown when not editing)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setCursor(Qt.PointingHandCursor)
        self.label.setToolTip("Double-click to edit")
        layout.addWidget(self.label)

        # Edit line (shown when editing)
        self.line_edit = QLineEdit()
        self.line_edit.setVisible(False)
        self.line_edit.returnPressed.connect(self._confirm_edit)
        self.line_edit.editingFinished.connect(self._on_editing_finished)
        layout.addWidget(self.line_edit)

        # Edit button
        self.edit_btn = QPushButton("✎")
        self.edit_btn.setFixedSize(20, 20)
        self.edit_btn.setToolTip("Edit name")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
                border-radius: 2px;
            }
        """)
        self.edit_btn.clicked.connect(self._start_edit)
        layout.addWidget(self.edit_btn)

    def setText(self, text: str) -> None:
        """Set the label text."""
        self.label.setText(text)
        self._original_text = text

    def text(self) -> str:
        """Get the current text."""
        return self.label.text()

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click to start editing."""
        self._start_edit()

    def _start_edit(self) -> None:
        """Start editing mode."""
        if self._editing:
            return
        self._editing = True
        self.label.setVisible(False)
        self.edit_btn.setVisible(False)
        self.line_edit.setText(self.label.text())
        self.line_edit.setVisible(True)
        self.line_edit.setFocus()
        self.line_edit.selectAll()

    def _confirm_edit(self) -> None:
        """Confirm the edit and emit signal if changed."""
        new_text = self.line_edit.text().strip()
        if new_text and new_text != self._original_text:
            self.label.setText(new_text)
            self._original_text = new_text
            self.text_changed.emit(new_text)
        self._end_edit()

    def _on_editing_finished(self) -> None:
        """Handle editing finished (blur, escape, etc.)."""
        if self._editing:
            self._confirm_edit()

    def _end_edit(self) -> None:
        """End editing mode."""
        self._editing = False
        self.line_edit.setVisible(False)
        self.label.setVisible(True)
        self.edit_btn.setVisible(True)

    def setEnabled(self, enabled: bool) -> None:
        """Enable or disable the widget."""
        super().setEnabled(enabled)
        self.edit_btn.setVisible(enabled)


class EventListItem(QListWidgetItem):
    """Custom list item for event display."""

    def __init__(self, event: Event):
        """Initialize the event list item."""
        super().__init__()
        self.event = event
        self._update_display()

    def _update_display(self) -> None:
        """Update the item display text."""
        created = format_datetime(self.event.created_at)
        icon = self.event.display_icon
        name = self.event.display_name
        self.setText(f"{icon} {name} - {created}")
        if self.event.description:
            self.setToolTip(self.event.description)


class TimelineWidget(QWidget):
    """Widget for displaying event timeline."""

    def __init__(self, parent=None):
        """Initialize the timeline widget."""
        super().__init__(parent)
        self._events: list[Event] = []
        self._order_desc = True
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header with sort toggle
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)

        self.sort_btn = QPushButton("Newest First")
        self.sort_btn.setFixedHeight(22)
        self.sort_btn.setToolTip("Toggle sort order")
        self.sort_btn.clicked.connect(self._toggle_sort)
        header_layout.addWidget(self.sort_btn)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Events list
        self.events_list = QListWidget()
        self.events_list.setMaximumHeight(120)
        self.events_list.setStyleSheet("QListWidget { font-size: 11px; }")
        layout.addWidget(self.events_list)

        # Empty state label
        self.empty_label = QLabel("No events recorded")
        self.empty_label.setStyleSheet("color: gray; font-size: 11px;")
        self.empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_label)

    def set_events(self, events: list[Event]) -> None:
        """Set the events to display."""
        self._events = events
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Rebuild the events list."""
        self.events_list.clear()

        if not self._events:
            self.events_list.setVisible(False)
            self.empty_label.setVisible(True)
            return

        self.events_list.setVisible(True)
        self.empty_label.setVisible(False)

        # Sort events based on current order
        sorted_events = sorted(
            self._events,
            key=lambda e: e.created_at,
            reverse=self._order_desc
        )

        for event in sorted_events:
            item = EventListItem(event)
            self.events_list.addItem(item)

    def _toggle_sort(self) -> None:
        """Toggle sort order."""
        self._order_desc = not self._order_desc
        self.sort_btn.setText("Newest First" if self._order_desc else "Oldest First")
        self._rebuild_list()

    def clear(self) -> None:
        """Clear the timeline."""
        self._events = []
        self.events_list.clear()
        self.events_list.setVisible(False)
        self.empty_label.setVisible(True)


class VersionListItem(QListWidgetItem):
    """Custom list item for version display."""

    def __init__(self, version: Version):
        """Initialize the version list item."""
        super().__init__()
        self.version = version
        self._update_display()

    def _update_display(self) -> None:
        """Update the item display text."""
        created = format_datetime(self.version.created_at)
        size = format_file_size(self.version.file_size)
        pin_indicator = "📌 " if self.version.is_pinned else ""
        self.setText(f"{pin_indicator}v{self.version.version_number} - {created} ({size})")
        tooltip = self.version.commit_message
        if self.version.is_pinned and self.version.pinned_path:
            tooltip += f"\n\n📌 Pinned: {self.version.pinned_path}"
        self.setToolTip(tooltip)

    def update_version(self, version: Version) -> None:
        """Update the version data."""
        self.version = version
        self._update_display()


class InspectorPanel(QWidget):
    """Panel for displaying file details and version history."""

    # Signals
    new_version_requested = Signal(str)  # Emits file_id
    delete_file_requested = Signal(str)  # Emits file_id
    # Version action signals
    open_version_requested = Signal(str, int)  # Emits (file_id, version_number)
    restore_version_requested = Signal(str, int)  # Emits (file_id, version_number)
    show_version_in_finder_requested = Signal(str, int)  # Emits (file_id, version_number)
    verify_version_requested = Signal(str, int)  # Emits (file_id, version_number)
    verify_all_versions_requested = Signal(str)  # Emits file_id
    pin_version_requested = Signal(str, int)  # Emits (file_id, version_number)
    show_pinned_version_requested = Signal(str, int)  # Emits (file_id, version_number)
    # Tag signals
    tag_added = Signal(str, str)  # Emits (file_id, tag_name)
    tag_removed = Signal(str, str)  # Emits (file_id, tag_id)
    # Name edit signal
    name_changed = Signal(str, str)  # Emits (file_id, new_name)
    # Metadata
    metadata_requested = Signal(str)  # Emits file_id

    def __init__(self, parent=None):
        """Initialize the inspector panel."""
        super().__init__(parent)
        self._current_file_id: str | None = None
        self._setup_ui()
        self._setup_version_context_menu()
        self._connect_signals()
        self.clear()

    def _setup_ui(self) -> None:
        """Set up the inspector UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Title with type badge
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)

        self.title_label = QLabel("Inspector")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_row.addWidget(self.title_label)

        self.type_badge = QLabel("")
        self.type_badge.setStyleSheet(
            "background: #e2e8f0; color: #0f172a; border-radius: 10px; padding: 2px 8px; font-size: 11px;"
        )
        self.type_badge.setVisible(False)
        title_row.addWidget(self.type_badge)
        title_row.addStretch()

        layout.addLayout(title_row)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)

        # File info group
        self.info_group = QGroupBox("File Information")
        info_layout = QFormLayout(self.info_group)

        self.name_edit = EditableLabel()
        self.name_edit.text_changed.connect(self._on_name_changed)
        info_layout.addRow("Name:", self.name_edit)

        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: gray; font-size: 11px;")
        info_layout.addRow("Path:", self.path_label)

        self.status_label = QLabel()
        info_layout.addRow("Status:", self.status_label)

        self.size_label = QLabel()
        info_layout.addRow("Size:", self.size_label)

        self.created_label = QLabel()
        info_layout.addRow("Added:", self.created_label)

        self.hash_label = QLabel()
        self.hash_label.setWordWrap(True)
        self.hash_label.setStyleSheet("color: gray; font-size: 10px; font-family: 'Menlo', 'Monaco', 'Courier New', monospace;")
        info_layout.addRow("Hash:", self.hash_label)

        # Tags widget
        self.tags_widget = TagsWidget()
        self.tags_widget.tag_added.connect(self._on_tag_added)
        self.tags_widget.tag_removed.connect(self._on_tag_removed)
        info_layout.addRow("Tags:", self.tags_widget)

        self.content_layout.addWidget(self.info_group)

        # Version history group
        self.version_group = QGroupBox("Version History")
        version_layout = QVBoxLayout(self.version_group)

        self.version_list = QListWidget()
        self.version_list.setMaximumHeight(180)
        self.version_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.version_list.customContextMenuRequested.connect(self._show_version_context_menu)
        version_layout.addWidget(self.version_list)

        # Selected version details
        self.version_message_label = QLabel()
        self.version_message_label.setWordWrap(True)
        self.version_message_label.setObjectName("versionMessage")
        version_layout.addWidget(self.version_message_label)

        # Version action buttons
        version_buttons = QHBoxLayout()

        self.open_version_btn = QPushButton("Open")
        self.open_version_btn.setToolTip("Open this version")
        self.open_version_btn.setEnabled(False)
        version_buttons.addWidget(self.open_version_btn)

        self.restore_btn = QPushButton("Restore")
        self.restore_btn.setToolTip("Restore file to this version")
        self.restore_btn.setEnabled(False)
        version_buttons.addWidget(self.restore_btn)

        self.verify_btn = QPushButton("Verify")
        self.verify_btn.setToolTip("Verify this version's integrity")
        self.verify_btn.setEnabled(False)
        version_buttons.addWidget(self.verify_btn)

        version_layout.addLayout(version_buttons)

        # Pin button row
        pin_buttons = QHBoxLayout()

        self.pin_btn = QPushButton("📌 Pin")
        self.pin_btn.setToolTip("Pin this version to separate storage")
        self.pin_btn.setEnabled(False)
        pin_buttons.addWidget(self.pin_btn)

        self.show_pinned_btn = QPushButton("Show Pinned")
        self.show_pinned_btn.setToolTip("Show pinned file in Finder")
        self.show_pinned_btn.setEnabled(False)
        self.show_pinned_btn.setVisible(False)
        pin_buttons.addWidget(self.show_pinned_btn)

        pin_buttons.addStretch()

        version_layout.addLayout(pin_buttons)

        # Verify all button
        self.verify_all_btn = QPushButton("Verify All Versions")
        self.verify_all_btn.setToolTip("Verify integrity of all version backups")
        self.verify_all_btn.setEnabled(False)
        version_layout.addWidget(self.verify_all_btn)

        # Verification result label
        self.verify_result_label = QLabel()
        self.verify_result_label.setWordWrap(True)
        self.verify_result_label.setVisible(False)
        version_layout.addWidget(self.verify_result_label)

        self.content_layout.addWidget(self.version_group)

        # Events timeline group
        self.timeline_group = QGroupBox("Events Timeline")
        timeline_layout = QVBoxLayout(self.timeline_group)
        self.timeline_widget = TimelineWidget()
        timeline_layout.addWidget(self.timeline_widget)
        self.content_layout.addWidget(self.timeline_group)

        # Metadata group
        self.metadata_group = QGroupBox("Metadata")
        meta_layout = QVBoxLayout(self.metadata_group)
        meta_btn_layout = QHBoxLayout()
        self.metadata_refresh_btn = QPushButton("Extract metadata")
        self.metadata_refresh_btn.clicked.connect(self._on_metadata_refresh)
        meta_btn_layout.addWidget(self.metadata_refresh_btn)
        meta_btn_layout.addStretch()
        meta_layout.addLayout(meta_btn_layout)

        self.metadata_view = QTextEdit()
        self.metadata_view.setReadOnly(True)
        self.metadata_view.setFixedHeight(140)
        meta_layout.addWidget(self.metadata_view)

        self.content_layout.addWidget(self.metadata_group)
        self.metadata_group.setVisible(False)

        # File action buttons
        file_buttons_layout = QHBoxLayout()

        self.new_version_btn = QPushButton("New Version")
        self.new_version_btn.setToolTip("Create a new version of this file")
        self.new_version_btn.setEnabled(False)
        file_buttons_layout.addWidget(self.new_version_btn)

        self.delete_btn = QPushButton("Remove")
        self.delete_btn.setToolTip("Stop tracking this file")
        file_buttons_layout.addWidget(self.delete_btn)

        self.content_layout.addLayout(file_buttons_layout)
        self.content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Set minimum width
        self.setMinimumWidth(250)

    def _setup_version_context_menu(self) -> None:
        """Set up context menu for version list."""
        self.version_context_menu = QMenu(self)

        self.ctx_open_action = QAction("Open Version", self)
        self.ctx_open_action.triggered.connect(self._on_context_open_version)
        self.version_context_menu.addAction(self.ctx_open_action)

        self.ctx_show_action = QAction("Show in Finder", self)
        self.ctx_show_action.triggered.connect(self._on_context_show_version)
        self.version_context_menu.addAction(self.ctx_show_action)

        self.version_context_menu.addSeparator()

        self.ctx_pin_action = QAction("📌 Pin Version", self)
        self.ctx_pin_action.triggered.connect(self._on_context_pin_version)
        self.version_context_menu.addAction(self.ctx_pin_action)

        self.ctx_show_pinned_action = QAction("Show Pinned in Finder", self)
        self.ctx_show_pinned_action.triggered.connect(self._on_context_show_pinned)
        self.version_context_menu.addAction(self.ctx_show_pinned_action)

        self.version_context_menu.addSeparator()

        self.ctx_verify_action = QAction("Verify Integrity", self)
        self.ctx_verify_action.triggered.connect(self._on_context_verify_version)
        self.version_context_menu.addAction(self.ctx_verify_action)

        self.version_context_menu.addSeparator()

        self.ctx_restore_action = QAction("Restore to This Version", self)
        self.ctx_restore_action.triggered.connect(self._on_context_restore_version)
        self.version_context_menu.addAction(self.ctx_restore_action)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.new_version_btn.clicked.connect(self._on_new_version_clicked)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.version_list.currentItemChanged.connect(self._on_version_selected)
        self.version_list.itemDoubleClicked.connect(self._on_version_double_clicked)
        self.open_version_btn.clicked.connect(self._on_open_version_clicked)
        self.restore_btn.clicked.connect(self._on_restore_clicked)
        self.verify_btn.clicked.connect(self._on_verify_clicked)
        self.verify_all_btn.clicked.connect(self._on_verify_all_clicked)
        self.pin_btn.clicked.connect(self._on_pin_clicked)
        self.show_pinned_btn.clicked.connect(self._on_show_pinned_clicked)

    def _get_selected_version(self) -> Version | None:
        """Get the currently selected version."""
        current = self.version_list.currentItem()
        if isinstance(current, VersionListItem):
            return current.version
        return None

    def _on_new_version_clicked(self) -> None:
        """Handle new version button click."""
        if self._current_file_id:
            self.new_version_requested.emit(self._current_file_id)

    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        if self._current_file_id:
            self.delete_file_requested.emit(self._current_file_id)

    def _on_version_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """Handle version selection."""
        if isinstance(current, VersionListItem):
            version = current.version
            self.version_message_label.setText(version.commit_message)
            self.open_version_btn.setEnabled(True)
            self.restore_btn.setEnabled(True)
            self.verify_btn.setEnabled(True)
            # Hide previous verification result when selection changes
            self.verify_result_label.setVisible(False)
            # Update pin button state
            self._update_pin_button(version)
        else:
            self.version_message_label.setText("")
            self.open_version_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
            self.verify_btn.setEnabled(False)
            self.pin_btn.setEnabled(False)
            self.show_pinned_btn.setEnabled(False)
            self.show_pinned_btn.setVisible(False)

    def _update_pin_button(self, version) -> None:
        """Update pin button state based on version."""
        self.pin_btn.setEnabled(True)
        if version.is_pinned:
            self.pin_btn.setText("📍 Unpin")
            self.pin_btn.setToolTip("Remove from pin storage")
            self.show_pinned_btn.setEnabled(True)
            self.show_pinned_btn.setVisible(True)
        else:
            self.pin_btn.setText("📌 Pin")
            self.pin_btn.setToolTip("Pin this version to separate storage")
            self.show_pinned_btn.setEnabled(False)
            self.show_pinned_btn.setVisible(False)

    def _on_version_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle version double click - open the version."""
        if isinstance(item, VersionListItem) and self._current_file_id:
            self.open_version_requested.emit(
                self._current_file_id, item.version.version_number
            )

    def _on_open_version_clicked(self) -> None:
        """Handle open version button click."""
        version = self._get_selected_version()
        if version and self._current_file_id:
            self.open_version_requested.emit(
                self._current_file_id, version.version_number
            )

    def _on_restore_clicked(self) -> None:
        """Handle restore button click."""
        version = self._get_selected_version()
        if version and self._current_file_id:
            self.restore_version_requested.emit(
                self._current_file_id, version.version_number
            )

    def _show_version_context_menu(self, position: QPoint) -> None:
        """Show context menu for version list."""
        item = self.version_list.itemAt(position)
        if isinstance(item, VersionListItem):
            self._context_version = item.version
            # Update pin action text based on pin status
            if item.version.is_pinned:
                self.ctx_pin_action.setText("📍 Unpin Version")
                self.ctx_show_pinned_action.setVisible(True)
            else:
                self.ctx_pin_action.setText("📌 Pin Version")
                self.ctx_show_pinned_action.setVisible(False)
            self.version_context_menu.exec(
                self.version_list.mapToGlobal(position)
            )

    def _on_context_open_version(self) -> None:
        """Handle open version from context menu."""
        if hasattr(self, '_context_version') and self._current_file_id:
            self.open_version_requested.emit(
                self._current_file_id, self._context_version.version_number
            )

    def _on_context_show_version(self) -> None:
        """Handle show version in finder from context menu."""
        if hasattr(self, '_context_version') and self._current_file_id:
            self.show_version_in_finder_requested.emit(
                self._current_file_id, self._context_version.version_number
            )

    def _on_context_restore_version(self) -> None:
        """Handle restore version from context menu."""
        if hasattr(self, '_context_version') and self._current_file_id:
            self.restore_version_requested.emit(
                self._current_file_id, self._context_version.version_number
            )

    def _on_context_verify_version(self) -> None:
        """Handle verify version from context menu."""
        if hasattr(self, '_context_version') and self._current_file_id:
            self.verify_version_requested.emit(
                self._current_file_id, self._context_version.version_number
            )

    def _on_context_pin_version(self) -> None:
        """Handle pin/unpin version from context menu."""
        if hasattr(self, '_context_version') and self._current_file_id:
            self.pin_version_requested.emit(
                self._current_file_id, self._context_version.version_number
            )

    def _on_context_show_pinned(self) -> None:
        """Handle show pinned version from context menu."""
        if hasattr(self, '_context_version') and self._current_file_id:
            self.show_pinned_version_requested.emit(
                self._current_file_id, self._context_version.version_number
            )

    def _on_verify_clicked(self) -> None:
        """Handle verify button click."""
        version = self._get_selected_version()
        if version and self._current_file_id:
            self.verify_version_requested.emit(
                self._current_file_id, version.version_number
            )

    def _on_verify_all_clicked(self) -> None:
        """Handle verify all button click."""
        if self._current_file_id:
            self.verify_all_versions_requested.emit(self._current_file_id)

    def _on_pin_clicked(self) -> None:
        """Handle pin/unpin button click."""
        version = self._get_selected_version()
        if version and self._current_file_id:
            self.pin_version_requested.emit(
                self._current_file_id, version.version_number
            )

    def _on_show_pinned_clicked(self) -> None:
        """Handle show pinned button click."""
        version = self._get_selected_version()
        if version and self._current_file_id:
            self.show_pinned_version_requested.emit(
                self._current_file_id, version.version_number
            )

    def show_verification_result(self, is_valid: bool, message: str) -> None:
        """Display the verification result.

        Args:
            is_valid: Whether the verification passed.
            message: Result message to display.
        """
        if is_valid:
            self.verify_result_label.setStyleSheet(
                "color: green; background-color: #e8f5e9; padding: 8px; border-radius: 4px;"
            )
            self.verify_result_label.setText(f"✓ {message}")
        else:
            self.verify_result_label.setStyleSheet(
                "color: red; background-color: #ffebee; padding: 8px; border-radius: 4px;"
            )
            self.verify_result_label.setText(f"✗ {message}")
        self.verify_result_label.setVisible(True)

    def clear(self) -> None:
        """Clear the inspector panel."""
        self._current_file_id = None

        self.name_edit.setText("-")
        self.name_edit.setEnabled(False)
        self.path_label.setText("-")
        self.status_label.setText("-")
        self.size_label.setText("-")
        self.created_label.setText("-")
        self.hash_label.setText("-")

        self.version_list.clear()
        self.version_message_label.setText("Select a file to view details")

        self.new_version_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.open_version_btn.setEnabled(False)
        self.restore_btn.setEnabled(False)
        self.verify_btn.setEnabled(False)
        self.verify_all_btn.setEnabled(False)
        self.verify_result_label.setVisible(False)
        self.pin_btn.setEnabled(False)
        self.pin_btn.setText("📌 Pin")
        self.show_pinned_btn.setEnabled(False)
        self.show_pinned_btn.setVisible(False)
        self.tags_widget.clear()
        self.timeline_widget.clear()
        if hasattr(self, "metadata_view"):
            self.metadata_view.clear()
        if hasattr(self, "metadata_group"):
            self.metadata_group.setVisible(False)
        if hasattr(self, "type_badge"):
            self.type_badge.setVisible(False)

    def set_file(
        self,
        tracked_file: TrackedFile,
        versions: list[Version],
        tags: list[Tag] = None,
        events: list[Event] = None,
        metadata: dict | None = None,
    ) -> None:
        """Set the file to display in the inspector."""
        self._current_file_id = tracked_file.id

        # Update file info
        self.name_edit.setText(tracked_file.display_name)
        self.name_edit.setEnabled(True)
        self.path_label.setText(tracked_file.file_path)
        self._set_status(tracked_file.status)
        self.size_label.setText(format_file_size(tracked_file.file_size))
        self.created_label.setText(format_datetime(tracked_file.created_at))

        # Display hash (truncated for readability)
        if tracked_file.file_hash:
            short_hash = tracked_file.file_hash[:16] + "..."
            self.hash_label.setText(short_hash)
            self.hash_label.setToolTip(tracked_file.file_hash)
        else:
            self.hash_label.setText("-")
            self.hash_label.setToolTip("")

        # Update version list
        self.version_list.clear()
        for version in versions:
            item = VersionListItem(version)
            self.version_list.addItem(item)

        # Select the latest version
        if self.version_list.count() > 0:
            self.version_list.setCurrentRow(0)

        # Enable new version unless file is missing
        self.new_version_btn.setEnabled(tracked_file.status != FileStatus.MISSING)
        self.delete_btn.setEnabled(True)
        self.verify_all_btn.setEnabled(len(versions) > 0)
        self.verify_result_label.setVisible(False)

        # Update tags
        if tags is not None:
            self.tags_widget.set_tags(tags)
        else:
            self.tags_widget.clear()

        # Update events timeline
        if events is not None:
            self.timeline_widget.set_events(events)
        else:
            self.timeline_widget.clear()

        self._populate_metadata(metadata or {})
        self.metadata_group.setVisible(True)
        self._set_type_badge(metadata)

    def set_events(self, events: list[Event]) -> None:
        """Update just the events timeline."""
        self.timeline_widget.set_events(events)

    def set_metadata(self, metadata: dict) -> None:
        """Update just the metadata view."""
        self._populate_metadata(metadata)

    def _populate_metadata(self, metadata: dict) -> None:
        if not hasattr(self, "metadata_view"):
            return
        if not metadata:
            self.metadata_view.setPlainText("No metadata")
            return

        lines = []
        warning = metadata.get("warning")
        if warning:
            lines.append(f"Warning: {warning}")

        for key in ["extension", "file_size", "modified_time", "width", "height", "duration", "codec", "type"]:
            if key in metadata:
                value = metadata[key]
                if key == "file_size":
                    value = format_file_size(value)
                elif key == "modified_time":
                    try:
                        value = format_datetime(datetime.fromtimestamp(value).isoformat())
                    except Exception:
                        pass
                elif key == "duration":
                    value = self._format_seconds(value)
                lines.append(f"{key}: {value}")

        exif = metadata.get("exif", {}) or {}
        if exif:
            lines.append("EXIF:")
            for k, v in exif.items():
                lines.append(f"  {k}: {v}")

        self.metadata_view.setPlainText("\n".join(lines))

    def _set_type_badge(self, metadata: dict | None) -> None:
        if not hasattr(self, "type_badge"):
            return
        meta = metadata or {}
        badge_text = None
        badge_color = "#e2e8f0"
        if meta.get("type") == "video":
            badge_text = "Video"
            badge_color = "#e0f2fe"
        elif meta.get("width") and meta.get("height"):
            badge_text = "Image"
            badge_color = "#ecfeff"
        elif meta.get("extension"):
            badge_text = meta.get("extension").lstrip(".").upper()

        if badge_text:
            self.type_badge.setText(badge_text)
            self.type_badge.setStyleSheet(
                f"background: {badge_color}; color: #0f172a; border-radius: 10px; padding: 2px 8px; font-size: 11px;"
            )
            self.type_badge.setVisible(True)
        else:
            self.type_badge.setVisible(False)

    def _format_seconds(self, secs) -> str:
        try:
            secs = float(secs)
        except Exception:
            return str(secs)
        m, s = divmod(int(secs), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:d}:{s:02d}"

    def _on_metadata_refresh(self) -> None:
        if self._current_file_id:
            self.metadata_requested.emit(self._current_file_id)

    def set_tags(self, tags: list[Tag]) -> None:
        """Update just the tags display."""
        self.tags_widget.set_tags(tags)

    def _on_tag_added(self, tag_name: str) -> None:
        """Handle tag added from widget."""
        if self._current_file_id:
            self.tag_added.emit(self._current_file_id, tag_name)

    def _on_tag_removed(self, tag_id: str) -> None:
        """Handle tag removed from widget."""
        if self._current_file_id:
            self.tag_removed.emit(self._current_file_id, tag_id)

    def _on_name_changed(self, new_name: str) -> None:
        """Handle name changed from editable label."""
        if self._current_file_id:
            self.name_changed.emit(self._current_file_id, new_name)

    def _set_status(self, status: FileStatus) -> None:
        """Set the status label with appropriate styling."""
        status_styles = {
            FileStatus.OK: ("OK", "color: green;"),
            FileStatus.MODIFIED: ("Modified", "color: orange;"),
            FileStatus.MISSING: ("Missing", "color: red;")
        }
        text, style = status_styles.get(status, (status.value, ""))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(style)

    def update_status(self, status: FileStatus) -> None:
        """Update just the status display."""
        self._set_status(status)
        self.new_version_btn.setEnabled(status != FileStatus.MISSING)

    def add_version(self, version: Version) -> None:
        """Add a new version to the list."""
        item = VersionListItem(version)
        self.version_list.insertItem(0, item)
        self.version_list.setCurrentRow(0)

    def update_version(self, version: Version) -> None:
        """Update a version in the list."""
        for i in range(self.version_list.count()):
            item = self.version_list.item(i)
            if isinstance(item, VersionListItem) and item.version.version_number == version.version_number:
                item.update_version(version)
                # Update buttons if this is the selected version
                if self.version_list.currentRow() == i:
                    self._update_pin_button(version)
                break
