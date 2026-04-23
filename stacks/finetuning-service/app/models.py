"""Pydantic models for the fine-tuning service."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self

from .config import get_allowed_models


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
    hub_model_id: str = Field(
        description=(
            "Hugging Face repo path to push the trained adapter to "
            "(e.g. 'username/my-adapter')."
        )
    )
    num_epochs: int = Field(ge=1)
    learning_rate: float = Field(gt=0)
    micro_batch_size: int = Field(default=4, ge=1)
    gradient_accumulation_steps: int = Field(default=1, ge=1)
    sequence_len: int = Field(default=512, ge=64)
    lora_r: int = Field(ge=1)
    lora_dropout: float = Field(default=0.0, ge=0.0, le=1.0)
    lora_target_modules: list[str] = Field(
        default=["q_proj", "v_proj", "k_proj", "o_proj"]
    )
    load_in_4bit: bool = Field(default=False)
    load_in_8bit: bool = Field(default=False)

    @field_validator("model")
    @classmethod
    def model_must_be_whitelisted(cls, v: str) -> str:
        """Validate the model is on the allowed list.

        Args:
            v: The model repo path to validate.

        Returns:
            The validated model path.

        Raises:
            ValueError: If the model is not on the whitelist.
        """
        allowed = get_allowed_models()
        if v not in allowed:
            raise ValueError(
                f"Model '{v}' is not permitted. Allowed models: {allowed}"
            )
        return v

    @field_validator("lora_target_modules")
    @classmethod
    def lora_target_modules_must_not_be_empty(cls, v: list[str]) -> list[str]:
        """Validate that at least one LoRA target module is specified.

        Args:
            v: The list of target modules.

        Returns:
            The validated list.

        Raises:
            ValueError: If the list is empty.
        """
        if not v:
            raise ValueError(
                "lora_target_modules must contain at least one module."
            )
        return v

    @model_validator(mode="after")
    def quantisation_modes_are_mutually_exclusive(self) -> Self:
        """Validate that 4-bit and 8-bit quantisation are not both set.

        Returns:
            The validated model instance.

        Raises:
            ValueError: If both load_in_4bit and load_in_8bit are True.
        """
        if self.load_in_4bit and self.load_in_8bit:
            raise ValueError(
                "load_in_4bit and load_in_8bit are mutually exclusive."
            )
        return self


class JobResponse(BaseModel):
    """Response body representing a fine-tuning job."""

    id: str
    status: JobStatus
    model: str
    hf_dataset: str
    hub_model_id: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
