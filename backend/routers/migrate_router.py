from __future__ import annotations

import asyncio
import json
import uuid
import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from urllib.parse import unquote, urlsplit
from typing import Optional

from ..salesforce.client import SalesforceClient
from ..auth.oauth import login_with_credentials
from ..migrator.object_groups import OBJECT_GROUPS, OBJECT_DEPS, PRODUCT_BUNDLE_OBJECTS
from ..migrator.job_store import (
    MigrationJob, ObjectMigrationResult,
    _jobs, _job_progress,
    get_job, set_job, get_progress, set_progress, get_log_delta, cancel_job,
)
from ..migrator.engine import MigrationEngine, rollback_job

router = APIRouter(prefix="/migrate", tags=["migrate"])


def _require_auth(request: Request) -> tuple[str, str]:
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token, instance_url


def _require_job(request: Request, job_id: str) -> MigrationJob:
    _, source_url = _require_auth(request)
    job = get_job(job_id)
    owner = request.session.get("migration_owner_id")
    if not job or not owner or job.migration_owner_id != owner or job.source_url != source_url:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _target_origin(value: str) -> str:
    url = value.strip()
    try:
        if any(ord(char) < 33 or ord(char) == 127 for char in url) or any(
                ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Invalid target origin")
        parsed = urlsplit(url)
        host = parsed.hostname
        if (parsed.scheme != "https" or not host or parsed.username is not None
                or parsed.password is not None or parsed.port is not None
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or "?" in url or "#" in url or "\\" in url
                or not host.isascii()
                or not host.endswith((".salesforce.com", ".force.com"))
                or any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?", label)
                       for label in host.split("."))
                or parsed.netloc.lower() != host.lower()):
            raise ValueError("Invalid target origin")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Salesforce target origin") from None
    return f"https://{host}"


# ──────────────────────────────────────────────────────────────────────────────
# GET /migrate/records/{object_name}  — fetch records for record picker
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/records/{object_name}")
async def get_records(object_name: str, request: Request, q: str = ""):
    token, instance_url = _require_auth(request)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", object_name):
        raise HTTPException(status_code=400, detail="Invalid object name")
    if object_name not in {obj["name"] for group in OBJECT_GROUPS for obj in group["objects"]}:
        raise HTTPException(status_code=400, detail="Object is not supported for migration")
    sf = SalesforceClient(token, instance_url)

    # Sanitise search term — strip SOQL-dangerous characters
    q_safe = re.sub(r"['\";\\%_]", "", q.strip())[:100]

    # Discover which fields to display: try Name + one meaningful key field
    display_fields = ["Id"]
    try:
        desc = await sf.describe_object(object_name)
        field_names = {f["name"] for f in desc.get("fields", [])}
        if "Name" in field_names:
            display_fields.append("Name")
        for candidate in ("StockKeepingUnit", "ExternalId__c", "Code__c", "ApiName", "DeveloperName", "MasterLabel"):
            if candidate in field_names:
                display_fields.append(candidate)
                break
    except Exception:
        pass  # fall back to Id-only

    select_clause = ", ".join(dict.fromkeys(display_fields))
    soql = f"SELECT {select_clause} FROM {object_name}"
    if q_safe:
        conditions = " OR ".join(
            f"{f} LIKE '%{q_safe}%'" for f in display_fields if f != "Id"
        )
        if conditions:
            soql += f" WHERE {conditions}"
    soql += " ORDER BY " + (display_fields[1] if len(display_fields) > 1 else "Id") + " ASC NULLS LAST LIMIT 500"

    try:
        result = await sf.query(soql)
    except Exception:
        # fallback: Id only
        fb = f"SELECT Id FROM {object_name} LIMIT 500"
        result = await sf.query(fb)
        display_fields = ["Id"]

    name_field   = display_fields[1] if len(display_fields) > 1 else "Id"
    sub_field    = display_fields[2] if len(display_fields) > 2 else None
    records_out  = [
        {
            "id":   r["Id"],
            "name": str(r.get(name_field) or r["Id"]),
            "sub":  str(r.get(sub_field, "")) if sub_field else "",
        }
        for r in result.get("records", [])
    ]
    return {"records": records_out, "total": result.get("totalSize", len(records_out))}


