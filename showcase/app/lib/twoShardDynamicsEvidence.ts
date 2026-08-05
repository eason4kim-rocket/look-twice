export const twoShardDynamicsEvidence = {
  prefixReportUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_60_REPORT.json",
  prefixChecksumsUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_60_SHA256SUMS",
  prefixPackageChecksumsUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_60_PACKAGE_SHA256SUMS",
  suffixReportUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_30_SUFFIX_REPORT.json",
  suffixChecksumsUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_30_SUFFIX_SHA256SUMS",
  suffixPackageChecksumsUrl:
    "/data/source/V8_ADDITIVE_DECISION_DYNAMICS_SINGLE_SCENE_30_SUFFIX_PACKAGE_SHA256SUMS",
  prefixProtocolUrl:
    "https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DECISION_DYNAMICS_60_PROTOCOL.md",
  suffixProtocolUrl:
    "https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DECISION_DYNAMICS_30_SUFFIX_PROTOCOL.md",
  prefixReportSha256:
    "3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450",
  prefixPackageChecksumsSha256:
    "8d4f891e6bacbf8627a9ba441c5396525259b88b8d4350c5b84bef7db6277c55",
  suffixReportSha256:
    "69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e",
  suffixPackageChecksumsSha256:
    "930f41c497e8aaa6dceb4ee12f6b7b87cea189c2320e3d90d1c03e850ca16d4b",
} as const;

export type SingleSceneDecisionDynamicsReport = {
  schema_version: string;
  run_class: string;
  boundary: {
    additive_non_locked: boolean;
    changes_frozen_v8_endpoint: boolean;
    formal_result_eligible: boolean;
    fixed_order_serial_actuation: boolean;
    simultaneous_cooperative_control: boolean;
    uses_archived_decisions_without_rerunning_policy: boolean;
  };
  execution: {
    genesis_scene_count: number;
    non_fixed_robot_entities_in_scene: number;
    post_build_entity_pose_writes: number;
    post_build_motion_actuation_api: string;
    scene_build_count: number;
    single_scene_id: string;
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
    direct_pairs_saving_at_least_0_50_m: number;
    distinct_non_fixed_robot_entities: number;
    mean_active_loaded_carrier_path_m: number;
    mean_passive_loaded_carrier_path_m: number;
    paired_mean_path_reduction_percent: number;
    total_active_pair_contact_rows: number;
    total_blocker_contact_rows: number;
    maximum_tilt_deg: number;
    maximum_stationary_partner_drift_m: number;
  };
  combined_claim_boundary?: {
    all_90_co_resident: boolean;
    cumulative_non_fixed_robot_entities: number;
    maximum_co_resident_non_fixed_robot_entities: number;
    prefix_exact_sha256_bound: string;
    prefix_independent_verification_required: boolean;
    shard_count: number;
    suffix_passed: boolean;
  } | null;
};
