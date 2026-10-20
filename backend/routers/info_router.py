import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
import httpx
import xml.etree.ElementTree as _ET

router = APIRouter(prefix="/info", tags=["info"])

_META_NS = "http://soap.sforce.com/2006/04/metadata"
_API_VERSION = "62.0"

# Types where listMetadata requires a folder parameter.
# Key = xmlName, Value = the folder-type to enumerate first.
_FOLDER_PARENT_TYPE: dict[str, str] = {
    "Report":        "ReportFolder",
    "Dashboard":     "DashboardFolder",
    "Document":      "DocumentFolder",
    "EmailTemplate": "EmailFolder",
}


def _require_auth(request: Request):
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token, instance_url.rstrip("/")


# ─── SOAP helpers ─────────────────────────────────────────────────────────────

def _soap_envelope(token: str, body_xml: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:met="http://soap.sforce.com/2006/04/metadata">'
        "<soapenv:Header>"
        "<met:CallOptions/>"
        "<met:SessionHeader>"
        f"<met:sessionId>{token}</met:sessionId>"
        "</met:SessionHeader>"
        "</soapenv:Header>"
        f"<soapenv:Body>{body_xml}</soapenv:Body>"
        "</soapenv:Envelope>"
    )


async def _soap_post(instance_url: str, token: str, action: str, body_xml: str, timeout: int = 30) -> str:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.post(
            f"{instance_url}/services/Soap/m/{_API_VERSION}",
            content=_soap_envelope(token, body_xml),
            headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": action},
        )
    resp.raise_for_status()
    return resp.text


def _xml_child_text(el: _ET.Element, local: str) -> str:
    child = el.find(f"{{{_META_NS}}}{local}")
    return (child.text or "") if child is not None else ""


def _xml_children_text(el: _ET.Element, local: str) -> list[str]:
    return [c.text for c in el.findall(f"{{{_META_NS}}}{local}") if c.text]


def _parse_file_properties(root: _ET.Element) -> list[dict]:
    """Parse all <result> / <result> elements from a listMetadata SOAP response."""
    items = []
    for r in root.iter(f"{{{_META_NS}}}result"):
        item = {}
        for child in r:
            tag = child.tag.split("}")[1] if "}" in child.tag else child.tag
            item[tag] = child.text
        if item:
            items.append(item)
    return items


# ─── describeMetadata ─────────────────────────────────────────────────────────

async def _soap_describe_metadata(token: str, instance_url: str) -> list[dict]:
    """
    Call describeMetadata — returns the full list of metadata types for this
    org/API version, with directoryName, suffix, inFolder, metaFile, childXmlNames.
    """
    body = f"<met:describeMetadata><met:asOfVersion>{_API_VERSION}</met:asOfVersion></met:describeMetadata>"
    try:
        xml_text = await _soap_post(instance_url, token, "describeMetadata", body, timeout=30)
        root = _ET.fromstring(xml_text)
        types: list[dict] = []
        for mo in root.iter(f"{{{_META_NS}}}metadataObjects"):
            types.append({
                "xmlName":        _xml_child_text(mo, "xmlName"),
                "directoryName":  _xml_child_text(mo, "directoryName"),
                "suffix":         _xml_child_text(mo, "suffix") or None,
                "inFolder":       _xml_child_text(mo, "inFolder") == "true",
                "metaFile":       _xml_child_text(mo, "metaFile") == "true",
                "childXmlNames":  _xml_children_text(mo, "childXmlNames"),
            })
        return sorted(types, key=lambda t: t.get("xmlName", ""))
    except Exception:
        return []


# ─── listMetadata ─────────────────────────────────────────────────────────────

async def _soap_list_one(token: str, instance_url: str, type_name: str, folder: Optional[str] = None) -> list[dict]:
    """Call listMetadata for a single type (with optional folder)."""
    folder_xml = f"<met:folder>{folder}</met:folder>" if folder else ""
    body = (
        "<met:listMetadata>"
        "<met:queries>"
        f"<met:type>{type_name}</met:type>"
        f"{folder_xml}"
        "</met:queries>"
        f"<met:asOfVersion>{_API_VERSION}</met:asOfVersion>"
        "</met:listMetadata>"
    )
    try:
        xml_text = await _soap_post(instance_url, token, "listMetadata", body, timeout=30)
        return _parse_file_properties(_ET.fromstring(xml_text))
    except Exception:
        return []


