"""Theme management for the application.

SwiftUI-inspired light style by default with soft cards and accent blue.
Supports a compact mode for narrow widths.
"""
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


def apply_dark_theme(app: QApplication, *, compact: bool = False) -> None:
    """Apply dark theme to the application (refreshed styling)."""
    palette = QPalette()

    # Base colors
    palette.setColor(QPalette.Window, QColor(20, 22, 25))
    palette.setColor(QPalette.WindowText, QColor(236, 238, 241))
    palette.setColor(QPalette.Base, QColor(28, 30, 34))
    palette.setColor(QPalette.AlternateBase, QColor(32, 34, 38))
    palette.setColor(QPalette.ToolTipBase, QColor(36, 38, 42))
    palette.setColor(QPalette.ToolTipText, QColor(236, 238, 241))
    palette.setColor(QPalette.Text, QColor(236, 238, 241))
    palette.setColor(QPalette.Button, QColor(35, 38, 43))
    palette.setColor(QPalette.ButtonText, QColor(236, 238, 241))
    palette.setColor(QPalette.BrightText, QColor(255, 255, 255))
    palette.setColor(QPalette.Link, QColor(105, 181, 255))
    palette.setColor(QPalette.Highlight, QColor(71, 145, 255))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))

    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))

    app.setPalette(palette)

    app.setStyleSheet(DARK_STYLE_COMPACT if compact else DARK_STYLE)


