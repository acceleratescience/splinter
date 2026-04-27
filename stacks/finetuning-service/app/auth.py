"""Authentication dependency for the fine-tuning service."""

import os

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer()

LITELLM_URL = os.environ["LITELLM_URL"]
LITELLM_MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]


async def verify_litellm_key(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> None:
    """Verify a Bearer token is a valid LiteLLM API key.

    Calls LiteLLM's /key/info endpoint using the service master key.
    Returns normally if the key is valid; raises 401 otherwise.

    Args:
        credentials: The Bearer token extracted from the Authorization
            header by FastAPI's HTTPBearer scheme.

    Raises:
        HTTPException: 401 if the token is not a valid LiteLLM key.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{LITELLM_URL}/key/info",
            params={"key": credentials.credentials},
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=401, detail="Invalid or inactive API key."
        )
