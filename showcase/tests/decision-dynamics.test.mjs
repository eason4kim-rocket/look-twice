import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

const canonicalRoot = new URL(
  "../../release/v8-derived/decision_dynamics_recovery_v2_102500_102529/",
  import.meta.url,
);
const publicRoot = new URL("../public/data/source/", import.meta.url);

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

test("publishes byte-identical decision-bound dynamics evidence", async () => {
  const copies = [
    ["REPORT.json", "V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_REPORT.json"],
    [
      "RECOVERY_EXECUTION_AUDIT.json",
      "V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_EXECUTION_AUDIT.json",
    ],
    [
      "PROVENANCE_REVIEW.json",
      "V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PROVENANCE_REVIEW.json",
    ],
    [
      "SOURCE_BINDING.json",
      "V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_SOURCE_BINDING.json",
    ],
    ["ATTEMPTS.jsonl", "V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_ATTEMPTS.jsonl"],
    ["PROGRESS.json", "V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PROGRESS.json"],
    ["SHA256SUMS", "V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_SHA256SUMS"],
    [
      "PACKAGE_SHA256SUMS",
      "V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PACKAGE_SHA256SUMS",
    ],
  ];
  for (const [canonical, published] of copies) {
    assert.deepEqual(
      await readFile(new URL(published, publicRoot)),
      await readFile(new URL(canonical, canonicalRoot)),
      `${published} must remain byte-identical to ${canonical}`,
    );
  }
});

test("30 fixed decision-bound dynamics scenes pass without broadening V8", async () => {
  const reportBytes = await readFile(new URL("REPORT.json", canonicalRoot));
  const report = JSON.parse(reportBytes);
  assert.equal(
    sha256(reportBytes),
    "1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99",
  );
  assert.equal(report.boundary.additive_non_locked, true);
  assert.equal(report.boundary.formal_result_eligible, false);
  assert.equal(report.boundary.changes_frozen_v8_endpoint, false);
  assert.equal(report.boundary.uses_archived_decisions_without_rerunning_policy, true);
  assert.equal(report.boundary.not_simultaneous_90_body_scene, true);
  assert.equal(report.execution.genesis_scene_count, 30);
  assert.equal(report.execution.non_fixed_robot_entities_per_scene, 3);
  assert.equal(report.execution.distinct_non_fixed_robot_entities_across_run, 90);
  assert.equal(report.summary.passed, 30);
  assert.equal(report.summary.failed, 0);
  assert.equal(report.summary.active_direct_decisions, 29);
  assert.equal(report.summary.active_safe_detours, 1);
  assert.equal(report.summary.direct_pairs_saving_at_least_0_50_m, 29);
  assert.ok(report.summary.paired_mean_path_reduction_percent >= 20.8);
  assert.equal(report.summary.total_blocker_contact_rows, 0);
  assert.equal(report.summary.total_active_pair_contact_rows, 0);
});

test("retained ledger shows one successful attempt per fixed seed", async () => {
  const attempts = (await readFile(new URL("ATTEMPTS.jsonl", canonicalRoot), "utf8"))
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line));
  const trials = await readdir(new URL("TRIALS/", canonicalRoot));
  assert.equal(attempts.length, 60);
  assert.equal(trials.length, 30);
  for (let index = 0; index < 30; index += 1) {
    const completed = attempts[index * 2];
    const sealed = attempts[index * 2 + 1];
    assert.equal(completed.seed, 102500 + index);
    assert.equal(completed.attempt, 1);
    assert.equal(completed.status, "completed");
    assert.equal(completed.exit_code, 0);
    assert.equal(sealed.seed, completed.seed);
    assert.equal(sealed.attempt, 1);
    assert.equal(sealed.status, "checkpoint_sealed");
  }
  const progress = JSON.parse(
    await readFile(new URL("PROGRESS.json", canonicalRoot), "utf8"),
  );
  assert.equal(progress.sealed_prefix_count, 30);
  assert.equal(progress.outcomes_exposed_in_progress_file, false);
});

test("site discloses proof-scope and scene-layout limits", async () => {
  const [home, results, reproduce, provenance] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/results/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/reproduce/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("PROVENANCE_REVIEW.json", canonicalRoot), "utf8").then(JSON.parse),
  ]);
  assert.match(home, /WAREHOUSE AMR SIMULATION/);
  assert.match(home, /PYTHON ∧ PURIFY GO/);
  assert.match(results, /ARCHIVED DECISIONS TO WHEEL DYNAMICS/);
  assert.match(results, /not a live perception-policy rerun or one simultaneous 90-body scene/);
  assert.match(results, /original formal SHA omitted attempts\/progress\/logs/);
  assert.match(results, /source binding omitted the direct v4_motion\.py dependency/);
  assert.match(results, /without claiming continuous cryptographic attestation/);
  assert.match(reproduce, /PACKAGE_SHA256SUMS/);
  assert.equal(provenance.proof_scope_findings.length, 2);
  assert.equal(provenance.required_boundary.formal_result_eligible, false);
});