async def _list_with_folders(token: str, instance_url: str, type_name: str) -> list[dict]:
    """
    For inFolder types (Report, Dashboard, Document, EmailTemplate):
    1. Enumerate folders via the companion *Folder type.
    2. Call listMetadata(type, folder=<name>) for each folder in parallel.
    Returns combined FileProperties list.
    """
    folder_type = _FOLDER_PARENT_TYPE.get(type_name)
    if not folder_type:
        return await _soap_list_one(token, instance_url, type_name)

    # Step 1: get folder list
    folders = await _soap_list_one(token, instance_url, folder_type)
    if not folders:
        return []

    folder_names = [f.get("fullName", "") for f in folders if f.get("fullName")]

    # Step 2: query all folders in parallel (batch of max 10 concurrent)
    sem = asyncio.Semaphore(10)

    async def _fetch(fn: str) -> list[dict]:
        async with sem:
            return await _soap_list_one(token, instance_url, type_name, folder=fn)

    batches = await asyncio.gather(*[_fetch(fn) for fn in folder_names])
    return [item for batch in batches for item in batch]


# ─── Tooling API SOQL (richer data for common dev types) ─────────────────────

_TOOLING_QUERIES: dict[str, str] = {
    "ApexClass":               "SELECT Id, Name, Status, LengthWithoutComments, LastModifiedDate FROM ApexClass ORDER BY Name LIMIT 2000",
    "ApexTrigger":             "SELECT Id, Name, TableEnumOrId, Status, IsValid, LastModifiedDate FROM ApexTrigger ORDER BY Name LIMIT 2000",
    "ApexPage":                "SELECT Id, Name, MasterLabel, IsAvailableInTouch, LastModifiedDate FROM ApexPage ORDER BY Name LIMIT 2000",
    "ApexComponent":           "SELECT Id, Name, MasterLabel, LastModifiedDate FROM ApexComponent ORDER BY Name LIMIT 2000",
    "Flow":                    "SELECT Id, ApiName, Label, ProcessType, Status, VersionNumber, LastModifiedDate FROM Flow ORDER BY Label LIMIT 2000",
    "FlowDefinition":          "SELECT Id, DeveloperName, Label, LastModifiedDate FROM FlowDefinition ORDER BY DeveloperName LIMIT 2000",
    "StaticResource":          "SELECT Id, Name, ContentType, BodyLength, LastModifiedDate FROM StaticResource ORDER BY Name LIMIT 2000",
    "Profile":                 "SELECT Id, Name, LastModifiedDate FROM Profile ORDER BY Name LIMIT 500",
    "PermissionSet":           "SELECT Id, Name, Label, IsCustom, LastModifiedDate FROM PermissionSet ORDER BY Name LIMIT 2000",
    "PermissionSetGroup":      "SELECT Id, DeveloperName, MasterLabel, Status FROM PermissionSetGroup ORDER BY DeveloperName LIMIT 500",
    "ConnectedApp":            "SELECT Id, Name, Description FROM ConnectedApp ORDER BY Name LIMIT 500",
    "CustomLabel":             "SELECT Id, Name, Value, Language, Category FROM ExternalString ORDER BY Name LIMIT 2000",
    "CustomField":             "SELECT Id, DeveloperName, TableEnumOrId, DataType, LastModifiedDate FROM CustomField ORDER BY DeveloperName LIMIT 2000",
    "ValidationRule":          "SELECT Id, EntityDefinition.QualifiedApiName, ValidationName, Active, Description FROM ValidationRule ORDER BY ValidationName LIMIT 2000",
    "WorkflowRule":            "SELECT Id, Name, TableEnumOrId, Active FROM WorkflowRule ORDER BY Name LIMIT 2000",
    "LightningComponentBundle":"SELECT Id, DeveloperName, MasterLabel, ApiVersion, LastModifiedDate FROM LightningComponentBundle ORDER BY DeveloperName LIMIT 2000",
    "AuraDefinitionBundle":    "SELECT Id, DeveloperName, ApiVersion, LastModifiedDate FROM AuraDefinitionBundle ORDER BY DeveloperName LIMIT 2000",
    "CustomObject":            "SELECT QualifiedApiName, Label, DeveloperName, IsCustomizable, IsEverCreatable, LastModifiedDate FROM EntityDefinition WHERE IsCustomizable=true ORDER BY QualifiedApiName LIMIT 2000",
    "GlobalValueSet":          "SELECT Id, DeveloperName, MasterLabel, LastModifiedDate FROM GlobalValueSet ORDER BY DeveloperName LIMIT 2000",
    "Layout":                  "SELECT Id, Name, EntityDefinitionId, LastModifiedDate FROM Layout ORDER BY Name LIMIT 2000",
    "QuickAction":             "SELECT Id, DeveloperName, Label, Type FROM QuickActionDefinition ORDER BY DeveloperName LIMIT 2000",
    "NamedCredential":         "SELECT Id, DeveloperName, MasterLabel FROM NamedCredential ORDER BY DeveloperName LIMIT 500",
    "RemoteSiteSetting":       "SELECT Id, Url, Description FROM RemoteSiteSetting ORDER BY Url LIMIT 500",
    "CustomMetadata":          "SELECT Id, DeveloperName, MasterLabel, QualifiedApiName FROM CustomMetadataType ORDER BY DeveloperName LIMIT 2000",
    "CustomPermission":        "SELECT Id, DeveloperName, MasterLabel FROM CustomPermission ORDER BY DeveloperName LIMIT 500",
    "CustomTab":               "SELECT Id, DurableId, Name, SobjectName FROM TabDefinition ORDER BY Name LIMIT 500",
}