# ──────────────────────────────────────────────────────────────────────────────
# GET /migrate/describe  — probe source org for available object groups
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/describe")
async def describe_objects(request: Request):
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)

    try:
        all_sobjects = set(await sf.list_sobjects())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not list org objects: {e}")

    omni_discovery = await sf.discover_omnistudio_objects()

    groups_out = []
    for grp in OBJECT_GROUPS:
        available = False
        objects_out = []

        if grp.get("virtual"):
            probe_key = grp.get("probe_key", "")
            probe_result = omni_discovery.get(probe_key, {})
            available = bool(probe_result.get("exists"))
            count = probe_result.get("count", 0)
            for obj in grp["objects"]:
                objects_out.append({**obj, "available": available, "count": count if obj == grp["objects"][0] else 0})
        else:
            probe_obj = grp.get("probe_object")
            if probe_obj:
                available = probe_obj in all_sobjects
            else:
                available = True

            count_tasks = {}
            for obj in grp["objects"]:
                if obj["name"] in all_sobjects:
                    count_tasks[obj["name"]] = sf.query(f"SELECT COUNT() FROM {obj['name']} LIMIT 1")

            count_results = {}
            if count_tasks:
                results = await asyncio.gather(*count_tasks.values(), return_exceptions=True)
                for name, result in zip(count_tasks.keys(), results):
                    count_results[name] = 0 if isinstance(result, Exception) else result.get("totalSize", 0)

            for obj in grp["objects"]:
                obj_available = obj["name"] in all_sobjects
                objects_out.append({**obj, "available": obj_available, "count": count_results.get(obj["name"], 0)})
                if obj_available:
                    available = True

        groups_out.append({
            "key": grp["key"],
            "label": grp["label"],
            "icon": grp["icon"],
            "description": grp["description"],
            "available": available,
            "virtual": grp.get("virtual", False),
            "primary_object": grp.get("primary_object", ""),
            "objects": objects_out,
        })

    return {"instance_url": instance_url, "groups": groups_out, "total_objects": len(all_sobjects)}


# ──────────────────────────────────────────────────────────────────────────────
# POST /migrate/scope-filters  — compute per-object WHERE clauses from product IDs
# ──────────────────────────────────────────────────────────────────────────────
class ScopeFiltersPayload(BaseModel):
    product_ids: list[str]            # selected Product2 record IDs


def _id_clause(ids: list[str]) -> str:
    """Build a SOQL-safe quoted IN list from a list of Salesforce IDs."""
    return ", ".join(f"'{i}'" for i in sorted(set(ids)))


_SF_ID = re.compile(r"^[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?$")
_SCOPE_BATCH = 150
_MAX_PRODUCTS = 150
_MAX_EXPANDED = 150


