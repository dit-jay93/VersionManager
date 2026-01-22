from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QCheckBox,
    QLineEdit,
)


@dataclass
class RelinkOptions:
    root_path: str
    use_hash: bool = False
    include_exts: list[str] | None = None
    max_size_mb: Optional[float] = None
    modified_within_days: Optional[int] = None


class RelinkDialog(QDialog):
    """Dialog to choose relink root and options."""

    def __init__(
        self,
        parent=None,
        last_path: Optional[str] = None,
        last_use_hash: bool = False,
        last_exts: Optional[str] = None,
        last_max_size: Optional[str] = None,
        last_within_days: Optional[str] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Relink Scan")
        self.resize(480, 220)

        self.root_edit = QLineEdit(self)
        if last_path:
            self.root_edit.setText(last_path)
        browse_btn = QPushButton("Browse…", self)
        browse_btn.clicked.connect(self._on_browse)

        self.hash_checkbox = QCheckBox("Use hash verification (slower)")
        self.hash_checkbox.setChecked(last_use_hash)

        self.ext_edit = QLineEdit(self)
        if last_exts:
            self.ext_edit.setText(last_exts)
        self.ext_edit.setPlaceholderText("e.g. mov,mp4,exr  (leave empty for all)")

        self.max_size_edit = QLineEdit(self)
        if last_max_size:
            self.max_size_edit.setText(last_max_size)
        self.max_size_edit.setPlaceholderText("Max size MB (optional)")

        self.within_days_edit = QLineEdit(self)
        if last_within_days:
            self.within_days_edit.setText(last_within_days)
        self.within_days_edit.setPlaceholderText("Modified within days (optional)")

        ext_layout = QHBoxLayout()
        ext_layout.addWidget(QLabel("Extension filter:"))
        ext_layout.addWidget(self.ext_edit)

        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Max size (MB):"))
        size_layout.addWidget(self.max_size_edit)

        days_layout = QHBoxLayout()
        days_layout.addWidget(QLabel("Modified within (days):"))
        days_layout.addWidget(self.within_days_edit)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Root folder:"))
        path_layout.addWidget(self.root_edit)
        path_layout.addWidget(browse_btn)

        buttons_layout = QHBoxLayout()
        ok_btn = QPushButton("Start")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addStretch()
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(path_layout)
        layout.addWidget(self.hash_checkbox)
        layout.addLayout(ext_layout)
        layout.addLayout(size_layout)
        layout.addLayout(days_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

    def _on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select relink root")
        if directory:
            self.root_edit.setText(directory)

    @staticmethod
    def get_options(
        parent=None,
        last_path: Optional[str] = None,
        last_use_hash: bool = False,
        last_exts: Optional[str] = None,
        last_max_size: Optional[str] = None,
        last_within_days: Optional[str] = None,
    ) -> Optional[RelinkOptions]:
        dialog = RelinkDialog(parent, last_path, last_use_hash, last_exts, last_max_size, last_within_days)
        if dialog.exec() == QDialog.Accepted:
            root = dialog.root_edit.text().strip()
            if not root:
                return None
            raw_exts = dialog.ext_edit.text().strip()
            exts = [e.strip().lower().lstrip(".") for e in raw_exts.split(",") if e.strip()] if raw_exts else None
            max_size_mb = dialog.max_size_edit.text().strip()
            within_days = dialog.within_days_edit.text().strip()
            return RelinkOptions(
                root_path=root,
                use_hash=dialog.hash_checkbox.isChecked(),
                include_exts=exts,
                max_size_mb=float(max_size_mb) if max_size_mb else None,
                modified_within_days=int(within_days) if within_days else None,
            )
        return None
