export const contractProgressEvidence = {
  reportUrl:
    "/data/source/V8_CONTRACT_PROGRESS_FORMAL_REPORT.json",
  verificationUrl:
    "/data/source/V8_CONTRACT_PROGRESS_FORMAL_VERIFICATION.json",
  rocmTelemetryUrl:
    "/data/source/V8_CONTRACT_PROGRESS_FORMAL_ROCM_TELEMETRY.json",
  preregistrationBranchUrl:
    "https://github.com/eason4kim-rocket/look-twice/tree/v8-contract-progress-nbv",
  commitBUrl:
    "https://github.com/eason4kim-rocket/look-twice/commit/427f2f729ce653df91a20db56c9fdbd16911a014",
  commitB: "427f2f729ce653df91a20db56c9fdbd16911a014",
  reportSha256:
    "8dc2d5026f697312bd39ddf6be7a65aa3ee08ac0e2799d0ca24cf4348c439a44",
  verificationSha256:
    "911495a29a51b0eb6d64c85e231e51a28713b570431b4f7dfffb60806dfb76be",
  rocmTelemetrySha256:
    "11e7442fa7b1c606f6951fc4e1655ce17452eb539841ddbc5f5941ea6f71ec6a",
} as const;

type Distribution = {
  mean: number;
  median: number;
  minimum: number;
  maximum: number;
};

type PairedBurdenMetric = {
  n: number;
  valid: boolean;
  baseline: Distribution;
  candidate: Distribution;
  paired_delta_candidate_minus_baseline: Distribution & {
    bootstrap_95: {
      method: string;
      replicates: number;
      rng_seed: number;
      lower: number;
      upper: number;
    };
  };
  relative_reduction: number;
  relative_reduction_bootstrap_95: {
    lower: number;
    upper: number;
  };
};

type DirectRate = {
  count: number;
  total: number;
  rate: number;
  lower: number;
  upper: number;
};

export type ContractProgressReport = {
  schema_version: string;
  formal_result_eligible: false;
  evidence_scope: {
    worlds: number;
    paired_episodes: number;
    seed_range: [number, number];
    generator_family: string;
    same_generator: boolean;
    not_ood: boolean;
    not_physical_robot: boolean;
    not_locked: boolean;
    motion_backend: string;
  };
  source_binding: {
    preregistration_sha256: string;
    run_manifest_sha256: string;
  };
  attempt_accounting: {
    rows: number;
    structurally_valid: number;
    mission_success: number;
    unsafe: number;
    false_clear: number;
    fallback: number;
    collisions: number;
  };
  full_chain_direct: {
    baseline: DirectRate;
    candidate: DirectRate;
    paired_table: {
      baseline_only: number;
      candidate_only: number;
      both_direct: number;
      neither_direct: number;
    };
  };
  operational_burden: {
    scout_path_length: PairedBurdenMetric;
    carrier_path_length: PairedBurdenMetric;
    team_path_length: PairedBurdenMetric;
    physical_capture_count: PairedBurdenMetric;
  };
  mandatory_gates: {
    all_pass: boolean;
  };
  capability_gates: {
    scout_path_relative_reduction_observed: number;
    team_path_relative_reduction_observed: number;
    physical_capture_relative_reduction_observed: number;
    all_pass: boolean;
  };
  promotion_pass: boolean;
  per_seed: Array<{
    seed: number;
    candidate: {
      native_selector_decision_count: number;
      nondelegated_candidate_chosen_count: number;
      delegated_chosen_count: number;
      delegated_decision_count: number;
    };
    paired_deltas_candidate_minus_baseline: {
      scout_path_length: number;
      carrier_path_length: number;
      team_path_length: number;
      physical_capture_count: number;
      vision_proposal_count: number;
    };
  }>;
};

export type ContractProgressVerification = {
  schema_version: string;
  verified_at_utc: string;
  formal_result_eligible: false;
  stage: string;
  attempt_count: number;
  exact_path_set_valid: boolean;
  telemetry_valid: boolean;
  raw_telemetry_observation: {
    sample_count: number;
    max_observed_gap_seconds: number;
    challenge_window_contains_all_attempts: boolean;
    raw_samples_cover_challenge_window: boolean;
    strictly_increasing_timestamps: boolean;
    summary_recomputed: boolean;
  };
  postrun_binding_valid: boolean;
  checksum_valid: boolean;
  mandatory_gates: { all_pass: boolean };
  capability_gates: { all_pass: boolean };
  promotion_pass: boolean;
  structural_verification_pass: boolean;
};

type TelemetryDistribution = {
  mean: number;
  minimum: number;
  maximum: number;
  median: number;
  samples: number;
};

export type ContractProgressRocmTelemetry = {
  schema_version: string;
  sample_interval_seconds: number;
  max_allowed_gap_seconds: number;
  challenge_started_monotonic_ns: number;
  challenge_ended_monotonic_ns: number;
  sample_count: number;
  max_observed_gap_seconds: number;
  sampler_errors: unknown[];
  coverage_valid: boolean;
  summary: {
    sample_count: number;
    gpu_use_percent: TelemetryDistribution;
    vram_allocated_percent: TelemetryDistribution;
    memory_activity_percent: TelemetryDistribution;
    graphics_package_power_w: TelemetryDistribution;
    temperature_edge_c: TelemetryDistribution;
    temperature_junction_c: TelemetryDistribution;
    temperature_memory_c: TelemetryDistribution;
  };
};
