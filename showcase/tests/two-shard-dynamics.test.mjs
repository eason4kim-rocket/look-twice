import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const canonicalPrefix = new URL(
  "../../release/v8-derived/decision_dynamics_single_scene_60_102500_102519/",
  import.meta.url,
);
const canonicalSuffix = new URL(
  "../../release/v8-derived/decision_dynamics_single_scene_30_suffix_102520_102529/",
  import.meta.url,
);
const publicRoot = new URL("../public/data/source/", import.meta.url);

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

test("publishes byte-identical reports and package indexes for both scene shards", async () => {
  const copies = [
    [canonicalPrefix, "REPORT.json", "V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_60_REPORT.json"],
    [canonicalPrefix, "SHA256SUMS", "V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_60_SHA256SUMS"],
    [canonicalPrefix, "PACKAGE_SHA256SUMS", "V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_60_PACKAGE_SHA256SUMS"],
    [canonicalSuffix, "REPORT.json", "V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_30_SUFFIX_REPORT.json"],
    [canonicalSuffix, "SHA256SUMS", "V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_30_SUFFIX_SHA256SUMS"],
    [canonicalSuffix, "PACKAGE_SHA256SUMS", "V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_30_SUFFIX_PACKAGE_SHA256SUMS"],
  ];
  for (const [root, canonical, published] of copies) {
    assert.deepEqual(
      await readFile(new URL(published, publicRoot)),
      await readFile(new URL(canonical, root)),
      `${published} must remain byte-identical to ${canonical}`,
    );
  }
  assert.equal(
    sha256(await readFile(new URL("REPORT.json", canonicalPrefix))),
    "3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450",
  );
  assert.equal(
    sha256(await readFile(new URL("REPORT.json", canonicalSuffix))),
    "69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e",
  );
});

test("two independent completed shards cover the fixed 30 seeds without a 90-body scene", async () => {
  const prefix = JSON.parse(await readFile(new URL("REPORT.json", canonicalPrefix)));
  const suffix = JSON.parse(await readFile(new URL("REPORT.json", canonicalSuffix)));
  assert.deepEqual(prefix.protocol.fixed_seed_order, Array.from({ length: 20 }, (_, index) => 102500 + index));
  assert.deepEqual(suffix.protocol.fixed_seed_order, Array.from({ length: 10 }, (_, index) => 102520 + index));
  assert.equal(prefix.summary.passed, 20);
  assert.equal(prefix.summary.failed, 0);
  assert.equal(suffix.summary.passed, 10);
  assert.equal(suffix.summary.failed, 0);
  assert.equal(prefix.execution.genesis_scene_count, 1);
  assert.equal(suffix.execution.genesis_scene_count, 1);
  assert.notEqual(prefix.execution.single_scene_id, suffix.execution.single_scene_id);
  assert.equal(prefix.execution.non_fixed_robot_entities_in_scene, 60);
  assert.equal(suffix.execution.non_fixed_robot_entities_in_scene, 30);
  assert.equal(prefix.execution.post_build_entity_pose_writes, 0);
  assert.equal(suffix.execution.post_build_entity_pose_writes, 0);
  assert.equal(prefix.summary.direct_pairs_saving_at_least_0_50_m + suffix.summary.direct_pairs_saving_at_least_0_50_m, 29);
  assert.equal(prefix.summary.total_blocker_contact_rows + suffix.summary.total_blocker_contact_rows, 0);
  assert.equal(prefix.summary.total_active_pair_contact_rows + suffix.summary.total_active_pair_contact_rows, 0);
  assert.equal(suffix.combined_claim_boundary.shard_count, 2);
  assert.equal(suffix.combined_claim_boundary.cumulative_non_fixed_robot_entities, 90);
  assert.equal(suffix.combined_claim_boundary.maximum_co_resident_non_fixed_robot_entities, 60);
  assert.equal(suffix.combined_claim_boundary.all_90_co_resident, false);
  assert.equal(suffix.combined_claim_boundary.prefix_independent_verification_required, true);
});

test("judge-facing site states the two-shard topology and proof boundary", async () => {
  const [home, results, reproduce, reproduceCss, evidence, publication, shell] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/results/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/reproduce/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/reproduce/reproduce.css", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/twoShardDynamicsEvidence.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/lib/publicationEvidence.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/components/SiteShell.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(home, /20\/20 @ 60-BODY \+ 10\/10 @ 30-BODY/);
  assert.match(home, /CUMULATIVE 90 · MAX CO-RESIDENT 60/);
  assert.match(results, /EXACTLY 2 SCENE SHARDS/);
  assert.match(results, /The 90 robots were never co-resident in one scene/);
  assert.match(results, /fixed-order serial wheel replay of archived decisions/);
  assert.match(results, /blocker \/ active-pair contact rows/);
  assert.match(results, /not a live perception-policy rerun inside the rigid-body run/);
  assert.match(reproduce, /never one 90-body scene/);
  assert.match(reproduce, /PACKAGE INDEX \(CLONE REQUIRED\)/);
  assert.match(reproduce, /running shasum -c requires the repository's trials, logs and source binding/);
  assert.match(reproduce, /verify_v8_additive_decision_dynamics_60\.py/);
  assert.match(reproduce, /verify_v8_additive_decision_dynamics_30_suffix\.py/);
  assert.match(reproduceCss, /\.challenge-repro > div \{ min-width: 0; \}/);
  assert.match(evidence, /3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450/);
  assert.match(evidence, /69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e/);
  assert.match(results, /PUBLICATION & UPSTREAM/);
  assert.match(results, /no upstream maintainer review, merge, or acceptance is claimed here/);
  assert.match(results, /publicationEvidence\.finalSourceTagUrl/);
  assert.match(publication, /v8-contract-progress-nbv/);
  assert.match(publication, /v8-competition-final-2026-08-05/);
  assert.match(publication, /V8_GENESIS_PR_3184_VALIDATION\.md/);
  assert.match(publication, /Genesis-Embodied-AI\/genesis-world\/issues\/3183/);
  assert.match(publication, /Genesis-Embodied-AI\/genesis-world\/pull\/3184/);
  assert.match(publication, /0fa0f4ae5c83e964282fea1d6ad44aa333ee1850/);
  assert.match(publication, /submission\/track3-liu-liang-look-twice-v8/);
  assert.match(publication, /7dc0b453191a4ea215e432f22de6b374319c8df72580026f3adc8fa064291143/);
  assert.match(shell, /publicationEvidence\.genesisPullRequestUrl/);
  assert.match(shell, /publicationEvidence\.competitionPackageUrl/);
  assert.match(shell, /publicationEvidence\.sourceBranchUrl/);
  assert.doesNotMatch(`${home}\n${results}\n${reproduce}`, /90 (?:robots|bodies) co-resident/i);
});
