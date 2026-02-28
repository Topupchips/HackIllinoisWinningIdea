"""
Optional API key authentication.
When API_KEY is set, requests must include X-API-Key header.
"""
from fastapi import Header, HTTPException, status

from config import API_KEY


async def verify_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    """Dependency: require valid API key when API_KEY is configured."""
    if not API_KEY:
        return
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide X-API-Key header.",
        )
