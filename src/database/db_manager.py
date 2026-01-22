"""SQLite database connection and CRUD operations."""
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

from .models import TrackedFile, Version, FileStatus, Tag, Event, EventType, Project


class DatabaseManager:
    """Manages SQLite database connections and operations."""

    def __init__(self, db_path: str):
        """Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()

    def _ensure_db_directory(self) -> None:
        """Ensure the database directory exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def _init_database(self) -> None:
        """Initialize database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create files table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    file_size INTEGER NOT NULL,
                    modified_time REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OK',
                    created_at TEXT NOT NULL,
                    file_hash TEXT
                )
            """)

            # Create versions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS versions (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    commit_message TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    modified_time REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    file_hash TEXT,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
                )
            """)

            # Create index for faster version lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_versions_file_id
                ON versions(file_id)
            """)

            # Create tags table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
            """)

            # Create tag_links table (many-to-many relationship)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tag_links (
                    id TEXT PRIMARY KEY,
                    tag_id TEXT NOT NULL,
                    file_id TEXT,
                    version_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
                    FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE
                )
            """)

            # Create indexes for tag lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tag_links_file_id
                ON tag_links(file_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tag_links_tag_id
                ON tag_links(tag_id)
            """)

            # Create events table for timeline
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
                )
            """)

            # Create metadata table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    file_id TEXT PRIMARY KEY,
                    data TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
                )
                """
            )

            # Create projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    color TEXT NOT NULL DEFAULT '#007AFF',
                    created_at TEXT NOT NULL
                )
            """)

            # Create index for event lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_file_id
                ON events(file_id)
            """)

            # Migrate: Add file_hash column if it doesn't exist
            self._migrate_add_hash_column(cursor)

            # Migrate: Add is_favorite column if it doesn't exist
            self._migrate_add_favorite_column(cursor)

            # Migrate: Add is_archived column if it doesn't exist
            self._migrate_add_archived_column(cursor)

            # Migrate: Add pin columns to versions table if they don't exist
            self._migrate_add_pin_columns(cursor)

            # Migrate: Add metadata table if missing columns (noop if already created)
            # (handled by CREATE IF NOT EXISTS above)

            # Migrate: Add project_id column to files table
            self._migrate_add_project_column(cursor)

            conn.commit()

    def _migrate_add_hash_column(self, cursor: sqlite3.Cursor) -> None:
        """Add file_hash column to existing tables if not present."""
        # Check and add to files table
        cursor.execute("PRAGMA table_info(files)")
        columns = [row[1] for row in cursor.fetchall()]
        if "file_hash" not in columns:
            cursor.execute("ALTER TABLE files ADD COLUMN file_hash TEXT")

        # Check and add to versions table
        cursor.execute("PRAGMA table_info(versions)")
        columns = [row[1] for row in cursor.fetchall()]
        if "file_hash" not in columns:
            cursor.execute("ALTER TABLE versions ADD COLUMN file_hash TEXT")

    def _migrate_add_favorite_column(self, cursor: sqlite3.Cursor) -> None:
        """Add is_favorite column to files table if not present."""
        cursor.execute("PRAGMA table_info(files)")
        columns = [row[1] for row in cursor.fetchall()]
        if "is_favorite" not in columns:
            cursor.execute("ALTER TABLE files ADD COLUMN is_favorite INTEGER DEFAULT 0")

    def _migrate_add_archived_column(self, cursor: sqlite3.Cursor) -> None:
        """Add is_archived column to files table if not present."""
        cursor.execute("PRAGMA table_info(files)")
        columns = [row[1] for row in cursor.fetchall()]
        if "is_archived" not in columns:
            cursor.execute("ALTER TABLE files ADD COLUMN is_archived INTEGER DEFAULT 0")

    def _migrate_add_pin_columns(self, cursor: sqlite3.Cursor) -> None:
        """Add is_pinned and pinned_path columns to versions table if not present."""
        cursor.execute("PRAGMA table_info(versions)")
        columns = [row[1] for row in cursor.fetchall()]
        if "is_pinned" not in columns:
            cursor.execute("ALTER TABLE versions ADD COLUMN is_pinned INTEGER DEFAULT 0")
        if "pinned_path" not in columns:
            cursor.execute("ALTER TABLE versions ADD COLUMN pinned_path TEXT")

    def _migrate_add_project_column(self, cursor: sqlite3.Cursor) -> None:
        """Add project_id column to files table if not present."""
        cursor.execute("PRAGMA table_info(files)")
        columns = [row[1] for row in cursor.fetchall()]
        if "project_id" not in columns:
            cursor.execute("ALTER TABLE files ADD COLUMN project_id TEXT REFERENCES projects(id)")

    # File CRUD operations

    def create_file(
        self,
        display_name: str,
        file_path: str,
        file_size: int,
        modified_time: float,
        file_hash: Optional[str] = None
    ) -> TrackedFile:
        """Create a new tracked file entry.

        Args:
            display_name: Display name for the file.
            file_path: Absolute path to the file.
            file_size: File size in bytes.
            modified_time: File modification timestamp.
            file_hash: Optional file hash for verification.

        Returns:
            The created TrackedFile object.
        """
        file_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        status = FileStatus.OK.value

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO files (id, display_name, file_path, file_size,
                                   modified_time, status, created_at, file_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_id, display_name, file_path, file_size,
                  modified_time, status, created_at, file_hash))
            conn.commit()

        return TrackedFile(
            id=file_id,
            display_name=display_name,
            file_path=file_path,
            file_size=file_size,
            modified_time=modified_time,
            status=FileStatus.OK,
            created_at=created_at,
            file_hash=file_hash
        )

    def get_file(self, file_id: str) -> Optional[TrackedFile]:
        """Get a file by ID.

        Args:
            file_id: The file's UUID.

        Returns:
            The TrackedFile or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, display_name, file_path, file_size,
                       modified_time, status, created_at, file_hash, is_favorite, is_archived, project_id
                FROM files WHERE id = ?
            """, (file_id,))
            row = cursor.fetchone()

        return TrackedFile.from_row(row) if row else None

    def get_file_by_path(self, file_path: str) -> Optional[TrackedFile]:
        """Get a file by its path.

        Args:
            file_path: The file's path.

        Returns:
            The TrackedFile or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, display_name, file_path, file_size,
                       modified_time, status, created_at, file_hash, is_favorite, is_archived, project_id
                FROM files WHERE file_path = ?
            """, (file_path,))
            row = cursor.fetchone()

        return TrackedFile.from_row(row) if row else None

    def get_all_files(self, include_archived: bool = False) -> list[TrackedFile]:
        """Get all tracked files.

        Args:
            include_archived: If True, include archived files.

        Returns:
            List of all TrackedFile objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if include_archived:
                cursor.execute("""
                    SELECT id, display_name, file_path, file_size,
                           modified_time, status, created_at, file_hash, is_favorite, is_archived, project_id
                    FROM files ORDER BY created_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT id, display_name, file_path, file_size,
                           modified_time, status, created_at, file_hash, is_favorite, is_archived, project_id
                    FROM files WHERE is_archived = 0 OR is_archived IS NULL
                    ORDER BY created_at DESC
                """)
            rows = cursor.fetchall()

        return [TrackedFile.from_row(row) for row in rows]

    def get_archived_files(self) -> list[TrackedFile]:
        """Get all archived files.

        Returns:
            List of archived TrackedFile objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, display_name, file_path, file_size,
                       modified_time, status, created_at, file_hash, is_favorite, is_archived, project_id
                FROM files WHERE is_archived = 1
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()

        return [TrackedFile.from_row(row) for row in rows]

    def update_file_status(self, file_id: str, status: FileStatus) -> None:
        """Update a file's status.

        Args:
            file_id: The file's UUID.
            status: The new status.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE files SET status = ? WHERE id = ?
            """, (status.value, file_id))
            conn.commit()

    def update_file_metadata(
        self,
        file_id: str,
        file_size: int,
        modified_time: float,
        status: FileStatus,
        file_hash: Optional[str] = None
    ) -> None:
        """Update a file's metadata after verification.

        Args:
            file_id: The file's UUID.
            file_size: New file size.
            modified_time: New modification time.
            status: New status.
            file_hash: Optional new file hash.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE files
                SET file_size = ?, modified_time = ?, status = ?, file_hash = ?
                WHERE id = ?
            """, (file_size, modified_time, status.value, file_hash, file_id))
            conn.commit()

    def update_file_location(
        self,
        file_id: str,
        file_path: str,
        file_size: int,
        modified_time: float,
        status: FileStatus,
        file_hash: Optional[str] = None
    ) -> None:
        """Update a file's path and metadata after relink.

        Args:
            file_id: The file's UUID.
            file_path: New absolute path.
            file_size: File size.
            modified_time: Modification time.
            status: New status.
            file_hash: Optional hash.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE files
                SET file_path = ?, file_size = ?, modified_time = ?, status = ?, file_hash = ?
                WHERE id = ?
                """,
                (file_path, file_size, modified_time, status.value, file_hash, file_id),
            )
            conn.commit()

    def update_display_name(self, file_id: str, display_name: str) -> None:
        """Update a file's display name.

        Args:
            file_id: The file's UUID.
            display_name: The new display name.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE files SET display_name = ? WHERE id = ?
            """, (display_name, file_id))
            conn.commit()

    def delete_file(self, file_id: str) -> None:
        """Delete a tracked file and all its versions.

        Args:
            file_id: The file's UUID.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete versions first (foreign key)
            cursor.execute("DELETE FROM versions WHERE file_id = ?", (file_id,))
            cursor.execute("DELETE FROM metadata WHERE file_id = ?", (file_id,))
            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
            conn.commit()

    # Version CRUD operations

    def create_version(
        self,
        file_id: str,
        commit_message: str,
        file_size: int,
        modified_time: float,
        file_hash: Optional[str] = None
    ) -> Version:
        """Create a new version for a file.

        Args:
            file_id: The parent file's UUID.
            commit_message: The commit message.
            file_size: File size at this version.
            modified_time: Modification time at this version.
            file_hash: Optional file hash at this version.

        Returns:
            The created Version object.
        """
        version_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        # Get next version number
        version_number = self.get_next_version_number(file_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO versions (id, file_id, version_number, commit_message,
                                      file_size, modified_time, created_at, file_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (version_id, file_id, version_number, commit_message,
                  file_size, modified_time, created_at, file_hash))
            conn.commit()

        return Version(
            id=version_id,
            file_id=file_id,
            version_number=version_number,
            commit_message=commit_message,
            file_size=file_size,
            modified_time=modified_time,
            created_at=created_at,
            file_hash=file_hash
        )

    def get_versions(self, file_id: str) -> list[Version]:
        """Get all versions for a file.

        Args:
            file_id: The file's UUID.

        Returns:
            List of Version objects, ordered by version number descending.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, file_id, version_number, commit_message,
                       file_size, modified_time, created_at, file_hash,
                       is_pinned, pinned_path
                FROM versions
                WHERE file_id = ?
                ORDER BY version_number DESC
            """, (file_id,))
            rows = cursor.fetchall()

        return [Version.from_row(row) for row in rows]

    def get_latest_version(self, file_id: str) -> Optional[Version]:
        """Get the latest version of a file.

        Args:
            file_id: The file's UUID.

        Returns:
            The latest Version or None if no versions exist.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, file_id, version_number, commit_message,
                       file_size, modified_time, created_at, file_hash,
                       is_pinned, pinned_path
                FROM versions
                WHERE file_id = ?
                ORDER BY version_number DESC
                LIMIT 1
            """, (file_id,))
            row = cursor.fetchone()

        return Version.from_row(row) if row else None

    def get_next_version_number(self, file_id: str) -> int:
        """Get the next version number for a file.

        Args:
            file_id: The file's UUID.

        Returns:
            The next version number (1 if no versions exist).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(version_number) FROM versions WHERE file_id = ?
            """, (file_id,))
            result = cursor.fetchone()[0]

        return (result or 0) + 1

    def get_version_by_number(self, file_id: str, version_number: int) -> Optional[Version]:
        """Get a specific version by file ID and version number.

        Args:
            file_id: The file's UUID.
            version_number: The version number.

        Returns:
            The Version or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, file_id, version_number, commit_message,
                       file_size, modified_time, created_at, file_hash,
                       is_pinned, pinned_path
                FROM versions
                WHERE file_id = ? AND version_number = ?
            """, (file_id, version_number))
            row = cursor.fetchone()

        return Version.from_row(row) if row else None

    def set_version_pinned(
        self,
        file_id: str,
        version_number: int,
        is_pinned: bool,
        pinned_path: Optional[str] = None
    ) -> None:
        """Set the pinned status of a version.

        Args:
            file_id: The file's UUID.
            version_number: The version number.
            is_pinned: Whether the version is pinned.
            pinned_path: Path to the pinned copy (None if unpinning).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE versions
                SET is_pinned = ?, pinned_path = ?
                WHERE file_id = ? AND version_number = ?
            """, (1 if is_pinned else 0, pinned_path, file_id, version_number))
            conn.commit()

    def get_pinned_versions(self, file_id: Optional[str] = None) -> list[Version]:
        """Get all pinned versions.

        Args:
            file_id: Optional file ID to filter by.

        Returns:
            List of pinned Version objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if file_id:
                cursor.execute("""
                    SELECT id, file_id, version_number, commit_message,
                           file_size, modified_time, created_at, file_hash,
                           is_pinned, pinned_path
                    FROM versions
                    WHERE file_id = ? AND is_pinned = 1
                    ORDER BY version_number DESC
                """, (file_id,))
            else:
                cursor.execute("""
                    SELECT id, file_id, version_number, commit_message,
                           file_size, modified_time, created_at, file_hash,
                           is_pinned, pinned_path
                    FROM versions
                    WHERE is_pinned = 1
                    ORDER BY created_at DESC
                """)
            rows = cursor.fetchall()

        return [Version.from_row(row) for row in rows]

    # Tag CRUD operations

    def get_or_create_tag(self, tag_name: str) -> Tag:
        """Get an existing tag or create a new one.

        Args:
            tag_name: The tag name (will be normalized).

        Returns:
            The Tag object.
        """
        normalized_name = Tag.normalize(tag_name)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Try to find existing tag
            cursor.execute(
                "SELECT id, name, created_at FROM tags WHERE name = ?",
                (normalized_name,)
            )
            row = cursor.fetchone()

            if row:
                return Tag.from_row(row)

            # Create new tag
            tag_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO tags (id, name, created_at) VALUES (?, ?, ?)",
                (tag_id, normalized_name, created_at)
            )
            conn.commit()

            return Tag(id=tag_id, name=normalized_name, created_at=created_at)

    def get_all_tags(self) -> list[Tag]:
        """Get all tags.

        Returns:
            List of all Tag objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, created_at FROM tags ORDER BY name"
            )
            rows = cursor.fetchall()

        return [Tag.from_row(row) for row in rows]

    def add_tag_to_file(self, tag_id: str, file_id: str) -> None:
        """Add a tag to a file.

        Args:
            tag_id: The tag's UUID.
            file_id: The file's UUID.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if link already exists
            cursor.execute(
                "SELECT id FROM tag_links WHERE tag_id = ? AND file_id = ?",
                (tag_id, file_id)
            )
            if cursor.fetchone():
                return  # Already linked

            link_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO tag_links (id, tag_id, file_id, created_at) VALUES (?, ?, ?, ?)",
                (link_id, tag_id, file_id, created_at)
            )
            conn.commit()

    def remove_tag_from_file(self, tag_id: str, file_id: str) -> None:
        """Remove a tag from a file.

        Args:
            tag_id: The tag's UUID.
            file_id: The file's UUID.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM tag_links WHERE tag_id = ? AND file_id = ?",
                (tag_id, file_id)
            )
            conn.commit()

    def get_file_tags(self, file_id: str) -> list[Tag]:
        """Get all tags for a file.

        Args:
            file_id: The file's UUID.

        Returns:
            List of Tag objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.name, t.created_at
                FROM tags t
                JOIN tag_links tl ON t.id = tl.tag_id
                WHERE tl.file_id = ?
                ORDER BY t.name
            """, (file_id,))
            rows = cursor.fetchall()

        return [Tag.from_row(row) for row in rows]

    def get_files_by_tag(self, tag_id: str) -> list[TrackedFile]:
        """Get all files with a specific tag.

        Args:
            tag_id: The tag's UUID.

        Returns:
            List of TrackedFile objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT f.id, f.display_name, f.file_path, f.file_size,
                       f.modified_time, f.status, f.created_at, f.file_hash, f.is_favorite, f.is_archived, f.project_id
                FROM files f
                JOIN tag_links tl ON f.id = tl.file_id
                WHERE tl.tag_id = ?
                ORDER BY f.display_name
            """, (tag_id,))
            rows = cursor.fetchall()

        return [TrackedFile.from_row(row) for row in rows]

    def delete_unused_tags(self) -> int:
        """Delete tags that are not linked to any files.

        Returns:
            Number of deleted tags.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM tags
                WHERE id NOT IN (SELECT DISTINCT tag_id FROM tag_links)
            """)
            deleted_count = cursor.rowcount
            conn.commit()

        return deleted_count

    def set_favorite(self, file_id: str, is_favorite: bool) -> None:
        """Set the favorite status of a file.

        Args:
            file_id: The file's UUID.
            is_favorite: Whether the file is a favorite.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE files SET is_favorite = ? WHERE id = ?
            """, (1 if is_favorite else 0, file_id))
            conn.commit()

    def toggle_favorite(self, file_id: str) -> bool:
        """Toggle the favorite status of a file.

        Args:
            file_id: The file's UUID.

        Returns:
            The new favorite status.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE files SET is_favorite = NOT COALESCE(is_favorite, 0) WHERE id = ?
            """, (file_id,))
            conn.commit()

            # Get the new value
            cursor.execute("SELECT is_favorite FROM files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            return bool(row[0]) if row else False

    def set_archived(self, file_id: str, is_archived: bool) -> None:
        """Set the archived status of a file.

        Args:
            file_id: The file's UUID.
            is_archived: Whether the file should be archived.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE files SET is_archived = ? WHERE id = ?
            """, (1 if is_archived else 0, file_id))
            conn.commit()

    def unarchive_file(self, file_id: str) -> None:
        """Unarchive a file (restore from archive).

        Args:
            file_id: The file's UUID.
        """
        self.set_archived(file_id, False)

    def get_file_search_data(self, file_id: str) -> dict:
        """Get searchable data for a file including commit messages and tags.

        Args:
            file_id: The file's UUID.

        Returns:
            Dict with 'commit_messages' (list) and 'tags' (list) keys.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get all commit messages for the file
            cursor.execute("""
                SELECT commit_message FROM versions WHERE file_id = ?
            """, (file_id,))
            commit_messages = [row[0] for row in cursor.fetchall()]

            # Get all tags for the file
            cursor.execute("""
                SELECT t.name FROM tags t
                JOIN tag_links tl ON t.id = tl.tag_id
                WHERE tl.file_id = ?
            """, (file_id,))
            tags = [row[0] for row in cursor.fetchall()]

        return {
            'commit_messages': commit_messages,
            'tags': tags
        }

    # Metadata operations

    def set_metadata(self, file_id: str, data: dict) -> None:
        """Upsert metadata JSON for a file."""
        payload = json.dumps(data)
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO metadata (file_id, data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at
                """,
                (file_id, payload, now, now),
            )
            conn.commit()

    def get_metadata(self, file_id: str) -> dict:
        """Fetch metadata JSON for a file."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM metadata WHERE file_id = ?", (file_id,))
            row = cursor.fetchone()
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except Exception:
            return {}

    def get_all_files_search_data(self) -> dict[str, dict]:
        """Get searchable data for all files.

        Returns:
            Dict mapping file_id to search data dict.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get all commit messages grouped by file
            cursor.execute("""
                SELECT file_id, commit_message FROM versions
            """)
            commit_data = {}
            for file_id, message in cursor.fetchall():
                if file_id not in commit_data:
                    commit_data[file_id] = []
                commit_data[file_id].append(message)

            # Get all tags grouped by file
            cursor.execute("""
                SELECT tl.file_id, t.name FROM tags t
                JOIN tag_links tl ON t.id = tl.tag_id
            """)
            tag_data = {}
            for file_id, tag_name in cursor.fetchall():
                if file_id not in tag_data:
                    tag_data[file_id] = []
                tag_data[file_id].append(tag_name)

        # Combine into final result
        all_file_ids = set(commit_data.keys()) | set(tag_data.keys())
        result = {}
        for file_id in all_file_ids:
            result[file_id] = {
                'commit_messages': commit_data.get(file_id, []),
                'tags': tag_data.get(file_id, [])
            }

        return result

    # Event CRUD operations

    def create_event(
        self,
        file_id: str,
        event_type: EventType,
        description: Optional[str] = None
    ) -> Event:
        """Create a new event for a file.

        Args:
            file_id: The file's UUID.
            event_type: The type of event.
            description: Optional event description.

        Returns:
            The created Event object.
        """
        event_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (id, file_id, event_type, description, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (event_id, file_id, event_type.value, description, created_at))
            conn.commit()

        return Event(
            id=event_id,
            file_id=file_id,
            event_type=event_type,
            description=description,
            created_at=created_at
        )

    def get_events(
        self,
        file_id: str,
        limit: Optional[int] = None,
        order_desc: bool = True
    ) -> list[Event]:
        """Get events for a file.

        Args:
            file_id: The file's UUID.
            limit: Optional limit on number of events.
            order_desc: If True, newest first; else oldest first.

        Returns:
            List of Event objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            order = "DESC" if order_desc else "ASC"
            query = f"""
                SELECT id, file_id, event_type, description, created_at
                FROM events
                WHERE file_id = ?
                ORDER BY created_at {order}
            """
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query, (file_id,))
            rows = cursor.fetchall()

        return [Event.from_row(row) for row in rows]

    def delete_events_for_file(self, file_id: str) -> int:
        """Delete all events for a file.

        Args:
            file_id: The file's UUID.

        Returns:
            Number of deleted events.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events WHERE file_id = ?", (file_id,))
            deleted_count = cursor.rowcount
            conn.commit()

        return deleted_count

    # Project CRUD operations

    def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        color: str = "#007AFF"
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name.
            description: Optional project description.
            color: Hex color for UI.

        Returns:
            The created Project object.
        """
        project_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO projects (id, name, description, color, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (project_id, name, description, color, created_at))
            conn.commit()

        return Project(
            id=project_id,
            name=name,
            description=description,
            color=color,
            created_at=created_at
        )

    def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID.

        Args:
            project_id: The project's UUID.

        Returns:
            The Project or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, description, color, created_at
                FROM projects WHERE id = ?
            """, (project_id,))
            row = cursor.fetchone()

        return Project.from_row(row) if row else None

    def get_all_projects(self) -> list[Project]:
        """Get all projects.

        Returns:
            List of all Project objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, description, color, created_at
                FROM projects ORDER BY name
            """)
            rows = cursor.fetchall()

        return [Project.from_row(row) for row in rows]

    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> None:
        """Update a project's properties.

        Args:
            project_id: The project's UUID.
            name: Optional new name.
            description: Optional new description.
            color: Optional new color.
        """
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if color is not None:
            updates.append("color = ?")
            params.append(color)

        if not updates:
            return

        params.append(project_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE projects SET {', '.join(updates)} WHERE id = ?
            """, params)
            conn.commit()

    def delete_project(self, project_id: str) -> None:
        """Delete a project (files will have project_id set to NULL).

        Args:
            project_id: The project's UUID.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Set files' project_id to NULL
            cursor.execute("UPDATE files SET project_id = NULL WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()

    def set_file_project(self, file_id: str, project_id: Optional[str]) -> None:
        """Assign a file to a project.

        Args:
            file_id: The file's UUID.
            project_id: The project's UUID (None to unassign).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE files SET project_id = ? WHERE id = ?", (project_id, file_id))
            conn.commit()

    def get_files_by_project(self, project_id: Optional[str], include_archived: bool = False) -> list[TrackedFile]:
        """Get all files for a project.

        Args:
            project_id: The project's UUID (None for unassigned files).
            include_archived: If True, include archived files.

        Returns:
            List of TrackedFile objects.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if project_id:
                if include_archived:
                    cursor.execute("""
                        SELECT id, display_name, file_path, file_size,
                               modified_time, status, created_at, file_hash, is_favorite, is_archived, project_id
                        FROM files WHERE project_id = ?
                        ORDER BY created_at DESC
                    """, (project_id,))
                else:
                    cursor.execute("""
                        SELECT id, display_name, file_path, file_size,
                               modified_time, status, created_at, file_hash, is_favorite, is_archived, project_id
                        FROM files WHERE project_id = ? AND (is_archived = 0 OR is_archived IS NULL)
                        ORDER BY created_at DESC
                    """, (project_id,))
            else:
                if include_archived:
                    cursor.execute("""
                        SELECT id, display_name, file_path, file_size,
                               modified_time, status, created_at, file_hash, is_favorite, is_archived, project_id
                        FROM files WHERE project_id IS NULL
                        ORDER BY created_at DESC
                    """)
                else:
                    cursor.execute("""
                        SELECT id, display_name, file_path, file_size,
                               modified_time, status, created_at, file_hash, is_favorite, is_archived, project_id
                        FROM files WHERE project_id IS NULL AND (is_archived = 0 OR is_archived IS NULL)
                        ORDER BY created_at DESC
                    """)
            rows = cursor.fetchall()

        return [TrackedFile.from_row(row) for row in rows]

    def get_project_file_count(self, project_id: str) -> int:
        """Get the number of files in a project.

        Args:
            project_id: The project's UUID.

        Returns:
            Number of files.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM files WHERE project_id = ?
            """, (project_id,))
            return cursor.fetchone()[0]
