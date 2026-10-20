"""In-memory multi-org slot store. Keyed by session ID, then org_key."""
from datetime import datetime, timezone
from typing import Optional
import hashlib

# session_id → { org_key → OrgEntry }
_orgs: dict[str, dict[str, dict]] = {}


def _org_key(instance_url: str) -> str:
    host = instance_url.replace("https://", "").split("/")[0]
    return hashlib.md5(host.encode()).hexdigest()[:8]


def add_org(session_id: str, access_token: str, instance_url: str,
            alias: str = "", org_id: str = "") -> str:
    key = _org_key(instance_url)
    if session_id not in _orgs:
        _orgs[session_id] = {}
    _orgs[session_id][key] = {
        "org_key": key,
        "access_token": access_token,
        "instance_url": instance_url,
        "alias": alias,
        "org_id": org_id,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "label": alias or instance_url.replace("https://", "").split(".")[0].replace("-", " ").title(),
    }
    return key


def get_orgs(session_id: str) -> list[dict]:
    orgs = _orgs.get(session_id, {})
    return [
        {k: v for k, v in org.items() if k != "access_token"}
        for org in orgs.values()
    ]


def get_org(session_id: str, org_key: str) -> Optional[dict]:
    return _orgs.get(session_id, {}).get(org_key)


def remove_org(session_id: str, org_key: str):
    if session_id in _orgs:
        _orgs[session_id].pop(org_key, None)


def clear_session(session_id: str):
    _orgs.pop(session_id, None)