async def build_product_scope(sf: SalesforceClient, product_ids: list[str]) -> dict:
    if not product_ids or len(product_ids) > _MAX_PRODUCTS or any(not _SF_ID.fullmatch(i) for i in product_ids):
        raise HTTPException(status_code=400, detail="product_ids must contain 1–150 Salesforce IDs")
    try:
        available = set(await sf.list_sobjects())
        if 'Product2' not in available:
            raise ValueError('Product2 is not available on source')
        filters: dict[str, str] = {}
        described = {}

        async def require(obj, *fields):
            if obj not in available:
                raise ValueError(f'Required source object {obj} unavailable')
            if obj not in described:
                described[obj] = {f['name'] for f in (await sf.describe_object(obj)).get('fields', [])}
            absent = set(fields) - described[obj]
            if absent:
                raise ValueError(f'{obj} missing required fields: {sorted(absent)}')

        async def ids(obj, field, where):
            if obj not in available:
                return []
            await require(obj, field, where[0])
            found = set()
            for start in range(0, len(where[1]), _SCOPE_BATCH):
                # where contains (field_name, ID list); never query an unbounded table.
                key, values = where
                batch = values[start:start + _SCOPE_BATCH]
                soql = f'SELECT {field} FROM {obj} WHERE {key} IN ({_id_clause(batch)})'
                result = await sf.query(soql)
                while True:
                    found.update(r[field] for r in result.get('records', []) if r.get(field))
                    if len(found) > _MAX_EXPANDED:
                        raise ValueError(f'{obj} discovery exceeds expansion limit')
                    if result.get('done', True):
                        break
                    url = result.get('nextRecordsUrl')
                    if not url:
                        raise ValueError(f'Incomplete discovery for {obj}')
                    import httpx
                    async with httpx.AsyncClient(timeout=30) as client:
                        response = await client.get(sf.instance_url + url, headers=sf.headers)
                        response.raise_for_status()
                        result = response.json()
            return sorted(found)

        async def optional_ids(obj, field, where):
            if obj in available:
                await require(obj)
                if field in described[obj]:
                    return await ids(obj, field, where)
            return []

        async def checked_refs(obj, field, row_ids, parent):
            values = await optional_ids(obj, field, ('Id', row_ids)) if row_ids else []
            if values:
                if parent not in available:
                    raise ValueError(f'{obj}.{field} requires source {parent}')
                if set(await ids(parent, 'Id', ('Id', values))) != set(values):
                    raise ValueError(f'{obj}.{field} references missing {parent} records')
            return values

        def put(obj, field, values):
            if obj in available and values:
                if len(set(values)) > _MAX_EXPANDED:
                    raise ValueError(f'{obj} scope exceeds safe SOQL IN limit ({_MAX_EXPANDED})')
                filters[obj] = f'{field} IN ({_id_clause(values)})'

        selected = sorted(set(product_ids))
        await require('Product2', 'Id')
        valid = await ids('Product2', 'Id', ('Id', selected))
        if set(valid) != set(selected):
            raise ValueError('Some selected Product2 IDs do not exist on source')
        frontier = selected
        while frontier:
            groups = await ids('ProductComponentGroup', 'Id', ('ParentProductId', frontier))
            children = await ids('ProductRelatedComponent', 'ChildProductId', ('ProductComponentGroupId', groups)) if groups else []
            if 'ProductRelatedComponent' in available:
                children += await ids('ProductRelatedComponent', 'ChildProductId', ('ParentProductId', frontier))
            new = sorted(set(children) - set(selected))
            if len(selected) + len(new) > _MAX_EXPANDED:
                raise ValueError('Product bundle exceeds expansion limit')
            if new and set(await ids('Product2', 'Id', ('Id', new))) != set(new):
                raise ValueError('Bundle references missing child Product2 records')
            selected = sorted(set(selected) | set(new))
            frontier = new
        put('Product2', 'Id', selected)
        groups = await ids('ProductComponentGroup', 'Id', ('ParentProductId', selected))
        group_frontier = groups
        while group_frontier:
            parents = await checked_refs('ProductComponentGroup', 'ParentGroupId', group_frontier, 'ProductComponentGroup')
            extra = sorted(set(parents) - set(groups))
            if extra:
                owners = await ids('ProductComponentGroup', 'ParentProductId', ('Id', extra))
                if set(owners) - set(selected):
                    raise ValueError('Group ancestor belongs to a product outside selected bundle')
                if len(groups) + len(extra) > _MAX_EXPANDED:
                    raise ValueError('Group hierarchy exceeds expansion limit')
            groups = sorted(set(groups) | set(extra))
            group_frontier = extra
        if groups:
            links = {}
            for group in groups:
                parent = await optional_ids('ProductComponentGroup', 'ParentGroupId', ('Id', [group]))
                links[group] = parent[0] if parent else None
            for group in groups:
                seen = set()
                current = group
                while current:
                    if current in seen:
                        raise ValueError('ProductComponentGroup parent cycle is unsupported')
                    seen.add(current)
                    current = links.get(current)
        put('ProductComponentGroup', 'Id', groups)
        if 'ProductRelatedComponent' in available:
            group_components = await ids('ProductRelatedComponent', 'Id', ('ProductComponentGroupId', groups)) if groups else []
            direct_components = await ids('ProductRelatedComponent', 'Id', ('ParentProductId', selected))
            component_ids = sorted(set(group_components + direct_components))
            put('ProductRelatedComponent', 'Id', component_ids)
            await require('ProductRelatedComponent', 'ChildProductId') if component_ids else None
            for field, parent, allowed in (
                ('ParentProductId', 'Product2', selected),
                ('ChildProductId', 'Product2', selected),
                ('ProductComponentGroupId', 'ProductComponentGroup', groups),
            ):
                values = await checked_refs('ProductRelatedComponent', field, component_ids, parent)
                if set(values) - set(allowed):
                    raise ValueError(f'ProductRelatedComponent.{field} references outside selected bundle')
        else:
            component_ids = []
        if groups:
            owners = await checked_refs('ProductComponentGroup', 'ParentProductId', groups, 'Product2')
            if set(owners) - set(selected):
                raise ValueError('ProductComponentGroup references outside selected bundle')
        if groups and 'ProductComponentGrpOverride' in available:
            await require('ProductComponentGrpOverride', 'Id', 'ProductComponentGroupId', 'OverrideContextId')
            override_ids = await ids('ProductComponentGrpOverride', 'Id', ('ProductComponentGroupId', groups))
            matching = []
            for override_id in override_ids:
                context = await ids('ProductComponentGrpOverride', 'OverrideContextId', ('Id', [override_id]))
                if context and context[0] in selected:
                    matching.append(override_id)
                elif context and context[0] not in selected and context[0] not in (await ids('Product2', 'Id', ('Id', [context[0]]))):
                    raise ValueError('Unsupported ProductComponentGrpOverride.OverrideContextId outside Product2')
            put('ProductComponentGrpOverride', 'Id', matching)
        for obj, field in (
            ('Product2DataTranslation', 'ParentId'),
            ('ProductCategoryProduct', 'ProductId'), ('PricebookEntry', 'Product2Id'),
            ('CostBookEntry', 'ProductId'), ('ProductSellingModelOption', 'Product2Id'),
            ('ProductRampSegment', 'ProductId'),
        ):
            put(obj, field, selected)

        async def refs(child, parent_field, key, values, parent):
            found = await ids(child, parent_field, (key, values)) if values else []
            put(parent, 'Id', found)
            return found

        # Parallel: BasedOnId lookup and PAD discovery are independent of each other
        _pc_raw, pad_instances = await asyncio.gather(
            optional_ids('Product2', 'BasedOnId', ('Id', selected)),
            ids('ProductAttributeDefinition', 'Id', ('Product2Id', selected)),
        )
        pc = _pc_raw
        if pc and 'ProductClassification' not in available:
            raise ValueError('ProductClassification required by Product2 is absent')
        if component_ids:
            pc = sorted(set(pc) | set(await checked_refs('ProductRelatedComponent', 'ChildProductClassificationId', component_ids, 'ProductClassification')))
        put('ProductAttributeDefinition', 'Id', pad_instances)
        linked_pca = await checked_refs('ProductAttributeDefinition', 'ProductClassificationAttributeId', pad_instances, 'ProductClassificationAttr')
        linked_pc = await checked_refs('ProductClassificationAttr', 'ProductClassificationId', linked_pca, 'ProductClassification')
        # Native classifications retain inherited attributes; linked classifications only bring their required PCA.
        for pass_index, roots in enumerate((pc, linked_pc)):
            ancestors = sorted(set(roots) - set(pc)) if pass_index else pc
            pc = sorted(set(pc) | set(ancestors))
            if len(pc) > _MAX_EXPANDED:
                raise ValueError('Classification hierarchy exceeds limit')
            while ancestors:
                more = await checked_refs('ProductClassification', 'ParentProductClassificationId', ancestors, 'ProductClassification')
                more = sorted(set(more) - set(pc))
                if len(pc) + len(more) > _MAX_EXPANDED:
                    raise ValueError('Classification hierarchy exceeds limit')
                pc = sorted(set(pc) | set(more))
                ancestors = more
            if not pass_index:
                native_pca = await ids('ProductClassificationAttr', 'Id', ('ProductClassificationId', pc)) if pc else []
        pca_instances = sorted(set(native_pca) | set(linked_pca))
        put('ProductClassificationAttr', 'Id', pca_instances)
        put('ProductClassification', 'Id', pc)
        pad = await checked_refs('ProductAttributeDefinition', 'AttributeDefinitionId', pad_instances, 'AttributeDefinition')
        pca = await checked_refs('ProductClassificationAttr', 'AttributeDefinitionId', pca_instances, 'AttributeDefinition')
        definitions = sorted(set(pad) | set(pca))
        put('AttributeDefinition', 'Id', definitions)
        if definitions and 'AttributeDefinition' not in available:
            raise ValueError('AttributeDefinition required by selected products is absent')
        # Compute categories from direct product-level assignments (PAD + PCA), not the
        # global AttributeCategoryAttribute registry which bloats scope to every org-wide use.
        pad_cats = await checked_refs('ProductAttributeDefinition', 'AttributeCategoryId', pad_instances, 'AttributeCategory') if pad_instances else []
        pca_cats = await checked_refs('ProductClassificationAttr', 'AttributeCategoryId', pca_instances, 'AttributeCategory')
        cats = sorted(set(pad_cats) | set(pca_cats))
        if not cats and definitions:
            # Fallback for orgs where PAD/PCA don't carry AttributeCategoryId
            cats = sorted(set(await ids('AttributeCategoryAttribute', 'AttributeCategoryId', ('AttributeDefinitionId', definitions))))
        put('AttributeCategory', 'Id', cats)
        # ACA: intersection of selected categories × selected definitions (not a full cross-product)
        if cats and definitions:
            aca_by_cat = set(await ids('AttributeCategoryAttribute', 'Id', ('AttributeCategoryId', cats)))
            aca_by_def = set(await ids('AttributeCategoryAttribute', 'Id', ('AttributeDefinitionId', definitions)))
            put('AttributeCategoryAttribute', 'Id', sorted(aca_by_cat & aca_by_def))
        elif definitions:
            put('AttributeCategoryAttribute', 'AttributeDefinitionId', definitions)
        picks = await optional_ids('AttributeDefinition', 'PicklistId', ('Id', definitions)) if definitions else []
        put('AttributePicklist', 'Id', picks)
        if picks and 'AttributePicklist' not in available:
            raise ValueError('AttributePicklist required by selected definitions is absent')
        put('AttributePicklistValue', 'PicklistId', picks)
        if picks and 'AttrPicklistExcludedValue' in available:
            values = await ids('AttributePicklistValue', 'Id', ('PicklistId', picks))
            await require('AttrPicklistExcludedValue', 'AttributePicklistValueId', 'AttributeId')
            excluded = await ids('AttrPicklistExcludedValue', 'Id', ('AttributePicklistValueId', values)) if values else []
            matching = []
            for excluded_id in excluded:
                attrs = await ids('AttrPicklistExcludedValue', 'AttributeId', ('Id', [excluded_id]))
                if attrs and attrs[0] in set(pad_instances) | set(pca_instances):
                    matching.append(excluded_id)
            put('AttrPicklistExcludedValue', 'Id', matching)
        categories = await ids('ProductCategoryProduct', 'ProductCategoryId', ('ProductId', selected))
        category_frontier = categories
        while category_frontier:
            parents = await optional_ids('ProductCategory', 'ParentCategoryId', ('Id', category_frontier))
            new_parents = sorted(set(parents) - set(categories))
            if len(categories) + len(new_parents) > _MAX_EXPANDED:
                raise ValueError('Category hierarchy exceeds limit')
            categories = sorted(set(categories) | set(new_parents))
            category_frontier = new_parents
        put('ProductCategory', 'Id', categories)
        put('ProductCategoryDataTranslation', 'ParentId', categories)
        catalogs = await optional_ids('ProductCategory', 'CatalogId', ('Id', categories)) if categories else []
        put('ProductCatalog', 'Id', catalogs)
        pricebooks = await refs('PricebookEntry', 'Pricebook2Id', 'Product2Id', selected, 'Pricebook2')
        costbooks = list(await refs('CostBookEntry', 'CostBookId', 'ProductId', selected, 'CostBook') or [])
        # Pricebook2 itself may reference a CostBook that has no CostBookEntry for
        # the selected products — include those to avoid unmapped scoped lookup errors.
        if pricebooks:
            pb_costbooks = await checked_refs('Pricebook2', 'CostBookId', pricebooks, 'CostBook')
            if pb_costbooks:
                costbooks = sorted(set(costbooks) | set(pb_costbooks))
                put('CostBook', 'Id', costbooks)
        models = await refs('ProductSellingModelOption', 'ProductSellingModelId', 'Product2Id', selected, 'ProductSellingModel')
        ramps = await ids('ProductRampSegment', 'Id', ('ProductId', selected))
        if ramps:
            models = sorted(set(models) | set(await checked_refs('ProductRampSegment', 'ProductSellingModelId', ramps, 'ProductSellingModel')))
        if component_ids:
            for field in ('ChildSellingModelId', 'ParentSellingModelId'):
                models = sorted(set(models) | set(await checked_refs('ProductRelatedComponent', field, component_ids, 'ProductSellingModel')))
        put('ProductSellingModel', 'Id', models)
        policies = await ids('ProductSellingModelOption', 'ProrationPolicyId', ('Product2Id', selected))
        put('ProrationPolicy', 'Id', policies)
        specs = []
        if 'ProductSpecificationType' in available:
            product_fields = {f['name'] for f in (await sf.describe_object('Product2')).get('fields', [])}
            if 'ProductSpecificationTypeId' in product_fields:
                specs = await ids('Product2', 'ProductSpecificationTypeId', ('Id', selected))
        put('ProductSpecificationType', 'Id', specs)
        put('ProductSpecificationRecType', 'ProductSpecificationTypeId', specs)
        # Parallel: all UOM FK lookups are independent — gather the ones that apply
        async def _empty():
            return []
        _uom_coros = [
            optional_ids('Product2', 'UnitOfMeasureId', ('Id', selected)),
            optional_ids('AttributeDefinition', 'UnitOfMeasureId', ('Id', definitions)) if definitions else _empty(),
            checked_refs('ProductClassificationAttr', 'UnitOfMeasureId', pca_instances, 'UnitOfMeasure') if pca_instances else _empty(),
            optional_ids('ProductAttributeDefinition', 'UnitOfMeasureId', ('Product2Id', selected)) if selected else _empty(),
            checked_refs('ProductRelatedComponent', 'UnitOfMeasureId', component_ids, 'UnitOfMeasure') if component_ids else _empty(),
            optional_ids('AttributePicklist', 'UnitOfMeasureId', ('Id', picks)) if picks else _empty(),
        ]
        uoms = [u for batch in await asyncio.gather(*_uom_coros) for u in batch]
        classes = await optional_ids('UnitOfMeasure', 'UnitOfMeasureClassId', ('Id', uoms)) if uoms else []
        for field in ('BaseUnitOfMeasureId', 'DefaultUnitOfMeasureId'):
            if classes:
                uoms += await optional_ids('UnitOfMeasureClass', field, ('Id', classes))
        put('UnitOfMeasure', 'Id', uoms)
        if uoms and 'UnitOfMeasure' not in available:
            raise ValueError('UnitOfMeasure required by selected products is absent')
        classes = sorted(set(classes) | set(await optional_ids('UnitOfMeasure', 'UnitOfMeasureClassId', ('Id', uoms)))) if uoms else []
        put('UnitOfMeasureClass', 'Id', classes)
        relationships = await checked_refs('ProductRelatedComponent', 'ProductRelationshipTypeId', component_ids, 'ProductRelationshipType')
        put('ProductRelationshipType', 'Id', relationships)
        # Optional schema can be absent, but every present bundle object must be explicitly scoped.
        # Every nonempty scoped relationship must retain its source parent.
        for obj, field, parents in (('ProductClassification', 'Id', pc),
                                     ('AttributeDefinition', 'Id', definitions),
                                     ('ProductCategory', 'Id', categories),
                                     ('ProductCatalog', 'Id', catalogs),
                                     ('Pricebook2', 'Id', await ids('PricebookEntry', 'Pricebook2Id', ('Product2Id', selected))),
                                     ('ProductRelationshipType', 'Id', relationships)):
            if parents and obj not in available:
                raise ValueError(f'Required source parent {obj} unavailable')
            if parents and set(await ids(obj, field, ('Id', parents))) != set(parents):
                raise ValueError(f'Missing source parent records in {obj}')
        return {'filters': filters, 'product_count': len(selected), 'counts_available': False,
                'debug': {'pids_original': len(product_ids), 'pids_expanded': len(selected), 'objects_scoped': sorted(filters)}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f'Product scope discovery failed: {exc}') from exc

