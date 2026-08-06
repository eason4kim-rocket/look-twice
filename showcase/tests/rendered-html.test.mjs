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

function ascii(bytes, start = 0, end = bytes.length) {
  return bytes.toString("ascii", start, end);
}

function uint24le(bytes, offset) {
  return bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16);
}

function inspectAnimatedWebp(bytes) {
  assert.equal(ascii(bytes, 0, 4), "RIFF");
  assert.equal(ascii(bytes, 8, 12), "WEBP");
  assert.equal(bytes.readUInt32LE(4) + 8, bytes.length);

  let width;
  let height;
  let loopCount;
  let frameCount = 0;
  let durationMilliseconds = 0;
  for (let offset = 12; offset + 8 <= bytes.length;) {
    const type = ascii(bytes, offset, offset + 4);
    const size = bytes.readUInt32LE(offset + 4);
    const payload = offset + 8;
    assert.ok(payload + size <= bytes.length, `${type} chunk exceeds the WebP container`);
    if (type === "VP8X") {
      assert.ok(bytes[payload] & 0x02, "VP8X must advertise animation");
      width = uint24le(bytes, payload + 4) + 1;
      height = uint24le(bytes, payload + 7) + 1;
    } else if (type === "ANIM") {
      loopCount = bytes.readUInt16LE(payload + 4);
    } else if (type === "ANMF") {
      frameCount += 1;
      durationMilliseconds += uint24le(bytes, payload + 12);
    }
    offset = payload + size + (size % 2);
  }
  return { width, height, loopCount, frameCount, durationMilliseconds };
}

function inspectMp4(bytes) {
  const text = ascii(bytes);
  const moovOffset = text.indexOf("moov");
  const mdatOffset = text.indexOf("mdat");
  assert.equal(ascii(bytes, 4, 8), "ftyp");
  assert.ok(moovOffset > 0, "MP4 must contain a moov box");
  assert.ok(mdatOffset > 0, "MP4 must contain an mdat box");
  assert.ok(moovOffset < mdatOffset, "MP4 must be faststart");

  const moov = text.slice(moovOffset, mdatOffset);
  assert.match(moov, /avc1/, "MP4 track must use H.264/AVC");
  assert.match(moov, /vide/, "MP4 must contain a video track");
  assert.doesNotMatch(moov, /soun/, "judge hook must not contain an audio track");

  const mvhdOffset = text.indexOf("mvhd", moovOffset);
  assert.ok(mvhdOffset > moovOffset && mvhdOffset < mdatOffset, "MP4 must contain mvhd");
  assert.equal(bytes[mvhdOffset + 4], 0, "test expects a version-zero mvhd box");
  const timescale = bytes.readUInt32BE(mvhdOffset + 16);
  const duration = bytes.readUInt32BE(mvhdOffset + 20);
  return { durationSeconds: duration / timescale };
}

