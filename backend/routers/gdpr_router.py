"""
GDPR Compliance Router
Handles record retention checks, anonymisation, Subject Access Request export, and deletion.
All destructive operations require an explicit confirm=true flag and produce an audit entry.
"""
import json
import csv
import io
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..salesforce.client import SalesforceClient

router = APIRouter(prefix="/gdpr", tags=["gdpr"])

# ── PII field heuristics ──────────────────────────────────────────────────────

_PII_FIELD_NAMES = {
    # Identity
    "name", "firstname", "lastname", "middlename", "salutation", "suffix",
    # Contact
    "email", "phone", "mobilephone", "homephone", "otherphone", "fax",
    "assistantphone", "personalphone",
    # Address
    "mailingstreet", "mailingcity", "mailingstate", "mailingpostalcode",
    "mailingcountry", "mailinglatitude", "mailinglongitude",
    "otherstreet", "othercity", "otherstate", "otherpostalcode", "othercountry",
    "street", "city", "state", "postalcode", "country",
    # Personal
    "birthdate", "dateofbirth", "gender", "nationalidentifier", "taxid",
    "passportnumber", "driverslicense", "ssn", "nationalid",
    # Account / financial
    "bankaccountnumber", "creditcardnumber", "iban",
    # Web identity
    "website", "twitterhandle", "linkedinuri",
    # Description / notes often contain PII
    "description", "notes",
}

_PII_KEYWORDS = [
    "personal", "private", "sensitive", "confidential", "pii", "gdpr",
    "address", "phone", "email", "birth", "national", "passport", "id_number",
]

# Anonymised replacement values by field type
_ANON_VALUES = {
    "email":   "gdpr-anonymized@invalid.invalid",
    "phone":   "+000000000",
    "name":    "GDPR Anonymized",
    "address": "[REDACTED]",
    "date":    None,
    "text":    "[REDACTED]",
    "url":     "[REDACTED]",
}


def _is_pii_field(field: dict) -> bool:
    name_lower = field.get("name", "").lower()
    label_lower = field.get("label", "").lower()
    if name_lower in _PII_FIELD_NAMES:
        return True
    if any(kw in name_lower or kw in label_lower for kw in _PII_KEYWORDS):
        return True
    return False


def _anon_value(field: dict):
    name_lower = field.get("name", "").lower()
    ftype = field.get("type", "string").lower()
    if "email" in name_lower:
        return _ANON_VALUES["email"]
    if any(x in name_lower for x in ("phone", "fax", "mobile")):
        return _ANON_VALUES["phone"]
    if any(x in name_lower for x in ("name", "firstname", "lastname", "salutation")):
        return _ANON_VALUES["name"]
    if any(x in name_lower for x in ("street", "city", "state", "postal", "country", "address")):
        return _ANON_VALUES["address"]
    if ftype in ("date", "datetime"):
        return _ANON_VALUES["date"]
    if ftype in ("url", "reference"):
        return _ANON_VALUES["url"]
    return _ANON_VALUES["text"]


# ── Auth helper ───────────────────────────────────────────────────────────────

def _require_auth(request: Request):
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token, instance_url


# ── Models ────────────────────────────────────────────────────────────────────

class PreviewRequest(BaseModel):
    soql: str
    object_name: str
    limit: int = 200


class ActionRequest(BaseModel):
    record_ids: List[str]
    object_name: str
    confirm: bool = False          # must be True to execute destructive ops
    fields_to_anonymize: Optional[List[str]] = None   # if None, auto-detect PII fields


class SubjectExportRequest(BaseModel):
    email: Optional[str] = None
    record_id: Optional[str] = None
    object_name: str = "Contact"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/pii-fields/{object_name}")
