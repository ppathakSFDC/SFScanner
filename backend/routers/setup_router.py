import os
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/setup", tags=["setup"])

ENV_PATH = Path(__file__).parent.parent / ".env"


def _read_env() -> dict:
    vals = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                vals[k.strip()] = v.strip()
    return vals


def _is_configured() -> bool:
    env = _read_env()
    return all(env.get(k, "").strip() not in ("", f"your_{k.lower()}_here", f"your_connected_app_{k.lower()}", "your_anthropic_api_key")
               for k in ("SF_CLIENT_ID", "SF_CLIENT_SECRET", "ANTHROPIC_API_KEY"))


@router.get("/status")
async def setup_status():
    return {"configured": _is_configured()}


@router.get("/config")
async def setup_config():
    env = _read_env()
    placeholder_ids = {"", "your_connected_app_consumer_key"}
    placeholder_secrets = {"", "your_connected_app_consumer_secret"}
    placeholder_keys = {"", "your_anthropic_api_key"}
    return {
        "sf_login_url": env.get("SF_LOGIN_URL", "https://login.salesforce.com"),
        "sf_client_id_set": env.get("SF_CLIENT_ID", "") not in placeholder_ids,
        "sf_client_secret_set": env.get("SF_CLIENT_SECRET", "") not in placeholder_secrets,
        "anthropic_api_key_set": env.get("ANTHROPIC_API_KEY", "") not in placeholder_keys,
    }


from typing import Optional


class SetupPayload(BaseModel):
    sf_client_id: Optional[str] = None
    sf_client_secret: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    sf_login_url: str = "https://login.salesforce.com"
    session_secret: str = ""


@router.post("/configure")
async def configure(payload: SetupPayload):
    import secrets as _secrets
    existing = _read_env()

    if payload.sf_client_id is not None and payload.sf_client_id.strip():
        existing["SF_CLIENT_ID"] = payload.sf_client_id.strip()
    if payload.sf_client_secret is not None and payload.sf_client_secret.strip():
        existing["SF_CLIENT_SECRET"] = payload.sf_client_secret.strip()
    if payload.anthropic_api_key is not None and payload.anthropic_api_key.strip():
        existing["ANTHROPIC_API_KEY"] = payload.anthropic_api_key.strip()
    existing["SF_LOGIN_URL"] = payload.sf_login_url.strip() or "https://login.salesforce.com"
    existing["SESSION_SECRET"] = payload.session_secret.strip() or existing.get("SESSION_SECRET") or _secrets.token_hex(24)
    existing.setdefault("SF_REDIRECT_URI", "http://localhost:5173/auth/callback")
    existing.setdefault("FRONTEND_URL", "http://localhost:5173")

    lines = [f"{k}={v}" for k, v in existing.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")

    # Reload settings in-process
    from ..config import settings
    settings.SF_CLIENT_ID = existing.get("SF_CLIENT_ID", "")
    settings.SF_CLIENT_SECRET = existing.get("SF_CLIENT_SECRET", "")
    settings.ANTHROPIC_API_KEY = existing.get("ANTHROPIC_API_KEY", "")
    settings.SF_LOGIN_URL = existing.get("SF_LOGIN_URL", "https://login.salesforce.com")
    settings.SESSION_SECRET = existing.get("SESSION_SECRET", "")

    return {"status": "saved"}


class AnthropicKeyPayload(BaseModel):
    anthropic_api_key: str


@router.patch("/anthropic-key")
async def update_anthropic_key(payload: AnthropicKeyPayload):
    key = payload.anthropic_api_key.strip()
    if not key:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    existing = _read_env()
    existing["ANTHROPIC_API_KEY"] = key
    lines = [f"{k}={v}" for k, v in existing.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")
    os.environ["ANTHROPIC_API_KEY"] = key
    from ..config import settings
    settings.ANTHROPIC_API_KEY = key
    return {"status": "saved"}
