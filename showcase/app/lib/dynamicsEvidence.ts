export const dynamicsEvidence = {
  reportUrl: "/data/source/V8_ADDITIVE_DUAL_BODY_DYNAMICS_REPORT.json",
  timeoutAuditUrl:
    "/data/source/V8_ADDITIVE_DUAL_BODY_DYNAMICS_TIMEOUT_AUDIT.json",
  recoveryAuditUrl:
    "/data/source/V8_ADDITIVE_DUAL_BODY_DYNAMICS_RECOVERY_AUDIT.json",
  checksumsUrl:
    "/data/source/V8_ADDITIVE_DUAL_BODY_DYNAMICS_SHA256SUMS",
  protocolUrl:
    "https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_PROTOCOL.md",
  resultNoteUrl:
    "https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_RESULT.md",
  reportSha256:
    "8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110",
  timeoutAuditSha256:
    "711547fb5f0ab928ae5cc8b6195f4e0e964a98f6df44dfa2955c67e624705d55",
  recoveryAuditSha256:
    "6c3ddfa0ec2b482c1ab01a160572d01451f0bb1b495137e09a18a96018f23e6e",
  sourceCommit: "c17c3a17904af34ba514d68e6e5ad8d1d96a353b",
} as const;

export type DynamicsReport = {
  generated_at_utc: string;
  boundary: {
    additive_non_locked: boolean;
    formal_result_eligible: boolean;
    changes_frozen_v8_endpoint: boolean;
  };
  source: {
    git_commit: string;
    git_status_porcelain: string;
  };
  environment: {
    genesis: string;
    torch: string;
    torch_hip: string;
    backend_requested: string;
    gpu: string;
  };
  protocol: {
    seeds: number[];
    post_build_actuation_api: string;
    carrier_and_scout_are_distinct_non_fixed_entities: boolean;
  };
  summary: {
    trials: number;
    passed: number;
    failed: number;
    all_passed: boolean;
    distinct_non_fixed_robot_entities: number;
    total_obstacle_contact_rows: number;
    total_pair_robot_contact_rows: number;
    maximum_tilt_deg: number;
    maximum_stationary_partner_drift_m: number;
    mean_scout_path_m: number;
    mean_carrier_path_m: number;
  };
  trials: Array<{
    seed: number;
    script_entity_set_pos_calls_after_build: number;
    assessment: { passed: boolean };
    scout: { final_goal_error_m: number; path_length_m: number };
    carrier: { final_goal_error_m: number; path_length_m: number };
  }>;
};
