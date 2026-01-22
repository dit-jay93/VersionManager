"""Commit message dialog for version creation."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QDialogButtonBox
)
from PySide6.QtCore import Qt


class CommitDialog(QDialog):
    """Dialog for entering commit messages."""

    def __init__(
        self,
        parent=None,
        title: str = "New Version",
        file_name: str = "",
        is_initial: bool = False
    ):
        """Initialize the commit dialog.

        Args:
            parent: Parent widget.
            title: Dialog title.
            file_name: Name of the file being committed.
            is_initial: Whether this is the initial version.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)

        self._file_name = file_name
        self._is_initial = is_initial
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        if self._file_name:
            if self._is_initial:
                header_text = f"Adding: {self._file_name}"
            else:
                header_text = f"New version for: {self._file_name}"
            header = QLabel(header_text)
            header.setStyleSheet("font-weight: bold;")
            layout.addWidget(header)

        # Message label
        message_label = QLabel("Commit message (required):")
        layout.addWidget(message_label)

        # Message input
        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText("Describe the changes...")
        self.message_edit.setMaximumHeight(100)
        layout.addWidget(self.message_edit)

        # Character count
        self.char_count = QLabel("0 characters")
        self.char_count.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.char_count)

        self.message_edit.textChanged.connect(self._on_text_changed)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton("Commit")
        self.ok_btn.setDefault(True)
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(button_layout)

    def _on_text_changed(self) -> None:
        """Handle text change in the message field."""
        text = self.message_edit.toPlainText().strip()
        char_count = len(text)

        self.char_count.setText(f"{char_count} characters")
        self.ok_btn.setEnabled(char_count > 0)

    def get_message(self) -> str:
        """Get the entered commit message.

        Returns:
            The commit message text.
        """
        return self.message_edit.toPlainText().strip()

    @staticmethod
    def get_commit_message(
        parent=None,
        title: str = "New Version",
        file_name: str = "",
        is_initial: bool = False
    ) -> str | None:
        """Show the dialog and return the commit message.

        Args:
            parent: Parent widget.
            title: Dialog title.
            file_name: Name of the file.
            is_initial: Whether this is the initial version.

        Returns:
            The commit message or None if cancelled.
        """
        dialog = CommitDialog(
            parent=parent,
            title=title,
            file_name=file_name,
            is_initial=is_initial
        )

        if dialog.exec() == QDialog.Accepted:
            return dialog.get_message()
        return None
