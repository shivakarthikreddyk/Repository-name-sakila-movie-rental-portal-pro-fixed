const { test } = require('node:test');
const assert = require('node:assert/strict');
const { once } = require('node:events');
const { createApp } = require('../src/app');

async function withServer(query, run) {
  const server = createApp(query, { error() {} }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  try { await run(`http://127.0.0.1:${server.address().port}`); }
  finally { await new Promise(resolve => server.close(resolve)); }
}

test('readiness rejects an unavailable or unseeded database without leaking details', async () => {
  for (const query of [async () => { throw new Error('private password detail'); }, async () => [{ total: 0 }]]) {
    await withServer(query, async base => {
      const response = await fetch(`${base}/api/health`);
      assert.equal(response.status, 503);
      assert.equal((await response.json()).database, 'UNAVAILABLE');
      assert.equal((await fetch(`${base}/api/live`)).status, 200);
    });
  }
});

test('query validation rejects nested values and invalid ratings before accessing MySQL', async () => {
  await withServer(async () => { assert.fail('Invalid input must not reach MySQL'); }, async base => {
    for (const query of ['search[x]=bad', 'search=a&search=b', `search=${'x'.repeat(101)}`, 'rating=INVALID']) {
      assert.equal((await fetch(`${base}/api/movies?${query}`)).status, 400);
    }
  });
});

test('search and rating use SQL parameters', async () => {
  let captured;
  await withServer(async (sql, params) => { captured = { sql, params }; return []; }, async base => {
    const search = "' OR 1=1 --";
    const response = await fetch(`${base}/api/movies?search=${encodeURIComponent(search)}&rating=PG`);
    assert.equal(response.status, 200);
    assert.deepEqual(captured.params, [`%${search}%`, 'PG', 'PG']);
    assert.ok(!captured.sql.includes(search));
  });
});

test('list errors are controlled and unknown API routes return JSON 404', async () => {
  await withServer(async () => { throw new Error('internal SQL details'); }, async base => {
    const response = await fetch(`${base}/api/movies`);
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: 'Database is temporarily unavailable' });
    assert.equal((await fetch(`${base}/api/unknown`)).status, 404);
  });
});
