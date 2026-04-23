"""SQLite database setup and job queue operations."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from .models import JobResponse, JobStatus, JobSubmitRequest

DB_PATH = Path("/data/jobs.db")


@dataclass
class JobDetail:
    """Internal job representation including sensitive fields.

    Not exposed via the API. Used by the worker to access the
    HF token and full training config.
    """

    id: str
    model: str
    hf_dataset: str
    hf_token: str
    hub_model_id: str
    config: str
    status: JobStatus


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
        hub_model_id=row["hub_model_id"],
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
                hf_token      TEXT,
                hub_model_id  TEXT NOT NULL,
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
            "num_epochs": request.num_epochs,
            "learning_rate": request.learning_rate,
            "micro_batch_size": request.micro_batch_size,
            "gradient_accumulation_steps": (
                request.gradient_accumulation_steps
            ),
            "sequence_len": request.sequence_len,
            "lora_r": request.lora_r,
            "lora_dropout": request.lora_dropout,
            "lora_target_modules": request.lora_target_modules,
            "load_in_4bit": request.load_in_4bit,
            "load_in_8bit": request.load_in_8bit,
        }
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, status, model, hf_dataset, hf_token,
                hub_model_id, config, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                JobStatus.QUEUED,
                request.model,
                request.hf_dataset,
                request.hf_token,
                request.hub_model_id,
                config,
                now,
            ),
        )
    return JobResponse(
        id=job_id,
        status=JobStatus.QUEUED,
        model=request.model,
        hf_dataset=request.hf_dataset,
        hub_model_id=request.hub_model_id,
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


def get_next_queued_job() -> Optional[JobDetail]:
    """Fetch the oldest queued job for the worker to process.

    Returns:
        A JobDetail if a queued job exists, otherwise None.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (JobStatus.QUEUED,),
        ).fetchone()
    if not row:
        return None
    return JobDetail(
        id=row["id"],
        model=row["model"],
        hf_dataset=row["hf_dataset"],
        hf_token=row["hf_token"],
        hub_model_id=row["hub_model_id"],
        config=row["config"],
        status=JobStatus(row["status"]),
    )


def claim_job(job_id: str) -> bool:
    """Atomically mark a queued job as running.

    Args:
        job_id: The UUID of the job to claim.

    Returns:
        True if the job was successfully claimed, False if it
        was already claimed by another process.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE jobs SET status = ?, started_at = ?
            WHERE id = ? AND status = ?
            """,
            (JobStatus.RUNNING, now, job_id, JobStatus.QUEUED),
        )
        return result.rowcount > 0


def complete_job(
    job_id: str,
    status: JobStatus,
    error_message: Optional[str] = None,
) -> None:
    """Mark a job as completed and clear its HF token.

    Args:
        job_id: The UUID of the job to complete.
        status: The final status (succeeded or failed).
        error_message: Optional error description for failed jobs.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                completed_at = ?,
                error_message = ?,
                hf_token = NULL
            WHERE id = ?
            """,
            (status, now, error_message, job_id),
        )
