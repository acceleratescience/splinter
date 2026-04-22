"""Pydantic models for the fine-tuning service."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status values for a fine-tuning job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSubmitRequest(BaseModel):
    """Request body for submitting a fine-tuning job."""

    model: str = Field(
        description="Hugging Face model repo path for fine-tuning."
    )
    hf_dataset: str = Field(description="Hugging Face dataset path.")
    hf_token: str = Field(
        description=(
            "Hugging Face token with read access to the training dataset "
            "and write access to the adapter destination."
        )
    )
    suffix: Optional[str] = Field(
        default=None,
        description="Label appended to the adapter repository name.",
    )
    # TODO: add hyperparameters/config keys
    #   (minimal subset of keys from axolotl config reference)


class JobResponse(BaseModel):
    """Response body representing a fine-tuning job."""

    id: str
    status: JobStatus
    model: str
    hf_dataset: str
    suffix: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
