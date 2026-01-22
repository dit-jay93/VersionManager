"""Versioned File Manager - Application entry point."""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


def get_db_path() -> str:
    """Get the path to the SQLite database file.

    Returns:
        Absolute path to the database file.
    """
    # Database is stored in the data directory relative to src
    app_dir = Path(__file__).parent.parent
    db_path = app_dir / "data" / "app.db"
    return str(db_path)


def main() -> int:
    """Application entry point.

    Returns:
        Exit code.
    """
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Versioned File Manager")
    app.setApplicationVersion("0.1")

    # Create and show main window
    db_path = get_db_path()
    window = MainWindow(db_path)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
