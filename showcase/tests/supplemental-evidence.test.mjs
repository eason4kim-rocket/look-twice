import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const resultsSource = await readFile(
  new URL("../app/results/page.tsx", import.meta.url),
  "utf8",
);

test("presents the locked archive as input-and-label evidence only", () => {
  assert.match(resultsSource, /LOCKED INPUT EVIDENCE PACK/);
  assert.match(resultsSource, /400 worlds and 3,200 metadata records generated before the formal open/);
  assert.match(
    resultsSource,
    /0933053f28aca5254f13eb2eb11ce16c2f488e1880e4e282b1e4dfd7d957cfba/,
  );
  assert.match(
    resultsSource,
    /v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z\.tar\.gz/,
  );
  assert.match(resultsSource, /docs\/V8_LOCKED_INPUT_EVIDENCE\.md/);
  assert.match(resultsSource, /V8_LOCKED_INPUT_PACK_MANIFEST\.json/);
  assert.match(resultsSource, /does not contain the original one-shot per-sample predictions/);
  assert.match(resultsSource, /24 raw locked live episodes/);
  assert.match(resultsSource, /cannot recompute the 1\.000 metrics/);
});

test("does not promote the reserved generator-family range as OOD evidence", () => {
  assert.match(resultsSource, /were evaluated once after public preregistration/);
  assert.match(resultsSource, /seeds 102530–102699 remain unevaluated/);
  assert.match(resultsSource, /Neither is presented as OOD/);
  assert.doesNotMatch(resultsSource, /OOD test/i);
  assert.doesNotMatch(resultsSource, /out-of-domain (?:test|result|evaluation)/i);
});

test("scopes the frozen ROCm telemetry to its controlled workload", () => {
  assert.match(resultsSource, /OLDER SEPARATE SUPPLEMENT · SYNTHETIC 60s FORWARD DEMO/);
  assert.match(resultsSource, /not the preregistered challenge's full-wall telemetry above/);
  assert.match(resultsSource, /CLEAN PREFLIGHT/);
  assert.match(resultsSource, /61<small>\/61 @ 100%<\/small>/);
  assert.match(resultsSource, /135\.33<small> W<\/small>/);
  assert.match(resultsSource, /156<small> W<\/small>/);
  assert.match(resultsSource, /376<small> \/ 60\.182 s<\/small>/);
  assert.match(resultsSource, /synthetic, preloaded-tensor, FP32 frozen-model forwards/);
  assert.match(resultsSource, /neither end-to-end performance nor an accuracy evaluation/);
  assert.match(resultsSource, /V8_FROZEN_ROCM_TELEMETRY\.json/);
});
