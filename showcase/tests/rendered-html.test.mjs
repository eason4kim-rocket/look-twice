import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${path}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request(`http://localhost${path}`, { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the Look Twice product entry", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>Look Twice — Active Evidence Assurance<\/title>/i);
  assert.match(html, /Before a robot acts/);
  assert.match(html, /Open Evidence Console/);
  assert.match(html, /RECORDED AMD GPU EVIDENCE/);
  assert.doesNotMatch(html, /react-loading-skeleton|Your site is taking shape/);
});

test("publishes candidate-neutral, traceable replay data", async () => {
  const manifest = JSON.parse(await readFile(new URL("../public/data/manifest.json", import.meta.url), "utf8"));
  assert.equal(manifest.default_candidate_id, "v8-frozen");
  assert.equal(manifest.replays.length, 2);
  for (const replay of manifest.replays) {
    assert.equal(replay.candidate_id, "v8-frozen");
    const bundle = JSON.parse(await readFile(new URL(`../public/data/replays/${replay.replay_id}.json`, import.meta.url), "utf8"));
    assert.equal(bundle.schema_version, "look-twice.episode-bundle/v1");
    assert.equal(bundle.episode_meta.live_gpu_dependency, false);
    assert.ok(bundle.integrity.source_episode_sha256);
    assert.ok(bundle.sensor_frames.every((frame) => frame.media.available));
  }
});
