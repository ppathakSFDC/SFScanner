"""
SF Scanner — Model Context Protocol (MCP) stdio server.
Python 3.9+, no external mcp SDK required.

Configure Claude Desktop (~/.config/claude/claude_desktop_config.json  or
~/Library/Application Support/Claude/claude_desktop_config.json):

{
  "mcpServers": {
    "sf-scanner": {
      "command": "/path/to/sf-scanner/backend/.venv/bin/python",
      "args": ["/path/to/sf-scanner/backend/mcp_server.py"],
      "env": {
        "SF_ACCESS_TOKEN": "00Dxx...",
        "SF_INSTANCE_URL": "https://yourorg.my.salesforce.com",
        "SF_SCANNER_URL": "http://localhost:8080",
        "MCP_API_KEY": "change-me"
      }
    }
  }
}

Configure Cursor (.cursor/mcp.json):

{
  "mcpServers": {
    "sf-scanner": {
      "command": "/path/to/backend/.venv/bin/python",
      "args": ["/path/to/backend/mcp_server.py"],
      "env": { ... }
    }
  }
}
"""

import asyncio
import json
import os
import sys

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

SF_ACCESS_TOKEN = os.environ.get("SF_ACCESS_TOKEN", "")
SF_INSTANCE_URL = os.environ.get("SF_INSTANCE_URL", "").rstrip("/")
SF_SCANNER_URL  = os.environ.get("SF_SCANNER_URL", "http://localhost:8080").rstrip("/")
MCP_API_KEY     = os.environ.get("MCP_API_KEY", "")

if not SF_ACCESS_TOKEN or not SF_INSTANCE_URL:
    sys.stderr.write(
        "ERROR: SF_ACCESS_TOKEN and SF_INSTANCE_URL environment variables are required.\n"
    )
    sys.exit(1)

_SF_HEADERS = {
    "Authorization": f"Bearer {SF_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

_BACKEND_HEADERS = {
    "X-MCP-API-Key":    MCP_API_KEY,
    "X-SF-Access-Token": SF_ACCESS_TOKEN,
    "X-SF-Instance-URL": SF_INSTANCE_URL,
}

_API = f"{SF_INSTANCE_URL}/services/data/v62.0"


# ── Tool definitions (sent to MCP clients on tools/list) ─────────────────────

TOOLS = [
    {
        "name": "run_soql",
        "description": (
            "Execute a SOQL query against the connected Salesforce org. "
            "Returns records array and totalSize."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SOQL query string"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "run_tooling_soql",
        "description": (
            "Execute a Tooling API SOQL query (ApexClass, Flow, CustomField, etc.). "
            "Returns records array."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Tooling SOQL query string"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "describe_object",
        "description": "Return field and relationship metadata for a Salesforce sObject.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "API name of the sObject (e.g. Account, Opportunity)",
                }
            },
            "required": ["object_name"],
        },
    },
    {
        "name": "list_objects",
        "description": "List all queryable sObjects available in the org.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_org_info",
        "description": "Return basic org info: name, type, edition, ID.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "start_scan",
        "description": (
            "Start a full health scan of the connected org (Apex, Flows, OmniStudio, "
            "Permissions, Security, Compliance). Returns a scan_id to poll."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_scan_progress",
        "description": "Poll the progress of a running scan.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scan_id": {"type": "string", "description": "scan_id from start_scan"}
            },
            "required": ["scan_id"],
        },
    },
    {
        "name": "get_scan_result",
        "description": "Retrieve the results of a completed scan including health scores and findings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scan_id": {"type": "string", "description": "scan_id from start_scan"}
            },
            "required": ["scan_id"],
        },
    },
    {
        "name": "get_health_scores",
        "description": "Return health scores from the most recent completed scan.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_security_summary",
        "description": (
            "Return security and compliance findings from the most recent scan, "
            "grouped by severity and category."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_metadata_types",
        "description": "List all metadata types available in the org (ApexClass, Flow, etc.).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_metadata_components",
        "description": "List components of a specific metadata type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type_name": {
                    "type": "string",
                    "description": "Metadata type xmlName, e.g. ApexClass, Flow, LightningComponentBundle",
                }
            },
            "required": ["type_name"],
        },
    },
]


# ── Tool implementations ──────────────────────────────────────────────────────