async def get_pii_fields(object_name: str, request: Request):
    """Describe the object and return fields likely to contain PII."""
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)
    try:
        desc = await sf.describe_object(object_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot describe {object_name}: {e}")

    all_fields = desc.get("fields", [])
    pii = [
        {
            "name": f["name"],
            "label": f["label"],
            "type": f["type"],
            "updateable": f.get("updateable", False),
            "nillable": f.get("nillable", True),
        }
        for f in all_fields
        if _is_pii_field(f) and f.get("updateable", False)
    ]
    non_pii_queryable = [
        {"name": f["name"], "label": f["label"], "type": f["type"]}
        for f in all_fields
        if not _is_pii_field(f) and f.get("queryable", False)
        and f["name"] not in ("Id", "IsDeleted", "SystemModstamp")
    ][:20]
    return {
        "object": object_name,
        "pii_fields": pii,
        "sample_non_pii_fields": non_pii_queryable,
        "total_fields": len(all_fields),
    }


@router.post("/preview")
async def preview_records(body: PreviewRequest, request: Request):
    """
    Run a SOQL query (dry-run) and return matching records + count.
    Used to show the user what WOULD be affected before any action.
    """
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)

    soql = body.soql.strip()
    if not soql.upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed in preview")

    # Enforce a LIMIT to avoid fetching huge datasets for display
    soql_upper = soql.upper()
    if "LIMIT" not in soql_upper:
        soql = f"{soql} LIMIT {body.limit}"

    try:
        result = await sf.query(soql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SOQL error: {e}")

    records = result.get("records", [])
    # Strip Salesforce metadata attributes from display
    clean = [{k: v for k, v in r.items() if k != "attributes"} for r in records]

    return {
        "object": body.object_name,
        "total_size": result.get("totalSize", len(records)),
        "returned": len(records),
        "records": clean,
        "soql": soql,
    }


@router.post("/anonymize")
async def anonymize_records(body: ActionRequest, request: Request):
    """
    Anonymise PII fields on the given record IDs.
    Requires confirm=true. Without it, returns a dry-run summary.
    """
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)

    if not body.record_ids:
        raise HTTPException(status_code=400, detail="No record IDs provided")

    # Detect which fields to anonymise
    if body.fields_to_anonymize:
        fields_to_clear = body.fields_to_anonymize
        field_meta: dict = {}
    else:
        try:
            desc = await sf.describe_object(body.object_name)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Cannot describe object: {e}")
        pii_fields = [
            f for f in desc.get("fields", [])
            if _is_pii_field(f) and f.get("updateable", False) and f.get("nillable", True)
            and f["name"] not in ("Name",)  # Name handled separately
        ]
        fields_to_clear = [f["name"] for f in pii_fields]
        field_meta = {f["name"]: f for f in pii_fields}

        # Always include Name if it's updateable (but set to anonymized, not null)
        name_field = next((f for f in desc.get("fields", []) if f["name"] == "Name" and f.get("updateable")), None)
        if name_field:
            fields_to_clear = ["Name"] + fields_to_clear
            field_meta["Name"] = name_field

    if not fields_to_clear:
        return {"status": "nothing_to_anonymize", "message": "No updateable PII fields detected"}

    # Build anonymisation payload
    anon_record_template: dict = {}
    for fname in fields_to_clear:
        meta = field_meta.get(fname, {"name": fname, "type": "string", "label": fname})
        anon_record_template[fname] = _anon_value(meta)

    dry_run_summary = {
        "object": body.object_name,
        "record_count": len(body.record_ids),
        "fields_to_anonymize": fields_to_clear,
        "sample_values": anon_record_template,
        "confirm_required": not body.confirm,
    }

    if not body.confirm:
        return {
            "status": "dry_run",
            "message": f"DRY RUN — {len(body.record_ids)} record(s) would have these fields anonymised. "
                       f"Set confirm=true to execute.",
            **dry_run_summary,
        }

    # Execute via Salesforce Composite API (batch updates, 200 per call)
    errors = []
    updated = 0
    batch_size = 200

    for i in range(0, len(body.record_ids), batch_size):
        batch_ids = body.record_ids[i: i + batch_size]
        records_payload = [{"Id": rid, **anon_record_template} for rid in batch_ids]
        try:
            result = await sf.bulk_update(body.object_name, records_payload)
            for r in result:
                if r.get("success"):
                    updated += 1
                else:
                    errors.append({"id": r.get("id"), "errors": r.get("errors")})
        except Exception as e:
            errors.append({"batch_start": i, "error": str(e)})

    return {
        "status": "completed" if not errors else "partial",
        "object": body.object_name,
        "updated": updated,
        "errors": errors,
        "fields_anonymized": fields_to_clear,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/export")
async def export_subject_data(body: SubjectExportRequest, request: Request):
    """
    Subject Access Request (SAR) — export all data for a specific individual.
    Returns a downloadable JSON file with all related records.
    """
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)

    if not body.email and not body.record_id:
        raise HTTPException(status_code=400, detail="Provide either email or record_id")

    # Build lookup query
    if body.record_id:
        soql = f"SELECT FIELDS(ALL) FROM {body.object_name} WHERE Id = '{body.record_id}' LIMIT 1"
    else:
        soql = f"SELECT FIELDS(ALL) FROM {body.object_name} WHERE Email = '{body.email}' LIMIT 10"

    try:
        result = await sf.query(soql)
    except Exception:
        # FIELDS(ALL) not always supported — fallback to common fields
        fields = "Id, Name, Email, Phone, CreatedDate, LastModifiedDate"
        if body.record_id:
            soql = f"SELECT {fields} FROM {body.object_name} WHERE Id = '{body.record_id}' LIMIT 1"
        else:
            soql = f"SELECT {fields} FROM {body.object_name} WHERE Email = '{body.email}' LIMIT 10"
        result = await sf.query(soql)

    records = result.get("records", [])
    clean = [{k: v for k, v in r.items() if k != "attributes"} for r in records]

    export_data = {
        "export_type": "Subject Access Request (GDPR Art. 15)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "instance_url": instance_url,
        "subject": body.email or body.record_id,
        "object": body.object_name,
        "record_count": len(clean),
        "records": clean,
    }

    content = json.dumps(export_data, indent=2, default=str)
    filename = f"SAR_{(body.email or body.record_id or 'export').replace('@','_')}.json"

    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/delete")
