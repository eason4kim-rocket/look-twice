import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const canonicalRoot = new URL(
  "../../release/v8-derived/dual_body_dynamics_160820_160839/",
  import.meta.url,
);
const publicRoot = new URL("../public/data/source/", import.meta.url);

async function bytes(url) {
  return readFile(url);
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

test("publishes byte-identical sealed dual-body dynamics evidence", async () => {
  const copies = [
    ["REPORT.json", "V8_ADDITIVE_DUAL_BODY_DYNAMICS_REPORT.json"],
    [
      "ATTEMPT_1_TIMEOUT_AUDIT.json",
      "V8_ADDITIVE_DUAL_BODY_DYNAMICS_TIMEOUT_AUDIT.json",
    ],
    [
      "RECOVERY_EXECUTION_AUDIT.json",
      "V8_ADDITIVE_DUAL_BODY_DYNAMICS_RECOVERY_AUDIT.json",
    ],
    ["SHA256SUMS", "V8_ADDITIVE_DUAL_BODY_DYNAMICS_SHA256SUMS"],
  ];
  for (const [canonical, published] of copies) {
    assert.deepEqual(
      await bytes(new URL(published, publicRoot)),
      await bytes(new URL(canonical, canonicalRoot)),
      `${published} must remain byte-identical to ${canonical}`,
    );
  }
});

test("dual-body report passes the fixed all-seed bar without broadening V8", async () => {
  const reportBytes = await bytes(new URL("REPORT.json", canonicalRoot));
  const report = JSON.parse(reportBytes);
  assert.equal(
    sha256(reportBytes),
    "8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110",
  );
  assert.equal(report.boundary.additive_non_locked, true);
  assert.equal(report.boundary.formal_result_eligible, false);
  assert.equal(report.boundary.changes_frozen_v8_endpoint, false);
  assert.deepEqual(report.protocol.seeds, Array.from({ length: 20 }, (_, i) => 160820 + i));
  assert.equal(report.protocol.post_build_actuation_api, "control_dofs_velocity only");
  assert.equal(
    report.protocol.carrier_and_scout_are_distinct_non_fixed_entities,
    true,
  );
  assert.equal(report.summary.passed, 20);
  assert.equal(report.summary.failed, 0);
  assert.equal(report.summary.all_passed, true);
  assert.equal(report.summary.distinct_non_fixed_robot_entities, 40);
  assert.equal(report.summary.total_obstacle_contact_rows, 0);
  assert.equal(report.summary.total_pair_robot_contact_rows, 0);
  assert.ok(
    report.trials.every(
      (trial) =>
        trial.assessment.passed === true &&
        trial.script_entity_set_pos_calls_after_build === 0,
    ),
  );
});

test("watchdog recovery changes no scientific input", async () => {
  const timeout = JSON.parse(
    await readFile(new URL("ATTEMPT_1_TIMEOUT_AUDIT.json", canonicalRoot), "utf8"),
  );
  const recovery = JSON.parse(
    await readFile(new URL("RECOVERY_EXECUTION_AUDIT.json", canonicalRoot), "utf8"),
  );
  assert.equal(timeout.status, "infrastructure_watchdog_timeout");
  assert.equal(timeout.execution.report_written, false);
  assert.equal(timeout.execution.per_seed_outcomes_observed, false);
  assert.equal(recovery.status, "completed_and_verified");
  assert.equal(recovery.execution.outer_watchdog_seconds, 10800);
  assert.equal(recovery.continuity_from_attempt_1.git_commit_unchanged, true);
  assert.equal(recovery.continuity_from_attempt_1.script_and_urdf_bytes_unchanged, true);
  assert.equal(recovery.continuity_from_attempt_1.confirmatory_seeds_unchanged, true);
  assert.equal(recovery.confirmatory_set.observed_seed_outcome_retried_or_replaced, false);
  assert.equal(recovery.verification.remote.exit_code, 0);
  assert.equal(recovery.verification.local.exit_code, 0);
});

test("site keeps frozen shared-chassis and additive dual-body claims separate", async () => {
  const [home, results, evidenceSource] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/results/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/dynamicsEvidence.ts", import.meta.url), "utf8"),
  ]);
  assert.match(home, /PREREGISTERED PRIMARY · 30 PAIRED WORLDS/);
  assert.match(home, /WAREHOUSE AMR SIMULATION/);
  assert.match(results, /SEPARATE ADDITIVE · DUAL-BODY RIGID DYNAMICS/);
  assert.match(results, /not a frozen-policy rerun/);
  assert.match(results, /not a physical-robot result/);
  assert.match(results, /Attempt 1 hit only the external watchdog/);
  assert.match(evidenceSource, /8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110/);
});
