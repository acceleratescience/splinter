"""SQLite database setup and job queue operations."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from .models import JobResponse, JobStatus, JobSubmitRequest

DB_PATH = Path("/data/jobs.db")


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yield a database connection with row factory configured.

    Yields:
        An open SQLite connection.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_job(row: sqlite3.Row) -> JobResponse:
    """Convert a database row to a JobResponse.

    Args:
        row: A row from the jobs table.

    Returns:
        A populated JobResponse instance.
    """
    return JobResponse(
        id=row["id"],
        status=JobStatus(row["status"]),
        model=row["model"],
        hf_dataset=row["hf_dataset"],
        suffix=row["suffix"],
        created_at=datetime.fromisoformat(row["created_at"]),
        started_at=(
            datetime.fromisoformat(row["started_at"])
            if row["started_at"]
            else None
        ),
        completed_at=(
            datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None
        ),
        error_message=row["error_message"],
    )


def init_db() -> None:
    """Initialise the database schema if it does not exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id            TEXT PRIMARY KEY,
                status        TEXT NOT NULL,
                model         TEXT NOT NULL,
                hf_dataset    TEXT NOT NULL,
                suffix        TEXT,
                config        TEXT NOT NULL,
                created_at    TEXT NOT NULL,
                started_at    TEXT,
                completed_at  TEXT,
                error_message TEXT
            )
        """)


def recover_running_jobs() -> None:
    """Mark any jobs left running at startup as failed.

    A job in 'running' state when the service exits will never
    complete. This is called at startup to mark such jobs as
    failed rather than leaving them hanging indefinitely.
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET status = ? WHERE status = ?",
            (JobStatus.FAILED, JobStatus.RUNNING),
        )


def create_job(request: JobSubmitRequest) -> JobResponse:
    """Insert a new job record and return it in queued status.

    Args:
        request: The validated job submission request.

    Returns:
        The newly created job.
    """
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    config = json.dumps(
        {
            # TODO: Add hyperparameters/config keys
        }
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, status, model, hf_dataset,
                suffix, config, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                JobStatus.QUEUED,
                request.model,
                request.hf_dataset,
                request.suffix,
                config,
                now,
            ),
        )
    return JobResponse(
        id=job_id,
        status=JobStatus.QUEUED,
        model=request.model,
        hf_dataset=request.hf_dataset,
        suffix=request.suffix,
        created_at=datetime.fromisoformat(now),
    )


def get_job(job_id: str) -> Optional[JobResponse]:
    """Fetch a single job by ID.

    Args:
        job_id: The UUID of the job to retrieve.

    Returns:
        The job if found, otherwise None.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return _row_to_job(row) if row else None


def list_jobs() -> list[JobResponse]:
    """Return all jobs ordered by creation time descending.

    Returns:
        All job records.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_job(row) for row in rows]


def cancel_job(job_id: str) -> Optional[JobResponse]:
    """Cancel a queued job.

    Only jobs in 'queued' status are affected. Jobs already
    running must be stopped via the process termination path.

    Args:
        job_id: The UUID of the job to cancel.

    Returns:
        The updated job if found, otherwise None.
    """
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs SET status = ?
            WHERE id = ? AND status = ?
            """,
            (JobStatus.CANCELLED, job_id, JobStatus.QUEUED),
        )
    return get_job(job_id)
