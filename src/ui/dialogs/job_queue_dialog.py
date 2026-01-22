from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QLabel,
    QProgressBar,
)

from core.job_queue import JobQueue, Job, JobStatus


class JobQueueDialog(QDialog):
    """Popup dialog to monitor background jobs."""

    def __init__(self, job_queue: JobQueue, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Job Queue")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.resize(640, 360)

        self.job_queue = job_queue
        self.rows: Dict[str, int] = {}

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["설명", "유형", "상태", "진행률", "오류"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for idx in range(1, 5):
            header.setSectionResizeMode(idx, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        self.status_label = QLabel("대기 중")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.pause_btn = QPushButton("일시정지")
        self.resume_btn = QPushButton("재개")
        self.cancel_btn = QPushButton("취소")
        self.hide_done_btn = QPushButton("완료 숨기기")
        self.clear_done_btn = QPushButton("완료 지우기")
        self.close_btn = QPushButton("닫기")

        self.hide_done_btn.setCheckable(True)

        self.pause_btn.clicked.connect(self.job_queue.pause_current)
        self.resume_btn.clicked.connect(self.job_queue.resume_current)
        self.cancel_btn.clicked.connect(self.job_queue.cancel_current)
        self.hide_done_btn.toggled.connect(self._apply_filters)
        self.clear_done_btn.clicked.connect(self._clear_completed)
        self.close_btn.clicked.connect(self.close)

        for btn in (
            self.pause_btn,
            self.resume_btn,
            self.cancel_btn,
            self.hide_done_btn,
            self.clear_done_btn,
            self.close_btn,
        ):
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        # Connect signals
        self.job_queue.job_updated.connect(self._on_job_update)
        self.job_queue.job_completed.connect(self._on_job_update)

    def _ensure_row(self, job: Job) -> int:
        if job.id in self.rows:
            return self.rows[job.id]
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.rows[job.id] = row
        return row

    def _on_job_update(self, job: Job) -> None:
        row = self._ensure_row(job)
        self.table.setItem(row, 0, QTableWidgetItem(job.description))
        self.table.setItem(row, 1, QTableWidgetItem(job.job_type.value))
        self.table.setItem(row, 2, QTableWidgetItem(job.status.value))
        progress_widget = self.table.cellWidget(row, 3)
        if not progress_widget:
            progress_widget = QProgressBar()
            progress_widget.setRange(0, 100)
            self.table.setCellWidget(row, 3, progress_widget)
        progress_widget.setValue(job.progress)
        self.table.setItem(row, 4, QTableWidgetItem(job.error or ""))

        current_text = f"현재 상태: {job.status.value}"
        if job.status == JobStatus.RUNNING:
            current_text += f" ({job.progress}%)"
        if job.status == JobStatus.FAILED and job.error:
            current_text += f" - {job.error}"
        self.status_label.setText(current_text)
        self._apply_filters()

    def _apply_filters(self) -> None:
        hide_done = self.hide_done_btn.isChecked()
        for job_id, row in self.rows.items():
            status_item = self.table.item(row, 2)
            if not status_item:
                continue
            status = status_item.text()
            is_done = status in {JobStatus.COMPLETED.value, JobStatus.CANCELED.value, JobStatus.FAILED.value}
            self.table.setRowHidden(row, hide_done and is_done)

    def _clear_completed(self) -> None:
        # Remove completed/canceled/failed rows from the table
        to_remove = []
        for job_id, row in list(self.rows.items()):
            status_item = self.table.item(row, 2)
            if status_item and status_item.text() in {
                JobStatus.COMPLETED.value,
                JobStatus.CANCELED.value,
                JobStatus.FAILED.value,
            }:
                to_remove.append((job_id, row))

        # Remove from bottom to avoid reindex issues
        for job_id, row in sorted(to_remove, key=lambda x: x[1], reverse=True):
            self.table.removeRow(row)
            self.rows.pop(job_id, None)
