// Package purifyrobotics implements the contest-only Purify Robotics Reference Core.
//
// It intentionally has no dependency on the private Purify product. The public
// wire types in this package form the Robot Evidence Contract used by Look Twice.
package purifyrobotics

import "encoding/json"

const (
	CommandSchema                 = "purify.robotics.command.v1"
	ResponseSchema                = "purify.robotics.response.v1"
	RobotClaimSchema              = "look-twice.robot-claim/v1"
	ActionContractSchema          = "purify.robotics.action-contract/v1"
	CalibrationArtifactSchema     = "purify.robotics.calibration.v1"
	BeliefGapSchema               = "purify.robotics.belief-gap/v1"
	GateReceiptSchema             = "purify.robotics.gate-receipt/v1"
	PlanInvalidationReceiptSchema = "purify.robotics.plan-invalidation-receipt/v1"
)

const (
	OperationEvaluateAction = "evaluate_action"
	OperationInvalidatePlan = "invalidate_plan"
)

// ClaimScope identifies the physical action context to which evidence applies.
// Scope comparison is exact: empty fields are not wildcards.
type ClaimScope struct {
	RobotID   string `json:"robot_id"`
	PayloadID string `json:"payload_id"`
	RegionID  string `json:"region_id"`
}

// RobotClaim is one independently auditable assertion. Clean simulator truth
// must never be represented as a RobotClaim; it belongs in evaluation-only data.
type RobotClaim struct {
	SchemaVersion  string     `json:"schema_version"`
	ClaimID        string     `json:"claim_id"`
	FactID         string     `json:"fact_id"`
	Predicate      string     `json:"predicate"`
	Value          string     `json:"value"`
	Confidence     float64    `json:"confidence"`
	ObservedStep   int64      `json:"observed_step"`
	ValidUntilStep int64      `json:"valid_until_step"`
	Modality       string     `json:"modality"`
	DeviceRootID   string     `json:"device_root_id"`
	CaptureRootID  string     `json:"capture_root_id"`
	CalibrationID  string     `json:"calibration_id"`
	PoseVersion    string     `json:"pose_version"`
	ModelID        string     `json:"model_id"`
	ArtifactSHA256 string     `json:"artifact_sha256"`
	ParentClaimIDs []string   `json:"parent_claim_ids"`
	Quality        float64    `json:"quality"`
	Visibility     float64    `json:"visibility"`
	TemporalSkew   int64      `json:"temporal_skew"`
	Scope          ClaimScope `json:"scope"`
}

// ActionContract is the complete admission policy for one physical action.
type ActionContract struct {
	SchemaVersion                string     `json:"schema_version"`
	ContractID                   string     `json:"contract_id"`
	Action                       string     `json:"action"`
	FactID                       string     `json:"fact_id"`
	Predicate                    string     `json:"predicate"`
	Scope                        ClaimScope `json:"scope"`
	RequiredPredictionSet        []string   `json:"required_prediction_set"`
	MaxEvidenceAge               int64      `json:"max_evidence_age"`
	MinDistinctMeasurementRoots  int        `json:"min_distinct_measurement_roots"`
	MaxModalitySkew              int64      `json:"max_modality_skew"`
	MaxUnresolvedConflicts       int        `json:"max_unresolved_conflicts"`
	RequireCalibrationApplicable bool       `json:"require_calibration_applicable"`
}

// CalibrationArtifact contains class-conditional split-conformal quantiles
// and the exact distribution/version scope in which they are applicable.
type CalibrationArtifact struct {
	SchemaVersion      string             `json:"schema_version"`
	ArtifactID         string             `json:"artifact_id"`
	Alpha              float64            `json:"alpha"`
	ClassQuantiles     map[string]float64 `json:"class_quantiles"`
	ApplicableProfiles []string           `json:"applicable_profiles"`
	MinNoiseIntensity  float64            `json:"min_noise_intensity"`
	MaxNoiseIntensity  float64            `json:"max_noise_intensity"`
	SensorVersions     []string           `json:"sensor_versions"`
	GitCommit          string             `json:"git_commit"`
	DatasetSHA256      string             `json:"dataset_sha256"`
	SeedRanges         []SeedRange        `json:"seed_ranges"`
}

// SeedRange is inclusive at both ends.
type SeedRange struct {
	Start int64 `json:"start"`
	End   int64 `json:"end"`
}

