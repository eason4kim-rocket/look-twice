import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const canonicalRoot = new URL(
  "../../release/v8-derived/contract_progress_challenge_102530_102549/formal_run/",
  import.meta.url,
);
const publicRoot = new URL("../public/data/source/", import.meta.url);

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

const copies = [
  ["REPORT.json", "V8_CONTRACT_PROGRESS_FORMAL_REPORT.json"],
  ["VERIFICATION.json", "V8_CONTRACT_PROGRESS_FORMAL_VERIFICATION.json"],
  ["ROCM_TELEMETRY.json", "V8_CONTRACT_PROGRESS_FORMAL_ROCM_TELEMETRY.json"],
];

const reportBytes = await readFile(new URL(copies[0][1], publicRoot));
const verificationBytes = await readFile(new URL(copies[1][1], publicRoot));
const telemetryBytes = await readFile(new URL(copies[2][1], publicRoot));
const report = JSON.parse(reportBytes);
const verification = JSON.parse(verificationBytes);
const telemetry = JSON.parse(telemetryBytes);

test("publishes byte-identical contract-progress formal evidence", async () => {
  for (const [canonical, published] of copies) {
    assert.deepEqual(
      await readFile(new URL(published, publicRoot)),
      await readFile(new URL(canonical, canonicalRoot)),
      `${published} must remain byte-identical to ${canonical}`,
    );
  }
  assert.equal(
    sha256(reportBytes),
    "8dc2d5026f697312bd39ddf6be7a65aa3ee08ac0e2799d0ca24cf4348c439a44",
  );
  assert.equal(
    sha256(verificationBytes),
    "911495a29a51b0eb6d64c85e231e51a28713b570431b4f7dfffb60806dfb76be",
  );
  assert.equal(
    sha256(telemetryBytes),
    "11e7442fa7b1c606f6951fc4e1655ce17452eb539841ddbc5f5941ea6f71ec6a",
  );
});

test("keeps the paired denominator, direct-rate tie and safety exact", () => {
  assert.equal(report.formal_result_eligible, false);
  assert.equal(report.evidence_scope.worlds, 20);
  assert.equal(report.evidence_scope.paired_episodes, 40);
  assert.deepEqual(report.evidence_scope.seed_range, [102530, 102549]);
  assert.equal(report.evidence_scope.same_generator, true);
  assert.equal(report.evidence_scope.not_locked, true);
  assert.equal(report.evidence_scope.not_ood, true);
  assert.equal(report.evidence_scope.not_physical_robot, true);
  assert.equal(report.evidence_scope.motion_backend, "kinematic");
  assert.deepEqual(
    [report.full_chain_direct.baseline.count, report.full_chain_direct.baseline.total],
    [20, 20],
  );
  assert.deepEqual(
    [report.full_chain_direct.candidate.count, report.full_chain_direct.candidate.total],
    [20, 20],
  );
  assert.equal(report.attempt_accounting.rows, 40);
  assert.equal(report.attempt_accounting.structurally_valid, 40);
  assert.equal(report.attempt_accounting.mission_success, 40);
  assert.equal(report.attempt_accounting.unsafe, 0);
  assert.equal(report.attempt_accounting.collisions, 0);
  assert.equal(report.attempt_accounting.fallback, 0);
  assert.equal(report.attempt_accounting.false_clear, 0);
});

test("publishes the exact efficiency deltas and native selector provenance", () => {
  assert.equal(
    report.operational_burden.scout_path_length.relative_reduction,
    0.40256323121347726,
  );
  assert.equal(
    report.operational_burden.team_path_length.relative_reduction,
    0.15030573929480717,
  );
  assert.equal(
    report.operational_burden.physical_capture_count.relative_reduction,
    0.2753623188405797,
  );
  assert.equal(
    report.per_seed.filter(
      (pair) => pair.paired_deltas_candidate_minus_baseline.scout_path_length < 0,
    ).length,
    20,
  );
  assert.equal(
    report.per_seed.filter(
      (pair) => pair.paired_deltas_candidate_minus_baseline.team_path_length < 0,
    ).length,
    20,
  );
  assert.equal(
    report.per_seed.reduce(
      (total, pair) => total + pair.candidate.native_selector_decision_count,
      0,
    ),
    30,
  );
  assert.equal(
    report.per_seed.reduce(
      (total, pair) => total + pair.candidate.delegated_decision_count,
      0,
    ),
    0,
  );
});

test("retains final verifier and ROCm coverage receipts", () => {
  assert.equal(verification.stage, "final");
  assert.equal(verification.formal_result_eligible, false);
  assert.equal(verification.attempt_count, 40);
  assert.equal(verification.exact_path_set_valid, true);
  assert.equal(verification.telemetry_valid, true);
  assert.equal(verification.postrun_binding_valid, true);
  assert.equal(verification.checksum_valid, true);
  assert.equal(verification.structural_verification_pass, true);
  assert.equal(telemetry.sample_count, 554);
  assert.equal(telemetry.sample_interval_seconds, 2);
  assert.equal(telemetry.max_observed_gap_seconds, 2.232328714);
  assert.equal(telemetry.coverage_valid, true);
  assert.deepEqual(telemetry.sampler_errors, []);
});

test("site positions contract progress as additive efficiency evidence", async () => {
  const [home, results, helper] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/results/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/contractProgressEvidence.ts", import.meta.url), "utf8"),
  ]);
  assert.ok(
    home.indexOf("PREREGISTERED PRIMARY · 30 PAIRED WORLDS") <
      home.indexOf("ACTIVE-VIEW SELECTOR SUPPLEMENT · 20 PAIRED WORLDS"),
  );
  assert.ok(
    results.indexOf("PRIMARY EVIDENCE · 30 PAIRED WORLDS") <
      results.indexOf("contract-progress-efficiency"),
  );
  for (const value of ["−40.3", "−15.0", "−27.5"]) {
    assert.match(home, new RegExp(value));
  }
  assert.match(results, /This is not a second direct-rate win/);
  assert.match(results, /20 PAIRED WORLDS · 40 CELLS/);
  assert.match(results, /SCOPE OF THIS SUPPLEMENT/);
  assert.match(results, /same-generator, non-locked kinematic simulation—not OOD or physical-robot evidence/);
  assert.match(results, /This is not a claim of new weights or learned NBV/);
  assert.match(results, /does not change or replace the frozen V8 primary result/);
  assert.match(helper, /v8-contract-progress-nbv/);
  assert.match(helper, /427f2f729ce653df91a20db56c9fdbd16911a014/);
  for (const [, published] of copies) assert.match(helper, new RegExp(published));
});