@router.post("/scope-filters")
async def compute_scope_filters(request: Request, body: ScopeFiltersPayload):
    token, instance_url = _require_auth(request)
    return await build_product_scope(SalesforceClient(token, instance_url), body.product_ids)


# ──────────────────────────────────────────────────────────────────────────────
# POST /migrate/validate-target  — verify target org credentials
# ──────────────────────────────────────────────────────────────────────────────
class ValidateTargetPayload(BaseModel):
    username: str
    password: str
    domain: str = "login.salesforce.com"


@router.post("/validate-target")
async def validate_target(body: ValidateTargetPayload):
    if not body.username.strip() or not body.password:
        raise HTTPException(status_code=400, detail="username and password are required")
    try:
        tokens = await login_with_credentials(body.username.strip(), body.password, body.domain)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"valid": True, "instance_url": tokens["instance_url"], "org_name": tokens.get("org_name", ""), "access_token": tokens["access_token"]}


# ──────────────────────────────────────────────────────────────────────────────
# POST /migrate/dependency-order
# ──────────────────────────────────────────────────────────────────────────────
class DependencyOrderPayload(BaseModel):
    selected_objects: list[str]


@router.post("/dependency-order")
async def dependency_order(body: DependencyOrderPayload):
    requested = set(body.selected_objects)

    # Expand: auto-include any transitive dependencies that are known in
    # OBJECT_DEPS but were not explicitly selected.  Without this, child
    # objects arrive before their parents have been migrated, leaving all
    # their lookup fields unresolved.
    expanded: set[str] = set(requested)
    frontier = list(requested)
    while frontier:
        obj = frontier.pop()
        for dep in OBJECT_DEPS.get(obj, []):
            if dep not in expanded:
                expanded.add(dep)
                frontier.append(dep)

    auto_added = sorted(expanded - requested)

    # Build dependency graph over the expanded set
    graph: dict[str, list[str]] = {
        obj: [d for d in OBJECT_DEPS.get(obj, []) if d in expanded]
        for obj in expanded
    }

    # Compute in-degree correctly
    in_degree = {n: 0 for n in expanded}
    for node, deps in graph.items():
        in_degree[node] = len(deps)

    # Kahn's topological sort
    queue = sorted([n for n, d in in_degree.items() if d == 0])
    order: list[str] = []
    visited: set[str] = set()

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        for candidate in sorted(expanded - visited):
            remaining = [d for d in graph.get(candidate, []) if d not in visited]
            if not remaining and candidate not in queue:
                queue.append(candidate)

    order += sorted(expanded - visited)
    return {"order": order, "auto_added": auto_added}


