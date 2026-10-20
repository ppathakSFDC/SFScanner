"""
Migration engine: orchestrates the full source → target data move.

Per-object flow:
  1. describe() both orgs → smart key strategy
  2. SOQL query_all()    → paginated source records
  3. clean_records()     → strip audit fields, resolve lookup IDs
  4. Bulk API 2.0 upsert / insert → target org
  5. Build ID map         → for child object lookup resolution
  6. Collect results      → inserted, updated, failed counts
  7. Two-pass self-loops  → update circular lookups (e.g. Account.ParentId)
"""

from __future__ import annotations

import asyncio
import re
import httpx
from datetime import datetime, timezone
from typing import Optional

from ..salesforce.client import SalesforceClient
from .bulk_api import BulkAPI2, records_to_csv, chunk_records
from .smart_key import describe_object, get_upsert_strategy, find_bulk_ext_id
from .rate_limiter import RateLimiter
from .job_store import MigrationJob, ObjectMigrationResult, set_job, set_progress, append_log
from .migration_logger import MigrationLogger
from .object_groups import PRODUCT_BUNDLE_OBJECTS

# Objects that can't be moved via Bulk API upsert — skip with a clear message
_UNSUPPORTED_OBJECTS = frozenset({
    "ContentDocument", "ContentVersion", "ContentBody",
    "Attachment", "ContentDocumentLink",
})

_ORG_LOCAL_REFS = frozenset({'OwnerId', 'CreatedById', 'LastModifiedById'})
_DEFERRED_UOM_CLASS_REFS = ('BaseUnitOfMeasureId', 'DefaultUnitOfMeasureId')

# Objects with composite unique constraints that may already exist on the target org.
# Pre-query the target and map source IDs → target IDs without inserting duplicates.
_COMPOSITE_KEY_OBJECTS: dict[str, list[str]] = {
    'ProductRelationshipType': ['MainProductRoleCat', 'AssociatedProductRoleCat'],
    # Junction objects whose composite key is FK-based (source IDs ≠ target IDs).
    # Pass cleaned records to _composite_key_preflight so remapped target IDs are used.
    'AttributeCategoryAttribute': ['AttributeDefinitionId', 'AttributeCategoryId'],
    'PricebookEntry': ['Pricebook2Id', 'Product2Id'],
    # ProductSellingModel: Salesforce enforces uniqueness on (SellingModelType, PricingTerm,
    # PricingTermUnit) regardless of Name — plain name-based upsert causes DUPLICATE_VALUE.
    'ProductSellingModel': ['SellingModelType', 'PricingTerm', 'PricingTermUnit'],
    # AttributePicklist / AttributeDefinition: Code is a unique field independent of Name.
    # A target record with same Code but different Name causes DUPLICATE_VALUE on insert.
    'AttributePicklist': ['Code'],
    'AttributeDefinition': ['Code'],
    # ProductClassificationAttr: junction between ProductClassification and AttributeDefinition.
    # Salesforce rejects INVALID_INPUT when the same attribute is already in the classification
    # hierarchy, and also when the SequenceNumber is already in use.  Both errors fire for the
    # same already-existing records, so the composite-key preflight skips them entirely.
    'ProductClassificationAttr': ['ProductClassificationId', 'AttributeDefinitionId'],
    # NOTE: AttributePicklistValue is handled via _NATURAL_KEYS 'Code' (natural-key upsert)
    # rather than composite-key preflight, because AttributePicklistId is non-queryable
    # in SOQL on the target org, causing the preflight SELECT to return 400.
}

# Objects whose _COMPOSITE_KEY_OBJECTS fields are FK-based (need cleaned/remapped records).
_FK_COMPOSITE_KEY_OBJECTS = frozenset({
    'AttributeCategoryAttribute', 'PricebookEntry', 'ProductClassificationAttr',
})

# Regex to extract the conflicting record ID from a Salesforce DUPLICATE_VALUE error message.
_DUP_RECORD_RE = re.compile(r'record with id:\s*(\w+)', re.IGNORECASE)