def apply_light_theme(app: QApplication, *, compact: bool = False) -> None:
    """Apply SwiftUI-like light theme with soft cards."""

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f6f8fb"))
    palette.setColor(QPalette.WindowText, QColor("#0f172a"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f1f5f9"))
    palette.setColor(QPalette.ToolTipBase, QColor("#0f172a"))
    palette.setColor(QPalette.ToolTipText, QColor("#e2e8f0"))
    palette.setColor(QPalette.Text, QColor("#0f172a"))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor("#0f172a"))
    palette.setColor(QPalette.Link, QColor("#0a84ff"))
    palette.setColor(QPalette.Highlight, QColor("#0a84ff"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    app.setStyleSheet(LIGHT_STYLE_COMPACT if compact else LIGHT_STYLE)


DARK_STYLE = """
        QWidget { background-color: #14171c; color: #e6e8ec; }
        QToolTip { background-color: #1f2229; color: #e6e8ec; border: 1px solid #2e323a; padding: 6px 8px; }
        QMenu { background-color: #1b1e24; border: 1px solid #2d3037; }
        QMenu::item:selected { background-color: #2f7bff; }
        QMenuBar { background: transparent; }
        QMenuBar::item:selected { background: #2f7bff; }
        QGroupBox { border: 1px solid #2d323c; border-radius: 8px; margin-top: 10px; padding: 10px 10px 12px 10px; }
        QGroupBox::title { color: #e6e8ec; subcontrol-origin: margin; left: 8px; }
        QLineEdit, QComboBox, QTextEdit { background: #1f232c; border: 1px solid #2e323c; border-radius: 10px; padding: 8px 10px; color: #e6e8ec; }
        QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border: 1px solid #2f7bff; }
        QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a82ff, stop:1 #2f6df6); border: none; color: #ffffff; padding: 8px 14px; border-radius: 10px; font-weight: 600; }
        QPushButton:flat { background: transparent; color: #e6e8ec; }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a8cff, stop:1 #2d62f2); color: #ffffff; }
        QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d62f2, stop:1 #2044a8); color: #ffffff; }
        QPushButton:checked { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d62f2, stop:1 #2044a8); color: #ffffff; }
        QPushButton:flat:pressed, QPushButton:flat:checked { color: #e6e8ec; background: rgba(255,255,255,0.06); }
        QPushButton:disabled { background: #1f232c; color: #7a7f87; }
        QListWidget { background: #171a20; border: 1px solid #262a33; border-radius: 12px; padding: 6px; }
        QListWidget::item { padding: 8px 10px; }
        QListWidget::item:selected { background: rgba(47,123,255,0.18); border-radius: 8px; }
        QListWidget::item:hover { background: rgba(255,255,255,0.05); border-radius: 8px; }
        QScrollBar:vertical { background: #1b1f26; width: 12px; margin: 4px; border-radius: 6px; }
        QScrollBar::handle:vertical { background: #2c3240; border-radius: 6px; min-height: 24px; }
        QScrollBar::handle:vertical:hover { background: #3a82ff; }
        QScrollBar:horizontal { background: #1b1f26; height: 12px; margin: 4px; border-radius: 6px; }
        QScrollBar::handle:horizontal { background: #2c3240; border-radius: 6px; min-width: 24px; }
        QScrollBar::handle:horizontal:hover { background: #3a82ff; }
        QLabel#versionMessage { background: #14171c; padding: 10px; border-radius: 10px; border: 1px solid #262c36; }
"""

DARK_STYLE_COMPACT = """
        QWidget { background-color: #14171c; color: #e6e8ec; }
        QGroupBox { border-radius: 6px; padding: 8px 8px 10px 8px; }
        QLineEdit, QComboBox, QTextEdit { border-radius: 8px; padding: 6px 8px; }
        QPushButton { padding: 7px 12px; border-radius: 8px; }
        QListWidget { border-radius: 10px; padding: 4px; }
        QListWidget::item { padding: 6px 8px; }
        QLabel#versionMessage { padding: 8px; border-radius: 8px; }
"""

LIGHT_STYLE = """
        QWidget { background-color: #f6f8fb; color: #0f172a; }
        QToolTip { background: #0f172a; color: #e2e8f0; border: 1px solid #1e293b; padding: 6px 8px; }
        QMenu { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; }
        QMenu::item { padding: 8px 12px; }
        QMenu::item:selected { background: rgba(10,132,255,0.12); }
        QMenuBar { background: transparent; }
        QMenuBar::item:selected { background: rgba(10,132,255,0.12); }
        QGroupBox { border: 1px solid #e2e8f0; border-radius: 12px; margin-top: 10px; padding: 10px 10px 12px 10px; background: #ffffff; }
        QGroupBox::title { color: #0f172a; subcontrol-origin: margin; left: 10px; }
        QLineEdit, QComboBox, QTextEdit { background: #ffffff; border: 1px solid #d7dde7; border-radius: 12px; padding: 10px 12px; color: #0f172a; }
        QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border: 1px solid #0a84ff; }
        QPushButton {
            background: #ffffff;
            border: 1px solid #d7dde7;
            color: #0f172a;
            padding: 9px 16px;
            border-radius: 12px;
            font-weight: 600;
        }
        QPushButton:flat { background: transparent; color: #0f172a; border: none; }
        QPushButton:hover { background: rgba(10,132,255,0.12); color: #0f172a; }
        QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0b7aea, stop:1 #0a60c8); color: #ffffff; border: none; }
        QPushButton:checked { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0b7aea, stop:1 #0a60c8); color: #ffffff; border: none; }
        QPushButton:flat:pressed, QPushButton:flat:checked { color: #0f172a; background: rgba(15,23,42,0.08); }
        QPushButton:disabled { background: #e2e8f0; color: #94a3b8; border: 1px solid #e2e8f0; }
        QListWidget { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 8px; }
        QListWidget::item { padding: 10px 12px; }
        QListWidget::item:selected { background: rgba(10,132,255,0.12); border-radius: 10px; }
        QListWidget::item:hover { background: rgba(15,23,42,0.04); border-radius: 10px; }
        QScrollBar:vertical { background: #eef2f7; width: 12px; margin: 4px; border-radius: 8px; }
        QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 8px; min-height: 28px; }
        QScrollBar::handle:vertical:hover { background: #0a84ff; }
        QScrollBar:horizontal { background: #eef2f7; height: 12px; margin: 4px; border-radius: 8px; }
        QScrollBar::handle:horizontal { background: #cbd5e1; border-radius: 8px; min-width: 28px; }
        QScrollBar::handle:horizontal:hover { background: #0a84ff; }
        QLabel#versionMessage { background: #ffffff; padding: 12px; border-radius: 12px; border: 1px solid #e2e8f0; }
"""

LIGHT_STYLE_COMPACT = """
        QWidget { background-color: #f6f8fb; color: #0f172a; }
        QGroupBox { border-radius: 10px; padding: 8px 8px 10px 8px; }
        QLineEdit, QComboBox, QTextEdit { border-radius: 10px; padding: 8px 10px; }
        QPushButton { padding: 8px 12px; border-radius: 10px; }
        QListWidget { border-radius: 12px; padding: 6px; }
        QListWidget::item { padding: 8px 10px; }
        QLabel#versionMessage { padding: 10px; border-radius: 10px; }
"""