// EvaluationContext contains only declared runtime context. In particular it
// contains no oracle labels, future observations, or realized noise parameters.
type EvaluationContext struct {
	CurrentStep    int64   `json:"current_step"`
	Profile        string  `json:"profile"`
	NoiseIntensity float64 `json:"noise_intensity"`
	SensorVersion  string  `json:"sensor_version"`
}

type EvaluateActionRequest struct {
	Claims      []RobotClaim        `json:"claims"`
	Contract    ActionContract      `json:"contract"`
	Calibration CalibrationArtifact `json:"calibration"`
	Context     EvaluationContext   `json:"context"`
}

// ClauseResult makes every admission requirement independently auditable.
type ClauseResult struct {
	Clause   string `json:"clause"`
	Required any    `json:"required"`
	Actual   any    `json:"actual"`
	Passed   bool   `json:"passed"`
}

type DiscountedClaim struct {
	ClaimID string `json:"claim_id"`
	Reason  string `json:"reason"`
}

// BeliefGap is a finite, machine-readable explanation of why evidence is not
// action-ready. Reason is restricted by validation/build logic in engine.go.
type BeliefGap struct {
	SchemaVersion string   `json:"schema_version"`
	Reason        string   `json:"reason"`
	ClaimIDs      []string `json:"claim_ids"`
	Detail        string   `json:"detail"`
}

// GateReceipt is the deterministic, content-addressed result of evaluating an
// ActionContract. ReceiptSHA256 hashes the canonical receipt with that field
// omitted; ReceiptID is derived from the pre-ID content hash.
type GateReceipt struct {
	SchemaVersion         string            `json:"schema_version"`
	ReceiptID             string            `json:"receipt_id"`
	ContractID            string            `json:"contract_id"`
	Action                string            `json:"action"`
	FactID                string            `json:"fact_id"`
	Predicate             string            `json:"predicate"`
	Scope                 ClaimScope        `json:"scope"`
	EvaluatedStep         int64             `json:"evaluated_step"`
	ValidUntilStep        int64             `json:"valid_until_step"`
	Admitted              bool              `json:"admitted"`
	Decision              string            `json:"decision"`
	PBlocked              float64           `json:"p_blocked"`
	PredictionSet         []string          `json:"prediction_set"`
	CalibrationArtifactID string            `json:"calibration_artifact_id"`
	CalibrationApplicable bool              `json:"calibration_applicable"`
	Clauses               []ClauseResult    `json:"clauses"`
	UsedClaimIDs          []string          `json:"used_claim_ids"`
	DiscountedClaims      []DiscountedClaim `json:"discounted_claims"`
	MeasurementRootIDs    []string          `json:"measurement_root_ids"`
	DeviceRootIDs         []string          `json:"device_root_ids"`
	UnresolvedConflicts   int               `json:"unresolved_conflicts"`
	BeliefGaps            []BeliefGap       `json:"belief_gaps"`
	Assumptions           []string          `json:"assumptions"`
	ReceiptSHA256         string            `json:"receipt_sha256"`
}

type InvalidatePlanRequest struct {
	PreviousReceipt  GateReceipt  `json:"previous_receipt"`
	CurrentStep      int64        `json:"current_step"`
	TriggeringClaims []RobotClaim `json:"triggering_claims"`
}

// PlanInvalidationReceipt records whether a previously admitted plan must be
// revoked because its evidence expired or a newer, contradictory Claim arrived.
type PlanInvalidationReceipt struct {
	SchemaVersion         string   `json:"schema_version"`
	ReceiptID             string   `json:"receipt_id"`
	PreviousReceiptSHA256 string   `json:"previous_receipt_sha256"`
	CurrentStep           int64    `json:"current_step"`
	Invalidated           bool     `json:"invalidated"`
	Reasons               []string `json:"reasons"`
	TriggeringClaimIDs    []string `json:"triggering_claim_ids"`
	ReceiptSHA256         string   `json:"receipt_sha256"`
}

type Command struct {
	SchemaVersion string          `json:"schema_version"`
	RequestID     string          `json:"request_id"`
	Op            string          `json:"op"`
	Payload       json.RawMessage `json:"payload"`
}

type ProtocolError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type Response struct {
	SchemaVersion string         `json:"schema_version"`
	RequestID     string         `json:"request_id"`
	OK            bool           `json:"ok"`
	Result        any            `json:"result"`
	Error         *ProtocolError `json:"error"`
}
