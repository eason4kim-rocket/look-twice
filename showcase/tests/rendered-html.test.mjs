import assert from "node:assert/strict";
import { createHash } from "node:crypto";
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

async function sha256(url) {
  const bytes = await readFile(url);
  return createHash("sha256").update(bytes).digest("hex");
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
    assert.equal(bundle.schema_version, "look-twice.episode-bundle/v1.1");
    assert.equal(bundle.episode_meta.live_gpu_dependency, false);
    assert.equal(
      bundle.episode_meta.agent_geometry.carrier.source,
      "scenario.public_context.carrier_width",
    );
    assert.equal(
      bundle.episode_meta.agent_geometry.scout.source,
      "scenario.public_context.scout_width",
    );
    assert.ok(bundle.integrity.source_episode_sha256);
    assert.ok(bundle.sensor_frames.every((frame) => frame.media.available));
    assert.equal(new Set(bundle.gate_receipts.map((gate) => gate.gate_id)).size, bundle.gate_receipts.length);
    assert.equal(new Set(bundle.motion_segments.map((motion) => motion.motion_id)).size, bundle.motion_segments.length);
    assert.equal(new Set(bundle.events.map((event) => event.event_id)).size, bundle.events.length);
    const targets = new Map([
      ...bundle.sensor_frames.map((item) => [`sensor_frame:${item.frame_id}`, item]),
      ...bundle.gate_receipts.map((item) => [`gate_receipt:${item.gate_id}`, item]),
      ...bundle.repair_requests.map((item) => [`repair_request:${item.request_id}`, item]),
      ...bundle.motion_segments.map((item) => [`motion_segment:${item.motion_id}`, item]),
      [`outcome:outcome`, bundle.outcome],
    ]);
    for (const event of bundle.events) {
      const target = targets.get(`${event.ref_kind}:${event.ref_id}`);
      assert.ok(target, `event ${event.event_id} has a resolvable reference`);
      if (event.ref_kind === "gate_receipt") {
        assert.equal(event.status, target.effective_admit ? "admitted" : "denied");
      }
    }
    for (const motion of bundle.motion_segments) {
      assert.ok(motion.trajectory_sample.length >= 2);
      const positions = new Set(
        motion.trajectory_sample.map((point) => `${point.x}:${point.y}:${point.yaw}`),
      );
      assert.ok(positions.size >= 2, `${motion.motion_id} must contain real movement`);
    }
    const serialized = JSON.stringify(bundle);
    assert.doesNotMatch(serialized, /\/workspace\/|\/Users\/|ssh\s|oracle|private purify/i);
  }
});

test("publishes a reproducible 30-second media pack", async () => {
  const mediaRoot = new URL("../public/media/", import.meta.url);
  const mediaManifest = JSON.parse(
    await readFile(new URL("look-twice-replay-30s.manifest.json", mediaRoot), "utf8"),
  );
  assert.equal(mediaManifest.candidate_id, "v8-frozen");
  assert.equal(mediaManifest.replay_id, "v8-active-repair-direct");
  assert.equal(
    mediaManifest.chapter_durations_seconds.reduce((a, b) => a + b, 0),
    30,
  );
  assert.equal(mediaManifest.video.width, 1920);
  assert.equal(mediaManifest.video.height, 1080);
  assert.equal(mediaManifest.video.fps, 30);
  assert.equal(mediaManifest.video.audio, false);
  assert.equal(
    mediaManifest.recording_method,
    "recorded_trajectory_replay_cinematic_capture",
  );
  assert.equal(mediaManifest.boundary.recorded_amd_gpu_evidence, true);
  assert.equal(mediaManifest.boundary.simulation_only, true);
  assert.equal(mediaManifest.boundary.live_gpu_dependency, false);
  assert.ok(mediaManifest.video.bytes < 50 * 1024 * 1024);
  assert.equal(
    mediaManifest.bundle_sha256,
    await sha256(new URL("../public/data/replays/v8-active-repair-direct.json", import.meta.url)),
  );
  assert.equal(
    mediaManifest.video.sha256,
    await sha256(new URL(mediaManifest.video.path, mediaRoot)),
  );
  assert.equal(
    mediaManifest.poster.sha256,
    await sha256(new URL(mediaManifest.poster.path, mediaRoot)),
  );
});