async def call_tool(name: str, args: dict) -> str:
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            return await _dispatch(client, name, args)
    except httpx.HTTPStatusError as exc:
        return json.dumps({"error": f"HTTP {exc.response.status_code}: {exc.response.text[:400]}"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


async def _dispatch(client: httpx.AsyncClient, name: str, args: dict) -> str:
    if name == "run_soql":
        resp = await client.get(
            f"{_API}/query",
            params={"q": args["query"]},
            headers=_SF_HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
        return json.dumps({"totalSize": data.get("totalSize"), "records": data.get("records", [])})

    if name == "run_tooling_soql":
        resp = await client.get(
            f"{_API}/tooling/query",
            params={"q": args["query"]},
            headers=_SF_HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
        return json.dumps({"totalSize": data.get("totalSize"), "records": data.get("records", [])})

    if name == "describe_object":
        obj = args["object_name"]
        resp = await client.get(
            f"{_API}/sobjects/{obj}/describe/",
            headers=_SF_HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
        fields = [
            {
                "name":        f.get("name"),
                "label":       f.get("label"),
                "type":        f.get("type"),
                "referenceTo": f.get("referenceTo", []),
            }
            for f in data.get("fields", [])
        ]
        return json.dumps({
            "name":   data.get("name"),
            "label":  data.get("label"),
            "fields": fields,
            "childRelationships": [
                {"childSObject": r.get("childSObject"), "field": r.get("field")}
                for r in data.get("childRelationships", [])
            ],
        })

    if name == "list_objects":
        resp = await client.get(f"{_API}/sobjects/", headers=_SF_HEADERS)
        resp.raise_for_status()
        objects = [
            {"name": s["name"], "label": s.get("label"), "custom": s.get("custom")}
            for s in resp.json().get("sobjects", [])
            if s.get("queryable")
        ]
        return json.dumps({"objects": objects, "total": len(objects)})

    if name == "get_org_info":
        resp = await client.get(
            f"{_API}/query",
            params={"q": "SELECT Id, Name, OrganizationType, IsSandbox FROM Organization LIMIT 1"},
            headers=_SF_HEADERS,
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        return json.dumps(records[0] if records else {})

    if name == "start_scan":
        resp = await client.get(
            f"{SF_SCANNER_URL}/mcp/scan/start",
            headers=_BACKEND_HEADERS,
        )
        resp.raise_for_status()
        return json.dumps(resp.json())

    if name == "get_scan_progress":
        resp = await client.get(
            f"{SF_SCANNER_URL}/mcp/scan/progress/{args['scan_id']}",
            headers=_BACKEND_HEADERS,
        )
        resp.raise_for_status()
        return json.dumps(resp.json())

    if name == "get_scan_result":
        resp = await client.get(
            f"{SF_SCANNER_URL}/mcp/scan/result/{args['scan_id']}",
            headers=_BACKEND_HEADERS,
        )
        resp.raise_for_status()
        return json.dumps(resp.json())

    if name == "get_health_scores":
        resp = await client.get(
            f"{SF_SCANNER_URL}/mcp/scan/health",
            headers=_BACKEND_HEADERS,
        )
        resp.raise_for_status()
        return json.dumps(resp.json())

    if name == "get_security_summary":
        resp = await client.get(
            f"{SF_SCANNER_URL}/mcp/security/summary",
            headers=_BACKEND_HEADERS,
        )
        resp.raise_for_status()
        return json.dumps(resp.json())

    if name == "list_metadata_types":
        resp = await client.get(
            f"{SF_SCANNER_URL}/mcp/info/metadata-types",
            headers=_BACKEND_HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
        names = [t["xmlName"] for t in data.get("metadata_types", [])]
        return json.dumps({"metadata_types": names, "total": len(names)})

    if name == "list_metadata_components":
        type_name = args["type_name"]
        resp = await client.get(
            f"{SF_SCANNER_URL}/mcp/info/metadata-components/{type_name}",
            headers=_BACKEND_HEADERS,
        )
        resp.raise_for_status()
        return json.dumps(resp.json())

    return json.dumps({"error": f"Unknown tool: {name}"})


# ── MCP JSON-RPC 2.0 protocol loop ────────────────────────────────────────────

def _response(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _write(msg: dict) -> None:
    line = json.dumps(msg, separators=(",", ":")) + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()


async def main() -> None:
    loop = asyncio.get_event_loop()

    def _stdin_readline():
        return sys.stdin.readline()

    while True:
        try:
            raw = await loop.run_in_executor(None, _stdin_readline)
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            break

        raw = raw.strip()
        if not raw:
            continue

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            _write(_error_response(None, -32700, "Parse error"))
            continue

        method    = msg.get("method", "")
        msg_id    = msg.get("id")          # None for notifications
        params    = msg.get("params") or {}

        # Notifications (no id) — no response required
        if msg_id is None:
            if method == "notifications/initialized":
                pass  # nothing to do
            continue

        # ── initialize ────────────────────────────────────────────────────────
        if method == "initialize":
            _write(_response(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "sf-scanner", "version": "1.0.0"},
            }))
            continue

        # ── ping ──────────────────────────────────────────────────────────────
        if method == "ping":
            _write(_response(msg_id, {}))
            continue

        # ── tools/list ────────────────────────────────────────────────────────
        if method == "tools/list":
            _write(_response(msg_id, {"tools": TOOLS}))
            continue

        # ── tools/call ────────────────────────────────────────────────────────
        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments") or {}
            result_text = await call_tool(tool_name, tool_args)
            _write(_response(msg_id, {
                "content": [{"type": "text", "text": result_text}],
                "isError": False,
            }))
            continue

        # ── unknown method ────────────────────────────────────────────────────
        _write(_error_response(msg_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    asyncio.run(main())
