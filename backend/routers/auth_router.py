import asyncio
import base64
import json
import secrets
import urllib.parse
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from ..auth.oauth import get_auth_url, exchange_code_for_tokens, generate_pkce_pair, login_with_credentials, _normalise_login_url
from ..auth.org_store import add_org, get_orgs, get_org, remove_org, clear_session
from ..config import settings

# ── PlatformCLI constants (same as Salesforce CLI / MCDM) ──────────────────────
_PLATFORM_CLI_ID  = "PlatformCLI"
_PLATFORM_CLI_PORT = 1717
_PLATFORM_CLI_REDIRECT = f"http://localhost:{_PLATFORM_CLI_PORT}/OauthRedirect"
_platform_jobs: dict[str, dict] = {}   # job_id → status/result


async def _run_local_oauth_server(expected_csrf: str, timeout: float = 300.0) -> dict:
    """
    Start a temporary TCP server on port 1717, wait for Salesforce to redirect
    back with ?code=... or ?error=..., then shut down the server.
    Returns {"type": "code", "code": "..."} or {"type": "error", "error": "..."}.
    """
    _CLOSE_HTML = (
        b"<!DOCTYPE html><html><body style='font-family:sans-serif;background:#0f172a;"
        b"color:#e2e8f0;display:flex;align-items:center;justify-content:center;"
        b"height:100vh;margin:0;flex-direction:column;gap:12px'>"
        b"<div style='font-size:40px'>&#10003;</div>"
        b"<h3 style='margin:0;color:#86efac'>Authorization complete</h3>"
        b"<p style='margin:0;color:#94a3b8;font-size:14px'>Closing window&hellip;</p>"
        b"<script>setTimeout(()=>window.close(),800)</script></body></html>"
    )
    result_future: asyncio.Future = asyncio.get_event_loop().create_future()

    async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            raw = await asyncio.wait_for(reader.read(8192), timeout=10)
            first_line = raw.decode("utf-8", errors="replace").split("\r\n")[0]
            path = first_line.split(" ")[1] if " " in first_line else "/"
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
            code  = qs.get("code",  [None])[0]
            error = qs.get("error", [None])[0]
            state = qs.get("state", [""])[0]
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n"
                + _CLOSE_HTML
            )
            await writer.drain()
        except Exception:
            code = error = state = None
        finally:
            try:
                writer.close()
            except Exception:
                pass

        if result_future.done():
            return
        returned_csrf, _ = _decode_state(state or "")
        if returned_csrf == expected_csrf:
            if code:
                result_future.set_result({"type": "code", "code": code})
            elif error:
                result_future.set_result({"type": "error", "error": error})

    try:
        server = await asyncio.start_server(_handle, "localhost", _PLATFORM_CLI_PORT)
    except OSError as e:
        raise RuntimeError(f"Cannot start local callback server on port {_PLATFORM_CLI_PORT}: {e}") from e

    try:
        return await asyncio.wait_for(result_future, timeout=timeout)
    except asyncio.TimeoutError:
        return {"type": "error", "error": "Authorization timed out (5 minutes)"}
    finally:
        server.close()
        await server.wait_closed()


async def _complete_platform_login(job_id: str, csrf: str, popup: str, code_verifier: str, effective_url: str):
    try:
        result = await _run_local_oauth_server(csrf)

        if result["type"] == "error":
            _platform_jobs[job_id] = {"status": "error", "error": result["error"]}
            return

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{effective_url}/services/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": _PLATFORM_CLI_ID,
                    "redirect_uri": _PLATFORM_CLI_REDIRECT,
                    "code": result["code"],
                    "code_verifier": code_verifier,
                },
            )

        if not resp.is_success:
            _platform_jobs[job_id] = {"status": "error", "error": f"Token exchange failed: {resp.text[:300]}"}
            return

        tokens = resp.json()
        _platform_jobs[job_id] = {
            "status": "done",
            "popup": popup,
            "access_token": tokens.get("access_token", ""),
            "instance_url": tokens.get("instance_url", ""),
        }
    except Exception as exc:
        _platform_jobs[job_id] = {"status": "error", "error": str(exc)}


def _encode_state(csrf: str, popup: str) -> str:
    """Embed popup mode inside the OAuth state so Salesforce echoes it back."""
    data = json.dumps({"c": csrf, "p": popup})
    return base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")


