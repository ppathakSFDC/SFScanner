"""
Smart keying: describe an sObject and determine the best upsert strategy.

Two separate concepts:
  key_field   — field used to build ID maps and to de-duplicate on re-runs.
                Can be a natural key like Name, DeveloperName, Email, etc.
                Selected from source describe only.
  op_ext_id   — field passed to the Bulk API as externalIdFieldName.
                MUST have externalId=True on the TARGET org or Salesforce
                returns INVALIDJOB.  Computed separately via
                find_bulk_ext_id() which cross-checks both org describes.
                 None requires an explicit Insert Only operation.

Also returns:
  - creatable_fields  : fields that can be written on insert/upsert
  - lookup_fields     : {field_name: related_object} for ID-mapping
  - self_lookups      : fields that reference the same object (need two-pass)
"""

import httpx
from typing import Optional

# Fields that Salesforce never allows you to set on DML
_SYSTEM_FIELDS = frozenset({
    "Id", "CreatedDate", "CreatedById", "LastModifiedDate", "LastModifiedById",
    "SystemModstamp", "LastActivityDate", "LastViewedDate", "LastReferencedDate",
    "IsDeleted", "MasterRecordId",
})

# Known natural-key overrides per object (when no externalId field exists).
# These must be unique within their object type so upsert doesn't duplicate.
_NATURAL_KEYS: dict[str, str] = {
    "Account":                          "Name",
    "Contact":                          "Email",
    "Lead":                             "Email",
    "User":                             "Username",
    "Product2":                         "StockKeepingUnit",
    "PriceBook2":                       "Name",
    "Pricebook2":                       "Name",
    "ProductCatalog":                   "Name",
    "ProductCategory":                  "Name",
    "AttributePicklist":                "Name",
    "AttributePicklistValue":           "Code",
    "AttributeSet":                     "Name",
    "AttributeDefinition":              "Name",
    "AttributeCategory":                "Name",
    "UnitOfMeasureClass":               "Name",
    "UnitOfMeasure":                    "Name",
    "CostBook":                         "Name",
    "ProductSellingModel":              "Name",
    "ProrationPolicy":                  "Name",
    "PriceAdjustmentSchedule":          "Name",
    "ProductConfigurationFlow":         "Name",
    "ProductComponentGroup":            "Name",
    "ProductSpecificationType":         "Name",
    "ExpressionSet":                    "DeveloperName",
    "ExpressionSetDefinition":          "DeveloperName",
    "BusinessRule":                     "DeveloperName",
    "OmniDataTransform":                "Name",
    "OmniProcess":                      "Name",
    # Vlocity
    "vlocity_cmt__PricingProcedure__c":  "Name",
    "vlocity_cmt__ContextDefinition__c": "Name",
    "vlocity_cmt__AttributeCategory__c": "Name",
    "vlocity_cmt__ObjectClass__c":       "Name",
}


async def describe_object(access_token: str, instance_url: str, object_name: str) -> dict:
    """Fetch Salesforce object describe metadata."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        resp = await client.get(
            f"{instance_url}/services/data/v62.0/sobjects/{object_name}/describe/",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


def get_upsert_strategy(describe_meta: dict, object_name: str) -> dict:
    """
    Returns:
      {
        "key_field":       str | None,    # field to use as upsert key (None = insert only)
        "creatable_fields": [str],        # fields to include in the migration payload
        "lookup_fields":   {field: related_object},
        "self_lookups":    [str],         # fields referencing own object (two-pass needed)
      }
    """
    fields = describe_meta.get("fields", [])

    creatable_fields = []
    queryable_fields = []   # subset of creatable that are also queryable (for SELECT)
    lookup_fields: dict[str, str] = {}
    self_lookups: list[str] = []
    external_id_candidates: list[str] = []

    for f in fields:
        name = f["name"]
        if name in _SYSTEM_FIELDS:
            continue
        if not f.get("createable", False):
            continue

        creatable_fields.append(name)

        # Only include in SELECT if queryable AND not encrypted.
        # Salesforce returns queryable=False for some encrypted fields, but also
        # exposes encrypted=True as a reliable signal — check both to be safe.
        if f.get("queryable", True) and not f.get("encrypted", False):
            queryable_fields.append(name)

        # Track lookup relationships for ID mapping
        if f["type"] in ("reference",) and f.get("referenceTo"):
            ref_to = f["referenceTo"]
            if len(ref_to) == 1:
                related = ref_to[0]
                if related == object_name:
                    self_lookups.append(name)
                else:
                    lookup_fields[name] = related
            elif len(ref_to) > 1:
                # Polymorphic lookup (e.g. WhoId → Contact|Lead) — store list;
                # engine will try each parent until one resolves.
                poly_parents = [r for r in ref_to if r != object_name]
                if poly_parents:
                    lookup_fields[name] = poly_parents

        # Collect external ID candidates — must be queryable and not encrypted
        if f.get("externalId") and f.get("queryable", True) and not f.get("encrypted", False):
            score = 2 if f.get("unique") else 1
            external_id_candidates.append((score, name))

    # Determine best upsert key
    key_field = None
    if external_id_candidates:
        external_id_candidates.sort(reverse=True)
        key_field = external_id_candidates[0][1]
    elif object_name in _NATURAL_KEYS:
        natural = _NATURAL_KEYS[object_name]
        # Verify the field actually exists and is creatable
        if natural in creatable_fields:
            key_field = natural
    else:
        # Check for a generic Name field
        if "Name" in creatable_fields:
            key_field = "Name"

    return {
        "key_field": key_field,
        "creatable_fields": creatable_fields,
        "queryable_fields": queryable_fields,
        "lookup_fields": lookup_fields,
        "self_lookups": self_lookups,
    }


def find_bulk_ext_id(source_desc: dict, target_desc: dict) -> Optional[str]:
    """
    Return the best external ID field that is valid for Bulk API upsert on the
    TARGET org.  Both orgs must have the field marked externalId=True — if only
    the source has it the target Bulk API will reject the job with INVALIDJOB.

    Returns None when no such common field exists; upsert must fail closed.
    """
    src_by_name = {f["name"]: f for f in source_desc.get("fields", [])}
    tgt_by_name = {f["name"]: f for f in target_desc.get("fields", [])}

    candidates: list[tuple[int, str]] = []
    for name, sf in src_by_name.items():
        if (not sf.get("externalId") or not sf.get("createable")
                or not sf.get("queryable", True) or sf.get("encrypted", False)):
            continue
        tf = tgt_by_name.get(name)
        if tf and tf.get("externalId") and tf.get("createable"):
            # Prefer fields that are also unique (more stable key)
            score = 2 if (sf.get("unique") or tf.get("unique")) else 1
            candidates.append((score, name))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]

    return None  # no common external ID → caller must choose insert explicitly
