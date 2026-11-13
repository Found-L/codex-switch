// Native code is evaluated in a VM with only fixture dependencies.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const sources = JSON.parse(fs.readFileSync(0, 'utf8'));
let context;
const cache = {};
const fixtures = {
  QosV: { c: size => Array(size).fill(Symbol.for('react.memo_cache_sentinel')) },
  y5DF: { Ul: () => 'fixture-host', _U: () => ({ data: context.requirements, isPending: false }) },
  zTeN: { Ul: () => 'fixture-host', _U: () => ({ data: context.requirements, isPending: false }) },
  tl5a: { Dc: 'host', QN: 'tier' },
  EOo5: { tn: () => context.auth },
  B81s: { b9: 'requirements', Wr: async () => context.requirements },
  mGK9: { s: async () => context.auth.authMethod ?? null },
  Qgfj: { YK: value => value },
  WFY2: { v: { error: () => { throw Error('Unexpected native error path'); } } },
  wCOm: { ig: async () => ({ config: { model: 'fixture', service_tier: null } }), Y$: v => v },
  Dgwo: { V: () => ({ sendRequest: async method => {
    assert.equal(method, 'model/list'); return { data: [context.model] };
  } }) },
};
function load(name) {
  if (fixtures[name]) return fixtures[name];
  if (cache[name]) return cache[name];
  assert.ok(sources[name], `Missing fixture dependency ${name}`);
  const exports = cache[name] = {};
  const module = vm.runInNewContext(`({${sources[name]}})`, {});
  module[name]({}, exports, load);
  return exports;
}
load.d = (target, getters, values) => {
  for (const [name, getter] of Object.entries(getters)) Object.defineProperty(target, name, { get: getter });
  Object.assign(target, values);
};
(async () => {
  const access = load('ipV4'), tiers = load('l2g8'), request = load('PAzX'), limits = load('eWgO');
  let scenarios = 0;
  for (const auth of ['apikey', null, 'chatgpt', 'personalAccessToken', 'amazonBedrock']) {
    for (const fast of [true, false]) for (const ultra of [true, false]) {
      context = { auth: { authMethod: auth, requiresAuth: auth !== null },
        requirements: { requirements: { featureRequirements: { fast_mode: fast, ultrafast_mode: ultra } }, supportsIndependentSpeedModes: true },
        model: { model: 'fixture', isDefault: true, serviceTiers: [{ id: 'priority', name: 'Fast' }, { id: 'ultrafast', name: 'Ultrafast' }] } };
      const actual = access.U({ hostId: 'fixture-host' }).serviceTierAccess;
      assert.deepEqual(JSON.parse(JSON.stringify(actual)), { fast, ultrafast: ultra });
      const options = tiers.HN(context.model).filter(e => limits.uw(e.value, actual)).map(e => e.value);
      assert.deepEqual(Array.from(options), [null, ...(fast ? ['priority'] : []), ...(ultra ? ['ultrafast'] : [])]);
      const scope = { get: () => ({ type: 'fromConfig' }), query: { setData: () => {} } };
      assert.equal(await request.e(scope, 'fixture-host', 'fixture', 'priority'), fast ? 'priority' : null);
      assert.equal(await request.e(scope, 'fixture-host', 'fixture', 'ultrafast'), ultra ? 'ultrafast' : null);
      assert.equal(await request.e(scope, 'fixture-host', 'fixture', null), null);
      scenarios++;
    }
  }
  context.auth = { authMethod: 'unsupported' };
  assert.equal(access.U({ hostId: 'fixture-host' }).serviceTierAccess, null);
  context.model.serviceTiers = [];
  assert.deepEqual(Array.from(tiers.HN(context.model), e => e.value), [null]);
  let executionScenarios = 0;
  if (sources.__saved && sources.__submit) {
    // Evaluate the actual patched snippets extracted from the pinned client asset.
    const saved = vm.runInNewContext(`(async e => {${sources.__saved}})`, {});
    const submit = vm.runInNewContext(`(async (e, d) => {${sources.__submit}})`, {});
    const accounts = [
      [{ account: { type: 'chatgpt' }, requiresOpenaiAuth: true }, true],
      [{ account: { type: 'amazonBedrock' }, requiresOpenaiAuth: true }, true],
      [{ account: { type: 'apiKey' }, requiresOpenaiAuth: true }, true],
      [{ account: null, requiresOpenaiAuth: false }, true],
      [{ account: null, requiresOpenaiAuth: true }, false],
      [{ account: null }, false],
      [{ account: { type: 'gcp' }, requiresOpenaiAuth: false }, false],
    ];
    for (const [account, allowed] of accounts) {
      const client = { getAccount: async () => account };
      assert.equal(await saved(client), allowed);
      for (const tier of ['priority', 'ultrafast']) {
        assert.equal(await submit(client, { serviceTier: tier }), allowed ? tier : null);
        executionScenarios++;
      }
    }
  }
  process.stdout.write(JSON.stringify({ scenarios, execution_scenarios: executionScenarios,
    account_requirements_preserved: true, request_tiers_preserved: true, unknown_model_standard_only: true }));
})().catch(error => { console.error(error); process.exitCode = 1; });
