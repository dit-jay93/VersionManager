"""Sidebar navigation component."""
from enum import Enum

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal


class FilterCategory(Enum):
    """Filter categories for the sidebar."""
    ALL = "all"
    FAVORITES = "favorites"
    RECENT = "recent"
    MODIFIED = "modified"
    ARCHIVED = "archived"


class Sidebar(QWidget):
    """Sidebar for navigation with filter functionality."""

    # Signal emitted when filter category changes
    filter_changed = Signal(FilterCategory)

    def __init__(self, parent=None):
        """Initialize the sidebar.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._current_filter = FilterCategory.ALL
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the sidebar UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("Navigation")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(180)

        # Add filter items with associated data
        self._filter_items = [
            ("All Files", FilterCategory.ALL),
            ("⭐ Favorites", FilterCategory.FAVORITES),
            ("Recent", FilterCategory.RECENT),
            ("Modified", FilterCategory.MODIFIED),
            ("Archived", FilterCategory.ARCHIVED),
        ]

        for item_text, category in self._filter_items:
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, category)
            self.nav_list.addItem(item)

        # Select "All Files" by default
        self.nav_list.setCurrentRow(0)

        layout.addWidget(self.nav_list)
        layout.addStretch()

        # Set fixed width for sidebar
        self.setMinimumWidth(150)
        self.setMaximumWidth(200)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.nav_list.currentItemChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """Handle filter selection change.

        Args:
            current: The newly selected item.
            previous: The previously selected item.
        """
        if current:
            category = current.data(Qt.UserRole)
            if category and category != self._current_filter:
                self._current_filter = category
                self.filter_changed.emit(category)

    def get_current_filter(self) -> FilterCategory:
        """Get the current filter category.

        Returns:
            The current FilterCategory.
        """
        return self._current_filter

    def set_filter(self, category: FilterCategory) -> None:
        """Set the current filter category.

        Args:
            category: The FilterCategory to set.
        """
        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            if item.data(Qt.UserRole) == category:
                self.nav_list.setCurrentItem(item)
                break
