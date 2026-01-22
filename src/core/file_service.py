"""File service - business logic for file and version management."""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional
import time
import json

try:
    from PIL import Image, ExifTags
except Exception:  # pragma: no cover - Pillow optional
    Image = None
    ExifTags = None

from database import DatabaseManager, TrackedFile, Version, FileStatus, Tag
from core.verification import (
    get_file_state,
    check_file_status,
    compute_file_hash,
    verify_file_hash,
    VerificationResult,
)


class FileService:
    """Service for managing tracked files and versions."""

    def __init__(self, db_manager: DatabaseManager, data_dir: str, pin_storage_path: Optional[str] = None):
        """Initialize the file service.

        Args:
            db_manager: Database manager instance.
            data_dir: Path to the data directory for storing version backups.
            pin_storage_path: Optional path to the pin storage directory.
        """
        self.db = db_manager
        self.data_dir = Path(data_dir)
        self.versions_dir = self.data_dir / "versions"
        self._pin_storage_path: Optional[Path] = Path(pin_storage_path) if pin_storage_path else None
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        if self._pin_storage_path:
            self._pin_storage_path.mkdir(parents=True, exist_ok=True)

    def set_pin_storage_path(self, path: Optional[str]) -> None:
        """Set the pin storage path.

        Args:
            path: Path to the pin storage directory, or None to disable.
        """
        self._pin_storage_path = Path(path) if path else None
        if self._pin_storage_path:
            self._pin_storage_path.mkdir(parents=True, exist_ok=True)

    def get_pin_storage_path(self) -> Optional[str]:
        """Get the current pin storage path.

        Returns:
            The pin storage path or None if not set.
        """
        return str(self._pin_storage_path) if self._pin_storage_path else None

    def migrate_existing_files(self) -> int:
        """Create backups for any existing tracked files that don't have them.

        Also renames legacy format backups (v1.ext) to new format (filename_v1.ext).

        Returns:
            Number of files migrated.
        """
        migrated = 0
        for tracked_file in self.db.get_all_files():
            versions = self.db.get_versions(tracked_file.id)
            for version in versions:
                new_path = self._get_version_path(
                    tracked_file.id, version.version_number, tracked_file.display_name
                )
                legacy_path = self._get_legacy_version_path(
                    tracked_file.id, version.version_number, tracked_file.display_name
                )

                if new_path.exists():
                    # Already in new format
                    continue

                if legacy_path.exists():
                    # Rename from legacy to new format
                    try:
                        legacy_path.rename(new_path)
                        migrated += 1
                    except Exception:
                        pass
                else:
                    # No backup exists - create from original file (only works for latest version)
                    source_path = Path(tracked_file.file_path)
                    if source_path.exists() and version.version_number == len(versions):
                        try:
                            self._backup_file(
                                str(source_path),
                                tracked_file.id,
                                version.version_number
                            )
                            migrated += 1
                        except Exception:
                            pass
        return migrated

    def _get_version_dir(self, file_id: str) -> Path:
        """Get the version storage directory for a file."""
        return self.versions_dir / file_id

    def _get_version_path(self, file_id: str, version_number: int, original_name: str) -> Path:
        """Get the path for a specific version backup file."""
        version_dir = self._get_version_dir(file_id)
        version_dir.mkdir(parents=True, exist_ok=True)
        # Preserve original name with version suffix
        path = Path(original_name)
        stem = path.stem
        ext = path.suffix
        return version_dir / f"{stem}_v{version_number}{ext}"

    def _get_legacy_version_path(self, file_id: str, version_number: int, original_name: str) -> Path:
        """Get the legacy version path (v1.ext format) for backwards compatibility."""
        version_dir = self._get_version_dir(file_id)
        ext = Path(original_name).suffix
        return version_dir / f"v{version_number}{ext}"

    def _backup_file(self, source_path: str, file_id: str, version_number: int) -> str:
        """Backup a file for a version.

        Args:
            source_path: Path to the source file.
            file_id: The file's UUID.
            version_number: The version number.

        Returns:
            Path to the backup file.
        """
        source = Path(source_path)
        backup_path = self._get_version_path(file_id, version_number, source.name)
        shutil.copy2(source, backup_path)  # copy2 preserves metadata
        return str(backup_path)

    def _delete_version_backups(self, file_id: str) -> None:
        """Delete all version backup files for a tracked file."""
        version_dir = self._get_version_dir(file_id)
        if version_dir.exists():
            shutil.rmtree(version_dir)

    def register_file(
        self,
        file_path: str,
        commit_message: str,
        display_name: Optional[str] = None
    ) -> tuple[TrackedFile, Version]:
        """Register a new file for tracking.

        Creates a file entry and its initial version (v1) with backup.

        Args:
            file_path: Absolute path to the file.
            commit_message: Commit message for the initial version.
            display_name: Optional display name (defaults to filename).

        Returns:
            Tuple of (TrackedFile, Version) for the registered file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file is already registered.
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check if already registered
        existing = self.db.get_file_by_path(str(path))
        if existing:
            raise ValueError(f"File already registered: {file_path}")

        # Get file metadata with hash
        state = get_file_state(file_path, compute_hash=True)

        # Create display name from filename if not provided
        if display_name is None:
            display_name = path.name

        # Create file record
        tracked_file = self.db.create_file(
            display_name=display_name,
            file_path=str(path),
            file_size=state.file_size,
            modified_time=state.modified_time,
            file_hash=state.file_hash
        )

        # Create initial version (v1)
        version = self.db.create_version(
            file_id=tracked_file.id,
            commit_message=commit_message,
            file_size=state.file_size,
            modified_time=state.modified_time,
            file_hash=state.file_hash
        )

        # Backup the file
        self._backup_file(file_path, tracked_file.id, version.version_number)

        return tracked_file, version

    def get_all_files(self) -> list[TrackedFile]:
        """Get all tracked files."""
        return self.db.get_all_files()

    def get_file(self, file_id: str) -> Optional[TrackedFile]:
        """Get a tracked file by ID."""
        return self.db.get_file(file_id)

    def get_versions(self, file_id: str) -> list[Version]:
        """Get all versions for a file."""
        return self.db.get_versions(file_id)

    def get_version(self, file_id: str, version_number: int) -> Optional[Version]:
        """Get a specific version of a file."""
        versions = self.db.get_versions(file_id)
        for v in versions:
            if v.version_number == version_number:
                return v
        return None

    def verify_file(self, file_id: str) -> FileStatus:
        """Verify a file's current status and compute hash if missing."""
        tracked_file = self.db.get_file(file_id)
        if not tracked_file:
            raise ValueError(f"File not found: {file_id}")

        new_status = check_file_status(tracked_file)

        # Compute and store hash if missing and file exists
        if not tracked_file.file_hash and new_status != FileStatus.MISSING:
            file_hash = compute_file_hash(tracked_file.file_path)
            if file_hash:
                self.db.update_file_metadata(
                    file_id=file_id,
                    file_size=tracked_file.file_size,
                    modified_time=tracked_file.modified_time,
                    status=new_status,
                    file_hash=file_hash
                )
                return new_status

        if new_status != tracked_file.status:
            self.db.update_file_status(file_id, new_status)

        return new_status

    def verify_all_files(self) -> dict[str, FileStatus]:
        """Verify all tracked files."""
        results = {}
        for tracked_file in self.db.get_all_files():
            results[tracked_file.id] = self.verify_file(tracked_file.id)
        return results

    def relink_missing_files(
        self,
        root_path: str,
        use_hash: bool = False,
        include_exts: Optional[list[str]] = None,
        max_size_bytes: Optional[int] = None,
        modified_within_days: Optional[int] = None,
    ) -> dict[str, int]:
        """Attempt to relink missing files by scanning a root directory.

        Args:
            root_path: Root directory to scan for candidates.
            use_hash: If True, compute hash on candidates when a stored hash exists.

        Returns:
            Summary dict with counts.
        """
        root = Path(root_path)
        if not root.exists() or not root.is_dir():
            raise ValueError("Root path is not a directory")

        # Build index by filename
        index: dict[str, list[dict[str, object]]] = {}
        cutoff_ts = None
        if modified_within_days:
            cutoff_ts = time.time() - (modified_within_days * 86400)

        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                ext = Path(name).suffix.lower().lstrip(".")
                if include_exts and ext not in include_exts:
                    continue
                candidate_path = Path(dirpath) / name
                try:
                    stat = candidate_path.stat()
                except OSError:
                    continue
                if max_size_bytes and stat.st_size > max_size_bytes:
                    summary["size_filtered"] += 1
                    continue
                if cutoff_ts and stat.st_mtime < cutoff_ts:
                    summary["date_filtered"] += 1
                    continue
                entry = {
                    "path": candidate_path,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
                index.setdefault(name, []).append(entry)

        # Find missing files
        missing = []
        for tracked_file in self.db.get_all_files(include_archived=False):
            path = Path(tracked_file.file_path)
            if tracked_file.status == FileStatus.MISSING or not path.exists():
                missing.append(tracked_file)

        summary = {
            "checked": len(missing),
            "relinked": 0,
            "not_found": 0,
            "scanned": len(index),
            "hash_checked": 0,
            "size_filtered": 0,
            "date_filtered": 0,
        }

        for tracked_file in missing:
            name = Path(tracked_file.file_path).name
            candidates = index.get(name, [])
            # Prefer exact size match
            size_matched = [c for c in candidates if c["size"] == tracked_file.file_size]
            candidate_entries = size_matched if size_matched else candidates

            chosen = None
            if use_hash and tracked_file.file_hash:
                for entry in candidate_entries:
                    cand_hash = compute_file_hash(str(entry["path"]))
                    summary["hash_checked"] += 1
                    if cand_hash == tracked_file.file_hash:
                        chosen = (entry, cand_hash)
                        break
            else:
                if candidate_entries:
                    # pick closest mtime among size-matched (or any candidates)
                    def _mtime_diff(entry: dict[str, object]) -> float:
                        return abs(float(entry["mtime"]) - float(tracked_file.modified_time))

                    best = min(candidate_entries, key=_mtime_diff)
                    chosen = (best, tracked_file.file_hash)

            if not chosen:
                summary["not_found"] += 1
                continue

            entry, new_hash = chosen
            new_path: Path = entry["path"]  # type: ignore[assignment]

            self.db.update_file_location(
                file_id=tracked_file.id,
                file_path=str(new_path),
                file_size=entry["size"],
                modified_time=entry["mtime"],
                status=FileStatus.OK,
                file_hash=new_hash,
            )

            self.db.create_event(
                tracked_file.id,
                EventType.RELINK,
                f"Relinked to {new_path}",
            )

            summary["relinked"] += 1

        return summary

    def extract_metadata(self, file_id: str) -> dict:
        """Extract and store metadata for a file (images only for now)."""
        tracked_file = self.db.get_file(file_id)
        if not tracked_file:
            raise ValueError("File not found")

        path = Path(tracked_file.file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        meta: dict = {
            "file_size": tracked_file.file_size,
            "modified_time": tracked_file.modified_time,
            "extension": path.suffix.lower(),
        }

        ext = path.suffix.lower()

        if Image and ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}:
            try:
                with Image.open(path) as img:
                    meta["width"], meta["height"] = img.size
                    if hasattr(img, "_getexif") and img._getexif():
                        exif_data = img._getexif() or {}
                        tag_map = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif_data.items()}
                        # Keep a small subset for brevity
                        keep_keys = [
                            "DateTimeOriginal",
                            "Model",
                            "Make",
                            "LensModel",
                            "FNumber",
                            "ExposureTime",
                            "ISOSpeedRatings",
                        ]
                        meta["exif"] = {k: tag_map.get(k) for k in keep_keys if k in tag_map}
            except Exception:
                meta.setdefault("exif", {})

        elif ext in {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}:
            video_meta = self._probe_video_metadata(path)
            if video_meta:
                meta.update(video_meta)

        self.db.set_metadata(file_id, meta)
        return meta

    def _probe_video_metadata(self, path: Path) -> Optional[dict]:
        """Use ffprobe (if available) to extract basic video metadata."""
        try:
            import shutil as _shutil

            if not _shutil.which("ffprobe"):
                return {"warning": "ffprobe not available"}

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,duration,codec_name",
                    "-of",
                    "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout or "{}")
            streams = data.get("streams", [])
            if not streams:
                return None
            stream = streams[0]
            meta = {
                "width": stream.get("width"),
                "height": stream.get("height"),
                "duration": float(stream.get("duration")) if stream.get("duration") else None,
                "codec": stream.get("codec_name"),
                "type": "video",
            }
            # Remove None values
            return {k: v for k, v in meta.items() if v is not None}
        except Exception:
            return None

    def create_new_version(
        self,
        file_id: str,
        commit_message: str
    ) -> Version:
        """Create a new version for a modified file.

        Backs up the current file state and creates a new version entry.

        Args:
            file_id: The file's UUID.
            commit_message: Commit message for the new version.

        Returns:
            The created Version.

        Raises:
            ValueError: If file not found or file is missing.
        """
        tracked_file = self.db.get_file(file_id)
        if not tracked_file:
            raise ValueError(f"File not found: {file_id}")

        # Get current file state with hash
        state = get_file_state(tracked_file.file_path, compute_hash=True)

        if not state.exists:
            raise ValueError("Cannot create version: file is missing")

        # Create new version
        version = self.db.create_version(
            file_id=file_id,
            commit_message=commit_message,
            file_size=state.file_size,
            modified_time=state.modified_time,
            file_hash=state.file_hash
        )

        # Backup the file
        self._backup_file(tracked_file.file_path, file_id, version.version_number)

        # Update file metadata to match new version
        self.db.update_file_metadata(
            file_id=file_id,
            file_size=state.file_size,
            modified_time=state.modified_time,
            status=FileStatus.OK,
            file_hash=state.file_hash
        )

        return version

    def get_version_backup_path(self, file_id: str, version_number: int) -> Optional[Path]:
        """Get the backup file path for a specific version.

        Args:
            file_id: The file's UUID.
            version_number: The version number.

        Returns:
            Path to the backup file or None if not found.
        """
        tracked_file = self.db.get_file(file_id)
        if not tracked_file:
            return None

        # Check new format first (filename_v1.ext)
        backup_path = self._get_version_path(
            file_id, version_number, tracked_file.display_name
        )
        if backup_path.exists():
            return backup_path

        # Fall back to legacy format (v1.ext)
        legacy_path = self._get_legacy_version_path(
            file_id, version_number, tracked_file.display_name
        )
        if legacy_path.exists():
            return legacy_path

        return None

    def open_version(self, file_id: str, version_number: int) -> bool:
        """Open a specific version's backup file.

        Args:
            file_id: The file's UUID.
            version_number: The version number to open.

        Returns:
            True if the file was opened successfully.
        """
        backup_path = self.get_version_backup_path(file_id, version_number)
        if not backup_path:
            return False

        # Open with default application
        if sys.platform == "darwin":
            subprocess.run(["open", str(backup_path)], check=False)
        elif sys.platform == "win32":
            os.startfile(str(backup_path))
        else:
            subprocess.run(["xdg-open", str(backup_path)], check=False)

        return True

    def restore_version(self, file_id: str, version_number: int) -> bool:
        """Restore a file to a specific version.

        Copies the backup file back to the original location.

        Args:
            file_id: The file's UUID.
            version_number: The version number to restore.

        Returns:
            True if restored successfully.
        """
        tracked_file = self.db.get_file(file_id)
        if not tracked_file:
            return False

        backup_path = self.get_version_backup_path(file_id, version_number)
        if not backup_path:
            return False

        # Copy backup to original location
        target_path = Path(tracked_file.file_path)
        shutil.copy2(backup_path, target_path)

        # Update file metadata
        state = get_file_state(str(target_path))
        self.db.update_file_metadata(
            file_id=file_id,
            file_size=state.file_size,
            modified_time=state.modified_time,
            status=FileStatus.OK
        )

        return True

    def delete_file(self, file_id: str) -> None:
        """Delete a tracked file and all its versions and backups.

        Args:
            file_id: The file's UUID.
        """
        # Delete version backups
        self._delete_version_backups(file_id)
        # Delete database records
        self.db.delete_file(file_id)

    def open_file(self, file_id: str, app_path: Optional[str] = None) -> bool:
        """Open a file with default application or specified app."""
        tracked_file = self.db.get_file(file_id)
        if not tracked_file:
            return False

        path = Path(tracked_file.file_path)
        if not path.exists():
            return False

        if sys.platform == "darwin":
            if app_path:
                subprocess.run(["open", "-a", app_path, str(path)], check=False)
            else:
                subprocess.run(["open", str(path)], check=False)
        elif sys.platform == "win32":
            if app_path:
                subprocess.run([app_path, str(path)], check=False)
            else:
                os.startfile(str(path))
        else:
            if app_path:
                subprocess.run([app_path, str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)

        return True

    def show_in_finder(self, file_id: str) -> bool:
        """Reveal a file in Finder (macOS) or Explorer (Windows)."""
        tracked_file = self.db.get_file(file_id)
        if not tracked_file:
            return False

        path = Path(tracked_file.file_path)
        if not path.exists():
            return False

        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path.parent)], check=False)

        return True

    def show_version_in_finder(self, file_id: str, version_number: int) -> bool:
        """Reveal a version backup file in Finder."""
        backup_path = self.get_version_backup_path(file_id, version_number)
        if not backup_path:
            return False

        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(backup_path)], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(backup_path)], check=False)
        else:
            subprocess.run(["xdg-open", str(backup_path.parent)], check=False)

        return True

    def verify_version_integrity(self, file_id: str, version_number: int) -> VerificationResult:
        """Verify the integrity of a version backup file using hash comparison.

        Args:
            file_id: The file's UUID.
            version_number: The version number to verify.

        Returns:
            VerificationResult with validation status and details.
        """
        # Get the version record
        version = self.get_version(file_id, version_number)
        if not version:
            return VerificationResult(
                is_valid=False,
                expected_hash=None,
                actual_hash=None,
                error="Version not found"
            )

        # Check if hash was stored
        if not version.file_hash:
            return VerificationResult(
                is_valid=False,
                expected_hash=None,
                actual_hash=None,
                error="No hash stored for this version"
            )

        # Get backup file path
        backup_path = self.get_version_backup_path(file_id, version_number)
        if not backup_path:
            return VerificationResult(
                is_valid=False,
                expected_hash=version.file_hash,
                actual_hash=None,
                error="Backup file not found"
            )

        # Verify the hash
        return verify_file_hash(str(backup_path), version.file_hash)

    def verify_all_versions(self, file_id: str) -> dict[int, VerificationResult]:
        """Verify all version backups for a file.

        Args:
            file_id: The file's UUID.

        Returns:
            Dictionary mapping version numbers to their verification results.
        """
        results = {}
        versions = self.get_versions(file_id)
        for version in versions:
            results[version.version_number] = self.verify_version_integrity(
                file_id, version.version_number
            )
        return results

    # Tag operations

    def add_tag_to_file(self, file_id: str, tag_name: str) -> Tag:
        """Add a tag to a file.

        Args:
            file_id: The file's UUID.
            tag_name: The tag name (with or without #).

        Returns:
            The Tag object.
        """
        tag = self.db.get_or_create_tag(tag_name)
        self.db.add_tag_to_file(tag.id, file_id)
        return tag

    def remove_tag_from_file(self, file_id: str, tag_id: str) -> None:
        """Remove a tag from a file.

        Args:
            file_id: The file's UUID.
            tag_id: The tag's UUID.
        """
        self.db.remove_tag_from_file(tag_id, file_id)
        # Clean up unused tags
        self.db.delete_unused_tags()

    def get_file_tags(self, file_id: str) -> list[Tag]:
        """Get all tags for a file.

        Args:
            file_id: The file's UUID.

        Returns:
            List of Tag objects.
        """
        return self.db.get_file_tags(file_id)

    def get_all_tags(self) -> list[Tag]:
        """Get all tags in the system.

        Returns:
            List of all Tag objects.
        """
        return self.db.get_all_tags()

    def get_files_by_tag(self, tag_id: str) -> list[TrackedFile]:
        """Get all files with a specific tag.

        Args:
            tag_id: The tag's UUID.

        Returns:
            List of TrackedFile objects.
        """
        return self.db.get_files_by_tag(tag_id)

    # Pin operations

    def _get_pinned_version_path(self, file_id: str, version_number: int, display_name: str) -> Path:
        """Get the path for a pinned version file.

        Args:
            file_id: The file's UUID.
            version_number: The version number.
            display_name: The file's display name.

        Returns:
            Path for the pinned file.
        """
        if not self._pin_storage_path:
            raise ValueError("Pin storage path is not set")

        # Create subdirectory for the file
        pin_dir = self._pin_storage_path / file_id
        pin_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with version suffix
        path = Path(display_name)
        stem = path.stem
        ext = path.suffix
        return pin_dir / f"{stem}_v{version_number}_pinned{ext}"

    def pin_version(self, file_id: str, version_number: int) -> Optional[str]:
        """Pin a version by copying it to the pin storage.

        Args:
            file_id: The file's UUID.
            version_number: The version number to pin.

        Returns:
            Path to the pinned file, or None if failed.

        Raises:
            ValueError: If pin storage path is not set.
        """
        if not self._pin_storage_path:
            raise ValueError("Pin storage path is not set")

        tracked_file = self.db.get_file(file_id)
        if not tracked_file:
            return None

        # Get the backup file
        backup_path = self.get_version_backup_path(file_id, version_number)
        if not backup_path or not backup_path.exists():
            return None

        # Determine the pinned path
        pinned_path = self._get_pinned_version_path(
            file_id, version_number, tracked_file.display_name
        )

        # Copy to pin storage
        shutil.copy2(backup_path, pinned_path)

        # Update database
        self.db.set_version_pinned(file_id, version_number, True, str(pinned_path))

        return str(pinned_path)

    def unpin_version(self, file_id: str, version_number: int) -> bool:
        """Unpin a version by removing it from the pin storage.

        Args:
            file_id: The file's UUID.
            version_number: The version number to unpin.

        Returns:
            True if successfully unpinned.
        """
        # Get the version to find the pinned path
        version = self.db.get_version_by_number(file_id, version_number)
        if not version or not version.is_pinned:
            return False

        # Delete the pinned file if it exists
        if version.pinned_path:
            pinned_path = Path(version.pinned_path)
            if pinned_path.exists():
                pinned_path.unlink()

            # Clean up empty directory
            if pinned_path.parent.exists() and not any(pinned_path.parent.iterdir()):
                pinned_path.parent.rmdir()

        # Update database
        self.db.set_version_pinned(file_id, version_number, False, None)

        return True

    def toggle_pin_version(self, file_id: str, version_number: int) -> tuple[bool, Optional[str]]:
        """Toggle the pin status of a version.

        Args:
            file_id: The file's UUID.
            version_number: The version number.

        Returns:
            Tuple of (new_is_pinned, pinned_path_or_none).
        """
        version = self.db.get_version_by_number(file_id, version_number)
        if not version:
            return (False, None)

        if version.is_pinned:
            self.unpin_version(file_id, version_number)
            return (False, None)
        else:
            pinned_path = self.pin_version(file_id, version_number)
            return (True, pinned_path)

    def get_pinned_versions(self, file_id: Optional[str] = None) -> list[Version]:
        """Get all pinned versions.

        Args:
            file_id: Optional file ID to filter by.

        Returns:
            List of pinned Version objects.
        """
        return self.db.get_pinned_versions(file_id)

    def show_pinned_version_in_finder(self, file_id: str, version_number: int) -> bool:
        """Reveal a pinned version file in Finder.

        Args:
            file_id: The file's UUID.
            version_number: The version number.

        Returns:
            True if successfully revealed.
        """
        version = self.db.get_version_by_number(file_id, version_number)
        if not version or not version.is_pinned or not version.pinned_path:
            return False

        pinned_path = Path(version.pinned_path)
        if not pinned_path.exists():
            return False

        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(pinned_path)], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(pinned_path)], check=False)
        else:
            subprocess.run(["xdg-open", str(pinned_path.parent)], check=False)

        return True
