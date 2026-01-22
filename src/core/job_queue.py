"""Lightweight job queue for background operations (verify, pin copy, restore, relink)."""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from typing import Callable, Dict, Optional, Any

from PySide6.QtCore import QObject, Signal


class JobType(str, Enum):
    VERIFY_ALL = "verify_all"
    PIN_COPY = "pin_copy"
    RESTORE = "restore"
    RELINK_SCAN = "relink_scan"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class Job:
    """Represents a background job."""

    job_type: JobType
    description: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0  # 0-100
    error: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.job_type.value,
            "description": self.description,
            "status": self.status.value,
            "progress": self.progress,
            "error": self.error,
        }


class JobQueue(QObject):
    """Simple in-memory job queue with worker pool."""

    job_updated = Signal(Job)
    job_completed = Signal(Job)

    def __init__(self, max_workers: int = 1):
        super().__init__()
        self._queue: Queue[Optional[Job]] = Queue()
        self._handlers: Dict[JobType, Callable[[Job], None]] = {}
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._running_jobs: Dict[str, Job] = {}
        self._workers: list[threading.Thread] = []
        self._max_workers = max(1, max_workers)
        self._start_workers(self._max_workers)

    def register_handler(self, job_type: JobType, handler: Callable[[Job], None]) -> None:
        """Register a handler function for a job type."""
        self._handlers[job_type] = handler

    def enqueue(self, job: Job) -> Job:
        self._queue.put(job)
        self.job_updated.emit(job)
        return job

    def stop(self) -> None:
        self._stop_event.set()
        for _ in self._workers:
            self._queue.put(None)

    def pause_current(self) -> None:
        # Pause all running jobs collectively
        if self._running_jobs:
            self._pause_event.set()
            for job in self._running_jobs.values():
                if job.status == JobStatus.RUNNING:
                    job.status = JobStatus.PAUSED
                    self.job_updated.emit(job)

    def resume_current(self) -> None:
        if self._running_jobs:
            self._pause_event.clear()
            for job in self._running_jobs.values():
                if job.status == JobStatus.PAUSED:
                    job.status = JobStatus.RUNNING
                    self.job_updated.emit(job)

    def cancel_current(self) -> None:
        if self._running_jobs:
            for job in list(self._running_jobs.values()):
                if job.status in {JobStatus.RUNNING, JobStatus.PAUSED}:
                    job.status = JobStatus.CANCELED
                    self.job_updated.emit(job)
            self._pause_event.clear()

    def set_max_workers(self, max_workers: int) -> None:
        max_workers = max(1, max_workers)
        if max_workers == self._max_workers:
            return
        if max_workers > self._max_workers:
            self._start_workers(max_workers - self._max_workers)
        else:
            # request extra workers to stop via sentinel
            diff = self._max_workers - max_workers
            for _ in range(diff):
                self._queue.put(None)
        self._max_workers = max_workers

    def _start_workers(self, count: int) -> None:
        for _ in range(count):
            worker = threading.Thread(target=self._run, daemon=True)
            self._workers.append(worker)
            worker.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = self._queue.get(timeout=0.2)
            except Empty:
                continue

            if job is None:
                break

            self._running_jobs[job.id] = job
            job.status = JobStatus.RUNNING
            job.progress = 0
            self.job_updated.emit(job)

            handler = self._handlers.get(job.job_type)
            if not handler:
                job.status = JobStatus.FAILED
                job.error = "No handler for job type"
                self.job_completed.emit(job)
                self._running_jobs.pop(job.id, None)
                continue

            try:
                # allow pause to gate work loops inside handler via callback
                handler(job)
                if job.status not in {JobStatus.CANCELED, JobStatus.FAILED}:
                    job.status = JobStatus.COMPLETED
                    job.progress = 100
            except Exception as exc:  # pragma: no cover - defensive
                job.status = JobStatus.FAILED
                job.error = str(exc)
            finally:
                self.job_completed.emit(job)
                self._running_jobs.pop(job.id, None)

    # Utility for handlers
    def wait_if_paused_or_canceled(self, job: Job) -> bool:
        """Return False if canceled, True otherwise. Blocks while paused."""
        while True:
            if job.status == JobStatus.CANCELED:
                return False
            if self._pause_event.is_set():
                self._pause_event.wait(0.2)
                continue
            return True
