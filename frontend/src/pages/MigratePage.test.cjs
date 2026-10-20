const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

const source = fs.readFileSync(require('node:path').join(__dirname, 'MigratePage.jsx'), 'utf8')
const handler = source.match(/  async function handleStartMigration\(\) \{[\s\S]*?\n  \}\n\n  async function handleRollback/)
assert.ok(handler, 'start handler must exist')

async function start({ selected = ['Product2'], selectedBundle = '', records = [], filters = {} } = {}) {
  let payload
  let error = ''
  const context = {
    targetOrg: { access_token: 'token', instance_url: 'https://target.salesforce.com' },
    selected: new Set(selected), selectedBundle, productBundle: !!selectedBundle,
    scopeReady: true, migrating: false, mode: 'upsert', filters,
    recordSelections: { Product2: records }, productIds: records.map(r => r.id),
    partialProductPlan: selectedBundle === '' && selected.includes('Product2') &&
      ((records.length > 0 && selected.length > 1) || !!filters.Product2?.trim()),
    setStartErr(value) { error = value }, setResult() {}, setProgress() {}, setLiveLog() {}, setTerminalLines() {},
    setMigrating() {}, setJobId() {}, setDepOrder() {}, startStream() {},
    fetch: async (_url, options) => {
      payload = JSON.parse(options.body)
      return { ok: true, json: async () => ({ job_id: 'job', dep_order: [] }) }
    },
  }
  vm.runInNewContext(handler[0].replace(/\n\n  async function handleRollback$/, '') + '\nhandleStartMigration()', context)
  await new Promise(resolve => setImmediate(resolve))
  return { payload, error }
}

const id = '01t000000000001AAA'
const record = { id, name: 'Selected product' }

test('no-bundle Product2 record picker starts with product_ids, not object_filters', async () => {
  const { payload } = await start({ records: [record] })
  assert.deepEqual(payload.product_ids, [id])
  assert.equal('object_filters' in payload, false)
  assert.deepEqual(Array.from(payload.selected_objects), ['Product2'])
})

test('manual WHERE and mixed selection are blocked; object-only Product2 stays legacy', async () => {
  for (const input of [
    { records: [record], filters: { Product2: 'Name != null' } },
    { records: [record], selected: ['Product2', 'Account'] },
    { records: [] },
  ]) {
    const { payload, error } = await start(input)
    if (input.records.length) {
      assert.equal(payload, undefined)
      assert.match(error, /product bundle/i)
    } else {
      assert.equal('product_ids' in payload, false)
      assert.deepEqual(payload.object_filters, {})
    }
  }
})

test('manual Product2 filter with other product objects prompts for bundle scope', async () => {
  const { payload, error } = await start({ selected: ['Product2', 'AttributeCategory'], filters: { Product2: `Id IN ('${id}')` } })
  assert.equal(payload, undefined)
  assert.match(error, /product bundle/i)
})

test('manual Product2 filter alone prompts for bundle scope', async () => {
  const { payload, error } = await start({ filters: { Product2: `Id IN ('${id}')` } })
  assert.equal(payload, undefined)
  assert.match(error, /product bundle/i)
})

test('invalid explicitly selected Product2 ID is blocked before start', async () => {
  const { payload, error } = await start({ records: [{ id: 'not-an-id', name: 'Invalid' }] })
  assert.equal(payload, undefined)
  assert.match(error, /valid.*Product2.*ID/i)
})

test('explicit bundle action replaces mixed selection and chooses Insert Only', () => {
  const action = source.match(/  function useProductBundle\(\) \{[\s\S]*?\n  \}/)
  assert.ok(action, 'explicit bundle action must exist')
  const state = { selectedBundle: '', selected: new Set(['Product2', 'AttributeCategory']), mode: 'upsert', records: { Product2: [record], AttributeCategory: [{ id: 'old' }] }, error: 'blocked' }
  const context = {
    recordSelections: state.records, isBusy: false,
    setSelectedBundle(value) { state.selectedBundle = value },
    setSelected(value) { state.selected = typeof value === 'function' ? value(state.selected) : value },
    setRecordSelections(value) { state.records = typeof value === 'function' ? value(state.records) : value },
    setScope() {}, setFilters() {}, setMode(value) { state.mode = value }, setStartErr(value) { state.error = value },
  }
  vm.runInNewContext(action[0] + '\nuseProductBundle()', context)
  assert.equal(state.selectedBundle, 'revenue_product_bundle')
  assert.deepEqual(Array.from(state.selected), ['Product2'])
  assert.deepEqual(state.records.Product2.map(r => r.id), [id])
  assert.equal(state.records.AttributeCategory, undefined)
  assert.equal(state.mode, 'insert')
  assert.equal(state.error, '')
})
