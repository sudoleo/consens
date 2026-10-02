// Rules are exercised by the client SDK; the Admin bypass only seeds/cleans.
import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { initializeTestEnvironment, assertFails, assertSucceeds } from '@firebase/rules-unit-testing';
import { collection, deleteDoc, doc, getDoc, getDocs, setDoc, updateDoc } from 'firebase/firestore';

const projectId = 'demo-consensio-e2e';
const config = JSON.parse(readFileSync(new URL('../../firebase.json', import.meta.url), 'utf8'));
const endpoint = new URL(`http://${process.env.FIRESTORE_EMULATOR_HOST || `${config.emulators.firestore.host}:${config.emulators.firestore.port}`}`);
if (!['127.0.0.1', 'localhost', '[::1]'].includes(endpoint.hostname) || !endpoint.port || endpoint.username || endpoint.password || endpoint.pathname !== '/') {
  throw new Error('Rules tests require an explicit loopback emulator endpoint.');
}
for (const name of ['GOOGLE_CLOUD_PROJECT', 'GCLOUD_PROJECT', 'FIREBASE_PROJECT_ID']) {
  if (process.env[name] && process.env[name] !== projectId) throw new Error(`Unexpected ${name}; only ${projectId} is allowed.`);
}
const rules = readFileSync(new URL('../../firestore.rules', import.meta.url), 'utf8');
const suffix = randomUUID();
const owner = `rules-owner-${suffix}`;
const paths = [
  `users/${owner}`, `users/${owner}/chats/chat`, `users/${owner}/memory/profile`,
  `users/${owner}/chats/chat/files/file`, `users/${owner}/usage_runs/day`,
  `api_consensus_keys/rules-${suffix}`,
  `users/${owner}/chats/chat/turns/turn/agents/agent`, `users/${owner}/llm_calls/receipt`,
  `source_check_jobs/rules-${suffix}`, `source_check_jobs_dispatch_v1_local/rules-${suffix}`,
  `source_check_jobs_dispatch_v1_production/rules-${suffix}`, `notification_outbox/rules-${suffix}`,
];
const settings = { projectId, firestore: { host: endpoint.hostname.replace(/^\[|\]$/g, ''), port: Number(endpoint.port), rules } };
let env;
before(async () => {
  env = await initializeTestEnvironment(settings);
  await env.withSecurityRulesDisabled(async context => {
    const db = context.firestore();
    for (const path of paths) await assertSucceeds(setDoc(doc(db, path), { owner_uid: owner, role: 'user', tier: 'free' }));
  });
});
after(async () => {
  if (!env) return;
  await env.withSecurityRulesDisabled(async context => {
    const db = context.firestore();
    for (const path of paths) await deleteDoc(doc(db, path));
  });
  await env.cleanup();
});

for (const identity of ['anonymous', 'owner', 'foreign', 'admin-claim']) {
  for (const path of paths) {
    test(`${identity}: no client read/write/query/delete of ${path.replace(owner, '{uid}').split('/').slice(0, -1).join('/')}`, async () => {
      const context = identity === 'anonymous' ? env.unauthenticatedContext()
        : env.authenticatedContext(identity === 'owner' ? owner : `other-${suffix}`, identity === 'admin-claim' ? { admin: true, role: 'admin' } : {});
      const db = context.firestore();
      const ref = doc(db, path);
      await assertFails(getDoc(ref));
      await assertFails(getDocs(collection(db, path.split('/').slice(0, -1).join('/'))));
      await assertFails(setDoc(ref, { role: 'admin', tier: 'pro' }));
      await assertFails(updateDoc(ref, { role: 'admin', tier: 'pro' }));
      await assertFails(deleteDoc(ref));
    });
  }
}

test('the same denial oracle detects an accidentally permitted owner write', async () => {
  const changed = rules.replace('match /{document=**}', 'match /users/{uid} { allow write: if request.auth.uid == uid; }\n    match /{document=**}');
  assert.notEqual(changed, rules);
  let mutated;
  try {
    mutated = await initializeTestEnvironment({ ...settings, firestore: { ...settings.firestore, rules: changed } });
    await assert.rejects(
      assertFails(setDoc(doc(mutated.authenticatedContext(owner).firestore(), `users/${owner}`), { role: 'admin' })),
      /Expected request to fail/,
    );
  } finally {
    const restored = await initializeTestEnvironment(settings);
    await restored.cleanup();
    if (mutated) await mutated.cleanup();
  }
  await assertFails(updateDoc(doc(env.authenticatedContext(owner).firestore(), `users/${owner}`), { tier: 'pro' }));
});
