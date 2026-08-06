export const decisionDynamicsEvidence = {
  reportUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_REPORT.json",
  executionAuditUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_EXECUTION_AUDIT.json",
  provenanceReviewUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PROVENANCE_REVIEW.json",
  sourceBindingUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_SOURCE_BINDING.json",
  attemptsUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_ATTEMPTS.jsonl",
  progressUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PROGRESS.json",
  checksumsUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_SHA256SUMS",
  packageChecksumsUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PACKAGE_SHA256SUMS",
  protocolUrl:
    "https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PROTOCOL.md",
  resultNoteUrl:
    "https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_RESULT.md",
  reportSha256:
    "1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99",
  sourceBindingSha256:
    "c40f6ba74a39ad761e4926ddb66326f33a1a645fef3c96364f9c53b9d5d3eb5d",
  executionAuditSha256:
    "344a948da49f89322f3486da2c025ee227dbf3454b33f7f8ab2f8acf6ea8eca4",
  provenanceReviewSha256:
    "4667a9f817c882e7cbe6b358c207a2fb3cc6afec643e185e99fbd30ae0f959a7",
  packageChecksumsSha256:
    "24d3538365d2818f5e5b64c5f06ecee94bdeae1e4d3df2ab320178248bf71540",
  sourceCommit: "b0c4f0d33b0a2d0c647dda0b2b3b7c03279a511a",
} as const;

export type DecisionDynamicsReport = {
  generated_at_utc: string;
  run_class: string;
  boundary: {
    additive_non_locked: boolean;
    formal_result_eligible: boolean;
    changes_frozen_v8_endpoint: boolean;
    uses_archived_decisions_without_rerunning_policy: boolean;
    not_simultaneous_90_body_scene: boolean;
  };
  source: {
    git_commit: string;
    git_status_porcelain_at_initial_start: string;
    source_binding_sha256: string;
  };
  protocol: {
    seed_order: number[];
    execution_layout: string;
    post_build_actuation_api: string;
    post_build_entity_pose_writes: number;
  };
  execution: {
    atomic_checkpoint_per_completed_seed: boolean;
    completed_checkpoint_reruns: number;
    seed_replacements: number;
    genesis_scene_count: number;
    non_fixed_robot_entities_per_scene: number;
    distinct_non_fixed_robot_entities_across_run: number;
  };
  summary: {
    trials: number;
    passed: number;
    failed: number;
    all_passed: boolean;
    active_direct_decisions: number;
    active_safe_detours: number;
    active_scout_reached: number;
    active_carrier_reached: number;
    passive_carrier_reached: number;
    distinct_non_fixed_robot_entities: number;
    direct_pairs_saving_at_least_0_50_m: number;
    mean_active_loaded_carrier_path_m: number;
    mean_passive_loaded_carrier_path_m: number;
    paired_mean_path_reduction_percent: number;
    total_blocker_contact_rows: number;
    total_active_pair_contact_rows: number;
    maximum_tilt_deg: number;
    maximum_stationary_partner_drift_m: number;
  };
};
