"""Queue worker for processing fine-tuning jobs."""

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import yaml
from app.config import load_config
from app.database import (
    claim_job,
    complete_job,
    get_next_queued_job,
    init_db,
    recover_running_jobs,
)
from app.models import JobStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
MAX_DURATION = int(os.getenv("MAX_JOB_DURATION_HOURS", "4")) * 3600
WORK_DIR = Path("/tmp/finetuning")


def build_axolotl_config(
    job_id: str,
    model: str,
    hf_dataset: str,
    hub_model_id: str,
    user_config: dict,
) -> Path:
    """Build an Axolotl config file for a job.

    Merges the service base config with user-provided settings
    and writes the result to a per-job temp directory.

    Args:
        job_id: The UUID of the job.
        model: The HuggingFace model repo path.
        hf_dataset: The HuggingFace dataset repo path.
        hub_model_id: The destination HuggingFace repo for the adapter.
        user_config: The user-provided training configuration.

    Returns:
        Path to the generated config file.
    """
    job_dir = WORK_DIR / job_id
    output_dir = job_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    base = load_config().get("axolotl_base_config", {})
    lora_r = user_config["lora_r"]

    config = {
        **base,
        "base_model": model,
        "output_dir": str(output_dir),
        "hub_model_id": hub_model_id,
        "datasets": [
            {
                "path": hf_dataset,
                "type": "chat_template",
                "split": "train",
            }
        ],
        **(
            {
                "test_datasets": [
                    {
                        "path": hf_dataset,
                        "type": "chat_template",
                        "split": "validation",
                    }
                ]
            }
            if user_config.get("do_eval")
            else {"eval_strategy": "no"}
        ),
        **(
            {
                "use_wandb": True,
                "wandb_project": user_config["wandb_project"],
                **(
                    {"wandb_entity": user_config["wandb_entity"]}
                    if user_config.get("wandb_entity")
                    else {}
                ),
            }
            if user_config.get("wandb_project")
            else {}
        ),
        "num_epochs": user_config["num_epochs"],
        "learning_rate": user_config["learning_rate"],
        "micro_batch_size": user_config["micro_batch_size"],
        "gradient_accumulation_steps": (
            user_config["gradient_accumulation_steps"]
        ),
        "sequence_len": user_config["sequence_len"],
        "lora_r": lora_r,
        "lora_alpha": lora_r * 2,
        "lora_dropout": user_config["lora_dropout"],
        "lora_target_modules": user_config["lora_target_modules"],
        "load_in_4bit": user_config["load_in_4bit"],
        "load_in_8bit": user_config["load_in_8bit"],
    }

    config_path = job_dir / "config.yaml"
    with config_path.open("w") as f:
        yaml.dump(config, f)

    log.info("Generated Axolotl config for job %s.", job_id)
    return config_path


def run_job(
    job_id: str,
    model: str,
    hf_dataset: str,
    hf_token: str,
    hub_model_id: str,
    wandb_token: Optional[str],
    user_config: dict,
) -> None:
    """Execute a fine-tuning job.

    Generates the Axolotl config, runs the training subprocess,
    and cleans up the temp directory on completion or failure.

    Args:
        job_id: The UUID of the job.
        model: The HuggingFace model repo path.
        hf_dataset: The HuggingFace dataset repo path.
        hf_token: The HuggingFace token for dataset and Hub access.
        hub_model_id: The destination HuggingFace repo for the adapter.
        wandb_token: Optional Weights & Biases API key.
        user_config: The user-provided training configuration.
    """
    job_dir = WORK_DIR / job_id
    error_message: Optional[str] = None
    final_status = JobStatus.SUCCEEDED

    try:
        config_path = build_axolotl_config(
            job_id, model, hf_dataset, hub_model_id, user_config
        )
        env = {**os.environ, "HF_TOKEN": hf_token}
        if wandb_token:
            env["WANDB_API_KEY"] = wandb_token
        subprocess.run(
            ["axolotl", "train", str(config_path)],
            env=env,
            timeout=MAX_DURATION,
            check=True,
        )
        log.info("Job %s completed successfully.", job_id)
    except subprocess.TimeoutExpired:
        error_message = "Job exceeded maximum wall-clock duration."
        final_status = JobStatus.FAILED
        log.error("Job %s timed out.", job_id)
    except subprocess.CalledProcessError as e:
        error_message = f"Training failed with exit code {e.returncode}."
        final_status = JobStatus.FAILED
        log.error("Job %s failed: %s", job_id, e)
    finally:
        complete_job(job_id, final_status, error_message)
        if job_dir.exists():
            shutil.rmtree(job_dir)
            log.info("Cleaned up temp dir for job %s.", job_id)


def main() -> None:
    """Main worker loop.

    Polls the job queue at a fixed interval and processes
    one job at a time.
    """
    init_db()
    recover_running_jobs()
    log.info(
        "Worker started. Polling every %ds, max job duration %dh.",
        POLL_INTERVAL,
        MAX_DURATION // 3600,
    )
    while True:
        job = get_next_queued_job()
        if job:
            log.info("Claiming job %s.", job.id)
            if claim_job(job.id):
                log.info("Running job %s.", job.id)
                user_config = json.loads(job.config)
                run_job(
                    job.id,
                    job.model,
                    job.hf_dataset,
                    job.hf_token,
                    job.hub_model_id,
                    job.wandb_token,
                    user_config,
                )
        else:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