# ──────────────────────────────────────────────────────────────────────────────
# POST /migrate/start  — launch a migration job
# ──────────────────────────────────────────────────────────────────────────────
class StartMigrationPayload(BaseModel):
    target_access_token: str
    target_instance_url: str
    selected_objects: list[str]
    mode: str = "upsert"    # upsert | insert
    object_filters: dict[str, str] = {}  # object_name → WHERE clause
    product_ids: Optional[list[str]] = None
    dry_run: bool = False           # validate-only; no records written to target
    failure_threshold_pct: int = 0  # abort when failed% exceeds this (0 = fail on any error)


@router.post("/start")
async def start_migration(request: Request, body: StartMigrationPayload):
    source_token, source_url = _require_auth(request)
    target_token = unquote(body.target_access_token.strip())
    target_url = _target_origin(body.target_instance_url)

    if body.mode not in ("upsert", "insert"):
        raise HTTPException(status_code=400, detail="mode must be 'upsert' or 'insert'")
    if not body.selected_objects:
        raise HTTPException(status_code=400, detail="No objects selected")
    # Resolve dependency order (auto-expands to include transitive deps)
    dep_resp = await dependency_order(DependencyOrderPayload(selected_objects=body.selected_objects))
    dep_order   = dep_resp["order"]
    auto_added  = dep_resp.get("auto_added", [])

    filters = body.object_filters
    if body.product_ids is not None:
        if any(obj not in PRODUCT_BUNDLE_OBJECTS for obj in dep_order):
            raise HTTPException(status_code=400, detail="product_ids only support product bundle objects")
        scope = await build_product_scope(SalesforceClient(source_token, source_url), body.product_ids)
        associated = {'ProductComponentGroup', 'ProductRelatedComponent', 'ProductComponentGrpOverride'}
        discovered = associated.intersection(scope['filters']) - set(dep_order)
        if discovered:
            dep_resp = await dependency_order(DependencyOrderPayload(selected_objects=dep_order + sorted(discovered)))
            dep_order = dep_resp['order']
            auto_added = sorted(set(dep_order) - set(body.selected_objects))
        unavailable = set(dep_order) - set(scope['filters'])
        if unavailable.intersection(body.selected_objects):
            raise HTTPException(status_code=400, detail=f"Source objects unavailable: {sorted(unavailable.intersection(body.selected_objects))}")
        if 'Product2' not in dep_order:
            raise HTTPException(status_code=400, detail='Product2 is required for product scoped jobs')
        dep_order = [obj for obj in dep_order if obj not in unavailable]
        auto_added = [obj for obj in auto_added if obj not in unavailable]
        filters = {obj: scope['filters'][obj] for obj in dep_order}

    job_id = str(uuid.uuid4())
    owner = request.session.get("migration_owner_id")
    if not owner:
        owner = uuid.uuid4().hex
        request.session["migration_owner_id"] = owner
    job = MigrationJob(
        job_id=job_id,
        source_url=source_url,
        target_url=target_url,
        migration_owner_id=owner,
        mode=body.mode,
        selected_objects=body.selected_objects,
        dep_order=dep_order,
        object_filters=filters,
        product_scoped=body.product_ids is not None,
        dry_run=body.dry_run,
        failure_threshold_pct=body.failure_threshold_pct,
    )
    set_job(job)
    set_progress(job_id, 0, "Starting migration engine…")

    asyncio.create_task(_run_migration(job, source_token, target_token))
    return {"job_id": job_id, "dep_order": dep_order, "auto_added": auto_added}