_STATIC_METADATA_TYPES = [
    {"xmlName": "ApexClass",               "directoryName": "classes",            "suffix": "cls",                 "inFolder": False},
    {"xmlName": "ApexComponent",           "directoryName": "components",         "suffix": "component",           "inFolder": False},
    {"xmlName": "ApexPage",                "directoryName": "pages",              "suffix": "page",                "inFolder": False},
    {"xmlName": "ApexTrigger",             "directoryName": "triggers",           "suffix": "trigger",             "inFolder": False},
    {"xmlName": "AuraDefinitionBundle",    "directoryName": "aura",               "suffix": None,                  "inFolder": False},
    {"xmlName": "ConnectedApp",            "directoryName": "connectedApps",      "suffix": "connectedApp",        "inFolder": False},
    {"xmlName": "CustomApplication",       "directoryName": "applications",       "suffix": "app",                 "inFolder": False},
    {"xmlName": "CustomField",             "directoryName": "objects",            "suffix": None,                  "inFolder": False},
    {"xmlName": "CustomLabel",             "directoryName": "labels",             "suffix": "labels",              "inFolder": False},
    {"xmlName": "CustomMetadata",          "directoryName": "customMetadata",     "suffix": "md",                  "inFolder": False},
    {"xmlName": "CustomObject",            "directoryName": "objects",            "suffix": "object",              "inFolder": False},
    {"xmlName": "CustomPermission",        "directoryName": "customPermissions",  "suffix": "customPermission",    "inFolder": False},
    {"xmlName": "CustomTab",               "directoryName": "tabs",               "suffix": "tab",                 "inFolder": False},
    {"xmlName": "Dashboard",               "directoryName": "dashboards",         "suffix": "dashboard",           "inFolder": True},
    {"xmlName": "EmailTemplate",           "directoryName": "email",              "suffix": "email",               "inFolder": True},
    {"xmlName": "Flow",                    "directoryName": "flows",              "suffix": "flow",                "inFolder": False},
    {"xmlName": "FlowDefinition",          "directoryName": "flowDefinitions",    "suffix": "flowDefinition",      "inFolder": False},
    {"xmlName": "GlobalValueSet",          "directoryName": "globalValueSets",    "suffix": "globalValueSet",      "inFolder": False},
    {"xmlName": "Layout",                  "directoryName": "layouts",            "suffix": "layout",              "inFolder": False},
    {"xmlName": "LightningComponentBundle","directoryName": "lwc",                "suffix": None,                  "inFolder": False},
    {"xmlName": "NamedCredential",         "directoryName": "namedCredentials",   "suffix": "namedCredential",     "inFolder": False},
    {"xmlName": "PermissionSet",           "directoryName": "permissionsets",     "suffix": "permissionset",       "inFolder": False},
    {"xmlName": "PermissionSetGroup",      "directoryName": "permissionsetgroups","suffix": "permissionsetgroup",  "inFolder": False},
    {"xmlName": "Profile",                 "directoryName": "profiles",           "suffix": "profile",             "inFolder": False},
    {"xmlName": "QuickAction",             "directoryName": "quickActions",       "suffix": "quickAction",         "inFolder": False},
    {"xmlName": "RemoteSiteSetting",       "directoryName": "remoteSiteSettings", "suffix": "remoteSite",          "inFolder": False},
    {"xmlName": "Report",                  "directoryName": "reports",            "suffix": "report",              "inFolder": True},
    {"xmlName": "StaticResource",          "directoryName": "staticresources",    "suffix": "resource",            "inFolder": False},
    {"xmlName": "ValidationRule",          "directoryName": "objects",            "suffix": None,                  "inFolder": False},
    {"xmlName": "WorkflowRule",            "directoryName": "workflows",          "suffix": "workflow",            "inFolder": False},
]


