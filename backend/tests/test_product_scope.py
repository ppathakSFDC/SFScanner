import asyncio
import csv
import io
import json
import os
import tempfile
import unittest
from dataclasses import asdict
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from backend.routers import migrate_router as router
from backend.migrator.engine import MigrationEngine, rollback_job
from backend.migrator import job_store
from backend.migrator.job_store import MigrationJob
from backend.migrator.object_groups import OBJECT_DEPS, PRODUCT_BUNDLE_OBJECTS, OBJECT_GROUPS
from backend.migrator.smart_key import get_upsert_strategy, find_bulk_ext_id


P = '01t000000000001AAA'
C = '01t000000000002AAA'
N = '01t000000000003AAA'
G = 'a00000000000001AAA'
R = 'a00000000000002AAA'
H = 'a00000000000003AAA'
T = 'a00000000000005AAA'
F = 'a00000000000006AAA'


def migration_request(source='https://source.salesforce.com', owner=None, authenticated=True):
    session = {'access_token': 'source-secret', 'instance_url': source} if authenticated else {}
    if owner is not None:
        session['migration_owner_id'] = owner
    return Request({'type': 'http', 'session': session})


class MigrationSecurityTests(unittest.TestCase):
    def job(self):
        job = MigrationJob('secure-job', 'https://source.salesforce.com',
                           'https://target.salesforce.com', 'insert', ['Product2'], ['Product2'])
        job.migration_owner_id = 'owner-a'
        return job

    def test_job_routes_require_auth_owner_and_source(self):
        job = self.job()
        from backend.migrator.job_store import ObjectMigrationResult
        job.object_results['Product2'] = ObjectMigrationResult('Product2', inserted_ids=[G])
        requests = (migration_request(authenticated=False), migration_request(owner='owner-b'),
                    migration_request(owner='owner-a', source='https://other.salesforce.com'),
                    migration_request())
        with patch.object(router, '_jobs', {job.job_id: job}), patch.object(router, 'get_job', return_value=job), \
             patch.object(router, 'cancel_job') as cancel, patch.object(router.asyncio, 'create_task') as task:
            for request in requests:
                expected = 401 if not request.session.get('access_token') else 404
                for call in (lambda: router.get_result(job.job_id, request),
                             lambda: router.stream_progress(job.job_id, request),
                             lambda: router.download_log(job.job_id, request),
                             lambda: router.stop_migration(job.job_id, request),
                             lambda: router.rollback(job.job_id, router.RollbackPayload(
                                 target_access_token='target-secret', target_instance_url=job.target_url), request)):
                    with self.assertRaises(HTTPException) as rejected:
                        asyncio.run(call())
                    self.assertEqual(expected, rejected.exception.status_code)
                if expected == 404:
                    self.assertEqual([], asyncio.run(router.list_jobs(request)))
                else:
                    with self.assertRaises(HTTPException) as rejected:
                        asyncio.run(router.list_jobs(request))
                    self.assertEqual(401, rejected.exception.status_code)
            cancel.assert_not_called()
            task.assert_not_called()
            owner = migration_request(owner='owner-a')
            self.assertEqual([job.job_id], [j['job_id'] for j in asyncio.run(router.list_jobs(owner))])
            self.assertEqual(job.job_id, asyncio.run(router.get_result(job.job_id, owner))['job_id'])

    def test_start_assigns_stable_owner_without_exposing_token(self):
        request = migration_request()
        payload = router.StartMigrationPayload(target_access_token='target-secret',
            target_instance_url='https://target.salesforce.com', selected_objects=['Product2'])
        async def no_run(*args): pass
        with patch.object(router, '_run_migration', no_run), patch.object(router, 'set_job') as save, \
             patch.object(router, 'set_progress') as progress:
            async def start():
                response = await router.start_migration(request, payload)
                await asyncio.sleep(0)
                return response
            first = asyncio.run(start())
            owner = request.session['migration_owner_id']
            self.assertTrue(owner)
            self.assertEqual(owner, save.call_args.args[0].migration_owner_id)
            self.assertNotIn('target-secret', str(first))
            self.assertNotIn('target-secret', str(asdict(save.call_args.args[0])))
            self.assertNotIn('target-secret', str(progress.call_args))
            asyncio.run(start())
            self.assertEqual(owner, request.session['migration_owner_id'])

    def test_start_rejects_partially_filtered_explicit_bundle_before_saving(self):
        payload = router.StartMigrationPayload(target_access_token='t',
            target_instance_url='https://target.salesforce.com',
            selected_objects=['Product2', 'AttributeCategory', 'ProductRampSegment'],
            object_filters={'Product2': f"Id IN ('{P}')", 'ProductRampSegment': '   '})
        async def no_run(*args): pass
        def schedule(coro): coro.close()
        with patch.object(router, 'set_job') as save, patch.object(router, 'set_progress') as progress, \
             patch.object(router, '_run_migration', no_run), \
             patch.object(router.asyncio, 'create_task', side_effect=schedule) as task:
            with self.assertRaises(HTTPException) as rejected:
                asyncio.run(router.start_migration(migration_request(), payload))
        self.assertEqual(400, rejected.exception.status_code)
        self.assertIn('product_ids', str(rejected.exception.detail))
        save.assert_not_called()
        progress.assert_not_called()
        task.assert_not_called()

    def test_start_rejects_unfiltered_auto_added_product_dependencies(self):
        async def no_run(*args): pass
        with patch.object(router, 'set_job') as save, patch.object(router, 'set_progress') as progress, \
             patch.object(router, '_run_migration', no_run), patch.object(router.asyncio, 'create_task') as task:
            for selected, filters in (
                (['Product2'], {'Product2': f"Id IN ('{P}')"}),
                (['ProductRampSegment'], {'ProductRampSegment': f"Id IN ('{R}')"}),
            ):
                with self.subTest(selected=selected):
                    with self.assertRaises(HTTPException) as rejected:
                        asyncio.run(router.start_migration(migration_request(), router.StartMigrationPayload(
                            target_access_token='t', target_instance_url='https://target.salesforce.com',
                            selected_objects=selected, object_filters=filters)))
                    self.assertEqual(400, rejected.exception.status_code)
                    self.assertIn('product_ids', str(rejected.exception.detail))
            save.assert_not_called()
            progress.assert_not_called()
            task.assert_not_called()

    def test_start_preserves_unfiltered_single_object_and_fully_filtered_bundle(self):
        async def no_run(*args): pass
        cases = (
            (['AttributeCategory'], {}),
            (['Product2'], {}),
            (['Product2', 'AttributeCategory'], {
                'Product2': f"Id IN ('{P}')", 'AttributeCategory': f"Id IN ('{G}')",
                'ProductClassification': f"Id IN ('{F}')", 'AttributeDefinition': f"Id IN ('{H}')",
                'AttributePicklist': f"Id IN ('{T}')", 'UnitOfMeasure': f"Id IN ('{N}')",
                'UnitOfMeasureClass': f"Id IN ('{C}')",
            }),
        )
        with patch.object(router, '_run_migration', no_run), patch.object(router, 'set_job') as save, \
             patch.object(router, 'set_progress'):
            for selected, filters in cases:
                with self.subTest(selected=selected):
                    async def start():
                        result = await router.start_migration(migration_request(), router.StartMigrationPayload(
                            target_access_token='t', target_instance_url='https://target.salesforce.com',
                            selected_objects=selected, object_filters=filters))
                        await asyncio.sleep(0)
                        return result
                    response = asyncio.run(start())
                    self.assertEqual(filters, save.call_args.args[0].object_filters)
                    self.assertFalse(save.call_args.args[0].product_scoped)
                    self.assertTrue(set(response['dep_order']).issubset(filters) or not filters)

    def test_owner_persists_with_completed_job_and_legacy_job_is_inaccessible(self):
        job = self.job()
        job.status = 'completed'
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(job_store, '_PERSIST_DIR', directory), \
             patch.object(job_store, '_JOBS_FILE', os.path.join(directory, 'jobs.json')), \
             patch.object(job_store, '_jobs', {job.job_id: job}):
            job_store._save_jobs()
            with open(job_store._JOBS_FILE) as saved:
                persisted = json.load(saved)
            self.assertEqual('owner-a', persisted[job.job_id]['migration_owner_id'])
            self.assertNotIn('target-secret', str(persisted))
            job_store._jobs.clear()
            job_store._load_jobs()
            self.assertEqual('owner-a', job_store.get_job(job.job_id).migration_owner_id)
            persisted[job.job_id].pop('migration_owner_id')
            with open(job_store._JOBS_FILE, 'w') as saved:
                json.dump(persisted, saved)
            job_store._jobs.clear()
            job_store._load_jobs()
            with patch.object(router, 'get_job', return_value=job_store.get_job(job.job_id)):
                with self.assertRaises(HTTPException) as rejected:
                    asyncio.run(router.get_result(job.job_id, migration_request(owner='owner-a')))
                self.assertEqual(404, rejected.exception.status_code)

    def test_running_job_with_inserted_ids_survives_restart_as_stopped(self):
        from backend.migrator.job_store import ObjectMigrationResult
        job = self.job()
        job.status = 'running'
        job.object_results['Product2'] = ObjectMigrationResult('Product2', inserted_ids=[G])
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(job_store, '_PERSIST_DIR', directory), \
             patch.object(job_store, '_JOBS_FILE', os.path.join(directory, 'jobs.json')), \
             patch.object(job_store, '_jobs', {}):
            job_store.set_job(job)
            job_store._jobs.clear()
            job_store._load_jobs()
            recovered = job_store.get_job(job.job_id)
            self.assertIsNotNone(recovered)
            self.assertEqual('stopped', recovered.status)
            self.assertEqual([G], recovered.object_results['Product2'].inserted_ids)

    def test_start_and_rollback_reject_unsafe_target_origins(self):
        job = self.job()
        from backend.migrator.job_store import ObjectMigrationResult
        job.status = 'completed'
        job.object_results['Product2'] = ObjectMigrationResult('Product2', inserted_ids=[G])
        unsafe = ('http://target.salesforce.com', 'https://localhost', 'https://127.0.0.1',
                  'https://10.0.0.1', 'https://target.salesforce.com.evil.test',
                  'https://user@target.salesforce.com', 'https://target.salesforce.com/path',
                  'https://target.salesforce.com?x=1', 'https://target.salesforce.com#fragment',
                  'https://target.salesforce.com:443', 'https://target.force.com@evil.test')
        unsafe += ('https://target.salesforce.com\n', 'https://target.salesforce.com?',
                   'https://target.salesforce.com#', 'https://target.salesforce.com//',
                   'https://-bad.salesforce.com', 'https://.salesforce.com')
        with patch.object(router, 'set_job') as save, patch.object(router.asyncio, 'create_task') as task, \
             patch.object(router, 'get_job', return_value=job):
            for url in unsafe:
                with self.subTest(url=url):
                    with self.assertRaises(HTTPException) as rejected:
                        asyncio.run(router.start_migration(migration_request(), router.StartMigrationPayload(
                            target_access_token='target-secret', target_instance_url=url, selected_objects=['Product2'])))
                    self.assertEqual(400, rejected.exception.status_code)
                    with self.assertRaises(HTTPException) as rejected:
                        asyncio.run(router.rollback(job.job_id, router.RollbackPayload(
                            target_access_token='target-secret', target_instance_url=url), migration_request(owner='owner-a')))
                    self.assertEqual(400, rejected.exception.status_code)
            save.assert_not_called()
            task.assert_not_called()

    def test_target_origin_accepts_salesforce_https_origins(self):
        self.assertEqual('https://target.salesforce.com',
                         router._target_origin('https://target.salesforce.com/'))
        self.assertEqual('https://example.force.com',
                         router._target_origin('https://example.force.com'))


class FakeSource:
    def __init__(self, rows=None, available=None, error=None):
        self.rows = rows or {}
        self.available = set(available or self.rows) | {'Product2'}
        self.error = error
        self.queries = []
        self.fields = {}

    async def describe_object(self, obj):
        return {'fields': [{'name': f} for f in self.fields.get(obj, set().union(*(r.keys() for r in self.rows.get(obj, []))) | {'Id', 'BasedOnId', 'UnitOfMeasureId', 'ParentProductId', 'ChildProductId', 'ChildProductClassificationId', 'ProductComponentGroupId', 'ParentProductClassificationId', 'PicklistId', 'AttributeDefinitionId', 'AttributeCategoryId', 'ProductCategoryId', 'CatalogId', 'Pricebook2Id', 'CostBookId', 'ProductSellingModelId', 'ProrationPolicyId', 'UnitOfMeasureClassId', 'ProductRelationshipTypeId'})]}

    async def list_sobjects(self):
        return list(self.available)

    async def query(self, soql):
        import re
        self.queries.append(soql)
        obj = re.search(r'\bFROM (\w+)', soql).group(1)
        if self.error == obj:
            raise RuntimeError('source query unavailable')
        if obj not in self.available:
            raise AssertionError(f'queried absent object {obj}')
        fields = [f.strip() for f in soql.split('SELECT ', 1)[1].split(' FROM ', 1)[0].split(',')]
        where = soql.split(' WHERE ', 1)[1] if ' WHERE ' in soql else ''
        match = re.search(r'(\w+) IN \(([^)]*)\)', where)
        ids = set(re.findall(r"'([^']+)'", match.group(2))) if match else set()
        selected = [r for r in self.rows.get(obj, []) if not match or r.get(match.group(1)) in ids]
        return {'records': [{f: r.get(f) for f in fields} for r in selected], 'done': True}