class MigrationEngine:
    def __init__(
        self,
        source_token: str, source_url: str,
        target_token: str, target_url: str,
        job: MigrationJob,
    ):
        self.source = SalesforceClient(source_token, source_url)
        self.source_token = source_token
        self.source_url = source_url
        self.target_token = target_token
        self.target_url = target_url
        self.target_bulk = BulkAPI2(target_token, target_url, log_fn=self._emit)
        self.job = job
        self.rl_source = RateLimiter(80)
        self.rl_target = RateLimiter(80)

        # ID mapping: {object_name: {source_record_id: target_record_id}}
        self._object_filters: dict[str, str] = job.object_filters or {}
        self._product_scoped = job.product_scoped
        self._id_map: dict[str, dict[str, str]] = {}
        # Key map: {object_name: {key_value: target_record_id}}
        self._key_map: dict[str, dict[str, str]] = {}
        self._preflight_ids: dict[str, set[str]] = {}
        self._category_preflight: dict[str, tuple[str, str]] | None = None
        # Source records cache for self-lookup second pass
        self._source_records: dict[str, list[dict]] = {}
        # Upsert strategies per object (instance variable — not shared across jobs)
        self._strategies: dict = {}
        self._create_only_self_order: dict[str, list[str]] = {}
        # Count of lookup IDs that could not be resolved (reset per object)
        self._unresolved_lookups: int = 0
        self._log: MigrationLogger | None = None

    def _emit(self, line: str):
        append_log(self.job.job_id, line)

    def _update(self, pct: int, msg: str, status: str = "running"):
        self.job.progress_pct = pct
        self.job.message = msg
        self.job.status = status
        set_progress(
            self.job.job_id, pct, msg, status,
            current_object=self.job.current_object,
            object_results=self.job.object_results,
        )
        set_job(self.job)

    # ──────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────────────────────
    async def run(self):
        try:
            self._log = MigrationLogger(self.job.job_id)
            self.job.log_path = str(self._log.path)

            # Header
            self._emit(f"--- Migration Job Started ---")
            self._emit(f"  Job ID : {self.job.job_id}")
            self._emit(f"  Source : {self.job.source_url}")
            self._emit(f"  Target : {self.job.target_url}")
            self._emit(f"  Mode   : {self.job.mode}")
            self._emit(f"  Objects: {len(self.job.dep_order)}")
            self._emit("")

            # Pre-flight: verify target connectivity and filter unavailable objects
            self._emit("🔎 Verifying target environment permissions...")
            await self._preflight_check()
            if self._product_scoped:
                await self._preflight_product_references()
            dep_order = self.job.dep_order  # may be trimmed by preflight
            total = len(dep_order)
            self._emit(f"✅ Target org verified. {total} object(s) to process.")
            self._emit("")
            self._emit("==================================")
            self._emit("🚀 STARTING MIGRATION PROCESS")
            self._emit("==================================")
            self._emit("")

            for i, obj_name in enumerate(dep_order):
                if self.job.cancelled:
                    self._emit("")
                    self._emit("⛔ Migration stopped by user.")
                    self.job.completed_at = datetime.now(timezone.utc).isoformat()
                    self._update(self.job.progress_pct, "Stopped by user.", status="stopped")
                    if self._log:
                        self._log.close("stopped")
                    return
                base_pct = int(i / total * 88)
                self.job.current_object = obj_name
                self._update(base_pct, f"Migrating {obj_name}…")
                await self._migrate_object(obj_name, base_pct, total)
                outcome = self.job.object_results.get(obj_name)
                if outcome and outcome.status == 'failed':
                    raise RuntimeError(f'{obj_name} failed: {outcome.error or outcome.failed}')
                # done_with_errors is only fatal when failure_threshold_pct == 0
                if outcome and outcome.status == 'done_with_errors' and self.job.failure_threshold_pct == 0:
                    raise RuntimeError(f'{obj_name} had errors: {outcome.error}')

            # Second pass: resolve self-referential lookups (e.g. Account.ParentId)
            for obj_name in dep_order:
                strategy = self._strategies.get(obj_name, {})
                if strategy.get("self_lookups") and obj_name not in self._create_only_self_order:
                    self._update(90, f"Resolving self-lookups on {obj_name}…")
                    self._emit(f"↻  Resolving self-referential lookups on {obj_name}...")
                    await self._second_pass_self_lookups(obj_name, strategy)

            # Final summary
            self._emit("")
            self._emit("==================================")
            self._emit("🎉 MIGRATION FINISHED")
            self._emit("==================================")
            self._emit("")
            self._emit("--- Final Summary ---")
            self._emit(f" {'SObject':<36} {'Created':>7} {'Updated':>7} {'Failed':>7}")
            self._emit(f" {'─' * 36} {'─' * 7} {'─' * 7} {'─' * 7}")
            for obj_name in dep_order:
                r = self.job.object_results.get(obj_name)
                if r:
                    self._emit(f" {obj_name:<36} {r.inserted:>7} {r.updated:>7} {r.failed:>7}")
            self._emit("")

            self.job.completed_at = datetime.now(timezone.utc).isoformat()
            if any(r.status in ('failed', 'done_with_errors') for r in self.job.object_results.values()):
                raise RuntimeError('One or more objects failed migration')
            self._update(100, "Migration complete!", status="completed")
            if self._log:
                self._log.close("completed")

        except Exception as e:
            self.job.error = str(e)
            self.job.completed_at = datetime.now(timezone.utc).isoformat()
            self._emit(f"")
            self._emit(f"❌ MIGRATION FAILED: {e}")
            self._update(self.job.progress_pct, f"Migration failed: {e}", status="failed")
            if self._log:
                self._log.error(f"MIGRATION_EXCEPTION error={str(e)!r}")
                self._log.close("failed")

    async def _preflight_check(self):
        """Verify target org connectivity; mark objects missing on target as skipped."""
        self._update(0, "Pre-flight: verifying target org…")
        if self._product_scoped:
            if 'Product2' not in self.job.dep_order:
                raise ValueError('Product2 is required for product scoped migration')
            for obj in self.job.dep_order:
                self._scope_where(obj)
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                resp = await client.get(
                    f"{self.target_url}/services/data/v62.0/sobjects/",
                    headers={"Authorization": f"Bearer {self.target_token}"},
                )
            if resp.status_code == 401:
                raise RuntimeError(
                    "Target org authentication failed — token expired or invalid. "
                    "Re-authenticate and restart."
                )
            resp.raise_for_status()
            if resp.status_code == 200:
                target_names = {s["name"] for s in resp.json().get("sobjects", [])}
                dep_order = self.job.dep_order
                missing = [o for o in dep_order if o not in target_names]
                if missing:
                    required = [o for o in missing if self._product_scoped]
                    if required:
                        raise RuntimeError(f"Required target objects unavailable: {', '.join(required)}")
                    for obj in missing:
                        self.job.object_results[obj] = ObjectMigrationResult(
                            object_name=obj, status="skipped",
                            error="Object does not exist on target org",
                        )
                    self.job.dep_order = [o for o in dep_order if o in target_names]
                    self.job.message = (
                        f"Pre-flight: {len(missing)} object(s) not in target org "
                        f"(skipped): {', '.join(missing[:5])}"
                    )
        except RuntimeError:
            raise
        except Exception:
            raise

    def _scope_where(self, obj_name: str) -> str:
        where = self._object_filters.get(obj_name, '').strip()
        if self._product_scoped and not where:
            raise ValueError(f'Missing product scope for {obj_name}')
        return where

    def _scoped_strategy(self, desc: dict, obj: str) -> dict:
        strategy = get_upsert_strategy(desc, obj)
        for key in ('creatable_fields', 'queryable_fields'):
            strategy[key] = [name for name in strategy[key] if name not in _ORG_LOCAL_REFS]
        for name in _ORG_LOCAL_REFS:
            strategy['lookup_fields'].pop(name, None)
            if name in strategy['self_lookups']:
                strategy['self_lookups'].remove(name)
        if self._product_scoped:
            if obj == 'UnitOfMeasureClass':
                for name in _DEFERRED_UOM_CLASS_REFS:
                    if name in strategy['lookup_fields']:
                        strategy['lookup_fields'].pop(name)
                        strategy['self_lookups'].append(name)
        return strategy

    def _category_upsert(self, obj: str) -> bool:
        return obj == 'AttributeCategory' and (self.job.mode == 'upsert' or self._product_scoped)

    @staticmethod
    def _category_pairs(rows: list[dict]) -> dict[str, tuple[str, str]]:
        pairs = {}
        names, codes = set(), set()
        for row in rows:
            name, code = (str(row.get(field) or '') for field in ('Name', 'Code'))
            if not name.strip() or not code.strip():
                raise ValueError('Missing AttributeCategory Name or Code')
            if name.casefold() in names or code.casefold() in codes:
                raise ValueError('Duplicate source AttributeCategory Name or Code')
            if row['Id'] in pairs:
                raise ValueError('Duplicate source AttributeCategory Id')
            names.add(name.casefold())
            codes.add(code.casefold())
            pairs[row['Id']] = (name, code)
        return pairs

    async def _category_candidates(self, pairs: dict[str, tuple[str, str]]) -> dict[tuple[str, str], str]:
        names = list(dict.fromkeys(pair[0] for pair in pairs.values()))
        codes = list(dict.fromkeys(pair[1] for pair in pairs.values()))
        found: dict[tuple[str, str], str] = {}
        wanted_pairs = set(pairs.values())
        def quoted(values):
            return ', '.join("'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'" for value in values)
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            for field, values in (('Name', names), ('Code', codes)):
                for i in range(0, len(values), 500):
                    soql = f'SELECT Id, Name, Code FROM AttributeCategory WHERE {field} IN ({quoted(values[i:i + 500])})'
                    await self.rl_target.acquire()
                    resp = await client.get(f'{self.target_url}/services/data/v62.0/query',
                                            params={'q': soql}, headers={'Authorization': f'Bearer {self.target_token}'})
                    resp.raise_for_status()
                    page = resp.json()
                    while True:
                        for row in page.get('records', []):
                            name, code = row.get('Name'), row.get('Code')
                            if (name, code) not in wanted_pairs:
                                raise ValueError('AttributeCategory one-sided collision on target')
                            previous = found.get((name, code))
                            if previous and previous != row['Id']:
                                raise ValueError('Ambiguous target AttributeCategory pair')
                            found[(name, code)] = row['Id']
                        if page.get('done', True):
                            break
                        url = page.get('nextRecordsUrl')
                        if not url:
                            raise ValueError('Incomplete target AttributeCategory pagination')
                        await self.rl_target.acquire()
                        resp = await client.get(f'{self.target_url}{url}', headers={'Authorization': f'Bearer {self.target_token}'})
                        resp.raise_for_status()
                        page = resp.json()
        return found

    async def _category_plan(self, rows: list[dict], desc: dict, target_desc: dict):
        pairs = self._category_pairs(rows)
        src_fields = {f['name']: f for f in desc.get('fields', [])}
        tgt_fields = {f['name']: f for f in target_desc.get('fields', [])}
        for field in ('Name', 'Code'):
            if (field not in src_fields or not src_fields[field].get('queryable', True)
                    or src_fields[field].get('encrypted', False) or field not in tgt_fields
                    or not tgt_fields[field].get('queryable', True) or tgt_fields[field].get('encrypted', False)):
                raise ValueError(f'AttributeCategory {field} is not available for matching')
        matches = await self._category_candidates(pairs) if pairs else {}
        strategy = self._scoped_strategy(desc, 'AttributeCategory')
        if (any(pairs[row['Id']] in matches and any(row.get(field) not in (None, '')
                 for field in strategy['queryable_fields'] if field not in ('Name', 'Code')) for row in rows)
                and not target_desc.get('updateable', False)):
            raise ValueError('Target AttributeCategory is not updateable')
        if any(pair not in matches for pair in pairs.values()) and not target_desc.get('createable', False):
            raise ValueError('Target AttributeCategory is not createable')
        unreadable = set(strategy['creatable_fields']) - set(strategy['queryable_fields'])
        if unreadable:
            raise ValueError(f'Cannot verify AttributeCategory source fields: {", ".join(sorted(unreadable))}')
        for field in ('Name', 'Code'):
            if field not in strategy['queryable_fields']:
                raise ValueError(f'AttributeCategory {field} is not writable on source')
        for row in rows:
            operation = 'updateable' if pairs[row['Id']] in matches else 'createable'
            for field in strategy['queryable_fields']:
                if field not in ('Name', 'Code') and row.get(field) not in (None, '') and not tgt_fields.get(field, {}).get(operation, False):
                    raise ValueError(f'Target AttributeCategory.{field} is not {operation}')
            for field in ('Name', 'Code'):
                if operation == 'createable' and not tgt_fields[field].get('createable', False):
                    raise ValueError(f'Target AttributeCategory.{field} is not createable')
        return pairs, matches

    async def _preflight_product_references(self):
        """Check scoped source lookup closure before any target Bulk job starts."""
        scoped_ids = {}
        metadata = {}
        target_metadata = {}
        target_createable = {}
        rows_by_object = {}
        references_by_object = {}
        for obj in self.job.dep_order:
            await self.rl_source.acquire()
            desc = await describe_object(self.source_token, self.source_url, obj)
            metadata[obj] = desc.get('fields', [])
            for field in metadata[obj]:
                if field['name'] in _ORG_LOCAL_REFS:
                    continue
                if (field.get('type') == 'reference' and field.get('createable', False)
                        and (not field.get('queryable', True) or field.get('encrypted', False))):
                    raise ValueError(f'Cannot verify scoped lookup {obj}.{field["name"]}')
            references = [f['name'] for f in metadata[obj]
                          if f['name'] not in _ORG_LOCAL_REFS and f.get('type') == 'reference'
                          and f.get('createable', False) and f.get('queryable', True)
                          and not f.get('encrypted', False)]
            references_by_object[obj] = references
            await self.rl_source.acquire()
            rows = await self._query_all(
                f"SELECT {', '.join(dict.fromkeys(['Id'] + references))} FROM {obj} WHERE {self._scope_where(obj)}"
            )
            rows_by_object[obj] = rows
            scoped_ids[obj] = {row['Id'] for row in rows}
            self._preflight_ids[obj] = scoped_ids[obj]
            if rows:
                if self._category_upsert(obj):
                    await self.rl_source.acquire()
                    select_fields = list(dict.fromkeys(['Id', 'Name', 'Code'] +
                        self._scoped_strategy(desc, obj)['queryable_fields']))
                    pair_rows = await self._query_all(
                        f'SELECT {", ".join(select_fields)} FROM {obj} WHERE {self._scope_where(obj)}')
                    if len(pair_rows) != len(rows) or {r['Id'] for r in pair_rows} != scoped_ids[obj]:
                        raise ValueError(f'Scoped source records changed for {obj} during preflight')
                    await self.rl_target.acquire()
                    target_desc = await describe_object(self.target_token, self.target_url, obj)
                    self._category_preflight, _ = await self._category_plan(pair_rows, desc, target_desc)
                key_field = get_upsert_strategy(desc, obj)['key_field']
                if not self._category_upsert(obj):
                    await self.rl_target.acquire()
                    target_desc = await describe_object(self.target_token, self.target_url, obj)
                target_createable[obj] = target_desc.get('createable', False)
                target_metadata[obj] = {f['name']: f for f in target_desc.get('fields', [])}
                if self._category_upsert(obj):
                    pass
                elif not key_field:
                    if self.job.mode != 'insert' and obj not in _COMPOSITE_KEY_OBJECTS:
                        raise ValueError(f'No mapping key for scoped {obj}; choose Insert Only')
                    if not target_desc.get('createable', False):
                        raise ValueError(f'Target {obj} is not createable for scoped insert')
                else:
                    if not any(f['name'] == key_field and f.get('queryable', True)
                               for f in target_desc.get('fields', [])):
                        raise ValueError(f'Missing target mapping key {obj}.{key_field}')
                    await self.rl_source.acquire()
                    keyed_rows = await self._query_all(
                        f'SELECT Id, {key_field} FROM {obj} WHERE {self._scope_where(obj)}'
                    )
                    keys = [str(row.get(key_field) or '') for row in keyed_rows]
                    if {row['Id'] for row in keyed_rows} != scoped_ids[obj] or len(keys) != len(rows):
                        raise ValueError(f'Scoped source records changed for {obj} during preflight')
                    if any(not key.strip() for key in keys) or len(set(keys)) != len(keys):
                        raise ValueError(f'Missing or duplicate source mapping key {obj}.{key_field}')
                    if self.job.mode == 'upsert':
                        tf = target_metadata[obj].get(key_field)
                        sf = next((f for f in metadata[obj] if f['name'] == key_field), {})
                        ext_id = key_field if (sf.get('externalId') and tf and tf.get('externalId')
                                               and tf.get('createable')) else find_bulk_ext_id(desc, target_desc)
                        if not ext_id:
                            append_log(self.job.job_id,
                                       f"⚠️  [{obj}] No common external ID — will fall back to insert "
                                       f"(natural key '{key_field}' cannot be used as Bulk API externalIdFieldName)")
                        else:
                            if ext_id == key_field:
                                ext_values = keys
                            else:
                                await self.rl_source.acquire()
                                ext_rows = await self._query_all(
                                    f'SELECT Id, {ext_id} FROM {obj} WHERE {self._scope_where(obj)}'
                                )
                                ext_values = [str(row.get(ext_id) or '') for row in ext_rows]
                                if ({row['Id'] for row in ext_rows} != scoped_ids[obj]
                                        or len(ext_values) != len(rows)):
                                    raise ValueError(f'Scoped source records changed for {obj} during preflight')
                            if any(not value.strip() for value in ext_values):
                                raise ValueError(f'Missing external ID {obj}.{ext_id} for scoped upsert')
                            if len(set(ext_values)) != len(ext_values):
                                raise ValueError(f'Duplicate external ID {obj}.{ext_id} for scoped upsert')

        for obj, rows in rows_by_object.items():
            self._create_only_self_order.pop(obj, None)
            self_fields = [f['name'] for f in metadata[obj] if f['name'] in references_by_object[obj]
                           and f.get('referenceTo') == [obj]]
            links = {row['Id']: [row[name] for name in self_fields if row.get(name)] for row in rows}
            order = []
            def visit(current, path, visited):
                if current in path:
                    raise ValueError(f'Unsupported scoped {obj} self-reference cycle')
                if current in visited:
                    return
                path.add(current)
                for parent in links.get(current, []):
                    visit(parent, path, visited)
                path.remove(current)
                visited.add(current)
                order.append(current)
            visited = set()
            for origin in links:
                visit(origin, set(), visited)
            create_only = set()
            for field in metadata[obj]:
                if field['name'] not in references_by_object[obj]:
                    continue
                name = field['name']
                for row in rows:
                    value = row.get(name)
                    if not value:
                        if not field.get('nillable', True):
                            raise ValueError(f'Missing required scoped lookup {obj}.{name} on {row["Id"]}')
                        continue
                    parents = field.get('referenceTo', [])
                    if not field.get('createable', False) or not parents:
                        raise ValueError(f'Unsupported scoped reference {obj}.{name} on {row["Id"]}')
                    if parents == [obj]:
                        target_field = target_metadata[obj].get(name, {})
                        if (target_field.get('type') != 'reference'
                                or obj not in target_field.get('referenceTo', [])):
                            raise ValueError(f'Target cannot map scoped self-reference {obj}.{name} on {row["Id"]}')
                        if not target_field.get('updateable', False):
                            if not target_field.get('createable', False):
                                raise ValueError(f'Target cannot create scoped self-reference {obj}.{name} on {row["Id"]}')
                            if self.job.mode != 'insert':
                                raise ValueError(f'Create-only scoped self-reference {obj}.{name} requires Insert Only')
                            create_only.add(name)
                        if value not in scoped_ids[obj]:
                            raise ValueError(f'Unmapped scoped lookup {obj}.{name}={value} on {row["Id"]}')
                        continue
                    if obj == 'UnitOfMeasureClass' and name in _DEFERRED_UOM_CLASS_REFS:
                        target_field = target_metadata[obj].get(name, {})
                        if (not target_field.get('updateable', target_field.get('createable', False))
                                or target_field.get('type') != 'reference'
                                or 'UnitOfMeasure' not in target_field.get('referenceTo', [])):
                            raise ValueError(f'Target cannot map scoped reference {obj}.{name} on {row["Id"]}')
                        if not any(value in scoped_ids.get(parent, set()) for parent in parents):
                            raise ValueError(f'Unmapped scoped lookup {obj}.{name}={value} on {row["Id"]}')
                        continue
                    target_field = target_metadata[obj].get(name, {})
                    if (not target_field.get('createable', False) or target_field.get('type') != 'reference'
                            or not set(parents).intersection(target_field.get('referenceTo', []))):
                        raise ValueError(f'Target cannot map scoped reference {obj}.{name} on {row["Id"]}')
                    if not any(value in scoped_ids.get(parent, set()) for parent in parents):
                        raise ValueError(f'Unmapped scoped lookup {obj}.{name}={value} on {row["Id"]}')
            if create_only:
                if not target_createable[obj] or not all(target_metadata[obj].get(name, {}).get('createable', False)
                                                        for name in self_fields):
                    raise ValueError(f'Target cannot create all scoped self-references on {obj}')
                self._create_only_self_order[obj] = order

    # ──────────────────────────────────────────────────────────────────────────
    # Migrate a single object
    # ──────────────────────────────────────────────────────────────────────────
    async def _migrate_object(self, obj_name: str, base_pct: int, total_objects: int):
        result = ObjectMigrationResult(object_name=obj_name, status="running")
        self.job.object_results[obj_name] = result
        tracked_inserts = 0
        self._unresolved_lookups = 0  # reset per-object counter

        self._emit(f"---===================================================---")
        self._emit(f"        Processing SObject: {obj_name}")
        self._emit(f"---===================================================---")
        self._emit("")

        # Skip objects that require special file-migration APIs
        if obj_name in _UNSUPPORTED_OBJECTS:
            result.status = "skipped"
            result.error = (
                f"{obj_name} requires file-specific migration (Bulk API upsert not supported). "
                "Use Salesforce Data Loader or the ContentVersion REST API for files/attachments."
            )
            self.job.object_results[obj_name] = result
            self._emit(f"⚠️  {obj_name} skipped: {result.error}")
            self._emit("")
            return

        if self._log:
            self._log.object_start(obj_name)

        try:
            # 1. Describe source — get key_field (used for SOQL + ID-map) and creatable list
            await self.rl_source.acquire()
            desc = await describe_object(self.source_token, self.source_url, obj_name)
            strategy = self._scoped_strategy(desc, obj_name)
            self._strategies[obj_name] = strategy

            key_field   = strategy["key_field"]    # natural/external key for ID-map queries
            creatable   = strategy["creatable_fields"]
            queryable   = strategy.get("queryable_fields", creatable)  # for SELECT (excludes encrypted fields)
            lookup_flds = strategy["lookup_fields"]
            self_loops  = strategy["self_lookups"]
            keyless_insert = self._product_scoped and not key_field and obj_name not in _COMPOSITE_KEY_OBJECTS
            if keyless_insert or obj_name in self._create_only_self_order:
                if self.job.mode != 'insert':
                    raise ValueError(f'No mapping key for scoped {obj_name}; choose Insert Only')
                await self.rl_target.acquire()
                target_desc = await describe_object(self.target_token, self.target_url, obj_name)
                if not target_desc.get('createable', False):
                    raise ValueError(f'Target {obj_name} is not createable for scoped insert')
                target_creatable = {f['name'] for f in target_desc.get('fields', []) if f.get('createable')}
                if any(f not in target_creatable for f in lookup_flds):
                    raise ValueError(f'Target cannot map scoped reference on {obj_name}')
                creatable = [f for f in creatable if f in target_creatable]
                queryable = [f for f in queryable if f in target_creatable]

            # 2. Determine the Bulk API external-ID field (op_ext_id).
            #
            #    Salesforce Bulk API requires externalIdFieldName to be a field
            #    with externalId=True on the TARGET org.  Natural keys like Name
            #    are NOT valid for the Bulk API even though we use them for ID maps.
            #
            #    Strategy:
            #      a. If mode=upsert AND key_field has externalId=True on TARGET → use it.
            #      b. If mode=upsert AND key_field is only externalId on SOURCE   → try to
            #         find another common external ID on both orgs.
            #      c. If nothing qualifies → fail rather than silently insert duplicates.
            op_ext_id: Optional[str] = None
            if self.job.mode == "upsert" and not self._category_upsert(obj_name):
                await self.rl_target.acquire()
                target_desc = await describe_object(self.target_token, self.target_url, obj_name)
                tgt_fields  = {f["name"]: f for f in target_desc.get("fields", [])}

                if key_field:
                    tf = tgt_fields.get(key_field)
                    if tf and tf.get("externalId") and tf.get("createable"):
                        # Happy path: key_field is a valid external ID on both orgs
                        op_ext_id = key_field
                    else:
                        # key_field is not valid on target — search for any common ext-id
                        fallback = find_bulk_ext_id(desc, target_desc)
                        reason = (
                            "field not found on target" if tf is None
                            else "not marked externalId=True on target"
                        )
                        if fallback:
                            self._emit(
                                f"⚠️  [{obj_name}] '{key_field}' — {reason}. "
                                f"Using '{fallback}' for upsert (ID map still keyed on '{key_field}')"
                            )
                            op_ext_id = fallback
                        else:
                            self._emit(
                                f"ℹ️  [{obj_name}] No Bulk API externalId — will use natural-key upsert on '{key_field}'"
                            )

            # 2. Build SOQL field list (always include Id for ID mapping).
            #    Use queryable_fields (not all creatable) to avoid encrypted/non-queryable
            #    fields that cause Salesforce to return 400 Bad Request on GET queries.
            select_fields = list(dict.fromkeys(["Id"] + ([key_field] if key_field else []) +
                                               (['Name', 'Code'] if self._category_upsert(obj_name) else []) + queryable))
            soql = f"SELECT {', '.join(select_fields)} FROM {obj_name}"
            where = self._scope_where(obj_name)
            if where:
                soql += f" WHERE {where}"

            # 3. Query all records from source (paginated)
            self._emit(f"🔍 Deployment Started for {obj_name}")
            await self.rl_source.acquire()
            records = await self._query_all(soql)
            result.queried = len(records)
            if self._product_scoped and obj_name in self._preflight_ids:
                if ({row['Id'] for row in records} != self._preflight_ids[obj_name]
                        or len(records) != len(self._preflight_ids[obj_name])):
                    raise ValueError(f'Scoped source records changed for {obj_name} after preflight')
            self._source_records[obj_name] = records
            self._emit(f"📥 [{obj_name}]: fetched {len(records)} record(s)")

            if not records:
                if self._product_scoped and obj_name == 'Product2':
                    raise ValueError('Selected Product2 records are absent on source')
                result.status = "skipped"
                self.job.object_results[obj_name] = result
                self._emit(f"  -> No records found. Skipping.")
                self._emit("")
                self._emit(f"---------------------------------")
                self._emit(f"✅ SOBJECT [{obj_name}] COMPLETE")
                self._emit(f"  - Created: 0  Updated: 0  Skipped: 1")
                self._emit(f"---------------------------------")
                self._emit("")
                return

            if self._category_upsert(obj_name):
                await self.rl_target.acquire()
                target_desc = await describe_object(self.target_token, self.target_url, obj_name)
                pairs, matches = await self._category_plan(records, desc, target_desc)
                if self._category_preflight is not None and pairs != self._category_preflight:
                    raise ValueError('Scoped source AttributeCategory Name/Code changed after preflight')
                self._id_map[obj_name] = {}
                target_fields = {f['name']: f for f in target_desc.get('fields', [])}
                clean = self._clean_records(records, creatable, lookup_flds, self_loops, key_field)
                if self._unresolved_lookups:
                    raise ValueError(f'Unresolved AttributeCategory lookup(s): {self._unresolved_lookups}')
                for rec, row in zip(records, clean):
                    row['Name'], row['Code'] = pairs[rec['Id']]
                for operation in ('update', 'insert'):
                    payload = []
                    for rec, row in zip(records, clean):
                        target_id = matches.get(pairs[rec['Id']])
                        if (operation == 'update') != bool(target_id):
                            continue
                        allowed = 'updateable' if target_id else 'createable'
                        fields = {f: v for f, v in row.items() if f in target_fields
                                  and target_fields[f].get(allowed, False) and f not in _ORG_LOCAL_REFS
                                  and (not target_id or f not in ('Name', 'Code'))}
                        if target_id:
                            if not any(value not in (None, '') for value in fields.values()):
                                self._id_map[obj_name][rec['Id']] = target_id
                                continue
                            fields['Id'] = target_id
                        payload.append(fields)
                    if not payload:
                        continue
                    fields = list(dict.fromkeys(f for row in payload for f in row))
                    for batch in chunk_records(payload):
                        csv_data = records_to_csv(batch, fields)
                        await self.rl_target.acquire()
                        bulk_id = await self.target_bulk.create_ingest_job(obj_name, operation)
                        await self.target_bulk.upload_job_data(bulk_id, csv_data)
                        await self.target_bulk.close_job(bulk_id)
                        state = await self.target_bulk.wait_for_completion(bulk_id)
                        if state != 'JobComplete':
                            raise RuntimeError(f'{obj_name} Bulk job {bulk_id} ended in {state}')
                        successes = await self.target_bulk.get_successful_results(bulk_id)
                        if operation == 'insert':
                            created_ids = [success.get('sf__Id') for success in successes]
                            result.inserted_ids.extend(target_id for target_id in created_ids if target_id)
                            result.inserted += sum(bool(target_id) for target_id in created_ids)
                            set_job(self.job)
                            set_progress(self.job.job_id, base_pct, self.job.message,
                                         current_object=self.job.current_object, object_results=self.job.object_results)
                        for success in successes:
                            target_id = success.get('sf__Id')
                            if not target_id:
                                raise ValueError('AttributeCategory Bulk success missing Id')
                            if operation == 'insert':
                                pair = (success.get('Name'), success.get('Code'))
                                sources = [src for src, value in pairs.items() if value == pair]
                                if len(sources) != 1 or sources[0] in self._id_map[obj_name]:
                                    raise ValueError('Ambiguous AttributeCategory insert result pair')
                                self._id_map[obj_name][sources[0]] = target_id
                            else:
                                if target_id not in matches.values():
                                    raise ValueError('Unexpected AttributeCategory update result Id')
                                source_ids = [src for src, pair in pairs.items() if matches.get(pair) == target_id]
                                if len(source_ids) != 1 or source_ids[0] in self._id_map[obj_name]:
                                    raise ValueError('Ambiguous AttributeCategory update result Id')
                                self._id_map[obj_name][source_ids[0]] = target_id
                                result.updated += 1
                        set_job(self.job)
                        set_progress(self.job.job_id, base_pct, self.job.message,
                                     current_object=self.job.current_object, object_results=self.job.object_results)
                        failures = await self.target_bulk.get_failed_results(bulk_id)
                        unprocessed = await self.target_bulk.get_unprocessed_records(bulk_id)
                        result.failed += len(failures)
                        if len(successes) + len(failures) + len(unprocessed) != len(batch) or unprocessed:
                            raise RuntimeError(f'{obj_name} Bulk job {bulk_id} has unprocessed or unaccounted rows')
                result.status = 'done' if not result.failed else 'done_with_errors'
                if result.failed:
                    result.error = f'{result.failed} AttributeCategory record(s) failed'
                return

            if op_ext_id:
                ext_values = [str(row.get(op_ext_id) or '') for row in records]
                if any(not value.strip() for value in ext_values):
                    raise ValueError(f'Missing external ID {obj_name}.{op_ext_id} for upsert')
                if len(set(ext_values)) != len(ext_values):
                    raise ValueError(f'Duplicate external ID {obj_name}.{op_ext_id} for upsert')

            # Build source-ID → key-value map
            src_id_to_key: dict[str, str] = {}
            if key_field:
                for r in records:
                    if self._product_scoped and not str(r.get(key_field) or '').strip():
                        raise ValueError(f'Missing source key {obj_name}.{key_field} on {r["Id"]}')
                    src_id_to_key[r["Id"]] = str(r.get(key_field) or r["Id"])

            # 4. Clean and transform records
            clean = self._clean_records(
                records, creatable, lookup_flds, self_loops, key_field,
                required_fields={f['name'] for f in desc.get('fields', []) if not f.get('nillable', True)},
            )
            if self._product_scoped and key_field and len(set(src_id_to_key.values())) != len(records):
                raise ValueError(f'Duplicate source keys on {obj_name}.{key_field}')

            # Dry-run: report what would be written without touching the target
            if self.job.dry_run:
                result.skipped_dry_run = len(records)
                result.status = "done"
                self._emit(f"  [DRY-RUN] {obj_name}: would process {len(records)} record(s) — no writes made")
                self.job.object_results[obj_name] = result
                return

            # For objects with composite unique constraints (e.g. ProductRelationshipType),
            # pre-query the target to find already-existing records, map their IDs, and
            # exclude them from the insert payload to avoid DUPLICATE_VALUE failures.
            if obj_name in _COMPOSITE_KEY_OBJECTS:
                composite_fields = _COMPOSITE_KEY_OBJECTS[obj_name]
                # FK-based objects (ACA, PricebookEntry) need cleaned records so target IDs
                # are used for the lookup.  Scalar/picklist objects use raw source values.
                existing_map = await self._composite_key_preflight(
                    obj_name, composite_fields, records,
                    clean if obj_name in _FK_COMPOSITE_KEY_OBJECTS else None,
                )
                if existing_map:
                    self._id_map.setdefault(obj_name, {}).update(existing_map)
                    result.updated += len(existing_map)
                    self._emit(f"  -> {len(existing_map)} {obj_name} record(s) already exist on target — mapped, skipping insert")
                    new_pairs = [(r, c) for r, c in zip(records, clean) if r['Id'] not in existing_map]
                    records = [r for r, _ in new_pairs]
                    clean = [c for _, c in new_pairs]
                    src_id_to_key = {k: v for k, v in src_id_to_key.items() if k not in existing_map}
                    if not records:
                        result.status = 'done'
                        self.job.object_results[obj_name] = result
                        self._emit(f"  -> All {obj_name} records already exist on target. Skipping insert.")
                        return

            if keyless_insert or obj_name in self._create_only_self_order:
                self._id_map[obj_name] = {}
                by_id = {rec['Id']: (rec, row) for rec, row in zip(records, clean)}
                ordered_ids = self._create_only_self_order.get(obj_name, list(by_id))
                if len(by_id) != len(records) or set(ordered_ids) != set(by_id):
                    raise ValueError(f'Scoped source records changed for {obj_name} after preflight')
                async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                    for source_id in ordered_ids:
                        rec, row = by_id[source_id]
                        payload = {f: row[f] for f in creatable if f not in self_loops and f != 'Id' and row.get(f) != ''}
                        for field in self_loops if obj_name in self._create_only_self_order else ():
                            if rec.get(field):
                                parent_id = self._id_map[obj_name].get(str(rec[field]))
                                if not parent_id:
                                    raise ValueError(f'Unresolved scoped self-reference {obj_name}.{field} on {source_id}')
                                payload[field] = parent_id
                        await self.rl_target.acquire()
                        resp = await client.post(
                            f'{self.target_url}/services/data/v62.0/sobjects/{obj_name}/',
                            headers={'Authorization': f'Bearer {self.target_token}'},
                            json=payload,
                        )
                        body = resp.json()
                        target_id = body.get('id') if isinstance(body, dict) else None
                        if resp.status_code != 201 or not isinstance(body, dict) or not body.get('success') or not target_id:
                            # For FIELD_INTEGRITY_EXCEPTION (e.g. ProductCategoryProduct
                            # "primary category" conflict or duplicate junction assignment),
                            # attempt to locate the pre-existing target record and map it.
                            errors = body if isinstance(body, list) else []
                            _conflict_codes = {'FIELD_INTEGRITY_EXCEPTION', 'DUPLICATE_VALUE'}
                            is_conflict = any(
                                e.get('errorCode') in _conflict_codes
                                for e in errors
                            )
                            reconciled_id: Optional[str] = None
                            if is_conflict:
                                # Build a WHERE clause from FK fields in the payload to
                                # find the conflicting target record.
                                fk_filters = {
                                    f: payload[f] for f in (
                                        'Product2Id', 'ProductCategoryId',
                                        'ProductClassificationId', 'AttributeDefinitionId',
                                        'ProductSellingModelId',
                                    )
                                    if f in payload and payload[f]
                                }
                                if fk_filters:
                                    fk_where = ' AND '.join(
                                        f"{f} = '{v}'" for f, v in fk_filters.items()
                                    )
                                    fk_soql = f'SELECT Id FROM {obj_name} WHERE {fk_where} LIMIT 1'
                                    try:
                                        await self.rl_target.acquire()
                                        fk_resp = await client.get(
                                            f'{self.target_url}/services/data/v62.0/query',
                                            params={'q': fk_soql},
                                            headers={'Authorization': f'Bearer {self.target_token}'},
                                        )
                                        if fk_resp.is_success:
                                            fk_records = fk_resp.json().get('records', [])
                                            if fk_records:
                                                reconciled_id = fk_records[0]['Id']
                                    except Exception:
                                        pass
                            if reconciled_id:
                                self._id_map[obj_name][rec['Id']] = reconciled_id
                                result.updated += 1
                                self._emit(
                                    f"  ℹ️  [{obj_name}] Record {rec['Id']} already exists on target "
                                    f"({reconciled_id}) — mapped, skipping insert"
                                )
                            else:
                                raise RuntimeError(f'{obj_name} REST create failed or missing Id for {rec["Id"]}: {body}')
                            continue
                        self._id_map[obj_name][rec['Id']] = target_id
                        result.inserted_ids.append(target_id)
                        result.inserted += 1
                        self.job.total_inserted += 1
                        tracked_inserts += 1
                        set_job(self.job)
                        set_progress(self.job.job_id, base_pct, self.job.message,
                                     current_object=self.job.current_object, object_results=self.job.object_results)
                result.status = 'done'
                return

            # 5. Determine payload fields.
            #    Include key_field in the CSV so we can query it back for ID-map
            #    building even when op_ext_id differs from key_field or is None.
            #    When op_ext_id is different from key_field, include both.
            payload_field_set = []
            if key_field:
                payload_field_set.append(key_field)
            if op_ext_id and op_ext_id != key_field:
                payload_field_set.append(op_ext_id)
            payload_field_set += [f for f in creatable if f not in self_loops]
            payload_fields = list(dict.fromkeys(payload_field_set))

            # 6. Bulk API upsert / insert in batches.
            # When there is no Bulk API externalId but we have a natural key, pre-query
            # the target to split records into updates (existing) and inserts (new).
            natural_key_upsert = (
                self.job.mode == 'upsert' and key_field is not None
                and op_ext_id is None and not self._category_upsert(obj_name)
            )

            all_successes: list[dict] = []
            all_failures:  list[dict] = []

            nku_insert_successes: list[dict] = []  # insert successes for direct ID map build
            nku_insert_src_ids:   list[str] = []   # source IDs in insert_clean order
            nku_insert_name_to_src: dict[str, str] = {}  # name.casefold()→src_id for dup reconciliation
            if natural_key_upsert and src_id_to_key:
                existing_key_to_tgt = await self._query_target_by_key(
                    obj_name, key_field, list(src_id_to_key.values())
                )
                update_clean: list[dict] = []
                insert_clean: list[dict] = []
                for r, c in zip(records, clean):
                    key_val = src_id_to_key.get(r['Id'])
                    # Casefold for case-insensitive match (SOQL is CI but Python dicts are CS)
                    tgt_id = existing_key_to_tgt.get(key_val.casefold()) if key_val else None
                    if tgt_id:
                        row = dict(c)
                        row['Id'] = tgt_id
                        update_clean.append(row)
                        self._id_map.setdefault(obj_name, {})[r['Id']] = tgt_id
                    else:
                        insert_clean.append(c)
                        nku_insert_src_ids.append(r['Id'])
                        nm = str(r.get('Name') or '').casefold()
                        if nm:
                            nku_insert_name_to_src[nm] = r['Id']
                self._emit(f"  -> Natural-key upsert on '{key_field}': {len(update_clean)} update(s), {len(insert_clean)} insert(s)")

                if update_clean:
                    update_fields = list(dict.fromkeys(['Id'] + [f for f in payload_fields if f != 'Id']))
                    for batch_num, batch in enumerate(chunk_records(update_clean), 1):
                        self._emit("")
                        self._emit(f" ⚙️  {obj_name} update-buffer flush: sending {len(batch)} records")
                        self._emit(f"    ⚙️ [BulkV2] UPDATE {obj_name}: {len(batch)} rows")
                        csv_data = records_to_csv(batch, update_fields)
                        await self.rl_target.acquire()
                        bulk_job_id = await self.target_bulk.create_ingest_job(obj_name, 'update')
                        await self.target_bulk.upload_job_data(bulk_job_id, csv_data)
                        await self.target_bulk.close_job(bulk_job_id)
                        state = await self.target_bulk.wait_for_completion(bulk_job_id)
                        if state != 'JobComplete':
                            raise RuntimeError(f'{obj_name} Bulk update job {bulk_job_id} ended in {state}')
                        batch_successes = await self.target_bulk.get_successful_results(bulk_job_id)
                        batch_failures  = await self.target_bulk.get_failed_results(bulk_job_id)
                        unprocessed = await self.target_bulk.get_unprocessed_records(bulk_job_id)
                        result.updated += len(batch_successes)
                        result.failed += len(batch_failures)
                        all_successes += batch_successes
                        all_failures += batch_failures
                        if len(batch_successes) + len(batch_failures) + len(unprocessed) != len(batch) or unprocessed:
                            raise RuntimeError(f'{obj_name} Bulk update job {bulk_job_id} has unprocessed or unaccounted rows')
                        self._emit(f"")
                        self._emit(f"    📦 Batch {batch_num} Results (update):")
                        self._emit(f"     - Updated  : {len(batch_successes)}")
                        self._emit(f"     - Failed   : {len(batch_failures)}")
                        if self._log:
                            self._log.bulk_job(obj_name, bulk_job_id, 'update', len(batch), len(batch_successes), len(batch_failures))
                            if batch_failures:
                                self._log.failed_records(obj_name, batch_failures)
                        set_job(self.job)
                        set_progress(self.job.job_id, base_pct, self.job.message,
                                     current_object=self.job.current_object, object_results=self.job.object_results)

                if insert_clean:
                    for batch_num, batch in enumerate(chunk_records(insert_clean), 1):
                        self._emit("")
                        self._emit(f" ⚙️  {obj_name} insert-buffer flush: sending {len(batch)} records")
                        self._emit(f"    ⚙️ [BulkV2] INSERT {obj_name}: {len(batch)} rows")
                        csv_data = records_to_csv(batch, payload_fields)
                        await self.rl_target.acquire()
                        bulk_job_id = await self.target_bulk.create_ingest_job(obj_name, 'insert')
                        await self.target_bulk.upload_job_data(bulk_job_id, csv_data)
                        await self.target_bulk.close_job(bulk_job_id)
                        state = await self.target_bulk.wait_for_completion(bulk_job_id)
                        if state != 'JobComplete':
                            raise RuntimeError(f'{obj_name} Bulk insert job {bulk_job_id} ended in {state}')
                        batch_successes = await self.target_bulk.get_successful_results(bulk_job_id)
                        batch_failures  = await self.target_bulk.get_failed_results(bulk_job_id)
                        unprocessed = await self.target_bulk.get_unprocessed_records(bulk_job_id)

                        # Reconcile DUPLICATE_VALUE failures: map source→target and count as update.
                        insert_kv_to_src = {
                            src_id_to_key.get(sid, '').casefold(): sid
                            for sid in nku_insert_src_ids
                            if str(src_id_to_key.get(sid, '')).casefold()
                        }
                        batch_failures, dup_reconciled_count = await self._reconcile_dup_failures(
                            obj_name, batch_failures, key_field,
                            insert_kv_to_src, nku_insert_name_to_src,
                        )

                        batch_inserted = sum(1 for r in batch_successes if r.get("sf__Created") == "true")
                        batch_updated  = sum(1 for r in batch_successes if r.get("sf__Created") != "true" and r.get("sf__Id"))
                        result.inserted += batch_inserted
                        result.updated  += batch_updated + dup_reconciled_count
                        result.failed   += len(batch_failures)
                        result.inserted_ids.extend(
                            r["sf__Id"] for r in batch_successes
                            if r.get("sf__Created") == "true" and r.get("sf__Id")
                        )
                        nku_insert_successes += batch_successes
                        all_successes += batch_successes
                        all_failures += batch_failures
                        if (len(batch_successes) + len(batch_failures) + len(unprocessed)
                                + dup_reconciled_count != len(batch) or unprocessed):
                            raise RuntimeError(f'{obj_name} Bulk insert job {bulk_job_id} has unprocessed or unaccounted rows')
                        self._emit(f"")
                        self._emit(f"    📦 Batch {batch_num} Results (insert):")
                        self._emit(f"     - Created  : {batch_inserted}")
                        self._emit(f"     - Mapped   : {dup_reconciled_count}")
                        self._emit(f"     - Failed   : {len(batch_failures)}")
                        if self._log:
                            self._log.bulk_job(obj_name, bulk_job_id, 'insert', len(batch), len(batch_successes), len(batch_failures))
                            if batch_failures:
                                self._log.failed_records(obj_name, batch_failures)
                        set_job(self.job)
                        set_progress(self.job.job_id, base_pct, self.job.message,
                                     current_object=self.job.current_object, object_results=self.job.object_results)

            else:
                # Standard path: Bulk API upsert (with externalId) or plain insert
                operation = "upsert" if op_ext_id else "insert"
                ext_id    = op_ext_id   # None for insert jobs

                # Pre-build reverse maps for DUPLICATE_VALUE reconciliation.
                # src_id_to_key already maps source_id→key_value; invert it here.
                std_kv_to_src: dict[str, str] = {
                    v.casefold(): k for k, v in src_id_to_key.items() if v.casefold()
                } if key_field else {}
                std_name_to_src: dict[str, str] = {
                    str(r.get('Name') or '').casefold(): r['Id']
                    for r in records if r.get('Name')
                }

                for batch_num, batch in enumerate(chunk_records(clean), 1):
                    self._emit("")
                    self._emit(f" ⚙️  {obj_name} {operation}-buffer flush: sending {len(batch)} records")
                    self._emit(f"    ⚙️ [BulkV2] {operation.upper()} {obj_name}: {len(batch)} rows")
                    csv_data = records_to_csv(batch, payload_fields)
                    await self.rl_target.acquire()
                    bulk_job_id = await self.target_bulk.create_ingest_job(obj_name, operation, ext_id)
                    await self.target_bulk.upload_job_data(bulk_job_id, csv_data)
                    await self.target_bulk.close_job(bulk_job_id)
                    state = await self.target_bulk.wait_for_completion(bulk_job_id)
                    if state != 'JobComplete':
                        raise RuntimeError(f'{obj_name} Bulk job {bulk_job_id} ended in {state}')
                    batch_successes = await self.target_bulk.get_successful_results(bulk_job_id)
                    batch_failures  = await self.target_bulk.get_failed_results(bulk_job_id)
                    unprocessed = await self.target_bulk.get_unprocessed_records(bulk_job_id)

                    # Reconcile DUPLICATE_VALUE failures: map source→target and count as update.
                    batch_failures, dup_reconciled_count = await self._reconcile_dup_failures(
                        obj_name, batch_failures, key_field,
                        std_kv_to_src, std_name_to_src,
                    )

                    batch_inserted = sum(1 for r in batch_successes if r.get("sf__Created") == "true")
                    batch_updated  = sum(1 for r in batch_successes if r.get("sf__Created") != "true" and r.get("sf__Id"))
                    result.inserted += batch_inserted
                    result.updated += batch_updated + dup_reconciled_count
                    result.failed += len(batch_failures)
                    result.inserted_ids.extend(
                        r["sf__Id"] for r in batch_successes
                        if r.get("sf__Created") == "true" and r.get("sf__Id")
                    )
                    all_successes += batch_successes
                    all_failures += batch_failures
                    if (len(batch_successes) + len(batch_failures) + len(unprocessed)
                            + dup_reconciled_count != len(batch) or unprocessed):
                        raise RuntimeError(f'{obj_name} Bulk job {bulk_job_id} has unprocessed or unaccounted rows')
                    self._emit(f"")
                    self._emit(f"    📦 Batch {batch_num} Results:")
                    self._emit(f"     - Created  : {batch_inserted}")
                    self._emit(f"     - Updated  : {batch_updated}")
                    self._emit(f"     - Mapped   : {dup_reconciled_count}")
                    self._emit(f"     - Failed   : {len(batch_failures)}")
                    if self._log:
                        self._log.bulk_job(obj_name, bulk_job_id, operation, len(batch), len(batch_successes), len(batch_failures))
                        if batch_failures:
                            self._log.failed_records(obj_name, batch_failures)

            result.status   = "done" if not all_failures else "done_with_errors"
            if all_failures:
                result.error = f"{len(all_failures)} record(s) failed: {all_failures[0].get('sf__Error', '')}"
                result.error_categories = self._categorize_failures(all_failures)

            # Enforce failure threshold (0 = fail on any error)
            if result.failed and self.job.failure_threshold_pct >= 0:
                total = result.queried or 1
                pct = result.failed / total * 100
                threshold = self.job.failure_threshold_pct
                if threshold == 0 or pct > threshold:
                    result.status = "failed"

            # Warn if any lookup IDs could not be resolved
            if self._unresolved_lookups > 0:
                note = (
                    f" [{self._unresolved_lookups} lookup(s) unresolved — "
                    "parent records may not exist on target org]"
                )
                result.error = (result.error or "") + note

            # 7. Build ID and key maps for child objects
            if self._product_scoped and not key_field and obj_name not in _COMPOSITE_KEY_OBJECTS:
                raise ValueError(f'No mapping key for {obj_name}')
            if natural_key_upsert and src_id_to_key:
                # Build ID map for insert successes. Updates + dup-reconciled records are
                # already in _id_map. For true new inserts, match by key_field value from
                # the success row (Bulk API 2.0 echoes input fields), fall back to Name,
                # then finally to positional order (only reliable when no dups were reconciled).
                if nku_insert_successes:
                    insert_kv_to_src = {
                        src_id_to_key.get(sid, '').casefold(): sid
                        for sid in nku_insert_src_ids
                        if str(src_id_to_key.get(sid, '')).casefold()
                    }
                    for i, success in enumerate(nku_insert_successes):
                        tgt_id = success.get('sf__Id')
                        if not tgt_id:
                            continue
                        src_id = None
                        kv = str(success.get(key_field) or '').casefold() if key_field else ''
                        if kv:
                            src_id = insert_kv_to_src.get(kv)
                        if not src_id and nku_insert_name_to_src:
                            nm = str(success.get('Name') or '').casefold()
                            if nm:
                                src_id = nku_insert_name_to_src.get(nm)
                        if not src_id and i < len(nku_insert_src_ids):
                            src_id = nku_insert_src_ids[i]  # positional fallback
                        if src_id and tgt_id:
                            self._id_map.setdefault(obj_name, {})[src_id] = tgt_id
            elif key_field and all_successes:
                await self._build_id_map(obj_name, key_field, src_id_to_key)

        except Exception as e:
            err_str = str(e)
            self._emit(f"❌ [{obj_name}] ERROR: {err_str[:200]}")
            if self._log:
                self._log.error(f"OBJECT_EXCEPTION object={obj_name} error={err_str!r}")
            if "401" in err_str or "INVALID_SESSION_ID" in err_str:
                result.status = "failed"
                result.error = (
                    "Target org session expired mid-migration. "
                    "Re-authenticate and restart."
                )
                raise RuntimeError("Target session expired") from e
            result.status = "failed"
            result.error  = err_str[:300]
        finally:
            if self._log:
                self._log.object_done(obj_name, result.queried, result.inserted, result.updated, result.failed, result.error)

            self.job.object_results[obj_name] = result
            self.job.total_queried  += result.queried
            self.job.total_inserted += result.inserted - tracked_inserts
            self.job.total_updated  += result.updated
            self.job.total_failed   += result.failed

        self._emit("")
        self._emit(f"---------------------------------")
        if result.status in ("done", "done_with_errors"):
            self._emit(f"✅ SOBJECT [{obj_name}] COMPLETE")
        elif result.status == "skipped":
            self._emit(f"⏭  SOBJECT [{obj_name}] SKIPPED")
        else:
            self._emit(f"❌ SOBJECT [{obj_name}] FAILED")
        self._emit(f"  - Created: {result.inserted}")
        self._emit(f"  - Updated: {result.updated}")
        self._emit(f"  - Failed : {result.failed}")
        if result.error:
            self._emit(f"  ⚠️  {result.error[:160]}")
        self._emit(f"---------------------------------")
        self._emit("")

        self._update(base_pct, f"Done {obj_name}: +{result.inserted} /{result.updated}u /{result.failed}x")

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────
    async def _query_all(self, soql: str) -> list[dict]:
        """Paginated SOQL fetch — follows nextRecordsUrl automatically."""
        records: list[dict] = []
        result = await self.source.query(soql)
        records.extend(result.get("records", []))

        while not result.get("done") and result.get("nextRecordsUrl"):
            next_url = result["nextRecordsUrl"]
            await self.rl_source.acquire()
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                resp = await client.get(
                    f"{self.source.instance_url}{next_url}",
                    headers=self.source.headers,
                )
                resp.raise_for_status()
                result = resp.json()
            records.extend(result.get("records", []))

        if not result.get('done', True):
            raise ValueError('Incomplete source query pagination')

        # Strip Salesforce metadata keys added by the REST API
        return [{k: v for k, v in r.items() if k != "attributes"} for r in records]

    @staticmethod
    def _categorize_failures(failures: list[dict]) -> dict[str, int]:
        """Return a dict of error_code → count from Bulk API failed result rows."""
        counts: dict[str, int] = {}
        for row in failures:
            raw = row.get("sf__Error", "")
            # Bulk API 2.0 error format: "ERROR_CODE:field:message" or just "ERROR_CODE:message"
            code = raw.split(":")[0].strip() or "UNKNOWN"
            counts[code] = counts.get(code, 0) + 1
        return counts

    def _clean_records(
        self,
        records: list[dict],
        creatable: list[str],
        lookup_flds: dict[str, str],
        self_loops: list[str],
        key_field: Optional[str],
        required_fields: set[str] | None = None,
    ) -> list[dict]:
        clean = []
        for rec in records:
            row: dict = {}
            for field in creatable:
                if field in _ORG_LOCAL_REFS:
                    continue
                if field in self_loops:
                    continue          # handled in second pass
                val = rec.get(field)
                if val is None:
                    if self._product_scoped and field in lookup_flds and field in (required_fields or set()):
                        raise ValueError(f'Missing required scoped lookup {field} on {rec.get("Id")}')
                    row[field] = ""
                    continue
                # Resolve lookup ID → target ID
                if field in lookup_flds:
                    parent_obj = lookup_flds[field]
                    if isinstance(parent_obj, list):
                        # Polymorphic lookup — try each possible parent object
                        resolved = None
                        for po in parent_obj:
                            resolved = self._resolve_lookup(po, str(val))
                            if resolved:
                                break
                    else:
                        resolved = self._resolve_lookup(parent_obj, str(val))
                    if resolved:
                        row[field] = resolved
                    else:
                        if self._product_scoped:
                            raise ValueError(f'Unresolved lookup {field} on {rec.get("Id")}')
                        row[field] = ""
                        self._unresolved_lookups += 1
                else:
                    row[field] = val
            if key_field:
                row[key_field] = str(rec.get(key_field) or rec.get("Id", ""))
            clean.append(row)
        return clean

    def _resolve_lookup(self, parent_obj: str, source_id: str) -> Optional[str]:
        """Map a source record ID to the corresponding target record ID."""
        return self._id_map.get(parent_obj, {}).get(source_id)

    async def _reconcile_dup_failures(
        self,
        obj_name: str,
        batch_failures: list[dict],
        key_field: Optional[str],
        kv_to_src: dict[str, str],
        name_to_src: dict[str, str],
    ) -> tuple[list[dict], int]:
        """Reconcile DUPLICATE_VALUE bulk failures.

        Phase 1: extract target record ID from the error message (works for most objects).
        Phase 2: for errors without a record ID (e.g. Product2 SKU), query the target
                 by key_field value to find the conflicting record.

        Returns (remaining_true_failures, reconciled_count).
        """
        reconciled = 0
        need_lookup: list[dict] = []
        true_failures: list[dict] = []

        for fail in batch_failures:
            err = fail.get('sf__Error', '')
            if 'DUPLICATE_VALUE' in err:
                m = _DUP_RECORD_RE.search(err)
                if m:
                    tgt_id = m.group(1)
                    src_id = None
                    if key_field:
                        kv = str(fail.get(key_field) or '').casefold()
                        if kv:
                            src_id = kv_to_src.get(kv)
                    if not src_id:
                        nm = str(fail.get('Name') or '').casefold()
                        if nm:
                            src_id = name_to_src.get(nm)
                    if src_id and tgt_id:
                        self._id_map.setdefault(obj_name, {})[src_id] = tgt_id
                        reconciled += 1
                        continue
                # Error has no "record with id:" — queue for key-value lookup
                if key_field and fail.get(key_field):
                    need_lookup.append(fail)
                    continue
            true_failures.append(fail)

        # Phase 2: query target by key value for failures without a record ID in the error
        if need_lookup and key_field:
            lookup_vals = list({str(f.get(key_field)) for f in need_lookup if f.get(key_field)})
            try:
                kv_to_tgt = await self._query_target_by_key(obj_name, key_field, lookup_vals)
                for fail in need_lookup:
                    kv = str(fail.get(key_field) or '').casefold()
                    src_id = kv_to_src.get(kv)
                    tgt_id = kv_to_tgt.get(kv)
                    if src_id and tgt_id:
                        self._id_map.setdefault(obj_name, {})[src_id] = tgt_id
                        reconciled += 1
                    else:
                        true_failures.append(fail)
            except Exception:
                true_failures.extend(need_lookup)

        return true_failures, reconciled

    async def _query_target_by_key(self, obj_name: str, key_field: str, key_values: list[str]) -> dict[str, str]:
        """Query target org for existing records matching key_field values.
        Returns {key_value: target_id} for records that already exist."""
        if not key_values:
            return {}
        key_to_target: dict[str, str] = {}
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            for i in range(0, len(key_values), 500):
                batch_vals = key_values[i:i + 500]
                quoted = ", ".join("'" + v.replace('\\', '\\\\').replace("'", "\\'") + "'" for v in batch_vals)
                soql = f"SELECT Id, {key_field} FROM {obj_name} WHERE {key_field} IN ({quoted})"
                await self.rl_target.acquire()
                resp = await client.get(
                    f"{self.target_url}/services/data/v62.0/query",
                    params={"q": soql},
                    headers={"Authorization": f"Bearer {self.target_token}"},
                )
                if resp.status_code == 400:
                    # Field not queryable on target — return empty so inserts run and
                    # DUPLICATE_VALUE reconciliation handles pre-existing records.
                    self._emit(
                        f"⚠️  [{obj_name}] Cannot query {key_field} on target (400) — "
                        "will reconcile DUPLICATE_VALUE conflicts at insert time"
                    )
                    return {}
                resp.raise_for_status()
                page = resp.json()
                while True:
                    for r in page.get('records', []):
                        # Casefold so case-only differences (e.g. target "standard cost book"
                        # vs source "Standard Cost Book") still resolve — SOQL is
                        # case-insensitive but Python dict lookups are not.
                        key = str(r.get(key_field, '')).casefold()
                        if key:
                            key_to_target[key] = r['Id']
                    if page.get('done', True):
                        break
                    url = page.get('nextRecordsUrl')
                    if not url:
                        raise ValueError(f'Incomplete target key query for {obj_name}')
                    await self.rl_target.acquire()
                    resp = await client.get(
                        f"{self.target_url}{url}",
                        headers={"Authorization": f"Bearer {self.target_token}"},
                    )
                    resp.raise_for_status()
                    page = resp.json()
        return key_to_target

    async def _composite_key_preflight(
        self, obj_name: str, key_fields: list[str], records: list[dict],
        cleaned_records: list[dict] | None = None,
    ) -> dict[str, str]:
        """Query target for records matching a composite unique key.
        Returns {source_record_id: target_record_id} for every source record that
        already exists on the target (matched by composite key tuple).

        cleaned_records: if provided, key field values are taken from here instead of
        records. Required when composite key fields are FKs (e.g. AttributeCategoryAttribute)
        where source IDs differ from target IDs — pass the cleaned (remapped) records so
        the lookup matches what the target org actually has."""
        lookup = cleaned_records if cleaned_records is not None else records
        src_key_to_id = {
            tuple(str(lookup[i].get(f) or '') for f in key_fields): records[i]['Id']
            for i in range(len(records))
        }
        id_map: dict[str, str] = {}
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            select = ', '.join(['Id'] + key_fields)
            # Restrict the target query to only the relevant values for each key field.
            # For FK-based keys (cleaned_records provided) this is essential to avoid full
            # table scans on large objects like PricebookEntry.  For scalar/picklist keys
            # (cleaned_records=None) it still avoids scanning the full table.
            where_parts = []
            for f in key_fields:
                vals = list({str(lookup[i].get(f) or '') for i in range(len(lookup))
                             if lookup[i].get(f)})
                if vals:
                    qv = ', '.join("'" + v.replace('\\', '\\\\').replace("'", "\\'") + "'"
                                   for v in vals[:500])
                    where_parts.append(f'{f} IN ({qv})')
            soql = f'SELECT {select} FROM {obj_name}'
            if where_parts:
                soql += ' WHERE ' + ' AND '.join(where_parts)
            await self.rl_target.acquire()
            resp = await client.get(
                f'{self.target_url}/services/data/v62.0/query',
                params={'q': soql},
                headers={'Authorization': f'Bearer {self.target_token}'},
            )
            resp.raise_for_status()
            page = resp.json()
            while True:
                for tgt in page.get('records', []):
                    key = tuple(str(tgt.get(f) or '') for f in key_fields)
                    src_id = src_key_to_id.get(key)
                    if src_id:
                        id_map[src_id] = tgt['Id']
                if page.get('done', True):
                    break
                url = page.get('nextRecordsUrl')
                if not url:
                    break
                await self.rl_target.acquire()
                resp = await client.get(
                    f'{self.target_url}{url}',
                    headers={'Authorization': f'Bearer {self.target_token}'},
                )
                resp.raise_for_status()
                page = resp.json()
        return id_map

    async def _build_id_map(self, obj_name: str, key_field: str, src_id_to_key: dict[str, str]):
        """
        After upsert, query target org to build {source_id → target_id}.
        Works by: source_id → key_value → target_id.
        """
        key_values = list(src_id_to_key.values())
        if not key_values:
            return
        if self._product_scoped and (not all(key_values) or len(set(key_values)) != len(key_values)):
            raise ValueError(f'Missing or duplicate source mapping keys on {obj_name}')

        # Query target in batches of 500 (IN clause limit)
        key_to_target: dict[str, str] = {}
        for i in range(0, len(key_values), 500):
            batch_vals = key_values[i: i + 500]
            quoted = ", ".join("'" + v.replace('\\', '\\\\').replace("'", "\\'") + "'" for v in batch_vals)
            soql = f"SELECT Id, {key_field} FROM {obj_name} WHERE {key_field} IN ({quoted})"
            await self.rl_target.acquire()
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                resp = await client.get(
                    f"{self.target_url}/services/data/v62.0/query",
                    params={"q": soql},
                    headers={"Authorization": f"Bearer {self.target_token}"},
                )
                resp.raise_for_status()
                page = resp.json()
                while True:
                    for r in page.get('records', []):
                        key = str(r.get(key_field, ''))
                        if key in key_to_target:
                            self._emit(
                                f"⚠️  [{obj_name}] Duplicate target record for {key_field}={key!r} — "
                                "keeping first match. Delete the duplicate from the target org to prevent this."
                            )
                            continue
                        key_to_target[key] = r['Id']
                    if page.get('done', True):
                        break
                    url = page.get('nextRecordsUrl')
                    if not url:
                        raise ValueError(f'Incomplete target mapping for {obj_name}')
                    await self.rl_target.acquire()
                    resp = await client.get(f'{self.target_url}{url}', headers={"Authorization": f"Bearer {self.target_token}"})
                    resp.raise_for_status()
                    page = resp.json()

        self._key_map[obj_name] = key_to_target

        # Now build full source_id → target_id
        id_map: dict[str, str] = {}
        for src_id, key_val in src_id_to_key.items():
            target_id = key_to_target.get(key_val)
            if target_id:
                id_map[src_id] = target_id
            elif self._product_scoped:
                raise ValueError(f'Missing target mapping for {obj_name}.{key_field}={key_val}')
        self._id_map[obj_name] = id_map

    async def _second_pass_self_lookups(self, obj_name: str, strategy: dict):
        """Update self-referential lookup fields (e.g. Account.ParentId) after all records exist."""
        records = self._source_records.get(obj_name, [])
        self_loops = strategy.get("self_lookups", [])
        if not records or not self_loops:
            return

        updates = []
        for rec in records:
            target_id = self._id_map.get(obj_name, {}).get(rec["Id"])
            if not target_id:
                if self._product_scoped:
                    raise ValueError(f'Missing self-lookup target mapping for {obj_name} {rec["Id"]}')
                continue
            row = {"Id": target_id}
            for field in self_loops:
                src_parent_id = rec.get(field)
                if src_parent_id:
                    parent_obj = 'UnitOfMeasure' if obj_name == 'UnitOfMeasureClass' and field in _DEFERRED_UOM_CLASS_REFS else obj_name
                    resolved = self._id_map.get(parent_obj, {}).get(str(src_parent_id))
                    if self._product_scoped and not resolved:
                        raise ValueError(f'Missing self-lookup parent {obj_name}.{field}={src_parent_id}')
                    row[field] = resolved or ""
                else:
                    row[field] = ""
            if any(row.get(f) for f in self_loops):
                updates.append(row)

        if not updates:
            return

        fields = ["Id"] + self_loops
        for batch in chunk_records(updates):
            csv_data = records_to_csv(batch, fields)
            await self.rl_target.acquire()
            bulk_job_id = await self.target_bulk.create_ingest_job(obj_name, "update")
            await self.target_bulk.upload_job_data(bulk_job_id, csv_data)
            await self.target_bulk.close_job(bulk_job_id)
            state = await self.target_bulk.wait_for_completion(bulk_job_id)
            if state != 'JobComplete':
                raise RuntimeError(f'Self-lookup Bulk job {bulk_job_id} ended in {state}')
            successes = await self.target_bulk.get_successful_results(bulk_job_id)
            failures = await self.target_bulk.get_failed_results(bulk_job_id)
            unprocessed = await self.target_bulk.get_unprocessed_records(bulk_job_id)
            if failures or unprocessed or len(successes) != len(batch):
                raise RuntimeError(f'Self-lookup Bulk job {bulk_job_id} failed or missed rows')