def _decode_state(state: str) -> tuple[str, str]:
    """Return (csrf, popup) from the encoded state, or ("", "") on error."""
    try:
        padded = state + "=" * (-len(state) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode())
        return data.get("c", ""), data.get("p", "")
    except Exception:
        return state, ""  # legacy plain state, no popup

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_id(request: Request) -> str:
    """Get or create a stable session namespace for multi-org storage."""
    sid = request.session.get("_sid")
    if not sid:
        import secrets as _secrets
        sid = _secrets.token_urlsafe(16)
        request.session["_sid"] = sid
    return sid


def _popup_close_page(data: dict) -> HTMLResponse:
    safe_json = json.dumps(data).replace("</", "<\\/")
    ok = "error" not in data
    icon = "✓" if ok else "✗"
    color = "#86efac" if ok else "#fca5a5"
    bg = "#dcfce7" if ok else "#fee2e2"
    msg = "Authorization successful" if ok else "Authorization failed"
    return HTMLResponse(f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;gap:12px">
<div style="width:48px;height:48px;border-radius:50%;background:{bg};display:flex;align-items:center;justify-content:center;font-size:24px;color:#1e293b">{icon}</div>
<h3 style="margin:0;color:{color}">{msg}</h3>
<p style="margin:0;color:#94a3b8;font-size:14px">Closing window&hellip;</p>
<script>
try {{ window.opener && window.opener.postMessage({safe_json}, window.location.origin); }} catch(e) {{}}
setTimeout(() => window.close(), 700);
</script>
</body></html>""")


@router.get("/login")
async def login(request: Request, popup: str = "", login_url: str = ""):
    """
    popup="" → regular OAuth flow, redirects to /dashboard after auth
    popup="source" → popup OAuth for source org, closes popup after auth
    popup="target" → popup OAuth for target org, closes popup and sends token via postMessage
    login_url → override the Salesforce login URL (for sandbox: test.salesforce.com)
    """
    csrf = secrets.token_urlsafe(16)
    code_verifier, code_challenge = generate_pkce_pair()
    # Encode popup mode inside the state so Salesforce echoes it back; avoids
    # session-cookie race condition when the parent tab makes concurrent requests.
    state = _encode_state(csrf, popup)
    request.session["oauth_state"] = csrf  # store only the CSRF token
    request.session["pkce_verifier"] = code_verifier
    effective_url = _normalise_login_url(login_url) if login_url else settings.SF_LOGIN_URL
    return RedirectResponse(get_auth_url(state, code_challenge, effective_url))


@router.get("/callback")
async def callback(request: Request, code: str = None, state: str = None, error: str = None):
    # Decode popup mode from the state parameter (echoed back by Salesforce).
    csrf, popup_mode = _decode_state(state or "")

    if error:
        if popup_mode:
            return _popup_close_page({"type": f"sf-{popup_mode}-auth", "error": error})
        return RedirectResponse(f"{settings.FRONTEND_URL}?error={error}")

    stored_csrf = request.session.get("oauth_state")
    if not csrf or csrf != stored_csrf:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    code_verifier = request.session.get("pkce_verifier", "")
    tokens = await exchange_code_for_tokens(code, code_verifier)

    if popup_mode == "target":
        return _popup_close_page({
            "type": "sf-target-auth",
            "access_token": tokens["access_token"],
            "instance_url": tokens.get("instance_url", ""),
        })

    # source popup or regular flow — both update the main session
    request.session["access_token"] = tokens["access_token"]
    request.session["instance_url"] = tokens["instance_url"]
    request.session["refresh_token"] = tokens.get("refresh_token", "")
    request.session["org_id"] = tokens.get("id", "").split("/")[-1] if tokens.get("id") else ""
    add_org(_session_id(request), tokens["access_token"], tokens["instance_url"], "", request.session["org_id"])

    if popup_mode == "source":
        return _popup_close_page({
            "type": "sf-source-auth",
            "instance_url": tokens.get("instance_url", ""),
            "org_id": request.session["org_id"],
        })

    return RedirectResponse(f"{settings.FRONTEND_URL}/dashboard")


# ── PlatformCLI OAuth endpoints ────────────────────────────────────────────────

@router.get("/platform-login")
async def platform_login(popup: str = "target", login_url: str = ""):
    """
    Start an OAuth flow using PlatformCLI (Salesforce's own client ID — no
    Connected App setup required, works in all orgs).

    Returns {auth_url, job_id}.  The caller should open auth_url in a new tab,
    then poll GET /auth/platform-status/{job_id} for the result.
    """
    csrf = secrets.token_urlsafe(16)
    code_verifier, code_challenge = generate_pkce_pair()
    state = _encode_state(csrf, popup)
    effective_url = _normalise_login_url(login_url) if login_url else settings.SF_LOGIN_URL

    params = {
        "response_type": "code",
        "client_id": _PLATFORM_CLI_ID,
        "redirect_uri": _PLATFORM_CLI_REDIRECT,
        "scope": "api refresh_token offline_access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "login",
    }
    auth_url = f"{effective_url}/services/oauth2/authorize?{urllib.parse.urlencode(params)}"

    job_id = secrets.token_urlsafe(10)
    _platform_jobs[job_id] = {"status": "pending"}

    asyncio.create_task(_complete_platform_login(job_id, csrf, popup, code_verifier, effective_url))

    return JSONResponse({"auth_url": auth_url, "job_id": job_id})


@router.get("/platform-status/{job_id}")
async def platform_status(job_id: str, request: Request):
    """
    Poll the result of a platform-login flow.
    When status=="done" for source popup, also writes the token into the session.
    """
    job = _platform_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Login job not found")

    if job.get("status") == "done":
        popup = job.get("popup", "")
        _platform_jobs.pop(job_id, None)
        if popup == "source":
            request.session["access_token"] = job["access_token"]
            request.session["instance_url"] = job["instance_url"]
            request.session["refresh_token"] = ""
            request.session["org_id"] = ""
            return {"status": "done", "instance_url": job["instance_url"]}
        return {"status": "done", "access_token": job["access_token"], "instance_url": job["instance_url"]}

    return job


@router.get("/me")
async def me(request: Request):
    token = request.session.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "instance_url": request.session.get("instance_url"),
        "org_id": request.session.get("org_id"),
        "alias": request.session.get("alias", ""),
        "authenticated": True,
    }


@router.get("/limits")
async def get_limits(request: Request):
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from ..salesforce.client import SalesforceClient
    sf = SalesforceClient(token, instance_url)
    try:
        return await sf.get_limits()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/describe-object/{object_name}")
async def describe_object_endpoint(object_name: str, request: Request):
    import re as _re
    if not _re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', object_name):
        raise HTTPException(status_code=400, detail="Invalid object name")
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from ..salesforce.client import SalesforceClient
    sf = SalesforceClient(token, instance_url)
    try:
        return await sf.describe_object(object_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list-records")
async def list_records(
    request: Request,
    object_name: str,
    fields: str = "Id,Name",
    filter_clause: str = "",
    tooling: bool = False,
    limit: int = 100,
):
    import re as _re
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not _re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', object_name):
        raise HTTPException(status_code=400, detail="Invalid object name")

    field_list = [
        f.strip() for f in fields.split(",")
        if _re.match(r'^[A-Za-z_][A-Za-z0-9_.]*$', f.strip())
    ] or ["Name"]

    all_fields = list(dict.fromkeys(["Id"] + field_list))
    order_field = field_list[0]
    soql = f"SELECT {', '.join(all_fields)} FROM {object_name}"
    if filter_clause:
        soql += f" WHERE {filter_clause}"
    soql += f" ORDER BY {order_field} ASC NULLS LAST LIMIT {min(limit, 500)}"

    from ..salesforce.client import SalesforceClient
    sf = SalesforceClient(token, instance_url)

    async def _run(q):
        return await (sf.tooling_query(q) if tooling else sf.query(q))

    try:
        result = await _run(soql)
    except Exception:
        # Retry without ORDER BY if the field isn't sortable
        fallback = f"SELECT {', '.join(all_fields)} FROM {object_name}"
        if filter_clause:
            fallback += f" WHERE {filter_clause}"
        fallback += f" LIMIT {min(limit, 500)}"
        try:
            result = await _run(fallback)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    def _flatten(r):
        flat = {}
        for k, v in r.items():
            if k == "attributes":
                continue
            if isinstance(v, dict):
                for nk, nv in v.items():
                    if nk != "attributes":
                        flat[f"{k}.{nk}"] = nv
            else:
                flat[k] = v
        return flat

    records = [_flatten(r) for r in result.get("records", [])]
    return {"records": records, "total": result.get("totalSize", len(records)), "columns": field_list}


@router.get("/apex-coverage")
async def apex_coverage(request: Request):
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from ..salesforce.client import SalesforceClient
    sf = SalesforceClient(token, instance_url)

    try:
        cov = await sf.tooling_query(
            "SELECT ApexClassOrTrigger.Name, NumLinesCovered, NumLinesUncovered "
            "FROM ApexCodeCoverageAggregate LIMIT 2000"
        )
        classes = cov.get("records", [])
    except Exception:
        classes = []

    try:
        tr = await sf.tooling_query("SELECT Outcome FROM ApexTestResult LIMIT 5000")
        tests = tr.get("records", [])
    except Exception:
        tests = []

    def pct(c):
        t = c.get("NumLinesCovered", 0) + c.get("NumLinesUncovered", 0)
        return round(c.get("NumLinesCovered", 0) / t * 100) if t else 0

    covered   = sum(c.get("NumLinesCovered",   0) for c in classes)
    uncovered = sum(c.get("NumLinesUncovered", 0) for c in classes)
    total_lines = covered + uncovered
    overall_pct = round(covered / total_lines * 100) if total_lines else 0

    below_75 = sorted(
        [
            {
                "name":    (c.get("ApexClassOrTrigger") or {}).get("Name", "Unknown"),
                "pct":     pct(c),
                "covered": c.get("NumLinesCovered", 0),
                "total":   c.get("NumLinesCovered", 0) + c.get("NumLinesUncovered", 0),
            }
            for c in classes
            if 0 < c.get("NumLinesCovered", 0) + c.get("NumLinesUncovered", 0) and pct(c) < 75
        ],
        key=lambda x: x["pct"],
    )

    outcomes = {}
    for t in tests:
        o = t.get("Outcome", "Unknown")
        outcomes[o] = outcomes.get(o, 0) + 1

    return {
        "total_classes":    len([c for c in classes if c.get("NumLinesCovered", 0) + c.get("NumLinesUncovered", 0) > 0]),
        "overall_pct":      overall_pct,
        "covered_lines":    covered,
        "total_lines":      total_lines,
        "classes_below_75": len(below_75),
        "below_75_list":    below_75[:10],
        "total_tests":      sum(outcomes.values()),
        "passed":           outcomes.get("Pass", 0),
        "failed":           outcomes.get("Fail", 0) + outcomes.get("CompileFail", 0),
        "skipped":          outcomes.get("Skip", 0),
    }


@router.get("/org-info")
async def org_info(request: Request):
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from ..salesforce.client import SalesforceClient
    sf = SalesforceClient(token, instance_url)
    info = await sf.get_org_info()
    return info


@router.post("/logout")
async def logout(request: Request):
    clear_session(_session_id(request))
    request.session.clear()
    return {"status": "logged_out"}


class PasswordLoginPayload(BaseModel):
    username: str
    password: str
    domain: str = ""
    alias: str = ""


@router.post("/login-password")
async def login_password(request: Request, body: PasswordLoginPayload):
    try:
        tokens = await login_with_credentials(
            body.username.strip(),
            body.password,
            body.domain,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    request.session["access_token"] = tokens["access_token"]
    request.session["instance_url"] = tokens["instance_url"]
    request.session["refresh_token"] = ""
    request.session["org_id"] = ""
    request.session["alias"] = body.alias.strip()
    add_org(_session_id(request), tokens["access_token"], tokens["instance_url"], body.alias.strip(), "")
    return {
        "instance_url": tokens["instance_url"],
        "org_id": "",
        "alias": request.session["alias"],
        "authenticated": True,
    }


class TokenLoginPayload(BaseModel):
    access_token: str
    instance_url: str


@router.post("/login-token")
async def login_token(request: Request, body: TokenLoginPayload):
    import httpx
    from urllib.parse import urlparse, unquote

    # URL-decode the token — browser cookies store '!' as '%21'
    access_token = unquote(body.access_token.strip())
    instance_url = body.instance_url.strip().rstrip("/")
    if not access_token or not instance_url:
        raise HTTPException(status_code=400, detail="access_token and instance_url are required")

    # Step 1: Reach the org and normalise the instance URL (follow redirects)
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                f"{instance_url}/services/data/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            final_url = str(resp.url)
            parsed = urlparse(final_url)
            instance_url = f"{parsed.scheme}://{parsed.netloc}"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not reach org: {e}")

    # Step 2: Validate the token is still active (SOQL requires real auth)
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            check = await client.get(
                f"{instance_url}/services/data/v62.0/query/?q=SELECT+Id+FROM+Organization+LIMIT+1",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if check.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="This Session ID has already expired. Please get a fresh SID from Salesforce (F12 → Application → Cookies → sid).",
                )
    except HTTPException:
        raise
    except Exception:
        pass  # Network / firewall issues — don't block login on connectivity failures

    request.session["access_token"] = access_token
    request.session["instance_url"] = instance_url
    request.session["refresh_token"] = ""
    request.session["org_id"] = ""
    add_org(_session_id(request), access_token, instance_url, "", "")
    return {"instance_url": instance_url, "org_id": "", "authenticated": True}


class CliLoginPayload(BaseModel):
    org: str


@router.post("/login-cli")
async def login_cli(request: Request, body: CliLoginPayload):
    org = body.org.strip()
    if not org:
        raise HTTPException(status_code=400, detail="org alias is required")

    try:
        proc = await asyncio.create_subprocess_exec(
            "sf", "org", "display", "--target-org", org, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(status_code=400, detail="sf org display timed out after 30 seconds")
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Salesforce CLI (sf) is not installed or not in PATH")

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip() or "sf org display failed"
        raise HTTPException(status_code=400, detail=err[:400])

    import json
    try:
        data = json.loads(stdout.decode("utf-8", errors="replace"))
        result = data.get("result", {})
        access_token = result.get("accessToken", "").strip()
        instance_url = result.get("instanceUrl", "").strip().rstrip("/")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse sf org display output")

    if not access_token or not instance_url:
        raise HTTPException(status_code=400, detail=f"Org '{org}' is not authenticated — run: sf org login web --alias {org}")

    request.session["access_token"] = access_token
    request.session["instance_url"] = instance_url
    request.session["refresh_token"] = ""
    request.session["org_id"] = ""
    add_org(_session_id(request), access_token, instance_url, body.org.strip(), "")
    return {"instance_url": instance_url, "org_id": "", "authenticated": True}


@router.get("/orgs")
async def list_orgs(request: Request):
    """List all orgs connected in this session."""
    sid = _session_id(request)
    orgs = get_orgs(sid)
    active_url = request.session.get("instance_url", "")
    for org in orgs:
        org["active"] = org["instance_url"] == active_url
    return {"orgs": orgs}


@router.post("/orgs/switch/{org_key}")
async def switch_org(org_key: str, request: Request):
    """Switch the active org for this session."""
    sid = _session_id(request)
    entry = get_org(sid, org_key)
    if not entry:
        raise HTTPException(status_code=404, detail="Org not found")
    request.session["access_token"] = entry["access_token"]
    request.session["instance_url"] = entry["instance_url"]
    request.session["alias"] = entry.get("alias", "")
    request.session["org_id"] = entry.get("org_id", "")
    return {
        "instance_url": entry["instance_url"],
        "alias": entry.get("alias", ""),
        "org_id": entry.get("org_id", ""),
        "authenticated": True,
    }


@router.delete("/orgs/{org_key}")
async def disconnect_org(org_key: str, request: Request):
    """Disconnect a specific org from this session."""
    sid = _session_id(request)
    entry = get_org(sid, org_key)
    remove_org(sid, org_key)
    if entry and entry["instance_url"] == request.session.get("instance_url"):
        request.session.pop("access_token", None)
        request.session.pop("instance_url", None)
        request.session.pop("alias", None)
        remaining = get_orgs(sid)
        if remaining:
            new_entry = get_org(sid, remaining[0]["org_key"])
            if new_entry:
                request.session["access_token"] = new_entry["access_token"]
                request.session["instance_url"] = new_entry["instance_url"]
                request.session["alias"] = new_entry.get("alias", "")
    return {"status": "disconnected"}
