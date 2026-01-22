from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


@dataclass
class OpenWithChoice:
    app_path: str
    always: bool


class OpenWithDialog(QDialog):
    """Dialog to pick an application to open a file with."""

    def __init__(self, parent=None, last_app: Optional[str] = None, remember_checked: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Open With")
        self.resize(440, 160)

        self.app_edit = QLineEdit(self)
        if last_app:
            self.app_edit.setText(last_app)
        browse_btn = QPushButton("Browse…", self)
        browse_btn.clicked.connect(self._on_browse)

        self.remember_checkbox = QCheckBox("Always use this app for this file")
        self.remember_checkbox.setChecked(remember_checked)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Application:"))
        path_layout.addWidget(self.app_edit)
        path_layout.addWidget(browse_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(path_layout)
        layout.addWidget(self.remember_checkbox)
        layout.addStretch()
        layout.addWidget(buttons)

    def _on_browse(self) -> None:
        app_path, _ = QFileDialog.getOpenFileName(self, "Select Application", "")
        if app_path:
            self.app_edit.setText(app_path)

    @staticmethod
    def get_choice(parent=None, last_app: Optional[str] = None, remember_checked: bool = False) -> Optional[OpenWithChoice]:
        dialog = OpenWithDialog(parent, last_app, remember_checked)
        if dialog.exec() == QDialog.Accepted:
            app_path = dialog.app_edit.text().strip()
            if not app_path:
                return None
            return OpenWithChoice(app_path=app_path, always=dialog.remember_checkbox.isChecked())
        return None
