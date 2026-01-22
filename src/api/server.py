"""FastAPI server for Versioned File Manager."""
import os
import sys
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, FileStatus, EventType
from core import FileService


# Pydantic models for API
class FileResponse(BaseModel):
    id: str
    display_name: str
    file_path: str
    file_size: int
    modified_time: float
    status: str
    created_at: str
    file_hash: Optional[str] = None
    is_favorite: bool = False
    is_archived: bool = False
    project_id: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    color: str
    created_at: str
    file_count: int = 0


class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#007AFF"


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class VersionResponse(BaseModel):
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


class TagResponse(BaseModel):
    id: str
    name: str
    created_at: str


class EventResponse(BaseModel):
    id: str
    file_id: str
    event_type: str
    description: Optional[str] = None
    created_at: str


class RegisterFileRequest(BaseModel):
    file_path: str
    commit_message: str
    display_name: Optional[str] = None


class NewVersionRequest(BaseModel):
    commit_message: str


class AddTagRequest(BaseModel):
    tag_name: str


class VerificationResult(BaseModel):
    is_valid: bool
    message: str


# Global services
db_manager: Optional[DatabaseManager] = None
file_service: Optional[FileService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global db_manager, file_service

    # Get data directory from environment or use default
    data_dir = os.environ.get("VFM_DATA_DIR", str(Path.home() / ".vfm"))
    db_path = os.path.join(data_dir, "vfm.db")
    pin_storage = os.path.join(data_dir, "pinned")

    # Initialize services
    db_manager = DatabaseManager(db_path)
    file_service = FileService(db_manager, data_dir, pin_storage)

    # Migrate existing files
    file_service.migrate_existing_files()

    print(f"Server started with data directory: {data_dir}")
    yield
    print("Server shutting down")


app = FastAPI(
    title="Versioned File Manager API",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for Swift app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper functions
def file_to_response(f) -> FileResponse:
    return FileResponse(
        id=f.id,
        display_name=f.display_name,
        file_path=f.file_path,
        file_size=f.file_size,
        modified_time=f.modified_time,
        status=f.status.value,
        created_at=f.created_at,
        file_hash=f.file_hash,
        is_favorite=f.is_favorite,
        is_archived=f.is_archived,
        project_id=f.project_id
    )


def project_to_response(p, file_count: int = 0) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        color=p.color,
        created_at=p.created_at,
        file_count=file_count
    )


def version_to_response(v) -> VersionResponse:
    return VersionResponse(
        id=v.id,
        file_id=v.file_id,
        version_number=v.version_number,
        commit_message=v.commit_message,
        file_size=v.file_size,
        modified_time=v.modified_time,
        created_at=v.created_at,
        file_hash=v.file_hash,
        is_pinned=v.is_pinned,
        pinned_path=v.pinned_path
    )


def tag_to_response(t) -> TagResponse:
    return TagResponse(
        id=t.id,
        name=t.name,
        created_at=t.created_at
    )


def event_to_response(e) -> EventResponse:
    return EventResponse(
        id=e.id,
        file_id=e.file_id,
        event_type=e.event_type.value,
        description=e.description,
        created_at=e.created_at
    )


# ============ File Endpoints ============

@app.get("/api/files", response_model=list[FileResponse])
async def get_all_files(include_archived: bool = False):
    """Get all tracked files."""
    files = db_manager.get_all_files(include_archived=include_archived)
    return [file_to_response(f) for f in files]


@app.get("/api/files/{file_id}", response_model=FileResponse)
async def get_file(file_id: str):
    """Get a specific file by ID."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return file_to_response(f)


@app.post("/api/files", response_model=FileResponse)
async def register_file(request: RegisterFileRequest):
    """Register a new file for tracking."""
    try:
        tracked_file, version = file_service.register_file(
            file_path=request.file_path,
            commit_message=request.commit_message,
            display_name=request.display_name
        )
        return file_to_response(tracked_file)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/files/{file_id}")
async def delete_file(file_id: str):
    """Delete a tracked file."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    file_service.delete_file(file_id)
    return {"status": "deleted"}


@app.post("/api/files/{file_id}/verify", response_model=FileResponse)
async def verify_file(file_id: str):
    """Verify a file's status."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    status = file_service.verify_file(file_id)

    # Record event
    if status == FileStatus.MODIFIED:
        db_manager.create_event(file_id, EventType.VERIFY_MODIFIED, "File has been modified")
    elif status == FileStatus.MISSING:
        db_manager.create_event(file_id, EventType.VERIFY_MISSING, "File is missing")
    else:
        db_manager.create_event(file_id, EventType.VERIFY_OK, "File integrity verified")

    updated_file = file_service.get_file(file_id)
    return file_to_response(updated_file)


@app.post("/api/files/{file_id}/open")
async def open_file(file_id: str):
    """Open a file with the default application."""
    if not file_service.open_file(file_id):
        raise HTTPException(status_code=400, detail="Could not open file")
    return {"status": "opened"}


@app.post("/api/files/{file_id}/reveal")
async def reveal_file(file_id: str):
    """Reveal a file in Finder."""
    if not file_service.show_in_finder(file_id):
        raise HTTPException(status_code=400, detail="Could not reveal file")
    return {"status": "revealed"}


@app.put("/api/files/{file_id}/favorite")
async def toggle_favorite(file_id: str):
    """Toggle favorite status."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    is_favorite = db_manager.toggle_favorite(file_id)
    return {"is_favorite": is_favorite}


@app.put("/api/files/{file_id}/archive")
async def set_archived(file_id: str, archived: bool = True):
    """Archive or unarchive a file."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    db_manager.set_archived(file_id, archived)
    return {"is_archived": archived}


@app.put("/api/files/{file_id}/name")
async def update_name(file_id: str, name: str):
    """Update file display name."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    db_manager.update_display_name(file_id, name)
    return {"display_name": name}


# ============ Version Endpoints ============

@app.get("/api/files/{file_id}/versions", response_model=list[VersionResponse])
async def get_versions(file_id: str):
    """Get all versions for a file."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    versions = file_service.get_versions(file_id)
    return [version_to_response(v) for v in versions]


@app.post("/api/files/{file_id}/versions", response_model=VersionResponse)
async def create_version(file_id: str, request: NewVersionRequest):
    """Create a new version for a file."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        version = file_service.create_new_version(file_id, request.commit_message)
        return version_to_response(version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/files/{file_id}/versions/{version_number}/restore")
async def restore_version(file_id: str, version_number: int):
    """Restore a file to a specific version."""
    if not file_service.restore_version(file_id, version_number):
        raise HTTPException(status_code=400, detail="Could not restore version")

    db_manager.create_event(file_id, EventType.RESTORE, f"Restored to version {version_number}")
    return {"status": "restored"}


@app.post("/api/files/{file_id}/versions/{version_number}/open")
async def open_version(file_id: str, version_number: int):
    """Open a specific version."""
    if not file_service.open_version(file_id, version_number):
        raise HTTPException(status_code=400, detail="Could not open version")
    return {"status": "opened"}


@app.post("/api/files/{file_id}/versions/{version_number}/reveal")
async def reveal_version(file_id: str, version_number: int):
    """Reveal a version backup in Finder."""
    if not file_service.show_version_in_finder(file_id, version_number):
        raise HTTPException(status_code=400, detail="Could not reveal version")
    return {"status": "revealed"}


@app.post("/api/files/{file_id}/versions/{version_number}/verify", response_model=VerificationResult)
async def verify_version(file_id: str, version_number: int):
    """Verify a version's integrity."""
    result = file_service.verify_version_integrity(file_id, version_number)
    if result.is_valid:
        return VerificationResult(is_valid=True, message=f"Version {version_number} verified")
    else:
        return VerificationResult(is_valid=False, message=result.error or "Verification failed")


@app.post("/api/files/{file_id}/versions/{version_number}/pin")
async def toggle_pin(file_id: str, version_number: int):
    """Toggle pin status for a version."""
    try:
        is_pinned, pinned_path = file_service.toggle_pin_version(file_id, version_number)

        if is_pinned:
            db_manager.create_event(file_id, EventType.PIN, f"Version {version_number} pinned")
        else:
            db_manager.create_event(file_id, EventType.UNPIN, f"Version {version_number} unpinned")

        return {"is_pinned": is_pinned, "pinned_path": pinned_path}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/files/{file_id}/versions/{version_number}/reveal-pinned")
async def reveal_pinned_version(file_id: str, version_number: int):
    """Reveal a pinned version in Finder."""
    if not file_service.show_pinned_version_in_finder(file_id, version_number):
        raise HTTPException(status_code=400, detail="Could not reveal pinned version")
    return {"status": "revealed"}


# ============ Tag Endpoints ============

@app.get("/api/files/{file_id}/tags", response_model=list[TagResponse])
async def get_file_tags(file_id: str):
    """Get all tags for a file."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    tags = file_service.get_file_tags(file_id)
    return [tag_to_response(t) for t in tags]


@app.post("/api/files/{file_id}/tags", response_model=TagResponse)
async def add_tag(file_id: str, request: AddTagRequest):
    """Add a tag to a file."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    tag = file_service.add_tag_to_file(file_id, request.tag_name)
    return tag_to_response(tag)


@app.delete("/api/files/{file_id}/tags/{tag_id}")
async def remove_tag(file_id: str, tag_id: str):
    """Remove a tag from a file."""
    file_service.remove_tag_from_file(file_id, tag_id)
    return {"status": "removed"}


@app.get("/api/tags", response_model=list[TagResponse])
async def get_all_tags():
    """Get all tags."""
    tags = file_service.get_all_tags()
    return [tag_to_response(t) for t in tags]


# ============ Metadata Endpoints ============

@app.get("/api/files/{file_id}/metadata")
async def get_metadata(file_id: str):
    """Get metadata for a file."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    metadata = db_manager.get_metadata(file_id)
    return metadata or {}


@app.post("/api/files/{file_id}/metadata")
async def extract_metadata(file_id: str):
    """Extract and store metadata for a file."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        metadata = file_service.extract_metadata(file_id)
        return metadata
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Event Endpoints ============

@app.get("/api/files/{file_id}/events", response_model=list[EventResponse])
async def get_events(file_id: str, limit: Optional[int] = None):
    """Get events for a file."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    events = db_manager.get_events(file_id, limit=limit)
    return [event_to_response(e) for e in events]


# ============ Project Endpoints ============

@app.get("/api/projects", response_model=list[ProjectResponse])
async def get_projects():
    """Get all projects."""
    projects = db_manager.get_all_projects()
    return [project_to_response(p, db_manager.get_project_file_count(p.id)) for p in projects]


@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(request: CreateProjectRequest):
    """Create a new project."""
    project = db_manager.create_project(
        name=request.name,
        description=request.description,
        color=request.color
    )
    return project_to_response(project, 0)


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """Get a project by ID."""
    project = db_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    file_count = db_manager.get_project_file_count(project_id)
    return project_to_response(project, file_count)


@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, request: UpdateProjectRequest):
    """Update a project."""
    project = db_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db_manager.update_project(
        project_id,
        name=request.name,
        description=request.description,
        color=request.color
    )
    updated = db_manager.get_project(project_id)
    file_count = db_manager.get_project_file_count(project_id)
    return project_to_response(updated, file_count)


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project (files will be unassigned)."""
    project = db_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db_manager.delete_project(project_id)
    return {"status": "deleted"}


@app.get("/api/projects/{project_id}/files", response_model=list[FileResponse])
async def get_project_files(
    project_id: str,
    include_archived: bool = Query(False)
):
    """Get all files in a project."""
    project = db_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    files = db_manager.get_files_by_project(project_id, include_archived)
    return [file_to_response(f) for f in files]


@app.put("/api/files/{file_id}/project")
async def set_file_project(file_id: str, project_id: Optional[str] = Query(None)):
    """Assign a file to a project (or unassign if project_id is None)."""
    f = file_service.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if project_id:
        project = db_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    db_manager.set_file_project(file_id, project_id)
    return {"status": "updated", "project_id": project_id}


# ============ Utility Endpoints ============

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.post("/api/verify-all")
async def verify_all_files():
    """Verify all tracked files."""
    results = file_service.verify_all_files()
    summary = {
        "total": len(results),
        "ok": sum(1 for s in results.values() if s == FileStatus.OK),
        "modified": sum(1 for s in results.values() if s == FileStatus.MODIFIED),
        "missing": sum(1 for s in results.values() if s == FileStatus.MISSING),
    }
    return summary


def start_server(host: str = "127.0.0.1", port: int = 8765):
    """Start the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