async def _run_migration(job: MigrationJob, source_token: str, target_token: str):
    engine = MigrationEngine(
        source_token=source_token,
        source_url=job.source_url,
        target_token=target_token,
        target_url=job.target_url,
        job=job,
    )
    await engine.run()


# ──────────────────────────────────────────────────────────────────────────────
# GET /migrate/validate/{job_id}  — summary for dry-run jobs
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/validate/{job_id}")
async def validate_summary(job_id: str, request: Request):
    _require_job(request, job_id)
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.dry_run:
        raise HTTPException(status_code=400, detail="Not a dry-run job")
    summary = []
    for obj_name in job.dep_order:
        r = job.object_results.get(obj_name)
        if r:
            summary.append({
                "object_name": r.object_name,
                "status": r.status,
                "queried": r.queried,
                "would_write": r.skipped_dry_run,
                "error": r.error,
            })
    return {
        "job_id": job_id,
        "status": job.status,
        "dry_run": True,
        "total_would_write": sum(s["would_write"] for s in summary),
        "objects": summary,
    }


# ──────────────────────────────────────────────────────────────────────────────
# GET /migrate/stream/{job_id}  — SSE progress stream
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/stream/{job_id}")
async def stream_progress(job_id: str, request: Request):
    _require_job(request, job_id)
    async def event_generator():
        last_hash = ""
        last_log_idx = 0
        for _ in range(43200):          # max 12 hours
            await asyncio.sleep(0.5)
            progress = _job_progress.get(job_id, {})
            status = progress.get("status", "running")

            new_lines, last_log_idx = get_log_delta(job_id, last_log_idx)

            current_json = json.dumps({**progress, "log_count": last_log_idx}, default=str)
            h = str(hash(current_json))

            if h != last_hash or new_lines:
                last_hash = h
                payload = {**progress, "log_lines_delta": new_lines}
                yield f"data: {json.dumps(payload, default=str)}\n\n"

            if status in ("completed", "failed", "rolled_back", "stopped"):
                # Flush any remaining log lines one last time
                final_lines, _ = get_log_delta(job_id, last_log_idx)
                if final_lines:
                    payload = {**progress, "log_lines_delta": final_lines}
                    yield f"data: {json.dumps(payload, default=str)}\n\n"
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ──────────────────────────────────────────────────────────────────────────────
# GET /migrate/log/{job_id}  — download per-job log file
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/log/{job_id}")
async def download_log(job_id: str, request: Request):
    _require_job(request, job_id)
    import os
    from pathlib import Path
    from fastapi.responses import FileResponse
    log_path = Path(os.path.expanduser(f"~/.sf-scanner/logs/migration_{job_id}.log"))
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found for this job")
    return FileResponse(str(log_path), media_type="text/plain", filename=log_path.name)


