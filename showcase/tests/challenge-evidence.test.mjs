import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const publicReportUrl = new URL(
  "../public/data/source/V8_FROZEN_CHALLENGE_REPORT.json",
  import.meta.url,
);
const canonicalReportUrl = new URL(
  "../../release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json",
  import.meta.url,
);
const publicFeasibilityAuditUrl = new URL(
  "../public/data/source/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json",
  import.meta.url,
);
const canonicalFeasibilityAuditUrl = new URL(
  "../../release/v8-derived/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json",
  import.meta.url,
);
const reportBytes = await readFile(publicReportUrl);
const canonicalBytes = await readFile(canonicalReportUrl);
const feasibilityAuditBytes = await readFile(publicFeasibilityAuditUrl);
const canonicalFeasibilityAuditBytes = await readFile(canonicalFeasibilityAuditUrl);
const report = JSON.parse(reportBytes);
const feasibilityAudit = JSON.parse(feasibilityAuditBytes);
const source = async (path) =>
  readFile(new URL(`../app/${path}`, import.meta.url), "utf8");

test("publishes a byte-identical copy of the preregistered challenge report", () => {
  assert.deepEqual(reportBytes, canonicalBytes);
  assert.equal(
    createHash("sha256").update(reportBytes).digest("hex"),
    "59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0",
  );
  assert.equal(report.schema_version, "look-twice.v8-frozen-challenge-report/v1");
  assert.equal(
    report.preregistration_sha256,
    "90679e84f835c6e46983c1b219c1196506164e3c82dd1dfffec33469a73e28a2",
  );
});

test("preregistered challenge denominator, primary result and safety are exact", () => {
  const analysis = report.analysis;
  assert.equal(analysis.evidence_scope.worlds, 30);
  assert.equal(analysis.evidence_scope.paired_episodes, 60);
  assert.deepEqual(analysis.evidence_scope.seed_range, [102500, 102529]);
  assert.equal(analysis.evidence_scope.not_ood, true);
  assert.equal(analysis.primary_endpoint.active.count, 29);
  assert.equal(analysis.primary_endpoint.active.total, 30);
  assert.equal(analysis.primary_endpoint.passive.count, 0);
  assert.equal(analysis.primary_endpoint.passive.total, 30);
  assert.equal(
    analysis.primary_endpoint.exact_mcnemar_two_sided_p,
    3.725290298461914e-9,
  );
  assert.equal(analysis.secondary_endpoints.mission_success.all_episodes.count, 60);
  assert.equal(analysis.secondary_endpoints.unsafe.all_episodes.count, 0);
  assert.equal(analysis.secondary_endpoints.fallback_used.all_episodes.count, 0);
});

test("publishes the byte-identical post-hoc feasibility audit without relabeling the primary", () => {
  assert.deepEqual(feasibilityAuditBytes, canonicalFeasibilityAuditBytes);
  assert.equal(
    createHash("sha256").update(feasibilityAuditBytes).digest("hex"),
    "dc1dc979c58e1a2c1155b144c8e826ffab5ffee4e2113e954351e92bb635c434",
  );
  assert.equal(feasibilityAudit.status, "passed");
  assert.deepEqual(
    feasibilityAudit.summary.preregistered_primary_active_direct_route,
    { count: 29, denominator: 30, percent: 96.66666666666667, unchanged: true },
  );
  assert.equal(
    feasibilityAudit.summary.oracle_clear_direct_and_selected_oracle_clear.count,
    29,
  );
  assert.equal(
    feasibilityAudit.summary.oracle_clear_direct_and_selected_oracle_clear.denominator,
    29,
  );
  assert.equal(feasibilityAudit.summary.both_blocked_safe_detour.count, 1);
  assert.equal(feasibilityAudit.summary.both_blocked_safe_detour.denominator, 1);
  assert.equal(
    feasibilityAudit.summary.offline_feasibility_consistent_route_outcomes.count,
    30,
  );
  assert.equal(
    feasibilityAudit.summary.offline_feasibility_consistent_route_outcomes.denominator,
    30,
  );
  assert.equal(feasibilityAudit.evidence_boundary.post_hoc, true);
  assert.equal(
    feasibilityAudit.evidence_boundary.secondary_not_preregistered_endpoint,
    true,
  );
  assert.equal(
    feasibilityAudit.evidence_boundary.does_not_relabel_detour_as_direct,
    true,
  );
});

test("preregistered challenge telemetry, receipts and scope stay visible", async () => {
  const analysis = report.analysis;
  const comparable =
    analysis.secondary_endpoints.python_go_gate_agreement.comparable_receipts;
  assert.equal(comparable.count, 250);
  assert.equal(comparable.total, 268);
  assert.equal(analysis.full_wall_rocm_telemetry.sample_count, 844);
  assert.equal(analysis.full_wall_rocm_telemetry.sample_interval_seconds, 2);
  assert.equal(
    analysis.evidence_scope.agent_realization,
    "single_shared_genesis_chassis_with_separate_logical_role_poses",
  );

  const [home, results, consoleSource, evidenceLinks] = await Promise.all([
    source("page.tsx"),
    source("results/page.tsx"),
    source("components/EvidenceConsole.tsx"),
    source("lib/challengeEvidence.ts"),
  ]);
  for (const page of [home, results, consoleSource]) {
    assert.match(page, /29<small>\/30|primary\.active\.count|29\/30/);
    assert.match(page, /0\/30|primary\.passive\.count/);
    assert.match(page, /29<small>\/29|29\/29/);
    assert.match(page, /1<small>\/1|1\/1/);
    assert.doesNotMatch(page, /30\/30\s+(?:full-chain\s+)?direct/i);
    assert.doesNotMatch(page, /30\/30\s+preregistered/i);
  }
  assert.match(home, /Post-hoc descriptive oracle-feasibility audit/);
  assert.match(results, /Post-hoc descriptive oracle audit, not a preregistered endpoint/);
  assert.match(consoleSource, /POST-HOC, NOT THE PREREGISTERED ENDPOINT/);
  assert.match(results, /250\/\{receipts\.total\}|250\/268|receipts\.count/);
  assert.match(results, /Post-hoc descriptive audit \(not a preregistered endpoint\)/);
  assert.match(results, /all \$\{receiptMismatches\} differences were active corridor B with Python=true, Go=false, effective=false/);
  assert.match(results, /no selected crossing relied on a disagreement/);
  assert.match(results, /one shared Genesis chassis/);
  assert.match(results, /not OOD/);
  assert.match(results, /AMD FULL-WALL TELEMETRY/);
  assert.match(consoleSource, /REPLAY ≠ 30-WORLD AGGREGATE/);
  assert.match(consoleSource, /ONE SHARED CHASSIS/);
  assert.match(consoleSource, /NON-LOCKED CONFIRMATORY REPLAY/);
  assert.doesNotMatch(consoleSource, /SELECTED REPLAY: ORIGINAL 12-PAIR LOCKED TEST/);
  assert.match(evidenceLinks, /V8_FROZEN_CHALLENGE_JUDGE_CARD\.md/);
  assert.match(evidenceLinks, /V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT\.json/);
  assert.match(evidenceLinks, /dc1dc979c58e1a2c1155b144c8e826ffab5ffee4e2113e954351e92bb635c434/);
  assert.match(evidenceLinks, /v8-frozen-challenge-102500-102529\.raw\.tar\.gz/);
  assert.match(evidenceLinks, /v8-frozen-challenge-102500-102529\.VERIFICATION\.json/);
});
