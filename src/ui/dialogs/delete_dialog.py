"""Delete options dialog for file removal."""
from enum import Enum

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QCheckBox, QFrame
)
from PySide6.QtCore import Qt


class DeleteOption(Enum):
    """Options for file deletion."""
    ARCHIVE = "archive"  # Hide from list, keep data
    REMOVE = "remove"    # Remove from app, keep actual file
    TRASH = "trash"      # Move actual file to trash


class DeleteDialog(QDialog):
    """Dialog for selecting delete options."""

    def __init__(self, file_name: str, version_count: int, parent=None):
        """Initialize the delete dialog.

        Args:
            file_name: Name of the file to delete.
            version_count: Number of versions for this file.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.file_name = file_name
        self.version_count = version_count
        self._selected_option = DeleteOption.ARCHIVE
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Remove File")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Header
        header_label = QLabel(f"Remove '{self.file_name}'?")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header_label)

        # Info
        version_text = "1 version" if self.version_count == 1 else f"{self.version_count} versions"
        info_label = QLabel(f"This file has {version_text} of history.")
        info_label.setStyleSheet("color: gray;")
        layout.addWidget(info_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #ddd;")
        layout.addWidget(separator)

        # Options label
        options_label = QLabel("Choose an action:")
        layout.addWidget(options_label)

        # Radio buttons
        self.button_group = QButtonGroup(self)

        # Option 1: Archive
        self.archive_radio = QRadioButton("Archive")
        self.archive_radio.setChecked(True)
        self.button_group.addButton(self.archive_radio)
        layout.addWidget(self.archive_radio)

        archive_desc = QLabel("Hide from the file list. Can be restored from Archive.")
        archive_desc.setStyleSheet("color: gray; font-size: 11px; margin-left: 20px;")
        layout.addWidget(archive_desc)

        # Option 2: Remove from app
        self.remove_radio = QRadioButton("Remove from App")
        self.button_group.addButton(self.remove_radio)
        layout.addWidget(self.remove_radio)

        remove_desc = QLabel("Delete all version history. The actual file on disk is kept.")
        remove_desc.setStyleSheet("color: gray; font-size: 11px; margin-left: 20px;")
        layout.addWidget(remove_desc)

        # Option 3: Move to Trash
        self.trash_radio = QRadioButton("Move to Trash")
        self.button_group.addButton(self.trash_radio)
        layout.addWidget(self.trash_radio)

        trash_desc = QLabel("Delete version history AND move the actual file to Trash.")
        trash_desc.setStyleSheet("color: #d32f2f; font-size: 11px; margin-left: 20px;")
        layout.addWidget(trash_desc)

        # Spacer
        layout.addSpacing(8)

        # Remember choice checkbox
        self.remember_checkbox = QCheckBox("Remember my choice")
        self.remember_checkbox.setStyleSheet("color: gray;")
        layout.addWidget(self.remember_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("Confirm")
        self.confirm_btn.setDefault(True)
        self.confirm_btn.clicked.connect(self._on_confirm)
        button_layout.addWidget(self.confirm_btn)

        layout.addLayout(button_layout)

    def _on_confirm(self) -> None:
        """Handle confirm button click."""
        if self.archive_radio.isChecked():
            self._selected_option = DeleteOption.ARCHIVE
        elif self.remove_radio.isChecked():
            self._selected_option = DeleteOption.REMOVE
        elif self.trash_radio.isChecked():
            self._selected_option = DeleteOption.TRASH
        self.accept()

    def get_selected_option(self) -> DeleteOption:
        """Get the selected delete option."""
        return self._selected_option

    def should_remember(self) -> bool:
        """Check if the user wants to remember the choice."""
        return self.remember_checkbox.isChecked()

    @staticmethod
    def get_delete_option(
        file_name: str,
        version_count: int,
        parent=None,
        default_option: DeleteOption = None
    ) -> tuple[DeleteOption | None, bool]:
        """Show the dialog and return the selected option.

        Args:
            file_name: Name of the file.
            version_count: Number of versions.
            parent: Parent widget.
            default_option: If set, skip dialog and return this option.

        Returns:
            Tuple of (selected option or None if cancelled, remember choice).
        """
        if default_option is not None:
            return default_option, False

        dialog = DeleteDialog(file_name, version_count, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_selected_option(), dialog.should_remember()
        return None, False