# ──────────────────────────────────────────────────────────────────────────────
# Rollback
# ──────────────────────────────────────────────────────────────────────────────
async def rollback_job(job: MigrationJob, target_token: str, target_url: str):
    """Delete all records inserted during a job, in reverse dependency order."""
    bulk = BulkAPI2(target_token, target_url)

    for obj_name in reversed(job.dep_order):
        result = job.object_results.get(obj_name)
        if not result or not result.inserted_ids:
            continue
        ids = result.inserted_ids
        records = [{"Id": rid} for rid in ids if rid]
        if not records:
            continue
        for batch in chunk_records(records):
            csv_data = records_to_csv(batch, ["Id"])
            bulk_job_id = await bulk.create_ingest_job(obj_name, "delete")
            await bulk.upload_job_data(bulk_job_id, csv_data)
            await bulk.close_job(bulk_job_id)
            state = await bulk.wait_for_completion(bulk_job_id)
            if state != 'JobComplete':
                raise RuntimeError(f'{obj_name} rollback Bulk job {bulk_job_id} ended in {state}')
            successes = await bulk.get_successful_results(bulk_job_id)
            failures = await bulk.get_failed_results(bulk_job_id)
            unprocessed = await bulk.get_unprocessed_records(bulk_job_id)
            expected_ids = {row['Id'] for row in batch}
            deleted_ids = [row.get('sf__Id') for row in successes]
            if (failures or unprocessed or len(successes) + len(failures) + len(unprocessed) != len(batch)
                    or len(deleted_ids) != len(expected_ids) or set(deleted_ids) != expected_ids):
                raise RuntimeError(
                    f'{obj_name} rollback Bulk job {bulk_job_id} incomplete: '
                    f'successful={len(successes)}, failed={len(failures)}, unprocessed={len(unprocessed)}; '
                    f'deleted IDs={deleted_ids}, expected IDs={sorted(expected_ids)}; '
                    f'failures={failures}, unprocessed rows={unprocessed}'
                )
            result.inserted_ids = [rid for rid in result.inserted_ids if rid not in expected_ids]
            set_job(job)
