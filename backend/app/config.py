"""Application settings loaded from environment variables."""

from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Project settings — values are read from .env at the backend/ root."""

    database_url: str

    # --- Authentication -------------------------------------------------
    # Production: set CLERK_JWKS_URL (e.g. https://<your-instance>.clerk.accounts.dev/.well-known/jwks.json).
    # Requests must then carry a valid Clerk session JWT as `Authorization: Bearer <token>`.
    clerk_jwks_url: Optional[str] = None
    # Optional: reject tokens not issued by this issuer (https://<your-instance>.clerk.accounts.dev).
    clerk_issuer: Optional[str] = None
    # Local development only: with no CLERK_JWKS_URL the API trusts the X-Clerk-User-Id header,
    # which ANYONE can forge. Set to false to refuse requests instead.
    allow_insecure_dev_auth: bool = True

    # Comma-separated list of allowed browser origins for CORS.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
