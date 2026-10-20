import hashlib
import base64
import os
import httpx
import urllib.parse
from ..config import settings


def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def get_auth_url(state: str, code_challenge: str, login_url: str = "") -> str:
    base = (login_url or settings.SF_LOGIN_URL).rstrip("/")
    params = {
        "response_type": "code",
        "client_id": settings.SF_CLIENT_ID,
        "redirect_uri": settings.SF_REDIRECT_URI,
        "scope": "api refresh_token offline_access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{base}/services/oauth2/authorize?{urllib.parse.urlencode(params)}"


async def exchange_code_for_tokens(code: str, code_verifier: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.SF_LOGIN_URL}/services/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.SF_CLIENT_ID,
                "client_secret": settings.SF_CLIENT_SECRET,
                "redirect_uri": settings.SF_REDIRECT_URI,
                "code": code,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()


def _normalise_login_url(domain: str) -> str:
    from urllib.parse import urlparse
    url = domain.strip().rstrip("/") if domain.strip() else settings.SF_LOGIN_URL
    if not url:
        return settings.SF_LOGIN_URL
    if not url.startswith("http"):
        url = f"https://{url}"
    # Strip any path the user may have pasted (e.g. a full browser URL)
    parsed = urlparse(url)
    if parsed.netloc:
        url = f"{parsed.scheme}://{parsed.netloc}"
    # Convert *.lightning.force.com → *.my.salesforce.com
    # Handles all variants: org.lightning.force.com, org.sandbox.lightning.force.com, etc.
    url = url.replace(".lightning.force.com", ".my.salesforce.com")
    return url


async def soap_login(username: str, password: str, domain: str = "") -> dict:
    """SOAP partner API login. Returns {access_token, instance_url, org_name}."""
    import xml.etree.ElementTree as ET
    from xml.sax.saxutils import escape as xml_escape
    from urllib.parse import urlparse

    login_url = _normalise_login_url(domain)
    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<env:Envelope xmlns:xsd="http://www.w3.org/2001/XMLSchema"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
              xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
  <env:Body>
    <n1:login xmlns:n1="urn:partner.soap.sforce.com">
      <n1:username>{xml_escape(username)}</n1:username>
      <n1:password>{xml_escape(password)}</n1:password>
    </n1:login>
  </env:Body>
</env:Envelope>"""

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{login_url}/services/Soap/u/62.0",
            content=soap_body.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=UTF-8", "SOAPAction": "login"},
        )

    if resp.status_code != 200:
        soap_url = f"{login_url}/services/Soap/u/62.0"
        try:
            root = ET.fromstring(resp.text)
            fault = root.find(".//faultstring")
            msg = fault.text if fault is not None else f"HTTP {resp.status_code} from {soap_url}"
        except Exception:
            body_snippet = resp.text[:200].strip() if resp.text else ""
            msg = f"HTTP {resp.status_code} from {soap_url}" + (f" — {body_snippet}" if body_snippet else "")
        raise Exception(msg)

    root = ET.fromstring(resp.text)
    ns = {"sf": "urn:partner.soap.sforce.com"}
    result = root.find(".//sf:result", ns)
    if result is None:
        raise Exception("Unexpected SOAP response")

    session_id = result.findtext("sf:sessionId", namespaces=ns) or ""
    server_url  = result.findtext("sf:serverUrl", namespaces=ns) or ""
    org_name    = result.findtext(".//sf:organizationName", namespaces=ns) or ""

    if not session_id:
        raise Exception("No session ID returned")

    parsed = urlparse(server_url)
    instance_url = f"{parsed.scheme}://{parsed.netloc}"
    return {"access_token": session_id, "instance_url": instance_url, "org_name": org_name}


async def login_with_credentials(username: str, password: str, domain: str = "") -> dict:
    """
    Try SOAP login first; if the org has SOAP login disabled, fall back to
    OAuth 2.0 password grant using the app's Connected App credentials.
    Returns {access_token, instance_url, org_name}.
    """
    soap_msg = None
    try:
        return await soap_login(username, password, domain)
    except Exception as soap_err:
        soap_msg = str(soap_err)
        soap_disabled = (
            "SOAP API login() is disabled" in soap_msg
            or "API_DISABLED_FOR_ORG" in soap_msg
            or "SOAP" in soap_msg.upper()
        )
        # INVALID_LOGIN from SOAP usually means IP not trusted → security token required.
        # Fall through to OAuth password grant, which can bypass this if the Connected App
        # has "Relax IP restrictions" enabled.
        invalid_login = "INVALID_LOGIN" in soap_msg
        if not soap_disabled and not invalid_login:
            raise  # not a recoverable error — propagate original

    # Fallback: OAuth password grant
    if not settings.SF_CLIENT_ID or not settings.SF_CLIENT_SECRET:
        if soap_msg and "INVALID_LOGIN" in soap_msg:
            raise Exception(
                "Login failed: your IP is not in Salesforce's trusted network. "
                "Options: (1) append your security token to your password, "
                "(2) add your IP to Setup → Network Access, or "
                "(3) configure a Connected App and use Session ID login."
            )
        raise Exception(
            f"SOAP login failed ({soap_msg}) and no OAuth Connected App is configured. "
            f"Go to Settings → API Configuration to add your Consumer Key and Secret, "
            f"or use Session ID login instead."
        )

    login_url = _normalise_login_url(domain)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{login_url}/services/oauth2/token",
            data={
                "grant_type": "password",
                "client_id": settings.SF_CLIENT_ID,
                "client_secret": settings.SF_CLIENT_SECRET,
                "username": username,
                "password": password,
            },
        )
    if not resp.is_success:
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        oauth_msg = body.get("error_description") or body.get("error") or resp.text

        if "INSUFFICIENT_ACCESS" in (soap_msg or "") or "Use Any API Auth" in (soap_msg or ""):
            raise Exception(
                f"Your Salesforce profile does not have API login access. "
                f"Ask your admin to enable 'Use Any API Auth' on your profile, "
                f"or use Session ID login instead (log in via browser → F12 → "
                f"Application → Cookies → copy the 'sid' value)."
            )

        if oauth_msg in ("authentication failure", "invalid_grant"):
            raise Exception(
                f"Username-password login is blocked by this org's security settings "
                f"(OAuth error: {oauth_msg}, SOAP error: {soap_msg}). "
                f"Use Session ID login instead: log in to Salesforce in your browser → "
                f"F12 → Application → Cookies → copy the 'sid' value."
            )

        raise Exception(f"{oauth_msg} (SOAP: {soap_msg})")

    data = resp.json()
    from urllib.parse import urlparse
    instance_url = data.get("instance_url", "")
    return {
        "access_token": data.get("access_token", ""),
        "instance_url": instance_url,
        "org_name": "",
    }


async def login_with_password(username: str, password: str, domain: str = "") -> dict:
    """Kept for backward compatibility — delegates to login_with_credentials."""
    return await login_with_credentials(username, password, domain)


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.SF_LOGIN_URL}/services/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": settings.SF_CLIENT_ID,
                "client_secret": settings.SF_CLIENT_SECRET,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()