# ──────────────────────────────────────────────────────────────────────────────
# GET /migrate/result/{job_id}  — final job summary
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/result/{job_id}")
async def get_result(job_id: str, request: Request):
    job = _require_job(request, job_id)
    return {
        "job_id": job.job_id,
        "status": job.status,
        "source_url": job.source_url,
        "target_url": job.target_url,
        "mode": job.mode,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "dep_order": job.dep_order,
        "total_queried": job.total_queried,
        "total_inserted": job.total_inserted,
        "rollback_remaining": sum(len(r.inserted_ids) for r in job.object_results.values()),
        "total_updated": job.total_updated,
        "total_failed": job.total_failed,
        "error": job.error,
        "log_path": job.log_path,
        "object_results": {
            k: {
                "object_name": v.object_name, "status": v.status,
                "queried": v.queried, "inserted": v.inserted,
                "updated": v.updated, "failed": v.failed, "error": v.error,
            }
            for k, v in job.object_results.items()
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# GET /migrate/jobs  — list all jobs (most recent first)
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/jobs")
async def list_jobs(request: Request):
    _, source_url = _require_auth(request)
    owner = request.session.get("migration_owner_id")
    jobs = sorted((j for j in _jobs.values() if owner and j.migration_owner_id == owner
                   and j.source_url == source_url), key=lambda j: j.started_at, reverse=True)
    return [
        {
            "job_id": j.job_id, "status": j.status,
            "source_url": j.source_url, "target_url": j.target_url,
            "mode": j.mode, "started_at": j.started_at, "completed_at": j.completed_at,
            "total_inserted": j.total_inserted, "total_updated": j.total_updated,
            "total_failed": j.total_failed, "objects": j.dep_order,
        }
        for j in jobs
    ]


# ──────────────────────────────────────────────────────────────────────────────
# POST /migrate/rollback/{job_id}  — delete all records inserted in a job
# ──────────────────────────────────────────────────────────────────────────────
class RollbackPayload(BaseModel):
    target_access_token: str
    target_instance_url: str


@router.post("/rollback/{job_id}")
async def rollback(job_id: str, body: RollbackPayload, request: Request):
    job = _require_job(request, job_id)
    if job.status not in ("completed", "failed", "stopped"):
        raise HTTPException(status_code=400, detail="Job must be completed, failed, or stopped to rollback")
    if not any(r.inserted_ids for r in job.object_results.values()):
        raise HTTPException(status_code=400, detail="No tracked inserted records remain to rollback")

    target_token = unquote(body.target_access_token.strip())
    target_url = _target_origin(body.target_instance_url)
    if target_url != job.target_url:
        raise HTTPException(status_code=400, detail="Rollback target must match the original migration target")

    job.status = "rolling_back"
    set_job(job)
    set_progress(job_id, 0, "Rolling back inserted records…", status="rolling_back")

    asyncio.create_task(_run_rollback(job, target_token, target_url))
    return {"status": "rolling_back", "job_id": job_id}


async def _run_rollback(job: MigrationJob, target_token: str, target_url: str):
    try:
        await rollback_job(job, target_token, target_url)
        if any(r.inserted_ids for r in job.object_results.values()):
            raise RuntimeError("Tracked inserted records remain after rollback")
        job.status = "rolled_back"
        job.error = ""
        set_job(job)
        set_progress(job.job_id, 100, "Rollback complete", status="rolled_back")
    except Exception as e:
        job.status = "failed"
        job.error = f"Rollback failed: {e}"
        set_job(job)
        set_progress(job.job_id, 0, f"Rollback failed: {e}", status="failed")


# ──────────────────────────────────────────────────────────────────────────────
# POST /migrate/stop/{job_id}  — request graceful stop of a running migration
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/stop/{job_id}")
async def stop_migration(job_id: str, request: Request):
    job = _require_job(request, job_id)
    if not cancel_job(job_id):
        raise HTTPException(status_code=400, detail=f"Job is not running (status: {job.status})")
    return {"status": "stopping", "job_id": job_id}