# ─── REST endpoints ───────────────────────────────────────────────────────────

@router.get("/describe/{object_name}")
async def describe_object(request: Request, object_name: str):
    token, instance_url = _require_auth(request)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(
            f"{instance_url}/services/data/v{_API_VERSION}/sobjects/{object_name}/describe/",
            headers={"Authorization": f"Bearer {token}"},
        )
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    return resp.json()


@router.get("/sobjects")
async def get_sobjects(request: Request):
    token, instance_url = _require_auth(request)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(
            f"{instance_url}/services/data/v{_API_VERSION}/sobjects/",
            headers={"Authorization": f"Bearer {token}"},
        )
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
        data = resp.json()

    return {
        "sobjects": [
            {
                "name":        s.get("name"),
                "label":       s.get("label"),
                "labelPlural": s.get("labelPlural"),
                "custom":      s.get("custom", False),
                "queryable":   s.get("queryable", False),
                "createable":  s.get("createable", False),
                "keyPrefix":   s.get("keyPrefix"),
            }
            for s in data.get("sobjects", [])
        ],
        "total": len(data.get("sobjects", [])),
    }


@router.get("/metadata-types")
async def get_metadata_types(request: Request):
    """
    Calls SOAP describeMetadata to return the full list of metadata types
    available in this org at the current API version.  Falls back to a static
    curated list when the SOAP call fails (sandbox restrictions, network, etc.).
    """
    token, instance_url = _require_auth(request)

    types = await _soap_describe_metadata(token, instance_url)
    if types:
        return {"metadata_types": types, "total": len(types), "source": "soap"}

    return {
        "metadata_types": _STATIC_METADATA_TYPES,
        "total": len(_STATIC_METADATA_TYPES),
        "source": "static",
    }


@router.get("/metadata-components/{type_name}")
async def get_metadata_components(request: Request, type_name: str):
    """
    Returns the component list for a metadata type using the best available method:
    1. Tooling API SOQL — richer fields for dev-centric types (Apex, Flow, etc.)
    2. SOAP listMetadata — works for ALL types including packages; handles
       folder-based types (Report/Dashboard/EmailTemplate/Document) by first
       enumerating folders then querying each one.
    """
    token, instance_url = _require_auth(request)

    # 1. Tooling API for types with richer data
    soql = _TOOLING_QUERIES.get(type_name)
    if soql:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(
                    f"{instance_url}/services/data/v{_API_VERSION}/tooling/query",
                    params={"q": soql},
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.is_success:
                records = resp.json().get("records", [])
                clean = [{k: v for k, v in r.items() if k != "attributes"} for r in records]
                if clean:
                    return {"type": type_name, "components": clean, "count": len(clean), "source": "tooling"}
        except Exception:
            pass

    # 2. SOAP listMetadata (primary path for everything else)
    #    Handles inFolder types by enumerating folders first.
    if type_name in _FOLDER_PARENT_TYPE:
        components = await _list_with_folders(token, instance_url, type_name)
    else:
        components = await _soap_list_one(token, instance_url, type_name)

    if components:
        return {"type": type_name, "components": components, "count": len(components), "source": "soap"}

    return {"type": type_name, "components": [], "count": 0, "source": "none"}
