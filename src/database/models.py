"""Data models for the Versioned File Manager."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


@dataclass
class Project:
    """Represents a project for grouping files."""
    id: str
    name: str
    description: Optional[str]
    color: str  # Hex color for UI
    created_at: str

    @classmethod
    def from_row(cls, row: tuple) -> "Project":
        """Create a Project from a database row."""
        return cls(
            id=row[0],
            name=row[1],
            description=row[2],
            color=row[3],
            created_at=row[4]
        )


class FileStatus(Enum):
    """Status of a tracked file."""
    OK = "OK"
    MODIFIED = "MODIFIED"
    MISSING = "MISSING"


class EventType(Enum):
    """Type of file event."""
    RESTORE = "RESTORE"
    PIN = "PIN"
    UNPIN = "UNPIN"
    DELETE = "DELETE"
    VERIFY_OK = "VERIFY_OK"
    VERIFY_MODIFIED = "VERIFY_MODIFIED"
    VERIFY_MISSING = "VERIFY_MISSING"
    RELINK = "RELINK"


@dataclass
class TrackedFile:
    """Represents a file being tracked for version management."""
    id: str
    display_name: str
    file_path: str
    file_size: int
    modified_time: float
    status: FileStatus
    created_at: str
    file_hash: Optional[str] = None
    is_favorite: bool = False
    is_archived: bool = False
    project_id: Optional[str] = None

    @classmethod
    def from_row(cls, row: tuple) -> "TrackedFile":
        """Create a TrackedFile from a database row."""
        return cls(
            id=row[0],
            display_name=row[1],
            file_path=row[2],
            file_size=row[3],
            modified_time=row[4],
            status=FileStatus(row[5]),
            created_at=row[6],
            file_hash=row[7] if len(row) > 7 else None,
            is_favorite=bool(row[8]) if len(row) > 8 else False,
            is_archived=bool(row[9]) if len(row) > 9 else False,
            project_id=row[10] if len(row) > 10 else None
        )


@dataclass
class Version:
    """Represents a version snapshot of a tracked file."""
    id: str
    file_id: str
    version_number: int
    commit_message: str
    file_size: int
    modified_time: float
    created_at: str
    file_hash: Optional[str] = None
    is_pinned: bool = False
    pinned_path: Optional[str] = None

    @classmethod
    def from_row(cls, row: tuple) -> "Version":
        """Create a Version from a database row."""
        return cls(
            id=row[0],
            file_id=row[1],
            version_number=row[2],
            commit_message=row[3],
            file_size=row[4],
            modified_time=row[5],
            created_at=row[6],
            file_hash=row[7] if len(row) > 7 else None,
            is_pinned=bool(row[8]) if len(row) > 8 else False,
            pinned_path=row[9] if len(row) > 9 else None
        )


@dataclass
class Tag:
    """Represents a tag for organizing files."""
    id: str
    name: str  # Stored as lowercase without #
    created_at: str

    @classmethod
    def from_row(cls, row: tuple) -> "Tag":
        """Create a Tag from a database row."""
        return cls(
            id=row[0],
            name=row[1],
            created_at=row[2]
        )

    @property
    def display_name(self) -> str:
        """Return the tag name with # prefix for UI display."""
        return f"#{self.name}"

    @staticmethod
    def normalize(tag_name: str) -> str:
        """Normalize a tag name for storage.

        Removes # prefix and converts to lowercase.
        """
        name = tag_name.strip()
        if name.startswith("#"):
            name = name[1:]
        return name.lower()


@dataclass
class Event:
    """Represents an event in the file's history timeline."""
    id: str
    file_id: str
    event_type: EventType
    description: Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, row: tuple) -> "Event":
        """Create an Event from a database row."""
        return cls(
            id=row[0],
            file_id=row[1],
            event_type=EventType(row[2]),
            description=row[3],
            created_at=row[4]
        )

    @property
    def display_icon(self) -> str:
        """Return an icon for the event type."""
        icons = {
            EventType.RESTORE: "↩",
            EventType.PIN: "📌",
            EventType.UNPIN: "📍",
            EventType.DELETE: "🗑",
            EventType.VERIFY_OK: "✓",
            EventType.VERIFY_MODIFIED: "⚠",
            EventType.VERIFY_MISSING: "✗",
            EventType.RELINK: "🔗",
        }
        return icons.get(self.event_type, "•")

    @property
    def display_name(self) -> str:
        """Return a human-readable name for the event type."""
        names = {
            EventType.RESTORE: "Restored",
            EventType.PIN: "Pinned",
            EventType.UNPIN: "Unpinned",
            EventType.DELETE: "Deleted",
            EventType.VERIFY_OK: "Verified OK",
            EventType.VERIFY_MODIFIED: "Modified Detected",
            EventType.VERIFY_MISSING: "Missing Detected",
            EventType.RELINK: "Relinked",
        }
        return names.get(self.event_type, self.event_type.value)
