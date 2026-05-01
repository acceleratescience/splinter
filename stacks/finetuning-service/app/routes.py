"""Route handlers for fine-tuning job management."""

from fastapi import APIRouter, HTTPException

from .database import cancel_job, create_job, get_job, list_jobs
from .models import JobResponse, JobSubmitRequest

router = APIRouter()


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def submit_job(request: JobSubmitRequest) -> JobResponse:
    """Submit a new fine-tuning job.

    Args:
        request: The job configuration.

    Returns:
        The created job with queued status.
    """
    return create_job(request)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str) -> JobResponse:
    """Retrieve the status of a fine-tuning job.

    Args:
        job_id: The UUID of the job.

    Returns:
        The current job state.

    Raises:
        HTTPException: 404 if the job does not exist.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.get("/jobs", response_model=list[JobResponse])
async def list_all_jobs() -> list[JobResponse]:
    """List all fine-tuning jobs.

    Returns:
        All jobs ordered by creation time descending.
    """
    return list_jobs()


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobResponse,
)
async def cancel_job_handler(job_id: str) -> JobResponse:
    """Cancel a queued fine-tuning job.

    Args:
        job_id: The UUID of the job to cancel.

    Returns:
        The updated job record.

    Raises:
        HTTPException: 404 if the job does not exist.
    """
    job = cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job