test("server-renders the Look Twice product entry", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>Look Twice — Action-Ready Evidence for Warehouse Robots<\/title>/i);
  assert.match(html, /Before a robot acts/);
  assert.match(html, /Open Evidence Console/);
  assert.match(html, /RECORDED 3:59 AMD GPU WORKFLOW/);
  assert.match(html, /\/media\/Look-Twice-V8-Demo\.mp4/);
  assert.match(html, /not physical-robot footage/);
  assert.match(html, /\/media\/look-twice-repair-to-action-10s\.mp4/);
  assert.match(html, /(?:recorded replay|recorded simulation replay|simulation only)/i);
  assert.match(html, /href=["']#full-demo["']/i);
  assert.match(html, /id=["']full-demo["']/i);
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
  const sourceManifestUrl = new URL("look-twice-replay-30s.manifest.json", mediaRoot);
  const mediaManifest = JSON.parse(
    await readFile(sourceManifestUrl, "utf8"),
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

  const hookManifest = JSON.parse(
    await readFile(new URL("look-twice-repair-to-action-10s.manifest.json", mediaRoot), "utf8"),
  );
  assert.equal(hookManifest.schema_version, "look-twice.judge-motion-hook/v1");
  assert.equal(hookManifest.candidate_id, "v8-frozen");
  assert.equal(hookManifest.hook_id, "repair-to-action-10s");
  assert.equal(hookManifest.derived_from.sha256, mediaManifest.video.sha256);
  assert.equal(hookManifest.derived_from.manifest_sha256, await sha256(sourceManifestUrl));
  assert.equal(hookManifest.derived_from.recorded_at_utc, mediaManifest.recorded_at_utc);
  assert.equal(
    hookManifest.derived_from.sha256,
    await sha256(new URL(mediaManifest.video.path, mediaRoot)),
  );
  assert.equal(
    hookManifest.derived_from.source_end_seconds - hookManifest.derived_from.source_start_seconds,
    hookManifest.video.duration_seconds,
  );
  assert.ok(hookManifest.video.duration_seconds >= 5);
  assert.ok(hookManifest.video.duration_seconds <= 10);
  assert.equal(hookManifest.video.codec, "h264");
  assert.equal(hookManifest.video.pixel_format, "yuv420p");
  assert.equal(hookManifest.video.width, 1280);
  assert.equal(hookManifest.video.height, 720);
  assert.equal(hookManifest.video.fps, 30);
  assert.equal(hookManifest.video.audio, false);
  assert.equal(hookManifest.video.faststart, true);
  assert.ok(hookManifest.video.bytes < 1024 * 1024);
  assert.equal(hookManifest.boundary.recorded_replay_excerpt, true);
  assert.equal(hookManifest.boundary.new_experiment_or_result, false);
  assert.equal(hookManifest.boundary.simulation_only, true);
  assert.equal(hookManifest.boundary.real_robot_footage, false);
  assert.equal(hookManifest.boundary.audio, false);

  const hookVideoUrl = new URL(hookManifest.video.path, mediaRoot);
  const hookVideo = await readFile(hookVideoUrl);
  assert.equal(hookManifest.video.bytes, hookVideo.length);
  assert.equal(hookManifest.video.sha256, await sha256(hookVideoUrl));
  assert.equal(inspectMp4(hookVideo).durationSeconds, hookManifest.video.duration_seconds);

  const previewUrl = new URL(hookManifest.readme_preview.path, mediaRoot);
  const preview = await readFile(previewUrl);
  const previewInspection = inspectAnimatedWebp(preview);
  assert.equal(hookManifest.readme_preview.bytes, preview.length);
  assert.equal(hookManifest.readme_preview.sha256, await sha256(previewUrl));
  assert.equal(hookManifest.readme_preview.format, "animated_webp");
  assert.equal(previewInspection.width, hookManifest.readme_preview.width);
  assert.equal(previewInspection.height, hookManifest.readme_preview.height);
  assert.equal(previewInspection.loopCount, 0);
  assert.ok(previewInspection.frameCount > 1);
  assert.equal(
    previewInspection.durationMilliseconds / 1000,
    hookManifest.readme_preview.duration_seconds,
  );
  assert.equal(hookManifest.readme_preview.loop, true);
  assert.ok(hookManifest.readme_preview.duration_seconds >= 5);
  assert.ok(hookManifest.readme_preview.duration_seconds <= 10);
});

test("publishes the complete browser-playable 3:59 demo", async () => {
  const mediaRoot = new URL("../public/media/", import.meta.url);
  const demoManifest = JSON.parse(
    await readFile(new URL("Look-Twice-V8-Demo.manifest.json", mediaRoot), "utf8"),
  );
  assert.equal(demoManifest.candidate_id, "v8-frozen");
  assert.equal(demoManifest.language, "English");
  assert.equal(demoManifest.video.filename, "Look-Twice-V8-Demo.mp4");
  assert.equal(demoManifest.video.duration_seconds, 239);
  assert.equal(demoManifest.video.width, 1920);
  assert.equal(demoManifest.video.height, 1080);
  assert.equal(demoManifest.video.fps, 30);
  assert.equal(demoManifest.video.codec, "h264");
  assert.equal(demoManifest.video.audio_codec, "aac");
  assert.equal(demoManifest.video.faststart, true);
  assert.equal(demoManifest.narration.ai_generated, true);
  assert.equal(demoManifest.narration.disclosure_burned_in, true);
  assert.equal(
    demoManifest.video.sha256,
    await sha256(new URL(demoManifest.video.filename, mediaRoot)),
  );
});
