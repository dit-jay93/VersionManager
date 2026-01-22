"""File verification and change detection logic."""
import hashlib
import os
from pathlib import Path
from typing import NamedTuple, Optional

from database.models import TrackedFile, FileStatus

# Try to use xxhash for faster hashing, fall back to sha256
try:
    import xxhash
    HASH_ALGORITHM = "xxhash64"
except ImportError:
    xxhash = None
    HASH_ALGORITHM = "sha256"


class FileState(NamedTuple):
    """Current state of a file on disk."""
    exists: bool
    file_size: int
    modified_time: float
    file_hash: Optional[str] = None


def compute_file_hash(file_path: str, chunk_size: int = 65536) -> Optional[str]:
    """Compute hash of a file.

    Args:
        file_path: Path to the file.
        chunk_size: Size of chunks to read (default 64KB).

    Returns:
        Hex string of the file hash, or None if file doesn't exist.
    """
    path = Path(file_path)
    if not path.exists():
        return None

    try:
        if xxhash is not None:
            hasher = xxhash.xxh64()
        else:
            hasher = hashlib.sha256()

        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)

        return hasher.hexdigest()
    except (IOError, OSError):
        return None


def get_file_state(file_path: str, compute_hash: bool = True) -> FileState:
    """Get the current state of a file on disk.

    Args:
        file_path: Path to the file.
        compute_hash: Whether to compute file hash (default True).

    Returns:
        FileState with current file information.
    """
    path = Path(file_path)

    if not path.exists():
        return FileState(exists=False, file_size=0, modified_time=0.0, file_hash=None)

    stat = path.stat()
    file_hash = compute_file_hash(file_path) if compute_hash else None

    return FileState(
        exists=True,
        file_size=stat.st_size,
        modified_time=stat.st_mtime,
        file_hash=file_hash
    )


def check_file_status(tracked_file: TrackedFile, use_hash: bool = True) -> FileStatus:
    """Check if a tracked file has been modified or is missing.

    Uses a two-stage verification:
    1. Quick check: size + mtime comparison
    2. Deep check: hash comparison (if size/mtime changed or hash is stored)

    Args:
        tracked_file: The TrackedFile to verify.
        use_hash: Whether to use hash verification (default True).

    Returns:
        FileStatus indicating the current state.
    """
    # Quick check without hash first
    state = get_file_state(tracked_file.file_path, compute_hash=False)

    if not state.exists:
        return FileStatus.MISSING

    # Check if size or mtime changed
    if (state.file_size != tracked_file.file_size or
            state.modified_time != tracked_file.modified_time):
        # Size/mtime changed - verify with hash if available
        if use_hash and tracked_file.file_hash:
            current_hash = compute_file_hash(tracked_file.file_path)
            if current_hash and current_hash == tracked_file.file_hash:
                # Hash matches - file content is same, just metadata changed
                return FileStatus.OK
        return FileStatus.MODIFIED

    # Size and mtime match - file is OK
    return FileStatus.OK


def has_file_changed(
    tracked_file: TrackedFile,
    current_state: FileState
) -> bool:
    """Check if file has changed compared to tracked metadata.

    Args:
        tracked_file: The TrackedFile to check.
        current_state: Current file state from disk.

    Returns:
        True if the file has changed.
    """
    if not current_state.exists:
        return True

    return (
        current_state.file_size != tracked_file.file_size or
        current_state.modified_time != tracked_file.modified_time
    )


class VerificationResult(NamedTuple):
    """Result of a hash verification."""
    is_valid: bool
    expected_hash: Optional[str]
    actual_hash: Optional[str]
    error: Optional[str] = None


def verify_file_hash(file_path: str, expected_hash: str) -> VerificationResult:
    """Verify a file's hash against an expected value.

    Args:
        file_path: Path to the file to verify.
        expected_hash: Expected hash value.

    Returns:
        VerificationResult with validation status and details.
    """
    path = Path(file_path)

    if not path.exists():
        return VerificationResult(
            is_valid=False,
            expected_hash=expected_hash,
            actual_hash=None,
            error="File not found"
        )

    try:
        actual_hash = compute_file_hash(file_path)
        if actual_hash is None:
            return VerificationResult(
                is_valid=False,
                expected_hash=expected_hash,
                actual_hash=None,
                error="Failed to compute hash"
            )

        is_valid = actual_hash == expected_hash
        return VerificationResult(
            is_valid=is_valid,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
            error=None if is_valid else "Hash mismatch"
        )
    except Exception as e:
        return VerificationResult(
            is_valid=False,
            expected_hash=expected_hash,
            actual_hash=None,
            error=str(e)
        )
