"""Dialog components for Versioned File Manager."""
from ui.dialogs.commit_dialog import CommitDialog
from ui.dialogs.delete_dialog import DeleteDialog, DeleteOption
from ui.dialogs.job_queue_dialog import JobQueueDialog
from ui.dialogs.relink_dialog import RelinkDialog, RelinkOptions
from ui.dialogs.open_with_dialog import OpenWithDialog, OpenWithChoice

__all__ = [
    "CommitDialog",
    "DeleteDialog",
    "DeleteOption",
    "JobQueueDialog",
    "RelinkDialog",
    "RelinkOptions",
    "OpenWithDialog",
    "OpenWithChoice",
]