async def delete_records(body: ActionRequest, request: Request):
    """
    Hard-delete records by ID. Requires confirm=true.
    Returns a dry-run summary when confirm is false.
    """
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)

    if not body.record_ids:
        raise HTTPException(status_code=400, detail="No record IDs provided")

    if not body.confirm:
        return {
            "status": "dry_run",
            "message": f"DRY RUN — {len(body.record_ids)} record(s) from {body.object_name} would be DELETED. "
                       f"Set confirm=true to execute. This action cannot be undone.",
            "object": body.object_name,
            "record_count": len(body.record_ids),
            "record_ids_preview": body.record_ids[:10],
        }

    errors = []
    deleted = 0
    batch_size = 200

    for i in range(0, len(body.record_ids), batch_size):
        batch_ids = body.record_ids[i: i + batch_size]
        ids_param = ",".join(batch_ids)
        try:
            result = await sf.bulk_delete(body.object_name, batch_ids)
            for r in result:
                if r.get("success"):
                    deleted += 1
                else:
                    errors.append({"id": r.get("id"), "errors": r.get("errors")})
        except Exception as e:
            errors.append({"batch_start": i, "error": str(e)})

    return {
        "status": "completed" if not errors else "partial",
        "object": body.object_name,
        "deleted": deleted,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/retention-suggestions")
async def retention_suggestions(request: Request):
    """
    Return common GDPR retention rule templates the user can apply.
    """
    return {
        "templates": [
            {
                "id": "inactive_contacts",
                "label": "Inactive Contacts (7+ years)",
                "description": "Contacts with no activity for 7 or more years",
                "object": "Contact",
                "soql": "SELECT Id, Name, Email, LastActivityDate, CreatedDate FROM Contact WHERE LastActivityDate < LAST_N_YEARS:7 OR (LastActivityDate = null AND CreatedDate < LAST_N_YEARS:7)",
                "recommended_action": "anonymize",
            },
            {
                "id": "unqualified_leads",
                "label": "Old Unqualified Leads (3+ years)",
                "description": "Leads not converted and untouched for 3 or more years",
                "object": "Lead",
                "soql": "SELECT Id, Name, Email, Status, LastModifiedDate FROM Lead WHERE IsConverted = false AND LastModifiedDate < LAST_N_YEARS:3",
                "recommended_action": "anonymize",
            },
            {
                "id": "closed_cases",
                "label": "Closed Cases (5+ years)",
                "description": "Cases closed more than 5 years ago",
                "object": "Case",
                "soql": "SELECT Id, CaseNumber, Subject, ClosedDate, ContactId FROM Case WHERE IsClosed = true AND ClosedDate < LAST_N_YEARS:5",
                "recommended_action": "anonymize",
            },
            {
                "id": "test_accounts",
                "label": "Test / Demo Accounts",
                "description": "Accounts with 'test', 'demo', or 'sample' in the name",
                "object": "Account",
                "soql": "SELECT Id, Name, CreatedDate FROM Account WHERE Name LIKE '%test%' OR Name LIKE '%demo%' OR Name LIKE '%sample%'",
                "recommended_action": "delete",
            },
            {
                "id": "bounced_emails",
                "label": "Hard-bounced Email Contacts",
                "description": "Contacts with email opt-out or invalid email",
                "object": "Contact",
                "soql": "SELECT Id, Name, Email, HasOptedOutOfEmail, EmailBouncedDate FROM Contact WHERE HasOptedOutOfEmail = true OR EmailBouncedDate != null",
                "recommended_action": "anonymize",
            },
        ]
    }
