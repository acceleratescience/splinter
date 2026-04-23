"""Service configuration loader."""

from pathlib import Path

import yaml

CONFIG_PATH = Path("/app/config.yaml")


def load_config() -> dict:
    """Load the service configuration from disk.

    Returns:
        The parsed configuration dictionary.
    """
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f)


def get_allowed_models() -> list[str]:
    """Return the list of models permitted for fine-tuning.

    Returns:
        A list of allowed Hugging Face model repo paths.
    """
    return load_config().get("allowed_models", [])
