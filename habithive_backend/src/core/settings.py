from __future__ import annotations

import os
from dataclasses import dataclass


def _get_env(name: str, default: str | None = None) -> str | None:
    """Internal helper for fetching environment variables."""
    value = os.getenv(name)
    if value is None:
        return default
    return value


@dataclass(frozen=True)
class Settings:
    """Application settings resolved from environment variables.

    Notes:
        - Database connection follows the platform convention:
          POSTGRES_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT.
        - Auth uses JWT; set JWT_SECRET in the environment.
    """

    postgres_url: str | None
    postgres_user: str | None
    postgres_password: str | None
    postgres_db: str | None
    postgres_port: str | None

    jwt_secret: str
    jwt_algorithm: str
    access_token_exp_minutes: int

    cors_allow_origins: list[str]


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Get application settings from environment variables.

    Returns:
        Settings: Parsed settings object.

    Required env vars:
        - JWT_SECRET: Secret used to sign JWT tokens.

    Optional env vars:
        - JWT_ALGORITHM (default: HS256)
        - ACCESS_TOKEN_EXP_MINUTES (default: 10080 i.e. 7 days)
        - CORS_ALLOW_ORIGINS (comma-separated, default: '*')
        - POSTGRES_URL / POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB / POSTGRES_PORT
    """
    jwt_secret = _get_env("JWT_SECRET")
    if not jwt_secret:
        # In CI/dev, it is better to fail fast rather than silently insecure defaults.
        raise RuntimeError(
            "Missing required environment variable JWT_SECRET. "
            "Set it in the backend container .env."
        )

    cors_raw = _get_env("CORS_ALLOW_ORIGINS", "*") or "*"
    cors_allow_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
    if not cors_allow_origins:
        cors_allow_origins = ["*"]

    exp_raw = _get_env("ACCESS_TOKEN_EXP_MINUTES", "10080") or "10080"
    try:
        exp_minutes = int(exp_raw)
    except ValueError as exc:
        raise RuntimeError("ACCESS_TOKEN_EXP_MINUTES must be an integer") from exc

    return Settings(
        postgres_url=_get_env("POSTGRES_URL"),
        postgres_user=_get_env("POSTGRES_USER"),
        postgres_password=_get_env("POSTGRES_PASSWORD"),
        postgres_db=_get_env("POSTGRES_DB"),
        postgres_port=_get_env("POSTGRES_PORT"),
        jwt_secret=jwt_secret,
        jwt_algorithm=_get_env("JWT_ALGORITHM", "HS256") or "HS256",
        access_token_exp_minutes=exp_minutes,
        cors_allow_origins=cors_allow_origins,
    )