class ScopeTests(unittest.TestCase):
    def category_engine(self, rows, candidates=(), scoped=False, target_fields=None, mode='upsert'):
        job = MigrationJob('category-pair', 'https://s', 'https://t', mode,
                           ['AttributeCategory'], ['AttributeCategory'],
                           object_filters={'AttributeCategory': f"Id IN ('{G}', '{H}')"} if scoped else {},
                           product_scoped=scoped)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        fields = [{'name': name, 'type': 'string', 'createable': True, 'updateable': True}
                  for name in ('Name', 'Code', 'Description')]
        fields.append({'name': 'OwnerId', 'type': 'reference', 'referenceTo': ['User'],
                       'createable': True, 'updateable': True})
        async def desc(token, url, obj):
            return {'createable': True, 'updateable': True,
                    'fields': fields if url == 'https://s' else (target_fields or fields)}
        async def source(soql):
            names = [part.strip() for part in soql.split('SELECT ', 1)[1].split(' FROM ', 1)[0].split(',')]
            return [{name: row.get(name) for name in names} for row in rows]
        async def no_op(): pass
        engine.rl_source.acquire = engine.rl_target.acquire = no_op
        engine._query_all = source
        queries = []
        class Response:
            def __init__(self, body): self.body = body
            def raise_for_status(self): pass
            def json(self): return self.body
        class Client:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def get(self, url, **kwargs):
                if 'next' in url:
                    return Response({'records': list(candidates[1:]), 'done': True})
                queries.append(kwargs['params']['q'])
                return Response({'records': list(candidates[:1]), 'done': len(candidates) <= 1,
                                 'nextRecordsUrl': '/next' if len(candidates) > 1 else None})
        class Bulk:
            def __init__(self): self.calls = []; self.csvs = []
            async def create_ingest_job(self, *args): self.calls.append(args); return str(len(self.calls))
            async def upload_job_data(self, job_id, data): self.csvs.append(data)
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, job_id):
                if self.calls[int(job_id)-1][1] == 'update':
                    return [{'sf__Id': row['Id'], 'sf__Created': 'false'}
                            for row in csv.DictReader(io.StringIO(self.csvs[int(job_id)-1]))]
                return [{'sf__Id': T, 'sf__Created': 'true', **row}
                        for row in csv.DictReader(io.StringIO(self.csvs[int(job_id)-1]))]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        engine.target_bulk = Bulk()
        return engine, job, desc, Client, queries

    def test_category_pair_update_insert_mapping_and_rollback(self):
        rows = [{'Id': G, 'Name': 'Same', 'Code': 'A', 'Description': 'changed', 'OwnerId': P},
                {'Id': H, 'Name': 'New', 'Code': 'B', 'Description': 'new'}]
        engine, job, desc, client, queries = self.category_engine(
            rows, [{'Id': R, 'Name': 'Same', 'Code': 'A'}])
        async def no_name_map(*args): raise AssertionError('name-only map used')
        engine._build_id_map = no_name_map
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client), \
             patch('backend.migrator.engine.set_job'), patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        result = job.object_results['AttributeCategory']
        self.assertEqual(('done', 1, 1, 0), (result.status, result.inserted, result.updated, result.failed))
        self.assertEqual({G: R, H: T}, engine._id_map['AttributeCategory'])
        self.assertEqual(R, engine._resolve_lookup('AttributeCategory', G))
        self.assertEqual(T, engine._resolve_lookup('AttributeCategory', H))
        self.assertEqual([T], result.inserted_ids)
        self.assertEqual(['update', 'insert'], [c[1] for c in engine.target_bulk.calls])
        self.assertIn('Id', next(csv.reader(io.StringIO(engine.target_bulk.csvs[0]))))
        self.assertNotIn('OwnerId', ''.join(engine.target_bulk.csvs))
        self.assertTrue(any('Name IN' in q for q in queries))
        self.assertTrue(any('Code IN' in q for q in queries))

    def test_product_scoped_insert_mode_reconciles_category_for_children(self):
        rows = [{'Id': G, 'Name': 'Same', 'Code': 'A', 'Description': 'changed'},
                {'Id': H, 'Name': 'New', 'Code': 'B'}]
        engine, job, desc, client, _ = self.category_engine(
            rows, [{'Id': R, 'Name': 'Same', 'Code': 'A'}], scoped=True, mode='insert')
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client), \
             patch('backend.migrator.engine.set_job'), patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine._preflight_product_references())
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        self.assertEqual('done', job.object_results['AttributeCategory'].status)
        self.assertEqual({G: R, H: T}, engine._id_map['AttributeCategory'])
        self.assertEqual([T], job.object_results['AttributeCategory'].inserted_ids)
        self.assertEqual(['update', 'insert'], [call[1] for call in engine.target_bulk.calls])

    def test_category_exact_match_without_other_fields_reuses_target_without_bulk_update(self):
        rows = [{'Id': G, 'Name': 'Same', 'Code': 'A'}]
        engine, job, desc, client, _ = self.category_engine(rows, [{'Id': R, 'Name': 'Same', 'Code': 'A'}])
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client):
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        self.assertEqual('done', job.object_results['AttributeCategory'].status)
        self.assertEqual({G: R}, engine._id_map['AttributeCategory'])
        self.assertEqual([], engine.target_bulk.calls)

    def test_category_read_only_exact_match_reuses_target_without_update(self):
        rows = [{'Id': G, 'Name': 'Same', 'Code': 'A'}]
        engine, job, desc, client, _ = self.category_engine(rows, [{'Id': R, 'Name': 'Same', 'Code': 'A'}])
        async def read_only_target(token, url, obj):
            metadata = await desc(token, url, obj)
            if url == 'https://t':
                metadata['updateable'] = False
            return metadata
        with patch('backend.migrator.engine.describe_object', read_only_target), \
             patch('backend.migrator.engine.httpx.AsyncClient', client):
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        self.assertEqual('done', job.object_results['AttributeCategory'].status)
        self.assertEqual({G: R}, engine._id_map['AttributeCategory'])
        self.assertEqual([], engine.target_bulk.calls)

    def test_category_conflicts_ambiguity_and_invalid_source_before_write(self):
        valid = [{'Id': G, 'Name': 'Same', 'Code': 'A'}]
        cases = [
            (valid, [{'Id': R, 'Name': 'Same', 'Code': 'other'}], 'collision'),
            (valid, [{'Id': R, 'Name': 'Same', 'Code': 'A'}, {'Id': T, 'Name': 'Same', 'Code': 'A'}], 'Ambiguous'),
            (valid, [{'Id': R, 'Name': 'Same', 'Code': 'other'}, {'Id': T, 'Name': 'other', 'Code': 'A'}], 'collision'),
            (valid, [{'Id': R, 'Name': 'same', 'Code': 'a'}], 'collision'),
            (valid, [{'Id': R, 'Name': 'Sáme', 'Code': 'A'}], 'collision'),
            ([{'Id': G, 'Name': ' ', 'Code': 'A'}], [], 'Missing'),
            ([{'Id': G, 'Name': 'Same', 'Code': 'A'}, {'Id': H, 'Name': 'Same', 'Code': 'B'}], [], 'Duplicate'),
            ([{'Id': G, 'Name': 'Same', 'Code': 'A'}, {'Id': H, 'Name': 'Other', 'Code': 'A'}], [], 'Duplicate'),
            ([{'Id': G, 'Name': 'Same', 'Code': 'A'}, {'Id': H, 'Name': 'same', 'Code': 'B'}], [], 'Duplicate'),
        ]
        for rows, candidates, error in cases:
            with self.subTest(error=error, rows=rows, candidates=candidates):
                engine, job, desc, client, _ = self.category_engine(rows, candidates)
                with patch('backend.migrator.engine.describe_object', desc), \
                     patch('backend.migrator.engine.httpx.AsyncClient', client):
                    asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
                self.assertEqual('failed', job.object_results['AttributeCategory'].status)
                self.assertIn(error, job.object_results['AttributeCategory'].error)
                self.assertEqual([], engine.target_bulk.calls)

    def test_category_unresolved_lookup_does_not_succeed_silently(self):
        rows = [{'Id': G, 'Name': 'New', 'Code': 'A', 'ParentId': H}]
        engine, job, desc, client, _ = self.category_engine(rows)
        base_desc = desc
        async def with_parent(token, url, obj):
            info = await base_desc(token, url, obj)
            info['fields'] = info['fields'] + [{'name': 'ParentId', 'type': 'reference',
                'referenceTo': ['AttributeDefinition'], 'createable': True, 'updateable': True}]
            return info
        with patch('backend.migrator.engine.describe_object', with_parent), \
             patch('backend.migrator.engine.httpx.AsyncClient', client):
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        self.assertEqual('failed', job.object_results['AttributeCategory'].status)
        self.assertIn('Unresolved', job.object_results['AttributeCategory'].error)
        self.assertEqual([], engine.target_bulk.calls)

    def test_category_scoped_preflight_detects_pairs_and_execution_drift(self):
        rows = [{'Id': G, 'Name': 'Same', 'Code': 'A'}]
        engine, job, desc, client, _ = self.category_engine(rows, [], scoped=True)
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client):
            asyncio.run(engine._preflight_product_references())
            rows[0]['Code'] = 'B'
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        self.assertEqual('failed', job.object_results['AttributeCategory'].status)
        self.assertIn('changed', job.object_results['AttributeCategory'].error)
        self.assertEqual([], engine.target_bulk.calls)

    def test_category_scoped_preflight_rejects_target_collision_before_bulk(self):
        engine, job, desc, client, _ = self.category_engine(
            [{'Id': G, 'Name': 'Same', 'Code': 'A'}],
            [{'Id': R, 'Name': 'Same', 'Code': 'Other'}], scoped=True)
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client):
            with self.assertRaisesRegex(ValueError, 'collision'):
                asyncio.run(engine._preflight_product_references())
        self.assertEqual([], engine.target_bulk.calls)

    def test_category_target_field_permission_checked_before_write(self):
        rows = [{'Id': G, 'Name': 'Same', 'Code': 'A', 'Description': 'nonempty'}]
        fields = [{'name': n, 'type': 'string', 'createable': True, 'updateable': n != 'Description'}
                  for n in ('Name', 'Code', 'Description')]
        engine, job, desc, client, _ = self.category_engine(rows, [{'Id': R, 'Name': 'Same', 'Code': 'A'}], target_fields=fields)
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client):
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        self.assertEqual('failed', job.object_results['AttributeCategory'].status)
        self.assertIn('Description', job.object_results['AttributeCategory'].error)
        self.assertEqual([], engine.target_bulk.calls)

    def test_category_target_pagination_escape_and_batch_limit(self):
        rows = [{'Id': f'a{i:017d}', 'Name': f"N{i}'\\", 'Code': f'C{i}'} for i in range(501)]
        engine, job, desc, client, queries = self.category_engine(rows)
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client), \
             patch('backend.migrator.engine.set_job'), patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        self.assertEqual('done', job.object_results['AttributeCategory'].status)
        self.assertEqual(501, job.object_results['AttributeCategory'].inserted)
        self.assertEqual(4, len(queries))
        self.assertIn("N0\\'\\\\", queries[0])
        self.assertTrue(all(q.count("', '") < 500 for q in queries))

    def test_category_bulk_partial_failure_preserves_insert_ids_for_rollback(self):
        rows = [{'Id': G, 'Name': 'New', 'Code': 'A'}, {'Id': H, 'Name': 'Other', 'Code': 'B'}]
        engine, job, desc, client, _ = self.category_engine(rows)
        async def successes(job_id): return [{'sf__Id': T, 'sf__Created': 'true', 'Name': 'New', 'Code': 'A'}]
        async def failures(job_id): return [{'sf__Error': 'rejected', 'Name': 'Other', 'Code': 'B'}]
        engine.target_bulk.get_successful_results = successes
        engine.target_bulk.get_failed_results = failures
        deleted = []
        class DeleteBulk:
            async def create_ingest_job(self, obj, operation):
                self_test.assertEqual(('AttributeCategory', 'delete'), (obj, operation))
                return 'delete'
            async def upload_job_data(self, job_id, data): deleted.append(data)
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args): return [{'sf__Id': T}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        self_test = self
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client), \
             patch('backend.migrator.engine.BulkAPI2', return_value=DeleteBulk()), \
             patch('backend.migrator.engine.set_job'), patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
            self.assertEqual([T], job.object_results['AttributeCategory'].inserted_ids)
            self.assertEqual({G: T}, engine._id_map['AttributeCategory'])
            self.assertEqual('done_with_errors', job.object_results['AttributeCategory'].status)
            asyncio.run(rollback_job(job, 't', 'https://t'))
        self.assertEqual([], job.object_results['AttributeCategory'].inserted_ids)
        self.assertIn(T, deleted[0])
        self.assertNotIn(R, deleted[0])

    def test_category_insert_ids_persist_before_failed_result_fetch(self):
        engine, job, desc, client, _ = self.category_engine([{'Id': G, 'Name': 'New', 'Code': 'A'}])
        async def fail_failed_results(*args):
            raise RuntimeError('failed result endpoint unavailable')
        engine.target_bulk.get_failed_results = fail_failed_results
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client), \
             patch('backend.migrator.engine.set_job') as save, \
             patch('backend.migrator.engine.set_progress') as progress:
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        result = job.object_results['AttributeCategory']
        self.assertEqual('failed', result.status)
        self.assertEqual([T], result.inserted_ids)
        self.assertEqual({G: T}, engine._id_map['AttributeCategory'])
        self.assertTrue(any(call.args[0].object_results['AttributeCategory'].inserted_ids == [T]
                            for call in save.call_args_list))
        progress.assert_called()

    def test_category_records_all_insert_ids_before_result_mapping_error(self):
        rows = [{'Id': G, 'Name': 'New', 'Code': 'A'},
                {'Id': H, 'Name': 'Other', 'Code': 'B'}]
        engine, job, desc, client, _ = self.category_engine(rows)
        async def successes(*args):
            return [{'sf__Id': T, 'Name': 'New', 'Code': 'A'},
                    {'sf__Id': F, 'Name': 'Unexpected', 'Code': 'Z'}]
        engine.target_bulk.get_successful_results = successes
        snapshots = []
        async def fail_failed_results(*args):
            raise RuntimeError('failed results unavailable')
        engine.target_bulk.get_failed_results = fail_failed_results
        def checkpoint(saved):
            snapshots.append((saved.status, list(saved.object_results['AttributeCategory'].inserted_ids)))
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client), \
             patch('backend.migrator.engine.set_job', side_effect=checkpoint), \
             patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        self.assertEqual('failed', job.object_results['AttributeCategory'].status)
        self.assertEqual([T, F], job.object_results['AttributeCategory'].inserted_ids)
        self.assertIn(('running', [T, F]), snapshots)

    def test_category_checkpoint_precedes_success_pair_validation(self):
        engine, job, desc, client, _ = self.category_engine([{'Id': G, 'Name': 'New', 'Code': 'A'}])
        async def successes(*args):
            return [{'sf__Id': T, 'Name': 'Unexpected', 'Code': 'Z'}]
        engine.target_bulk.get_successful_results = successes
        snapshots = []
        def checkpoint(saved):
            category = saved.object_results['AttributeCategory']
            snapshots.append((category.status, list(category.inserted_ids)))
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', client), \
             patch('backend.migrator.engine.set_job', side_effect=checkpoint), \
             patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine._migrate_object('AttributeCategory', 0, 1))
        self.assertEqual('failed', job.object_results['AttributeCategory'].status)
        self.assertIn(('running', [T]), snapshots)

    def test_fallback_external_id_must_be_selectable_and_writable_on_source(self):
        target = {'fields': [{'name': 'GoodKey', 'externalId': True, 'createable': True},
                             {'name': 'ReadOnlyKey', 'externalId': True, 'createable': True},
                             {'name': 'UnqueryableKey', 'externalId': True, 'createable': True},
                             {'name': 'EncryptedKey', 'externalId': True, 'createable': True}]}
        source = {'fields': [{'name': 'GoodKey', 'externalId': True, 'createable': True},
                             {'name': 'ReadOnlyKey', 'externalId': True, 'createable': False},
                             {'name': 'UnqueryableKey', 'externalId': True, 'createable': True,
                              'queryable': False},
                             {'name': 'EncryptedKey', 'externalId': True, 'createable': True,
                              'encrypted': True}]}
        self.assertEqual('GoodKey', find_bulk_ext_id(source, target))

    def test_legacy_org_local_refs_are_never_queried_or_cleaned(self):
        engine, _ = self.migration_engine('insert')
        fields = [{'name': 'Name', 'type': 'string', 'createable': True}]
        fields += [{'name': name, 'type': 'reference', 'referenceTo': ['User'], 'createable': True}
                   for name in ('OwnerId', 'CreatedById', 'LastModifiedById')]
        strategy = engine._scoped_strategy({'fields': fields}, 'AttributeCategory')
        for key in ('creatable_fields', 'queryable_fields'):
            self.assertFalse(set(('OwnerId', 'CreatedById', 'LastModifiedById')) & set(strategy[key]))
        row = {'Id': G, 'Name': 'category', 'OwnerId': H, 'CreatedById': T, 'LastModifiedById': F}
        cleaned = engine._clean_records([row], strategy['creatable_fields'], strategy['lookup_fields'],
                                        strategy['self_lookups'], strategy['key_field'])
        self.assertEqual([{'Name': 'category'}], cleaned)
        self.assertEqual(0, engine._unresolved_lookups)

    def test_org_local_references_are_neither_preflighted_nor_written(self):
        engine, job = self.migration_engine('insert')
        job.product_scoped = engine._product_scoped = True
        job.object_filters = engine._object_filters = {'Product2': f"Id IN ('{P}')"}
        fields = [{'name': 'StockKeepingUnit', 'type': 'string', 'createable': True},
                  {'name': 'OwnerId', 'type': 'reference', 'referenceTo': ['User'], 'createable': True},
                  {'name': 'CreatedById', 'type': 'reference', 'referenceTo': ['User'], 'createable': True},
                  {'name': 'LastModifiedById', 'type': 'reference', 'referenceTo': ['User'], 'createable': True}]
        queries = []
        async def desc(*args): return {'fields': fields}
        async def rows(soql):
            queries.append(soql)
            return [{'Id': P, 'StockKeepingUnit': 'sku', 'OwnerId': G,
                     'CreatedById': H, 'LastModifiedById': T}]
        engine._query_all = rows
        async def no_op(): pass
        engine.rl_source.acquire = engine.rl_target.acquire = no_op
        with patch('backend.migrator.engine.describe_object', desc):
            asyncio.run(engine._preflight_product_references())
        self.assertFalse(any('OwnerId' in q or 'CreatedById' in q for q in queries))
        strategy = engine._scoped_strategy({'fields': fields}, 'Product2')
        clean = engine._clean_records([{'Id': P, 'StockKeepingUnit': 'sku', 'OwnerId': G}],
                                      strategy['creatable_fields'], strategy['lookup_fields'],
                                      strategy['self_lookups'], strategy['key_field'])
        self.assertNotIn('OwnerId', clean[0])
        self.assertNotIn('CreatedById', strategy['creatable_fields'])

    def test_uom_class_cycle_is_deferred_and_resolved(self):
        job = MigrationJob('uom-class', 'https://s', 'https://t', 'insert',
                           ['UnitOfMeasureClass', 'UnitOfMeasure'], ['UnitOfMeasureClass', 'UnitOfMeasure'],
                           object_filters={'UnitOfMeasureClass': f"Id IN ('{G}')",
                                           'UnitOfMeasure': f"Id IN ('{H}', '{T}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        fields = {
            'UnitOfMeasureClass': [{'name': 'Name', 'type': 'string', 'createable': True},
                                   {'name': 'BaseUnitOfMeasureId', 'type': 'reference', 'createable': True,
                                    'referenceTo': ['UnitOfMeasure']},
                                   {'name': 'DefaultUnitOfMeasureId', 'type': 'reference', 'createable': True,
                                    'referenceTo': ['UnitOfMeasure']}],
            'UnitOfMeasure': [{'name': 'Name', 'type': 'string', 'createable': True},
                              {'name': 'UnitOfMeasureClassId', 'type': 'reference', 'createable': True,
                               'referenceTo': ['UnitOfMeasureClass']}],
        }
        rows_by_obj = {'UnitOfMeasureClass': [{'Id': G, 'Name': 'class', 'BaseUnitOfMeasureId': H,
                                               'DefaultUnitOfMeasureId': T}],
                       'UnitOfMeasure': [{'Id': H, 'Name': 'base', 'UnitOfMeasureClassId': G},
                                         {'Id': T, 'Name': 'default', 'UnitOfMeasureClassId': G}]}
        async def desc(token, url, obj): return {'fields': fields[obj]}
        async def rows(soql):
            obj = soql.split(' FROM ', 1)[1].split(' ', 1)[0]
            return rows_by_obj[obj]
        async def no_op(): pass
        engine.rl_source.acquire = engine.rl_target.acquire = no_op
        engine._query_all = rows
        engine._source_records = rows_by_obj
        engine._id_map = {'UnitOfMeasureClass': {G: P}, 'UnitOfMeasure': {H: C, T: N}}
        class Bulk:
            csv = None
            async def create_ingest_job(self, *args): return 'job'
            async def upload_job_data(self, job, csv): self.csv = csv
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args): return [{'sf__Id': P}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        engine.target_bulk = Bulk()
        with patch('backend.migrator.engine.describe_object', desc):
            asyncio.run(engine._preflight_product_references())
        strategy = engine._scoped_strategy({'fields': fields['UnitOfMeasureClass']}, 'UnitOfMeasureClass')
        self.assertEqual(['BaseUnitOfMeasureId', 'DefaultUnitOfMeasureId'], strategy['self_lookups'])
        self.assertNotIn('BaseUnitOfMeasureId', engine._clean_records(rows_by_obj['UnitOfMeasureClass'],
            strategy['creatable_fields'], strategy['lookup_fields'], strategy['self_lookups'], strategy['key_field'])[0])
        asyncio.run(engine._second_pass_self_lookups('UnitOfMeasureClass', strategy))
        self.assertIn(C, engine.target_bulk.csv)
        self.assertIn(N, engine.target_bulk.csv)
        self.assertNotIn(H, engine.target_bulk.csv)

    def test_scoped_upsert_preflights_every_populated_object_before_write(self):
        job = MigrationJob('upsert-all', 'https://s', 'https://t', 'upsert', ['Product2', 'ProductRampSegment'],
                           ['Product2', 'ProductRampSegment'],
                           object_filters={'Product2': f"Id IN ('{P}')", 'ProductRampSegment': f"Id IN ('{G}')"},
                           product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def desc(token, url, obj):
            return {'fields': [{'name': 'StockKeepingUnit' if obj == 'Product2' else 'Name',
                                'type': 'string', 'createable': True,
                                'externalId': obj == 'Product2'}]}
        async def rows(soql):
            return [{'Id': P, 'StockKeepingUnit': 'sku'}] if 'FROM Product2 ' in soql else [{'Id': G, 'Name': 'ramp'}]
        async def no_op(): pass
        engine._query_all = rows
        engine.rl_source.acquire = engine.rl_target.acquire = no_op
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'external ID.*ProductRampSegment|ProductRampSegment.*external ID'):
                asyncio.run(engine._preflight_product_references())
        self.assertEqual({}, job.object_results)

    def test_scoped_upsert_preflight_rejects_missing_fallback_key(self):
        job = MigrationJob('missing-ext', 'https://s', 'https://t', 'upsert',
                           ['Product2'], ['Product2'],
                           object_filters={'Product2': f"Id IN ('{P}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        source_fields = [{'name': 'ZPrimaryKey', 'type': 'string', 'createable': True,
                          'externalId': True},
                         {'name': 'ASecondaryKey', 'type': 'string', 'createable': True,
                          'externalId': True}]
        async def desc(token, url, obj):
            fields = [dict(f) for f in source_fields]
            if url == 'https://t':
                fields[0]['externalId'] = False
            return {'createable': True, 'fields': fields}
        async def rows(soql):
            return [{'Id': P, 'ZPrimaryKey': 'item', 'ASecondaryKey': None}]
        async def no_op(): pass
        engine.rl_source.acquire = engine.rl_target.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'Missing.*external ID.*Product2'):
                asyncio.run(engine._preflight_product_references())
        self.assertEqual({}, job.object_results)

    def test_scoped_preflight_rejects_same_count_changed_ids_and_blank_key(self):
        for changed in (True, False):
            with self.subTest(changed=changed):
                job = MigrationJob('scope-drift', 'https://s', 'https://t', 'insert',
                                   ['Product2'], ['Product2'],
                                   object_filters={'Product2': f"Id IN ('{P}')"}, product_scoped=True)
                with patch('backend.migrator.engine.RateLimiter'):
                    engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
                async def desc(*args):
                    return {'createable': True, 'fields': [{'name': 'StockKeepingUnit', 'type': 'string',
                                                            'createable': True}]}
                async def rows(soql):
                    if soql.startswith('SELECT Id FROM '):
                        return [{'Id': P}]
                    return [{'Id': C if changed else P, 'StockKeepingUnit': 'sku' if changed else '   '}]
                async def no_op(): pass
                engine.rl_source.acquire = engine.rl_target.acquire = no_op
                engine._query_all = rows
                with patch('backend.migrator.engine.describe_object', desc):
                    with self.assertRaisesRegex(ValueError, 'changed|mapping key'):
                        asyncio.run(engine._preflight_product_references())
                self.assertEqual({}, job.object_results)

    def test_scoped_migration_rejects_rows_outside_preflight_ids(self):
        engine, job = self.migration_engine('insert')
        job.product_scoped = engine._product_scoped = True
        job.object_filters = engine._object_filters = {'Product2': f"Id IN ('{P}')"}
        engine._preflight_ids = {'Product2': {P}}
        async def desc(*args):
            return {'fields': [{'name': 'StockKeepingUnit', 'type': 'string', 'createable': True}]}
        async def rows(*args): return [{'Id': C, 'StockKeepingUnit': 'replacement'}]
        engine._query_all = rows
        class Bulk:
            def __init__(self): self.calls = []
            async def create_ingest_job(self, *args): self.calls.append(args)
        engine.target_bulk = Bulk()
        with patch('backend.migrator.engine.describe_object', desc):
            asyncio.run(engine._migrate_object('Product2', 0, 1))
        self.assertEqual('failed', job.object_results['Product2'].status)
        self.assertIn('changed', job.object_results['Product2'].error)
        self.assertEqual([], engine.target_bulk.calls)

    def test_keyless_scoped_preflight_allows_insert_only_for_creatable_target(self):
        for mode, createable in (('insert', True), ('insert', False), ('upsert', True)):
            with self.subTest(mode=mode, createable=createable):
                job = MigrationJob('keyless-preflight', 'https://s', 'https://t', mode,
                                   ['ProductRampSegment'], ['ProductRampSegment'],
                                   object_filters={'ProductRampSegment': f"Id IN ('{R}')"}, product_scoped=True)
                with patch('backend.migrator.engine.RateLimiter'):
                    engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
                async def desc(token, url, obj):
                    return {'createable': createable if url == 'https://t' else True,
                            'fields': [{'name': 'Id', 'type': 'id'},
                                       {'name': 'Name', 'type': 'string', 'createable': False}]}
                async def rows(soql): return [{'Id': R}]
                async def no_op(): pass
                engine.rl_source.acquire = engine.rl_target.acquire = no_op
                engine._query_all = rows
                with patch('backend.migrator.engine.describe_object', desc):
                    if mode == 'insert' and createable:
                        asyncio.run(engine._preflight_product_references())
                    else:
                        with self.assertRaisesRegex(ValueError, 'Insert Only|createable'):
                            asyncio.run(engine._preflight_product_references())
                self.assertEqual({}, job.object_results)

    def test_keyless_scoped_rest_posts_mapped_rows_and_tracks_rollback_on_failure(self):
        job = MigrationJob('keyless-rest', 'https://s', 'https://t', 'insert',
                           ['ProductRelatedComponent'], ['ProductRelatedComponent'],
                           object_filters={'ProductRelatedComponent': f"Id IN ('{R}', '{H}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        engine._id_map['Product2'] = {P: C}
        rows = [{'Id': R, 'Name': 'generated', 'ChildProductId': P, 'ReadOnly': 'no'},
                {'Id': H, 'Name': 'generated2', 'ChildProductId': P, 'ReadOnly': 'no'}]
        async def desc(*args):
            return {'createable': True, 'fields': [{'name': 'Id', 'type': 'id', 'createable': False},
                               {'name': 'Name', 'type': 'string', 'createable': False},
                               {'name': 'ReadOnly', 'type': 'string', 'createable': False},
                               {'name': 'ChildProductId', 'type': 'reference', 'referenceTo': ['Product2'],
                                'createable': True, 'nillable': False}]}
        async def source_rows(*args): return rows
        engine._query_all = source_rows
        async def no_op(): pass
        engine.rl_source.acquire = engine.rl_target.acquire = no_op
        class NoBulk:
            async def create_ingest_job(self, *args): raise AssertionError('keyless row used Bulk')
        engine.target_bulk = NoBulk()
        posts = []
        deleted = []
        saved_counts = []
        class DeleteBulk:
            async def create_ingest_job(self, obj, operation):
                self_test.assertEqual(('ProductRelatedComponent', 'delete'), (obj, operation))
                return 'delete-job'
            async def upload_job_data(self, job_id, csv): deleted.append(csv)
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args): return [{'sf__Id': G}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        self_test = self
        class Response:
            def __init__(self, status, body): self.status_code, self.body = status, body
            def json(self): return self.body
        class Client:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def post(self, url, **kwargs):
                posts.append((url, kwargs))
                return Response(201, {'id': G, 'success': True, 'errors': []}) if len(posts) == 1 else Response(400, [{'message': 'rejected'}])
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.httpx.AsyncClient', Client), \
             patch('backend.migrator.engine.BulkAPI2', return_value=DeleteBulk()), \
             patch('backend.migrator.engine.set_job') as saved, \
             patch('backend.migrator.engine.set_progress'):
            saved.side_effect = lambda current: saved_counts.append(current.total_inserted)
            asyncio.run(engine._migrate_object('ProductRelatedComponent', 0, 1))
            asyncio.run(rollback_job(job, 't', 'https://t'))
        result = job.object_results['ProductRelatedComponent']
        self.assertEqual('failed', result.status)
        self.assertEqual((1, 0), (result.inserted, result.updated))
        self.assertEqual([], result.inserted_ids)
        self.assertEqual({R: G}, engine._id_map['ProductRelatedComponent'])
        self.assertEqual(1, job.total_inserted)
        self.assertIn(1, saved_counts)
        self.assertIs(saved.call_args.args[0].object_results['ProductRelatedComponent'], result)
        self.assertEqual(2, len(posts))
        self.assertTrue(all(url == 'https://t/services/data/v62.0/sobjects/ProductRelatedComponent/' for url, _ in posts))
        self.assertTrue(all(kwargs['json'] == {'ChildProductId': C} for _, kwargs in posts))
        self.assertTrue(all(kwargs['headers']['Authorization'] == 'Bearer t' for _, kwargs in posts))
        self.assertEqual(1, len(deleted))
        self.assertIn(G, deleted[0])
        self.assertNotIn(H, deleted[0])

    def test_keyless_rest_rejects_missing_id_and_unresolved_required_lookup(self):
        job = MigrationJob('keyless-invalid', 'https://s', 'https://t', 'insert',
                           ['ProductRampSegment'], ['ProductRampSegment'],
                           object_filters={'ProductRampSegment': f"Id IN ('{R}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def desc(*args):
            return {'createable': True, 'fields': [{'name': 'ProductId', 'type': 'reference', 'referenceTo': ['Product2'],
                                'createable': True, 'nillable': False}]}
        async def no_op(): pass
        engine.rl_source.acquire = engine.rl_target.acquire = no_op
        calls = []
        class Client:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def post(self, *args, **kwargs):
                calls.append(kwargs)
                class Response:
                    status_code = 201
                    def json(self): return {'success': True}
                return Response()
        async def rows(*args): return [{'Id': R, 'ProductId': P}]
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc), patch('backend.migrator.engine.httpx.AsyncClient', Client):
            asyncio.run(engine._migrate_object('ProductRampSegment', 0, 1))
            self.assertIn('Unresolved lookup', job.object_results['ProductRampSegment'].error)
            self.assertEqual([], calls)
            engine._id_map['Product2'] = {P: C}
            asyncio.run(engine._migrate_object('ProductRampSegment', 0, 1))
        self.assertIn('Id', job.object_results['ProductRampSegment'].error)
        self.assertEqual([], job.object_results['ProductRampSegment'].inserted_ids)
        self.assertEqual(1, len(calls))

    def test_large_expansion_fails_before_generating_oversized_scope(self):
        children = [f'a{i:017d}' for i in range(151)]
        source = FakeSource({'Product2': [{'Id': P}], 'ProductComponentGroup': [{'Id': i, 'ParentProductId': P} for i in children]})
        with self.assertRaises(HTTPException) as raised:
            self.plan(source)
        self.assertIn('limit', str(raised.exception.detail).lower())

    def test_excluded_values_scope_uses_value_and_attribute_ids(self):
        source = FakeSource({'Product2': [{'Id': P}],
            'ProductAttributeDefinition': [{'Id': R, 'Product2Id': P, 'AttributeDefinitionId': G},
                                           {'Id': C, 'Product2Id': N, 'AttributeDefinitionId': G}],
            'AttributeDefinition': [{'Id': G, 'PicklistId': H}],
            'AttributePicklist': [{'Id': H}],
            'AttributePicklistValue': [{'Id': T, 'PicklistId': H}, {'Id': F, 'PicklistId': H},
                                       {'Id': N, 'PicklistId': C}],
            'AttrPicklistExcludedValue': [{'Id': 'a00000000000007AAA', 'AttributePicklistValueId': T, 'AttributeId': R},
                                          {'Id': 'a00000000000008AAA', 'AttributePicklistValueId': F, 'AttributeId': C},
                                          {'Id': 'a00000000000009AAA', 'AttributePicklistValueId': N, 'AttributeId': R},
                                          {'Id': 'a00000000000010AAA', 'AttributePicklistValueId': F, 'AttributeId': G}]})
        source.fields['AttrPicklistExcludedValue'] = {'Id', 'AttributePicklistValueId', 'AttributeId'}
        scope = self.plan(source)
        self.assertEqual("Id IN ('a00000000000007AAA')", scope['filters']['AttrPicklistExcludedValue'])
        self.assertTrue(all('PicklistId' not in q for q in source.queries if 'FROM AttrPicklistExcludedValue' in q))

    def test_classification_attribute_exclusion_uses_selected_instance(self):
        source = FakeSource({'Product2': [{'Id': P, 'BasedOnId': G}],
            'ProductClassification': [{'Id': G}],
            'ProductClassificationAttr': [{'Id': R, 'ProductClassificationId': G, 'AttributeDefinitionId': H},
                                          {'Id': C, 'ProductClassificationId': N, 'AttributeDefinitionId': H}],
            'AttributeDefinition': [{'Id': H, 'PicklistId': T}],
            'AttributePicklist': [{'Id': T}],
            'AttributePicklistValue': [{'Id': F, 'PicklistId': T}],
            'AttrPicklistExcludedValue': [{'Id': 'a00000000000007AAA', 'AttributePicklistValueId': F, 'AttributeId': R},
                                          {'Id': 'a00000000000008AAA', 'AttributePicklistValueId': F, 'AttributeId': C}]})
        self.assertEqual("Id IN ('a00000000000007AAA')", self.plan(source)['filters']['AttrPicklistExcludedValue'])

    def test_pad_pca_cross_classification_closure_is_scoped(self):
        root, foreign, sibling = G, H, T
        linked, unrelated = R, F
        definition, category, uom = 'a00000000000011AAA', 'a00000000000012AAA', 'a00000000000013AAA'
        source = FakeSource({
            'Product2': [{'Id': P}],
            'ProductAttributeDefinition': [
                {'Id': C, 'Product2Id': P, 'ProductClassificationAttributeId': linked},
                {'Id': N, 'Product2Id': C, 'ProductClassificationAttributeId': unrelated}],
            'ProductClassificationAttr': [
                {'Id': linked, 'ProductClassificationId': foreign, 'AttributeDefinitionId': definition,
                 'AttributeCategoryId': category, 'UnitOfMeasureId': uom},
                {'Id': unrelated, 'ProductClassificationId': foreign, 'AttributeDefinitionId': sibling}],
            'ProductClassification': [{'Id': foreign, 'ParentProductClassificationId': root},
                                      {'Id': root}],
            'AttributeDefinition': [{'Id': definition}, {'Id': sibling}],
            'AttributeCategory': [{'Id': category}],
            'UnitOfMeasure': [{'Id': uom}],
        })
        scope = self.plan(source)['filters']
        self.assertEqual(f"Id IN ('{C}')", scope['ProductAttributeDefinition'])
        self.assertEqual(f"Id IN ('{linked}')", scope['ProductClassificationAttr'])
        self.assertEqual(f"Id IN ('{root}', '{foreign}')", scope['ProductClassification'])
        self.assertEqual(f"Id IN ('{definition}')", scope['AttributeDefinition'])
        self.assertEqual(f"Id IN ('{category}')", scope['AttributeCategory'])
        self.assertEqual(f"Id IN ('{uom}')", scope['UnitOfMeasure'])
        self.assertNotIn(unrelated, str(scope))
        self.assertNotIn(sibling, str(scope))
        self.assertTrue(all(' WHERE ' in q for q in source.queries))

    def test_pad_pca_missing_parent_fails_scope(self):
        for missing, expected in (
            ('ProductClassificationAttr', 'ProductClassificationAttr'),
            ('ProductClassification', 'ProductClassification'),
            ('ancestor', 'ProductClassification'),
            ('AttributeDefinition', 'AttributeDefinition'),
            ('AttributeCategory', 'AttributeCategory'),
            ('UnitOfMeasure', 'UnitOfMeasure'),
        ):
            with self.subTest(missing=missing):
                source = FakeSource({
                    'Product2': [{'Id': P}],
                    'ProductAttributeDefinition': [{'Id': C, 'Product2Id': P,
                                                    'ProductClassificationAttributeId': R}],
                    'ProductClassificationAttr': [{'Id': R, 'ProductClassificationId': H,
                                                   'AttributeDefinitionId': T, 'AttributeCategoryId': F,
                                                   'UnitOfMeasureId': G}],
                    'ProductClassification': [{'Id': H, 'ParentProductClassificationId': N}, {'Id': N}],
                    'AttributeDefinition': [{'Id': T}], 'AttributeCategory': [{'Id': F}],
                    'UnitOfMeasure': [{'Id': G}],
                })
                if missing == 'ancestor':
                    source.rows['ProductClassification'].pop()
                else:
                    source.rows[missing].clear()
                with self.assertRaises(HTTPException) as raised:
                    self.plan(source)
                self.assertIn(expected, str(raised.exception.detail))

    def test_based_on_classification_keeps_ancestor_attributes(self):
        source = FakeSource({
            'Product2': [{'Id': P, 'BasedOnId': H}],
            'ProductClassification': [{'Id': H, 'ParentProductClassificationId': G}, {'Id': G}],
            'ProductClassificationAttr': [{'Id': R, 'ProductClassificationId': G,
                                           'AttributeDefinitionId': T}],
            'AttributeDefinition': [{'Id': T}],
        })
        scope = self.plan(source)['filters']
        self.assertEqual(f"Id IN ('{R}')", scope['ProductClassificationAttr'])
        self.assertEqual(f"Id IN ('{T}')", scope['AttributeDefinition'])

    def test_exclusion_dependencies_are_acyclic_and_ordered(self):
        parents = {'AttributePicklistValue', 'ProductAttributeDefinition', 'ProductClassificationAttr'}
        self.assertEqual(parents, set(OBJECT_DEPS['AttrPicklistExcludedValue']))
        order = asyncio.run(router.dependency_order(router.DependencyOrderPayload(
            selected_objects=['AttrPicklistExcludedValue'])))['order']
        self.assertEqual(len(order), len(set(order)))
        self.assertTrue(all(order.index(parent) < order.index('AttrPicklistExcludedValue') for parent in parents))

    def test_override_scope_requires_group_and_selected_product_context(self):
        source = FakeSource({'Product2': [{'Id': P}, {'Id': C}],
            'ProductComponentGroup': [{'Id': G, 'ParentProductId': P}],
            'ProductComponentGrpOverride': [{'Id': R, 'ProductComponentGroupId': G, 'OverrideContextId': P},
                                            {'Id': H, 'ProductComponentGroupId': G, 'OverrideContextId': C}]})
        scope = self.plan(source)
        self.assertIn(R, scope['filters']['ProductComponentGrpOverride'])
        self.assertNotIn(H, scope['filters']['ProductComponentGrpOverride'])
        self.assertTrue(any('ProductComponentGrpOverride' in o['name'] for g in OBJECT_GROUPS[:2] for o in g['objects']))

    def test_ramp_segment_is_product_bundle_member_and_scoped(self):
        source = FakeSource({'Product2': [{'Id': P}],
                             'ProductRampSegment': [{'Id': R, 'ProductId': P, 'ProductSellingModelId': G}],
                             'ProductSellingModel': [{'Id': G}, {'Id': H}]})
        self.assertIn('ProductRampSegment', PRODUCT_BUNDLE_OBJECTS)
        self.assertIn(P, self.plan(source)['filters']['ProductRampSegment'])
        self.assertEqual(f"Id IN ('{G}')", self.plan(source)['filters']['ProductSellingModel'])
        self.assertIn('Product2', OBJECT_DEPS['ProductRampSegment'])
        self.assertIn('ProductSellingModel', OBJECT_DEPS['ProductRampSegment'])
        order = asyncio.run(router.dependency_order(router.DependencyOrderPayload(
            selected_objects=['ProductRampSegment'])))['order']
        self.assertLess(order.index('ProductSellingModel'), order.index('ProductRampSegment'))

    def test_classification_parent_is_deferred_when_acyclic_and_updateable(self):
        job = MigrationJob('class-parent', 'https://s', 'https://t', 'insert',
                           ['ProductClassification'], ['ProductClassification'],
                           object_filters={'ProductClassification': f"Id IN ('{G}', '{H}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        rows = [{'Id': G, 'Name': 'root'}, {'Id': H, 'Name': 'child', 'ParentProductClassificationId': G}]
        fields = [{'name': 'Name', 'type': 'string', 'createable': True},
                  {'name': 'ParentProductClassificationId', 'type': 'reference', 'createable': True,
                   'referenceTo': ['ProductClassification']}]
        async def desc(token, url, obj):
            return {'createable': True, 'fields': [fields[0], {**fields[1], 'updateable': updateable}] if url == 'https://t' else fields}
        async def query(*args): return rows
        async def no_op(): pass
        engine.rl_source.acquire = engine.rl_target.acquire = no_op
        engine._query_all = query
        for updateable in (False, True):
            with patch('backend.migrator.engine.describe_object', desc):
                asyncio.run(engine._preflight_product_references())
                if not updateable:
                    self.assertEqual([G, H], engine._create_only_self_order['ProductClassification'])
                else:
                    self.assertNotIn('ProductClassification', engine._create_only_self_order)
        strategy = engine._scoped_strategy({'fields': fields}, 'ProductClassification')
        self.assertIn('ParentProductClassificationId', strategy['self_lookups'])
        self.assertNotIn('ParentProductClassificationId', engine._clean_records(
            rows, strategy['creatable_fields'], strategy['lookup_fields'], strategy['self_lookups'], strategy['key_field'])[1])
        engine._source_records['ProductClassification'] = rows
        engine._id_map['ProductClassification'] = {G: P, H: C}
        class Bulk:
            csv = None
            async def create_ingest_job(self, *args): return 'job'
            async def upload_job_data(self, job, csv): self.csv = csv
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args): return [{'sf__Id': C}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        engine.target_bulk = Bulk()
        asyncio.run(engine._second_pass_self_lookups('ProductClassification', strategy))
        self.assertIn(P, engine.target_bulk.csv)
        self.assertNotIn(G, engine.target_bulk.csv)

    def test_create_only_self_refs_insert_parent_first_with_target_ids_and_rollback(self):
        for obj, field in (('ProductClassification', 'ParentProductClassificationId'),
                           ('ProductClassificationAttr', 'OverriddenInheritedAttributeId'),
                           ('ProductAttributeDefinition', 'OverriddenProductAttributeDefinitionId')):
            with self.subTest(obj=obj):
                job = MigrationJob('create-only', 'https://s', 'https://t', 'insert', [obj], [obj],
                                   object_filters={obj: f"Id IN ('{G}', '{H}', '{T}', '{F}')"}, product_scoped=True)
                with patch('backend.migrator.engine.RateLimiter'):
                    engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
                rows = [{'Id': F, 'Name': 'grandchild', field: H},
                        {'Id': T, 'Name': 'sibling', field: G},
                        {'Id': H, 'Name': 'child', field: G},
                        {'Id': G, 'Name': 'root'}]
                fields = [{'name': 'Name', 'type': 'string', 'createable': True},
                          {'name': field, 'type': 'reference', 'referenceTo': [obj],
                           'createable': True, 'updateable': False}]
                async def desc(token, url, name):
                    return {'createable': True, 'fields': fields}
                async def query(soql):
                    return [{name: row.get(name) for name in
                             [part.strip() for part in soql.split('SELECT ', 1)[1].split(' FROM ', 1)[0].split(',')]}
                            for row in rows]
                async def no_op(): pass
                engine.rl_source.acquire = engine.rl_target.acquire = no_op
                engine._query_all = query
                posts, deleted = [], []
                target_ids = {G: P, H: C, T: N, F: R}
                class Response:
                    status_code = 201
                    def __init__(self, id): self.id = id
                    def json(self): return {'success': True, 'id': self.id}
                class Client:
                    def __init__(self, **kwargs): pass
                    async def __aenter__(self): return self
                    async def __aexit__(self, *args): pass
                    async def post(self, url, **kwargs):
                        posts.append(kwargs['json'])
                        source_id = next(row['Id'] for row in rows if row['Name'] == kwargs['json']['Name'])
                        return Response(target_ids[source_id])
                class DeleteBulk:
                    async def create_ingest_job(self, name, operation):
                        self_test.assertEqual((obj, 'delete'), (name, operation))
                        return 'delete-job'
                    async def upload_job_data(self, job_id, csv): deleted.append(csv)
                    async def close_job(self, *args): pass
                    async def wait_for_completion(self, *args): return 'JobComplete'
                    async def get_successful_results(self, *args):
                        return [{'sf__Id': id} for id in target_ids.values()]
                    async def get_failed_results(self, *args): return []
                    async def get_unprocessed_records(self, *args): return []
                self_test = self
                with patch('backend.migrator.engine.describe_object', desc), \
                     patch('backend.migrator.engine.httpx.AsyncClient', Client), \
                     patch('backend.migrator.engine.BulkAPI2', return_value=DeleteBulk()), \
                     patch('backend.migrator.engine.set_job'), patch('backend.migrator.engine.set_progress'):
                    asyncio.run(engine._preflight_product_references())
                    asyncio.run(engine._migrate_object(obj, 0, 1))
                    asyncio.run(rollback_job(job, 't', 'https://t'))
                self.assertEqual('done', job.object_results[obj].status)
                self.assertEqual([{'Name': 'root'}, {'Name': 'child', field: P},
                                  {'Name': 'grandchild', field: C}, {'Name': 'sibling', field: P}], posts)
                self.assertEqual(target_ids, engine._id_map[obj])
                self.assertEqual(4, job.total_inserted)
                self.assertEqual([], job.object_results[obj].inserted_ids)
                self.assertEqual(1, len(deleted))
                for id in target_ids.values(): self.assertIn(id, deleted[0])
                for id in (G, H, T, F): self.assertNotIn(id, deleted[0])

    def test_create_only_self_ref_upsert_and_cycle_fail_before_writes(self):
        obj, field = 'ProductClassification', 'ParentProductClassificationId'
        for mode, rows, message in (
            ('upsert', [{'Id': G, 'Name': 'root'}, {'Id': H, 'Name': 'child', field: G}], 'Insert Only'),
            ('insert', [{'Id': G, 'Name': 'first', field: H}, {'Id': H, 'Name': 'second', field: G}], 'cycle'),
        ):
            with self.subTest(mode=mode):
                job = MigrationJob('reject-create-only', 'https://s', 'https://t', mode, [obj], [obj],
                                   object_filters={obj: f"Id IN ('{G}', '{H}')"}, product_scoped=True)
                with patch('backend.migrator.engine.RateLimiter'):
                    engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
                fields = [{'name': 'Name', 'type': 'string', 'createable': True, 'externalId': True},
                          {'name': field, 'type': 'reference', 'referenceTo': [obj],
                           'createable': True, 'updateable': False}]
                async def desc(*args): return {'createable': True, 'fields': fields}
                async def query(*args): return rows
                async def no_op(): pass
                engine.rl_source.acquire = engine.rl_target.acquire = no_op
                engine._query_all = query
                with patch('backend.migrator.engine.describe_object', desc):
                    with self.assertRaisesRegex(ValueError, message):
                        asyncio.run(engine._preflight_product_references())
                self.assertEqual({}, job.object_results)
                self.assertEqual({}, engine._id_map)

    def test_preflight_rejects_cycle_across_self_lookup_fields(self):
        job = MigrationJob('cross-cycle', 'https://s', 'https://t', 'insert',
                           ['ProductClassification'], ['ProductClassification'],
                           object_filters={'ProductClassification': f"Id IN ('{G}', '{H}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        fields = [{'name': 'Name', 'type': 'string', 'createable': True}]
        fields += [{'name': name, 'type': 'reference', 'createable': True, 'updateable': True,
                    'referenceTo': ['ProductClassification']} for name in ('ParentProductClassificationId', 'AlternativeParentId')]
        async def desc(*args): return {'fields': fields}
        async def rows(*args): return [{'Id': G, 'Name': 'first', 'ParentProductClassificationId': H},
                                       {'Id': H, 'Name': 'second', 'AlternativeParentId': G}]
        async def no_op(): pass
        engine.rl_source.acquire = engine.rl_target.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'cycle'):
                asyncio.run(engine._preflight_product_references())

    def migration_engine(self, mode='upsert'):
        job = MigrationJob('batch-test', 'https://s', 'https://t', mode, ['Product2'], ['Product2'])
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def no_op(*args): pass
        engine.rl_source.acquire = no_op
        engine.rl_target.acquire = no_op
        async def rows(*args):
            return [{'Id': P, 'StockKeepingUnit': 'one'}, {'Id': C, 'StockKeepingUnit': 'two'},
                    {'Id': N, 'StockKeepingUnit': 'three'}]
        engine._query_all = rows
        engine._build_id_map = no_op
        return engine, job

    def test_legacy_upsert_without_common_external_id_does_not_insert(self):
        engine, job = self.migration_engine()
        job.selected_objects = job.dep_order = ['AttributePicklist']
        async def desc(*args):
            return {'fields': [{'name': 'Name', 'type': 'string', 'createable': True,
                                'externalId': False}]}
        class Bulk:
            def __init__(self): self.calls = []
            async def create_ingest_job(self, *args): self.calls.append(args)
        engine.target_bulk = Bulk()
        with patch('backend.migrator.engine.describe_object', desc):
            asyncio.run(engine._migrate_object('AttributePicklist', 0, 1))
        self.assertEqual('failed', job.object_results['AttributePicklist'].status)
        self.assertIn('No common external ID', job.object_results['AttributePicklist'].error)
        self.assertIn('Insert Only', job.object_results['AttributePicklist'].error)
        self.assertEqual([], engine.target_bulk.calls)

    def test_upsert_rejects_blank_external_id_before_bulk_job(self):
        engine, job = self.migration_engine()
        async def desc(*args):
            return {'fields': [{'name': 'StockKeepingUnit', 'type': 'string',
                                'createable': True, 'externalId': True}]}
        async def rows(*args):
            return [{'Id': P, 'StockKeepingUnit': 'valid'},
                    {'Id': C, 'StockKeepingUnit': ''}]
        engine._query_all = rows
        class Bulk:
            def __init__(self): self.calls = []
            async def create_ingest_job(self, *args): self.calls.append(args)
        engine.target_bulk = Bulk()
        with patch('backend.migrator.engine.describe_object', desc):
            asyncio.run(engine._migrate_object('Product2', 0, 1))
        self.assertEqual('failed', job.object_results['Product2'].status)
        self.assertIn('Missing external ID', job.object_results['Product2'].error)
        self.assertEqual([], engine.target_bulk.calls)

    def test_upsert_rejects_duplicate_external_id_before_bulk_job(self):
        engine, job = self.migration_engine()
        async def desc(*args):
            return {'fields': [{'name': 'StockKeepingUnit', 'type': 'string',
                                'createable': True, 'externalId': True}]}
        async def rows(*args):
            return [{'Id': P, 'StockKeepingUnit': 'same'},
                    {'Id': C, 'StockKeepingUnit': 'same'}]
        engine._query_all = rows
        class Bulk:
            def __init__(self): self.calls = []
            async def create_ingest_job(self, *args): self.calls.append(args)
        engine.target_bulk = Bulk()
        with patch('backend.migrator.engine.describe_object', desc):
            asyncio.run(engine._migrate_object('Product2', 0, 1))
        self.assertEqual('failed', job.object_results['Product2'].status)
        self.assertIn('Duplicate external ID', job.object_results['Product2'].error)
        self.assertEqual([], engine.target_bulk.calls)

    def test_rollback_excludes_updated_target_rows(self):
        engine, job = self.migration_engine()
        class Bulk:
            async def create_ingest_job(self, *args): return 'batch'
            async def upload_job_data(self, *args): pass
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args):
                return [{'sf__Id': G, 'sf__Created': 'true'},
                        {'sf__Id': H, 'sf__Created': 'false'},
                        {'sf__Id': T, 'sf__Created': 'true'}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        engine.target_bulk = Bulk()
        async def desc(*args):
            return {'fields': [{'name': 'StockKeepingUnit', 'type': 'string', 'createable': True, 'externalId': True}]}
        deleted = []
        class DeleteBulk(Bulk):
            async def create_ingest_job(self, *args): return 'delete'
            async def upload_job_data(self, job_id, csv_data): deleted.append(csv_data)
            async def get_successful_results(self, *args):
                return [{'sf__Id': G}, {'sf__Id': T}]
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.BulkAPI2', return_value=DeleteBulk()), \
             patch('backend.migrator.engine.set_job'), patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine._migrate_object('Product2', 0, 1))
            asyncio.run(rollback_job(job, 't', 'https://t'))
        result = job.object_results['Product2']
        self.assertEqual((2, 1, 0), (result.inserted, result.updated, result.failed))
        self.assertEqual([], result.inserted_ids)
        self.assertEqual((2, 1, 0), (job.total_inserted, job.total_updated, job.total_failed))
        self.assertEqual(1, len(deleted))
        self.assertIn(G, deleted[0])
        self.assertIn(T, deleted[0])
        self.assertNotIn(H, deleted[0])

    def test_bulk_failure_error_precedes_unresolved_note_in_job_and_summary(self):
        engine, job = self.migration_engine('insert')
        async def desc(*args):
            return {'fields': [{'name': 'StockKeepingUnit', 'type': 'string', 'createable': True},
                               {'name': 'Pricebook2Id', 'type': 'reference', 'referenceTo': ['Pricebook2'],
                                'createable': True}]}
        async def rows(*args):
            return [{'Id': P, 'StockKeepingUnit': 'one', 'Pricebook2Id': C},
                    {'Id': C, 'StockKeepingUnit': 'two', 'Pricebook2Id': None},
                    {'Id': N, 'StockKeepingUnit': 'three', 'Pricebook2Id': None}]
        engine._query_all = rows
        class Bulk:
            async def create_ingest_job(self, *args): return 'batch'
            async def upload_job_data(self, *args): pass
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args):
                return [{'sf__Id': G, 'sf__Created': 'true'}, {'sf__Id': H, 'sf__Created': 'true'}]
            async def get_failed_results(self, *args):
                return [{'sf__Error': 'DUPLICATE_VALUE: duplicate value found: Name'}]
            async def get_unprocessed_records(self, *args): return []
        engine.target_bulk = Bulk()
        class Log:
            path = '/tmp/migration-test.log'
            def close(self, *args): pass
            def error(self, *args): pass
            def object_start(self, *args): pass
            def object_done(self, *args): pass
            def bulk_job(self, *args): pass
            def failed_records(self, *args): pass
        async def preflight(): pass
        with patch('backend.migrator.engine.describe_object', desc), \
             patch.object(engine, '_preflight_check', preflight), \
             patch('backend.migrator.engine.MigrationLogger', return_value=Log()), \
             patch('backend.migrator.engine.set_job'), patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine.run())
        result = job.object_results['Product2']
        self.assertEqual('done_with_errors', result.status)
        self.assertEqual(2, result.inserted)
        self.assertEqual(1, result.failed)
        self.assertEqual([G, H], result.inserted_ids)
        self.assertTrue(result.error.startswith('1 record(s) failed: DUPLICATE_VALUE: duplicate value found: Name'))
        self.assertIn('1 lookup(s) unresolved', result.error)
        self.assertLess(result.error.index('DUPLICATE_VALUE'), result.error.index('lookup(s) unresolved'))
        self.assertIn(result.error, job.error)
        job.migration_owner_id = 'owner-a'
        job.source_url = 'https://source.salesforce.com'
        with patch.object(router, 'get_job', return_value=job):
            summary = asyncio.run(router.get_result(job.job_id, migration_request(owner='owner-a')))
        self.assertEqual(result.error, summary['object_results']['Product2']['error'])
        self.assertIn('DUPLICATE_VALUE', summary['error'])

    def test_later_batch_exception_preserves_prior_results_for_rollback(self):
        engine, job = self.migration_engine()
        async def rows(*args):
            return [{'Id': P, 'StockKeepingUnit': 'one'}, {'Id': C, 'StockKeepingUnit': 'two'},
                    {'Id': N, 'StockKeepingUnit': 'three'}, {'Id': F, 'StockKeepingUnit': 'four'}]
        engine._query_all = rows
        class Bulk:
            def __init__(self): self.calls = 0
            async def create_ingest_job(self, *args):
                self.calls += 1
                return f'batch-{self.calls}'
            async def upload_job_data(self, *args): pass
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args):
                if self.calls == 2: raise RuntimeError('second batch unavailable')
                return 'JobComplete'
            async def get_successful_results(self, *args):
                return [{'sf__Id': G, 'sf__Created': 'true'}, {'sf__Id': H, 'sf__Created': 'false'}]
            async def get_failed_results(self, *args): return [{'sf__Error': 'rejected'}]
            async def get_unprocessed_records(self, *args): return []
        engine.target_bulk = Bulk()
        async def desc(*args):
            return {'fields': [{'name': 'StockKeepingUnit', 'type': 'string', 'createable': True, 'externalId': True}]}
        from backend.migrator.bulk_api import chunk_records
        deleted = []
        class DeleteBulk(Bulk):
            async def upload_job_data(self, job_id, csv_data): deleted.append(csv_data)
            async def get_successful_results(self, *args): return [{'sf__Id': G}]
            async def get_failed_results(self, *args): return []
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.chunk_records', side_effect=lambda rows: chunk_records(rows, 3)), \
             patch('backend.migrator.engine.BulkAPI2', return_value=DeleteBulk()), \
             patch('backend.migrator.engine.set_job') as saved, patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine._migrate_object('Product2', 0, 1))
            asyncio.run(rollback_job(job, 't', 'https://t'))
        result = job.object_results['Product2']
        self.assertEqual('failed', result.status)
        self.assertIn('second batch unavailable', result.error)
        self.assertEqual((1, 1, 1), (result.inserted, result.updated, result.failed))
        self.assertEqual([], result.inserted_ids)
        self.assertEqual((1, 1, 1), (job.total_inserted, job.total_updated, job.total_failed))
        self.assertEqual(4, job.total_queried)
        self.assertIs(saved.call_args.args[0].object_results['Product2'], result)
        self.assertEqual(1, len(deleted))
        self.assertIn(G, deleted[0])
        self.assertNotIn(H, deleted[0])

    def test_unaccounted_batch_keeps_reported_successes_and_failure(self):
        engine, job = self.migration_engine()
        class Bulk:
            async def create_ingest_job(self, *args): return 'batch'
            async def upload_job_data(self, *args): pass
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args):
                return [{'sf__Id': G, 'sf__Created': 'true'}]
            async def get_failed_results(self, *args): return [{'sf__Error': 'rejected'}]
            async def get_unprocessed_records(self, *args): return []
        engine.target_bulk = Bulk()
        async def desc(*args):
            return {'fields': [{'name': 'StockKeepingUnit', 'type': 'string',
                                'createable': True, 'externalId': True}]}
        with patch('backend.migrator.engine.describe_object', desc), \
             patch('backend.migrator.engine.set_job'), patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine._migrate_object('Product2', 0, 1))
        result = job.object_results['Product2']
        self.assertEqual('failed', result.status)
        self.assertIn('unprocessed or unaccounted', result.error)
        self.assertEqual((1, 0, 1), (result.inserted, result.updated, result.failed))
        self.assertEqual([G], result.inserted_ids)
        self.assertEqual((1, 0, 1), (job.total_inserted, job.total_updated, job.total_failed))

    def plan(self, source, ids=None):
        return asyncio.run(router.build_product_scope(source, ids or [P]))

    def test_nested_bundle_and_complete_fail_closed_plan(self):
        source = FakeSource({
            'Product2': [{'Id': P}, {'Id': C}, {'Id': N}, {'Id': F}],
            'ProductComponentGroup': [{'Id': G, 'ParentProductId': P}, {'Id': H, 'ParentProductId': P, 'ParentGroupId': G},
                                      {'Id': T, 'ParentProductId': C}],
            'ProductRelatedComponent': [{'Id': R, 'ProductComponentGroupId': H, 'ParentProductId': P, 'ChildProductId': C,
                                         'ProductRelationshipTypeId': T},
                                        {'Id': 'a00000000000004AAA', 'ProductComponentGroupId': T, 'ChildProductId': N},
                                        {'Id': 'a00000000000007AAA', 'ParentProductId': F, 'ChildProductId': P}],
            'AttributeDefinition': [], 'AttributePicklist': [], 'AttributePicklistValue': [],
            'ProductClassification': [], 'ProductRelationshipType': [{'Id': T}],
        })
        scope = self.plan(source)
        self.assertEqual(3, scope['product_count'])
        self.assertIn(T, scope['filters']['ProductRelationshipType'])
        self.assertIn(H, scope['filters']['ProductComponentGroup'])
        self.assertIn(R, scope['filters']['ProductRelatedComponent'])
        self.assertNotIn(F, str(scope['filters']))
        self.assertNotIn('a00000000000007AAA', str(scope['filters']))
        self.assertFalse(scope['counts_available'])
        self.assertTrue(all(' WHERE ' in q for q in source.queries))

    def test_missing_id_and_discovery_error_rejected(self):
        source = FakeSource({'Product2': []})
        with self.assertRaises(HTTPException):
            self.plan(source)

    def test_pagination_and_bounded_input(self):
        source = FakeSource({'Product2': [{'Id': P}], 'ProductClassification': [], 'UnitOfMeasure': [], 'UnitOfMeasureClass': []})
        original = source.query
        async def first_page(soql):
            result = await original(soql)
            if soql.startswith('SELECT Id FROM Product2 WHERE'):
                return {'records': [], 'done': False, 'nextRecordsUrl': '/next'}
            return result
        source.query = first_page
        source.instance_url = 'https://source'
        source.headers = {}
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return {'records': [{'Id': P}], 'done': True}
        class Client:
            def __init__(self, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def get(self, *args, **kwargs):
                return Response()
        with patch('httpx.AsyncClient', Client):
            self.assertIn(P, self.plan(source)['filters']['Product2'])
        with self.assertRaises(HTTPException):
            self.plan(source, [P] * 151)
        source = FakeSource({'Product2': [{'Id': P}], 'ProductComponentGroup': []}, error='ProductComponentGroup')
        with self.assertRaises(HTTPException):
            self.plan(source)

    def test_start_recomputes_and_rejects_client_filter(self):
        source = FakeSource({'Product2': [{'Id': P}], 'AttributeDefinition': [],
                             'ProductClassification': [], 'UnitOfMeasure': [], 'UnitOfMeasureClass': []})
        payload = router.StartMigrationPayload(target_access_token='t', target_instance_url='https://target.salesforce.com',
            selected_objects=['Product2'], product_ids=[P], object_filters={'Product2': 'Id != null'})
        async def no_run(*args):
            pass
        with patch.object(router, '_require_auth', return_value=('s', 'https://source')), \
             patch.object(router, 'SalesforceClient', return_value=source), \
             patch.object(router, 'set_job') as save, patch.object(router, 'set_progress'), \
             patch.object(router, '_run_migration', no_run):
            async def start():
                response = await router.start_migration(migration_request(), payload)
                await asyncio.sleep(0)
                return response
            result = asyncio.run(start())
        self.assertIn(P, save.call_args.args[0].object_filters['Product2'])
        self.assertNotIn('Id != null', save.call_args.args[0].object_filters['Product2'])
        self.assertIn('Product2', result['dep_order'])
        self.assertTrue(save.call_args.args[0].product_scoped)

    def test_start_adds_associated_bundle_objects(self):
        source = FakeSource({'Product2': [{'Id': P}, {'Id': C}],
                             'ProductComponentGroup': [{'Id': G, 'ParentProductId': P}],
                             'ProductRelatedComponent': [{'Id': R, 'ProductComponentGroupId': G, 'ChildProductId': C}]})
        async def no_run(*args): pass
        with patch.object(router, '_require_auth', return_value=('s', 'https://source')), \
             patch.object(router, 'SalesforceClient', return_value=source), \
             patch.object(router, 'set_job') as save, patch.object(router, 'set_progress'), \
             patch.object(router, '_run_migration', no_run):
            async def start():
                response = await router.start_migration(migration_request(), router.StartMigrationPayload(
                    target_access_token='t', target_instance_url='https://target.salesforce.com',
                    selected_objects=['Product2'], product_ids=[P]))
                await asyncio.sleep(0)
                return response
            result = asyncio.run(start())
        self.assertIn('ProductComponentGroup', result['dep_order'])
        self.assertIn('ProductRelatedComponent', result['dep_order'])
        self.assertIn(R, save.call_args.args[0].object_filters['ProductRelatedComponent'])

    def test_legacy_filter_does_not_enable_product_scope(self):
        job = MigrationJob('legacy', 'https://s', 'https://t', 'insert', ['Product2'], ['Product2'],
                           object_filters={'Product2': f"Id IN ('{P}')"})
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        self.assertFalse(engine._product_scoped)
        self.assertEqual(job.object_filters['Product2'], engine._scope_where('Product2'))

    def test_start_rejects_missing_source_dependency_and_empty_scope(self):
        source = FakeSource({'Product2': [{'Id': P}]})
        async def no_run(*args):
            pass
        with patch.object(router, '_require_auth', return_value=('s', 'https://source')), \
             patch.object(router, 'SalesforceClient', return_value=source), \
             patch.object(router, '_run_migration', no_run):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(router.start_migration(migration_request(), router.StartMigrationPayload(
                    target_access_token='t', target_instance_url='https://target.salesforce.com',
                    selected_objects=['ProductClassification'], product_ids=[P])))
            with self.assertRaises(HTTPException):
                asyncio.run(router.start_migration(migration_request(), router.StartMigrationPayload(
                    target_access_token='t', target_instance_url='https://target.salesforce.com',
                    selected_objects=['Product2'], product_ids=[])))
        self.assertIn('source', str(raised.exception.detail).lower())

    def test_group_null_parent_component_and_missing_reference(self):
        source = FakeSource({'Product2': [{'Id': P}, {'Id': C}],
                             'ProductRelatedComponent': [{'Id': R, 'ParentProductId': P, 'ChildProductId': C}]})
        self.assertIn(R, self.plan(source)['filters']['ProductRelatedComponent'])
        source.rows['Product2'] = [{'Id': P}]
        with self.assertRaises(HTTPException) as missing:
            self.plan(source)
        self.assertIn('missing child', str(missing.exception.detail).lower())

    def test_foreign_child_classification_and_missing_relationship_are_rejected(self):
        source = FakeSource({'Product2': [{'Id': P}, {'Id': C}],
                             'ProductRelatedComponent': [{'Id': R, 'ParentProductId': P, 'ChildProductId': C,
                                                          'ChildProductClassificationId': F}] ,
                             'ProductClassification': [{'Id': F}]})
        self.assertIn(F, self.plan(source)['filters']['ProductClassification'])
        source.rows['ProductClassification'] = []
        with self.assertRaises(HTTPException) as missing:
            self.plan(source)
        self.assertIn('ProductClassification', str(missing.exception.detail))
        source.rows['ProductClassification'] = [{'Id': F}]
        source.rows['ProductRelatedComponent'][0]['ProductRelationshipTypeId'] = T
        with self.assertRaises(HTTPException) as missing:
            self.plan(source)
        self.assertIn('ProductRelationshipType', str(missing.exception.detail))

    def test_cyclic_group_hierarchy_is_rejected(self):
        source = FakeSource({'Product2': [{'Id': P}],
                             'ProductComponentGroup': [{'Id': G, 'ParentProductId': P, 'ParentGroupId': H},
                                                       {'Id': H, 'ParentProductId': P, 'ParentGroupId': G}]})
        with self.assertRaises(HTTPException) as raised:
            self.plan(source)
        self.assertIn('cycle', str(raised.exception.detail).lower())

    def test_direct_component_discovers_nested_child_without_group(self):
        source = FakeSource({'Product2': [{'Id': P}, {'Id': C}, {'Id': N}],
                             'ProductRelatedComponent': [{'Id': R, 'ParentProductId': P, 'ChildProductId': C},
                                                         {'Id': H, 'ParentProductId': C, 'ChildProductId': N}]})
        scope = self.plan(source)
        self.assertEqual(3, scope['product_count'])
        self.assertIn(H, scope['filters']['ProductRelatedComponent'])

    def test_component_selling_models_and_uom_include_direct_rows(self):
        source = FakeSource({'Product2': [{'Id': P}, {'Id': C}],
                             'ProductRelatedComponent': [{'Id': R, 'ParentProductId': P, 'ChildProductId': C,
                                                          'ParentSellingModelId': G, 'ChildSellingModelId': H,
                                                          'UnitOfMeasureId': T}],
                             'ProductSellingModel': [{'Id': G}, {'Id': H}],
                             'UnitOfMeasure': [{'Id': T}]})
        scope = self.plan(source)
        self.assertIn(G, scope['filters']['ProductSellingModel'])
        self.assertIn(H, scope['filters']['ProductSellingModel'])
        self.assertIn(T, scope['filters']['UnitOfMeasure'])

    def test_group_parent_second_pass_maps_and_checks_results(self):
        job = MigrationJob('group', 'https://s', 'https://t', 'insert', ['ProductComponentGroup'],
                           ['ProductComponentGroup'], product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        engine._source_records['ProductComponentGroup'] = [{'Id': G}, {'Id': H, 'ParentGroupId': G}]
        engine._id_map['ProductComponentGroup'] = {G: P, H: C}
        class Bulk:
            def __init__(self): self.csv = None
            async def create_ingest_job(self, *args): return 'job'
            async def upload_job_data(self, *args): self.csv = args[1]
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args): return [{'sf__Id': C}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        engine.target_bulk = Bulk()
        async def no_op(): pass
        engine.rl_target.acquire = no_op
        asyncio.run(engine._second_pass_self_lookups('ProductComponentGroup', {'self_lookups': ['ParentGroupId']}))
        self.assertIn(P, engine.target_bulk.csv)
        engine.target_bulk.get_successful_results = lambda *args: asyncio.sleep(0, result=[])
        with self.assertRaises(RuntimeError):
            asyncio.run(engine._second_pass_self_lookups('ProductComponentGroup', {'self_lookups': ['ParentGroupId']}))

    def test_preflight_rejects_unmapped_required_bundle_lookup_before_write(self):
        job = MigrationJob('preflight', 'https://s', 'https://t', 'insert', ['ProductRelatedComponent'],
                           ['Product2', 'ProductRelatedComponent'],
                           object_filters={'Product2': f"Id IN ('{P}')", 'ProductRelatedComponent': f"Id IN ('{R}')"},
                           product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        descriptions = {
            'Product2': {'fields': [{'name': 'Id', 'type': 'id'}, {'name': 'StockKeepingUnit', 'type': 'string', 'createable': True}]},
            'ProductRelatedComponent': {'fields': [{'name': 'Id', 'type': 'id'}, {'name': 'Name', 'type': 'string', 'createable': True},
                {'name': 'ChildProductId', 'type': 'reference', 'referenceTo': ['Product2'],
                 'createable': True, 'nillable': False}]},
        }
        async def desc(token, url, obj):
            if url == 'https://t':
                return {'fields': descriptions[obj]['fields']}
            return descriptions[obj]
        async def rows(soql):
            return [{'Id': P, 'StockKeepingUnit': 'parent'}] if 'FROM Product2' in soql else [{'Id': R, 'Name': 'component', 'ChildProductId': C}]
        engine._query_all = rows
        async def no_op(): pass
        engine.rl_source.acquire = no_op
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'ChildProductId'):
                asyncio.run(engine._preflight_product_references())
        self.assertEqual({}, engine._id_map)

    def test_preflight_rejects_unqueryable_writable_reference(self):
        job = MigrationJob('unqueryable', 'https://s', 'https://t', 'insert', ['Product2'], ['Product2'],
                           object_filters={'Product2': f"Id IN ('{P}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def desc(*args): return {'fields': [{'name': 'HiddenParentId', 'type': 'reference',
                                                    'referenceTo': ['Product2'], 'createable': True,
                                                    'queryable': False}]}
        async def rows(*args): return [{'Id': P}]
        async def no_op(): pass
        engine.rl_source.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'HiddenParentId'):
                asyncio.run(engine._preflight_product_references())

    def test_preflight_rejects_missing_required_reference(self):
        job = MigrationJob('required', 'https://s', 'https://t', 'insert', ['Product2'], ['Product2'],
                           object_filters={'Product2': f"Id IN ('{P}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def desc(*args): return {'fields': [{'name': 'StockKeepingUnit', 'type': 'string', 'createable': True},
                                                  {'name': 'BasedOnId', 'type': 'reference',
                                                    'referenceTo': ['ProductClassification'],
                                                    'createable': True, 'nillable': False}]}
        async def rows(*args): return [{'Id': P, 'StockKeepingUnit': 'sku', 'BasedOnId': None}]
        async def no_op(): pass
        engine.rl_source.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'BasedOnId'):
                asyncio.run(engine._preflight_product_references())

    def test_preflight_rejects_unmappable_parent_key_before_write(self):
        job = MigrationJob('no-key', 'https://s', 'https://t', 'insert', ['ProductRelatedComponent'],
                           ['ProductRelatedComponent'],
                           object_filters={'ProductRelatedComponent': f"Id IN ('{R}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def desc(*args): return {'fields': [{'name': 'Id', 'type': 'id'}]}
        async def rows(*args): return [{'Id': R}]
        async def no_op(): pass
        engine.rl_source.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'createable'):
                asyncio.run(engine._preflight_product_references())

    def test_preflight_rejects_target_missing_mapping_key(self):
        job = MigrationJob('target-key', 'https://s', 'https://t', 'insert', ['Product2'], ['Product2'],
                           object_filters={'Product2': f"Id IN ('{P}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def desc(token, url, obj):
            fields = [{'name': 'StockKeepingUnit', 'type': 'string', 'createable': True}] if url == 'https://s' else []
            return {'fields': fields}
        async def rows(*args): return [{'Id': P, 'StockKeepingUnit': 'sku'}]
        async def no_op(): pass
        engine.rl_source.acquire = no_op
        engine.rl_target.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'target mapping key'):
                asyncio.run(engine._preflight_product_references())

    def test_preflight_rejects_target_missing_writable_relationship(self):
        job = MigrationJob('target-ref', 'https://s', 'https://t', 'insert', ['Product2'], ['Product2'],
                           object_filters={'Product2': f"Id IN ('{P}', '{C}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def desc(token, url, obj):
            fields = [{'name': 'StockKeepingUnit', 'type': 'string', 'createable': True}]
            if url == 'https://s':
                fields.append({'name': 'ParentProductId', 'type': 'reference',
                               'referenceTo': ['Product2'], 'createable': True})
            return {'fields': fields}
        async def rows(*args): return [{'Id': P, 'StockKeepingUnit': 'root'},
                                       {'Id': C, 'StockKeepingUnit': 'child', 'ParentProductId': P}]
        async def no_op(): pass
        engine.rl_source.acquire = no_op
        engine.rl_target.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'ParentProductId'):
                asyncio.run(engine._preflight_product_references())

    def test_preflight_rejects_uom_cycle_before_write(self):
        job = MigrationJob('uom-cycle', 'https://s', 'https://t', 'insert', ['UnitOfMeasure'],
                           ['UnitOfMeasure'], object_filters={'UnitOfMeasure': f"Id IN ('{G}', '{H}')"},
                           product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        fields = [{'name': 'Name', 'type': 'string', 'createable': True},
                  {'name': 'ParentUnitOfMeasureId', 'type': 'reference', 'createable': True,
                   'referenceTo': ['UnitOfMeasure']}]
        async def desc(*args): return {'fields': fields}
        async def rows(*args): return [{'Id': G, 'Name': 'first', 'ParentUnitOfMeasureId': H},
                                       {'Id': H, 'Name': 'second', 'ParentUnitOfMeasureId': G}]
        async def no_op(): pass
        engine.rl_source.acquire = no_op
        engine.rl_target.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            with self.assertRaisesRegex(ValueError, 'cycle'):
                asyncio.run(engine._preflight_product_references())

    def test_preflight_accepts_group_parent_hierarchy(self):
        job = MigrationJob('group-ok', 'https://s', 'https://t', 'insert', ['ProductComponentGroup'],
                           ['ProductComponentGroup'],
                           object_filters={'ProductComponentGroup': f"Id IN ('{G}', '{H}')"},
                           product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        fields = [{'name': 'Name', 'type': 'string', 'createable': True},
                  {'name': 'ParentGroupId', 'type': 'reference', 'createable': True, 'updateable': True,
                   'referenceTo': ['ProductComponentGroup']}]
        async def desc(*args): return {'fields': fields}
        async def rows(*args): return [{'Id': G, 'Name': 'root'},
                                       {'Id': H, 'Name': 'child', 'ParentGroupId': G}]
        async def no_op(): pass
        engine.rl_source.acquire = no_op
        engine.rl_target.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            asyncio.run(engine._preflight_product_references())

    def test_group_parent_second_pass_rejects_missing_mapping(self):
        job = MigrationJob('group-missing', 'https://s', 'https://t', 'insert', ['ProductComponentGroup'],
                           ['ProductComponentGroup'], product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        engine._source_records['ProductComponentGroup'] = [{'Id': H, 'ParentGroupId': G}]
        engine._id_map['ProductComponentGroup'] = {H: C}
        with self.assertRaisesRegex(ValueError, 'ParentGroupId'):
            asyncio.run(engine._second_pass_self_lookups('ProductComponentGroup', {'self_lookups': ['ParentGroupId']}))

    def test_missing_schema_field_fails_instead_of_dropping_graph_edge(self):
        source = FakeSource({'Product2': [{'Id': P}], 'ProductComponentGroup': [{'Id': G, 'ParentProductId': P}],
                             'ProductRelatedComponent': [{'Id': R, 'ProductComponentGroupId': G}]})
        source.fields['ProductRelatedComponent'] = {'Id', 'ProductComponentGroupId', 'ParentProductId'}
        with self.assertRaises(HTTPException) as raised:
            self.plan(source)
        self.assertIn('ChildProductId', str(raised.exception.detail))

    def test_scoped_upsert_requires_external_id_and_mapping_is_complete(self):
        job = MigrationJob('test', 'https://s', 'https://t', 'upsert', ['Product2'], ['Product2'],
                           object_filters={'Product2': f"Id IN ('{P}')"}, product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def desc(*args):
            return {'fields': [{'name': 'StockKeepingUnit', 'type': 'string', 'createable': True}]}
        async def rows(*args):
            return [{'Id': P, 'StockKeepingUnit': 'sku'}]
        async def no_op(*args):
            pass
        engine.rl_source.acquire = no_op
        engine.rl_target.acquire = no_op
        engine._query_all = rows
        with patch('backend.migrator.engine.describe_object', desc):
            asyncio.run(engine._migrate_object('Product2', 0, 1))
        self.assertEqual('failed', job.object_results['Product2'].status)
        self.assertIn('external ID', job.object_results['Product2'].error)

    def test_map_escaping_and_ambiguous_or_missing_rows_fail(self):
        job = MigrationJob('map', 'https://s', 'https://t', 'insert', ['Product2'], ['Product2'], product_scoped=True)
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        async def no_op():
            pass
        engine.rl_target.acquire = no_op
        class Response:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {'records': [{'Id': P, 'Name': "O'Brien"}, {'Id': C, 'Name': "O'Brien"}], 'done': True}
        class Client:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def get(self, *args, **kwargs):
                self_test.assertIn("O\\'Brien", kwargs['params']['q'])
                return Response()
        self_test = self
        with patch('backend.migrator.engine.httpx.AsyncClient', Client):
            with self.assertRaises(ValueError):
                asyncio.run(engine._build_id_map('Product2', 'Name', {P: "O'Brien"}))

    def test_engine_forbids_missing_scope_and_required_lookup_loss(self):
        job = MigrationJob('test', 'https://s', 'https://t', 'insert', ['Product2'], ['Product2'], object_filters={})
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        engine._product_scoped = True
        with self.assertRaises(ValueError):
            engine._scope_where('Product2')
        with self.assertRaises(ValueError):
            engine._clean_records([{'Id': P, 'ParentProductId': C}], ['ParentProductId'],
                                  {'ParentProductId': 'Product2'}, [], None,
                                  required_fields={'ParentProductId'})

    def test_graph_orders_classification_and_relationship_refs(self):
        order = asyncio.run(router.dependency_order(router.DependencyOrderPayload(selected_objects=['ProductRelatedComponent'])))['order']
        self.assertLess(order.index('ProductClassification'), order.index('Product2'))
        self.assertLess(order.index('ProductRelationshipType'), order.index('ProductRelatedComponent'))
        self.assertLess(order.index('ProductSellingModel'), order.index('ProductRelatedComponent'))
        self.assertLess(order.index('UnitOfMeasure'), order.index('ProductRelatedComponent'))
        self.assertIn('ProductRelationshipType', OBJECT_DEPS['ProductRelatedComponent'])
        strategy = get_upsert_strategy({'fields': [
            {'name': 'StockKeepingUnit', 'type': 'string', 'createable': True},
            {'name': 'ProductCode', 'type': 'string', 'createable': True},
        ]}, 'Product2')
        self.assertEqual('StockKeepingUnit', strategy['key_field'])

    def test_scope_endpoint_rejects_query_error(self):
        source = FakeSource({'Product2': [{'Id': P}], 'ProductComponentGroup': []}, error='ProductComponentGroup')
        with patch.object(router, '_require_auth', return_value=('s', 'https://source')), \
             patch.object(router, 'SalesforceClient', return_value=source):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(router.compute_scope_filters(None, router.ScopeFiltersPayload(product_ids=[P])))
        self.assertEqual(400, raised.exception.status_code)

    def test_product_job_fails_on_object_failure(self):
        job = MigrationJob('test', 'https://s', 'https://t', 'insert', ['Product2'], ['Product2'],
                           object_filters={'Product2': f"Id IN ('{P}')"})
        with patch('backend.migrator.engine.RateLimiter'):
            engine = MigrationEngine('s', 'https://s', 't', 'https://t', job)
        class Log:
            path = '/tmp/test.log'
            def close(self, *args):
                pass
            def error(self, *args):
                pass
        async def preflight():
            pass
        async def fail_object(obj, pct, total):
            from backend.migrator.job_store import ObjectMigrationResult
            job.object_results[obj] = ObjectMigrationResult(obj, status='failed', error='bulk failure')
        with patch.object(engine, '_preflight_check', preflight), \
             patch.object(engine, '_preflight_product_references', preflight), \
             patch.object(engine, '_migrate_object', fail_object), \
             patch('backend.migrator.engine.MigrationLogger', return_value=Log()), \
             patch('backend.migrator.engine.set_job'), patch('backend.migrator.engine.set_progress'):
            asyncio.run(engine.run())
        self.assertEqual('failed', job.status)


class RollbackOutcomeTests(unittest.TestCase):
    def job(self):
        from backend.migrator.job_store import ObjectMigrationResult
        job = MigrationJob('rollback-outcome', 'https://s', 'https://t', 'insert',
                           ['Product2'], ['Product2'], status='failed')
        job.object_results['Product2'] = ObjectMigrationResult(
            'Product2', inserted_ids=[G, T])
        job.migration_owner_id = 'owner-a'
        job.source_url = 'https://source.salesforce.com'
        job.target_url = 'https://target.salesforce.com'
        return job

    def test_delete_failure_is_not_reported_as_rolled_back(self):
        job = self.job()
        class Bulk:
            async def create_ingest_job(self, *args): return 'delete-job'
            async def upload_job_data(self, *args): pass
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args):
                return [{'sf__Id': G}]
            async def get_failed_results(self, *args):
                return [{'Id': T, 'sf__Error': 'cannot delete'}]
            async def get_unprocessed_records(self, *args): return []
        with patch('backend.migrator.engine.BulkAPI2', return_value=Bulk()), \
             patch.object(router, 'set_job'), patch.object(router, 'set_progress') as progress:
            asyncio.run(router._run_rollback(job, 't', 'https://t'))
        self.assertEqual('failed', job.status)
        self.assertIn('cannot delete', job.error)
        self.assertEqual('failed', progress.call_args.kwargs['status'])
        self.assertEqual([G, T], job.object_results['Product2'].inserted_ids)

    def test_verified_batches_checkpoint_and_retry_only_remaining_ids(self):
        job = self.job()
        job.object_results['Product2'].inserted_ids = [G, T, H]
        uploaded = []
        class Bulk:
            async def create_ingest_job(self, *args): return 'delete-job'
            async def upload_job_data(self, _, csv): uploaded.append(csv)
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args):
                return [{'sf__Id': G}] if len(uploaded) == 1 else [{'sf__Id': T}, {'sf__Id': H}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        from backend.migrator.bulk_api import chunk_records
        snapshots = []
        with patch('backend.migrator.engine.BulkAPI2', return_value=Bulk()), \
             patch('backend.migrator.engine.chunk_records', side_effect=lambda rows: chunk_records(rows, 1)), \
             patch('backend.migrator.engine.set_job', side_effect=lambda j: snapshots.append(list(j.object_results['Product2'].inserted_ids))):
            with self.assertRaises(RuntimeError):
                asyncio.run(rollback_job(job, 't', 'https://t'))
            self.assertEqual([[T, H]], snapshots)
            self.assertEqual([T, H], job.object_results['Product2'].inserted_ids)
            self.assertNotIn(G, uploaded[1])
            # Verify both remaining records on a retry, never re-delete the checkpointed one.
            async def successes(*args):
                return [{'sf__Id': T}] if len(uploaded) == 3 else [{'sf__Id': H}]
            with patch.object(Bulk, 'get_successful_results', successes):
                asyncio.run(rollback_job(job, 't', 'https://t'))
        self.assertEqual([], job.object_results['Product2'].inserted_ids)
        self.assertEqual([[T, H], [H], []], snapshots)
        self.assertTrue(all(G not in csv for csv in uploaded[2:]))

    def test_stopped_and_failed_jobs_with_remaining_records_can_rollback_only_original_target(self):
        for status in ('stopped', 'failed', 'completed'):
            with self.subTest(status=status):
                job = self.job()
                job.status = status
                payload = router.RollbackPayload(target_access_token='t', target_instance_url='https://wrong.salesforce.com')
                with patch.object(router, '_require_auth', return_value=('s', job.source_url)), \
                     patch.object(router, 'get_job', return_value=job), \
                     patch.object(router, 'set_job'), patch.object(router, 'set_progress'), \
                     patch.object(router.asyncio, 'create_task') as task:
                    with self.assertRaises(HTTPException) as rejected:
                        asyncio.run(router.rollback(job.job_id, payload, migration_request(owner='owner-a')))
                    self.assertEqual(400, rejected.exception.status_code)
                    task.assert_not_called()
                    payload.target_instance_url = 'https://target.salesforce.com/'
                    async def invoke():
                        response = await router.rollback(job.job_id, payload, migration_request(owner='owner-a'))
                        return response
                    async def no_rollback(*args): pass
                    def schedule(coro): coro.close()
                    task.side_effect = schedule
                    with patch.object(router, '_run_rollback', no_rollback):
                        self.assertEqual('rolling_back', asyncio.run(invoke())['status'])

    def test_result_exposes_tracked_remaining_not_historical_insert_count(self):
        job = self.job()
        job.total_inserted = 10
        with patch.object(router, 'get_job', return_value=job):
            self.assertEqual(2, asyncio.run(router.get_result(job.job_id, migration_request(owner='owner-a')))['rollback_remaining'])
            job.object_results['Product2'].inserted_ids.clear()
            self.assertEqual(0, asyncio.run(router.get_result(job.job_id, migration_request(owner='owner-a')))['rollback_remaining'])

    def test_no_remaining_ids_cannot_report_successful_rollback(self):
        job = self.job()
        job.object_results['Product2'].inserted_ids.clear()
        with patch.object(router, 'get_job', return_value=job), \
              patch.object(router, '_require_auth', return_value=('s', job.source_url)), \
             patch.object(router.asyncio, 'create_task') as task:
            with self.assertRaises(HTTPException):
                asyncio.run(router.rollback(job.job_id, router.RollbackPayload(
                     target_access_token='t', target_instance_url=job.target_url), migration_request(owner='owner-a')))
            task.assert_not_called()

    def test_partial_rollback_failure_can_be_retried_from_failed_status(self):
        job = self.job()
        job.object_results['Product2'].inserted_ids = [G, T, H]
        uploaded = []
        class Bulk:
            async def create_ingest_job(self, *args): return 'delete-job'
            async def upload_job_data(self, _, csv): uploaded.append(csv)
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args):
                return [{'sf__Id': G}] if len(uploaded) == 1 else [
                    {'sf__Id': T}, {'sf__Id': H}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        from backend.migrator.bulk_api import chunk_records
        with patch('backend.migrator.engine.BulkAPI2', return_value=Bulk()), \
             patch('backend.migrator.engine.chunk_records', side_effect=lambda rows: chunk_records(rows, 1)), \
             patch('backend.migrator.engine.set_job'), \
             patch.object(router, 'set_job'), patch.object(router, 'set_progress'), \
             patch.object(router, 'get_job', return_value=job), \
              patch.object(router, '_require_auth', return_value=('s', job.source_url)):
            asyncio.run(router._run_rollback(job, 't', 'https://t'))
            self.assertEqual('failed', job.status)
            self.assertIn('Rollback failed:', job.error)
            self.assertEqual([T, H], job.object_results['Product2'].inserted_ids)
            self.assertEqual(2, asyncio.run(router.get_result(job.job_id, migration_request(owner='owner-a')))['rollback_remaining'])
            async def successes(*args):
                return [{'sf__Id': T}] if len(uploaded) == 3 else [{'sf__Id': H}]
            async def retry():
                response = await router.rollback(job.job_id, router.RollbackPayload(
                     target_access_token='t', target_instance_url=job.target_url), migration_request(owner='owner-a'))
                return response
            def schedule(coro): coro.close()
            with patch.object(Bulk, 'get_successful_results', successes), \
                 patch.object(router.asyncio, 'create_task', side_effect=schedule):
                self.assertEqual('rolling_back', asyncio.run(retry())['status'])
                asyncio.run(router._run_rollback(job, 't', 'https://t'))
        self.assertEqual('rolled_back', job.status)
        self.assertEqual('', job.error)
        self.assertEqual([], job.object_results['Product2'].inserted_ids)
        self.assertTrue(all(G not in csv for csv in uploaded[2:]))

    def test_unvisited_tracked_object_prevents_false_completion(self):
        from backend.migrator.job_store import ObjectMigrationResult
        job = self.job()
        job.object_results['Other'] = ObjectMigrationResult('Other', inserted_ids=[H])
        class Bulk:
            async def create_ingest_job(self, *args): return 'delete-job'
            async def upload_job_data(self, *args): pass
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args): return [{'sf__Id': G}, {'sf__Id': T}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        with patch('backend.migrator.engine.BulkAPI2', return_value=Bulk()), \
             patch('backend.migrator.engine.set_job'), patch.object(router, 'set_job'), \
             patch.object(router, 'set_progress') as progress:
            asyncio.run(router._run_rollback(job, 't', 'https://t'))
        self.assertEqual('failed', job.status)
        self.assertIn('remain', job.error)
        self.assertEqual([H], job.object_results['Other'].inserted_ids)
        self.assertEqual('failed', progress.call_args.kwargs['status'])

    def test_stopped_stream_emits_terminal_event_and_closes(self):
        job = self.job()
        job.job_id = 'stopped-test'
        async def consume():
            response = await router.stream_progress('stopped-test', migration_request(owner='owner-a'))
            return [part async for part in response.body_iterator]
        async def no_sleep(*args): pass
        with patch.object(router, 'get_job', return_value=job), \
             patch.object(router, '_job_progress', {'stopped-test': {'status': 'stopped'}}), \
             patch.object(router, 'get_log_delta', return_value=([], 0)), \
             patch.object(router.asyncio, 'sleep', no_sleep):
            events = asyncio.run(consume())
        self.assertEqual(1, len(events))
        self.assertIn('"stopped"', events[0])

    def test_unverifiable_or_incomplete_delete_keeps_ids_and_fails(self):
        for state, successes, failures, unprocessed in (
            ('Failed', [], [], []),
            ('JobComplete', [{'sf__Id': G}], [], []),
            ('JobComplete', [{'sf__Id': G}, {'sf__Id': H}], [], []),
            ('JobComplete', [{'sf__Id': G}], [], [{'Id': T}]),
        ):
            with self.subTest(state=state, successes=successes, unprocessed=unprocessed):
                job = self.job()
                class Bulk:
                    async def create_ingest_job(self, *args): return 'delete-job'
                    async def upload_job_data(self, *args): pass
                    async def close_job(self, *args): pass
                    async def wait_for_completion(self, *args): return state
                    async def get_successful_results(self, *args): return successes
                    async def get_failed_results(self, *args): return failures
                    async def get_unprocessed_records(self, *args): return unprocessed
                with patch('backend.migrator.engine.BulkAPI2', return_value=Bulk()):
                    with self.assertRaises(RuntimeError):
                        asyncio.run(rollback_job(job, 't', 'https://t'))
                self.assertEqual([G, T], job.object_results['Product2'].inserted_ids)

    def test_result_lookup_exception_is_not_swallowed(self):
        job = self.job()
        class Bulk:
            async def create_ingest_job(self, *args): return 'delete-job'
            async def upload_job_data(self, *args): pass
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args):
                raise RuntimeError('results unavailable')
        with patch('backend.migrator.engine.BulkAPI2', return_value=Bulk()):
            with self.assertRaisesRegex(RuntimeError, 'results unavailable'):
                asyncio.run(rollback_job(job, 't', 'https://t'))
        self.assertEqual([G, T], job.object_results['Product2'].inserted_ids)

    def test_verified_delete_reports_rolled_back(self):
        job = self.job()
        class Bulk:
            async def create_ingest_job(self, *args): return 'delete-job'
            async def upload_job_data(self, *args): pass
            async def close_job(self, *args): pass
            async def wait_for_completion(self, *args): return 'JobComplete'
            async def get_successful_results(self, *args):
                return [{'sf__Id': G}, {'sf__Id': T}]
            async def get_failed_results(self, *args): return []
            async def get_unprocessed_records(self, *args): return []
        with patch('backend.migrator.engine.BulkAPI2', return_value=Bulk()), \
             patch.object(router, 'set_job'), patch.object(router, 'set_progress') as progress:
            asyncio.run(router._run_rollback(job, 't', 'https://t'))
        self.assertEqual('rolled_back', job.status)
        self.assertEqual('rolled_back', progress.call_args.kwargs['status'])
        self.assertEqual([], job.object_results['Product2'].inserted_ids)


if __name__ == '__main__':
    unittest.main()
