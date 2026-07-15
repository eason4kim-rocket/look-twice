package purifyrobotics

import (
	"encoding/json"
	"strings"
	"testing"
)

const testHash = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

func testScope() ClaimScope {
	return ClaimScope{RobotID: "robot-01", PayloadID: "payload-small", RegionID: "crossing-01"}
}

func testClaim(id, value, capture, device string, observed int64) RobotClaim {
	return RobotClaim{
		SchemaVersion:  RobotClaimSchema,
		ClaimID:        id,
		FactID:         "region:crossing-01",
		Predicate:      "traversable",
		Value:          value,
		Confidence:     0.95,
		ObservedStep:   observed,
		ValidUntilStep: observed + 100,
		Modality:       "depth_geometry",
		DeviceRootID:   device,
		CaptureRootID:  capture,
		CalibrationID:  "sensors-v1",
		PoseVersion:    "pose-v1",
		ModelID:        "depth-rule-v1",
		ArtifactSHA256: "",
		ParentClaimIDs: []string{},
		Quality:        1,
		Visibility:     1,
		TemporalSkew:   0,
		Scope:          testScope(),
	}
}

func testRequest(claims ...RobotClaim) EvaluateActionRequest {
	return EvaluateActionRequest{
		Claims: claims,
		Contract: ActionContract{
			SchemaVersion:                ActionContractSchema,
			ContractID:                   "cross-region-v1",
			Action:                       "cross_region",
			FactID:                       "region:crossing-01",
			Predicate:                    "traversable",
			Scope:                        testScope(),
			RequiredPredictionSet:        []string{"clear"},
			MaxEvidenceAge:               60,
			MinDistinctMeasurementRoots:  2,
			MaxModalitySkew:              2,
			MaxUnresolvedConflicts:       0,
			RequireCalibrationApplicable: true,
		},
		Calibration: CalibrationArtifact{
			SchemaVersion:      CalibrationArtifactSchema,
			ArtifactID:         "calibration-v1",
			Alpha:              0.05,
			ClassQuantiles:     map[string]float64{"clear": 0.1, "blocked": 0.1},
			ApplicableProfiles: []string{"independent-noise"},
			MinNoiseIntensity:  0,
			MaxNoiseIntensity:  0.5,
			SensorVersions:     []string{"sensors-v1"},
			GitCommit:          "deadbeef",
			DatasetSHA256:      testHash,
			SeedRanges:         []SeedRange{{Start: 30000, End: 30049}},
		},
		Context: EvaluationContext{
			CurrentStep:    20,
			Profile:        "independent-noise",
			NoiseIntensity: 0.2,
			SensorVersion:  "sensors-v1",
		},
	}
}

func clause(t *testing.T, receipt GateReceipt, name string) ClauseResult {
	t.Helper()
	for _, result := range receipt.Clauses {
		if result.Clause == name {
			return result
		}
	}
	t.Fatalf("missing clause %q", name)
	return ClauseResult{}
}

func hasGap(receipt GateReceipt, reason string) bool {
	for _, gap := range receipt.BeliefGaps {
		if gap.Reason == reason {
			return true
		}
	}
	return false
}

func TestEvaluateActionAdmitsTwoIndependentClearCaptures(t *testing.T) {
	request := testRequest(
		testClaim("depth-1", "clear", "capture-1", "camera-1", 10),
		testClaim("depth-2", "clear", "capture-2", "camera-1", 11),
	)
	receipt, err := EvaluateAction(request)
	if err != nil {
		t.Fatal(err)
	}
	if !receipt.Admitted || receipt.Decision != "admitted" {
		t.Fatalf("expected admission, got %#v", receipt)
	}
	if len(receipt.MeasurementRootIDs) != 2 || len(receipt.DeviceRootIDs) != 1 {
		t.Fatalf("unexpected roots: measurement=%v device=%v", receipt.MeasurementRootIDs, receipt.DeviceRootIDs)
	}
	if len(receipt.PredictionSet) != 1 || receipt.PredictionSet[0] != "clear" {
		t.Fatalf("unexpected prediction set: %v", receipt.PredictionSet)
	}
	if err := VerifyGateReceipt(receipt); err != nil {
		t.Fatalf("receipt hash should verify: %v", err)
	}
}

func TestCaptureRootCollapseDeniesEchoedEvidence(t *testing.T) {
	depth := testClaim("depth", "clear", "capture-1", "camera-1", 10)
	semantic := testClaim("semantic", "clear", "capture-1", "camera-1", 10)
	semantic.Modality = "simulated_semantic_sensor"
	receipt, err := EvaluateAction(testRequest(depth, semantic))
	if err != nil {
		t.Fatal(err)
	}
	if receipt.Admitted || len(receipt.MeasurementRootIDs) != 1 {
		t.Fatalf("same capture must not satisfy two-root contract: %#v", receipt)
	}
	if !hasGap(receipt, "shared_root") || !hasGap(receipt, "insufficient_roots") {
		t.Fatalf("expected shared/insufficient root gaps, got %v", receipt.BeliefGaps)
	}
}

func TestArtifactAndParentLineageCollapse(t *testing.T) {
	first := testClaim("first", "clear", "capture-1", "camera-1", 10)
	first.ArtifactSHA256 = testHash
	duplicate := testClaim("duplicate", "clear", "capture-2", "camera-2", 11)
	duplicate.ArtifactSHA256 = testHash
	receipt, err := EvaluateAction(testRequest(first, duplicate))
	if err != nil {
		t.Fatal(err)
	}
	if len(receipt.MeasurementRootIDs) != 1 || receipt.Admitted {
		t.Fatalf("artifact duplicate must not add a root: %#v", receipt)
	}
	if len(receipt.DiscountedClaims) != 1 || !strings.HasPrefix(receipt.DiscountedClaims[0].Reason, "artifact_duplicate_of:") {
		t.Fatalf("duplicate was not audited: %v", receipt.DiscountedClaims)
	}

	first.ArtifactSHA256 = ""
	duplicate.ArtifactSHA256 = ""
	duplicate.ParentClaimIDs = []string{"first"}
	receipt, err = EvaluateAction(testRequest(first, duplicate))
	if err != nil {
		t.Fatal(err)
	}
	if len(receipt.MeasurementRootIDs) != 1 || !strings.HasPrefix(receipt.MeasurementRootIDs[0], "lineage:") {
		t.Fatalf("parent lineage must collapse roots conservatively: %v", receipt.MeasurementRootIDs)
	}
}

func TestArtifactEchoRetainsOriginalLineageSource(t *testing.T) {
	original := testClaim("semantic-original", "clear", "capture-1", "camera-1", 10)
	original.Modality = "simulated_semantic_sensor"
	original.ArtifactSHA256 = testHash
	echo := testClaim("000-forwarded-echo", "clear", "capture-1", "camera-1", 10)
	echo.Modality = original.Modality
	echo.ArtifactSHA256 = testHash
	echo.ParentClaimIDs = []string{original.ClaimID}
	second := testClaim("depth-second", "clear", "capture-2", "camera-1", 11)

	receipt, err := EvaluateAction(testRequest(original, echo, second))
	if err != nil {
		t.Fatal(err)
	}
	if !receipt.Admitted || len(receipt.MeasurementRootIDs) != 2 {
		t.Fatalf("echo must be discounted without losing its source root: %#v", receipt)
	}
	found := false
	for _, discounted := range receipt.DiscountedClaims {
		if discounted.ClaimID == echo.ClaimID && strings.HasPrefix(discounted.Reason, "artifact_duplicate_of:") {
			found = true
		}
	}
	if !found {
		t.Fatalf("forwarded echo was not audited: %v", receipt.DiscountedClaims)
	}
}

func TestMissingParentLineageCannotBecomeIndependent(t *testing.T) {
	derived := testClaim("derived", "clear", "capture-1", "camera-1", 10)
	derived.ParentClaimIDs = []string{"missing-source-claim"}
	independent := testClaim("independent", "clear", "capture-2", "camera-2", 11)
	receipt, err := EvaluateAction(testRequest(derived, independent))
	if err != nil {
		t.Fatal(err)
	}
	if receipt.Admitted || len(receipt.MeasurementRootIDs) != 1 {
		t.Fatalf("unresolvable parent lineage must fail closed: %#v", receipt)
	}
}

func TestUnknownRootsAndStaticMapNeverCount(t *testing.T) {
	unknown := testClaim("unknown", "clear", "unknown", "unavailable", 10)
	staticMap := testClaim("map", "clear", "map-capture", "map-device", 10)
	staticMap.Modality = "static_map"
	receipt, err := EvaluateAction(testRequest(unknown, staticMap))
	if err != nil {
		t.Fatal(err)
	}
	if receipt.Admitted || len(receipt.MeasurementRootIDs) != 0 {
		t.Fatalf("unknown and map roots must not count: %#v", receipt)
	}
	if clause(t, receipt, "distinct_measurement_roots").Passed {
		t.Fatal("root clause unexpectedly passed")
	}
}

func TestMismatchedCalibrationVersionCannotSupplyASecondRoot(t *testing.T) {
	current := testClaim("current", "clear", "capture-current", "camera-1", 10)
	drifted := testClaim("drifted", "clear", "capture-drifted", "camera-1", 11)
	drifted.CalibrationID = "sensors-v1+pose-drift"
	receipt, err := EvaluateAction(testRequest(current, drifted))
	if err != nil {
		t.Fatal(err)
	}
	if receipt.Admitted || len(receipt.MeasurementRootIDs) != 1 {
		t.Fatalf("mismatched calibration must not satisfy root contract: %#v", receipt)
	}
	found := false
	for _, discounted := range receipt.DiscountedClaims {
		if discounted.ClaimID == drifted.ClaimID && discounted.Reason == "calibration_version_mismatch" {
			found = true
		}
	}
	if !found {
		t.Fatalf("mismatched Claim was not audited: %v", receipt.DiscountedClaims)
	}
}

func TestConflictSkewStaleAndOODFailClosed(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(*EvaluateActionRequest)
		gap    string
	}{
		{
			name: "conflict",
			mutate: func(request *EvaluateActionRequest) {
				request.Claims[1].Value = "blocked"
			},
			gap: "modality_conflict",
		},
		{
			name: "skew",
			mutate: func(request *EvaluateActionRequest) {
				request.Claims[1].TemporalSkew = 3
			},
			gap: "time_skew",
		},
		{
			name: "stale",
			mutate: func(request *EvaluateActionRequest) {
				request.Claims[0].ValidUntilStep = 19
			},
			gap: "stale",
		},
		{
			name: "ood",
			mutate: func(request *EvaluateActionRequest) {
				request.Context.Profile = "ood-severity"
			},
			gap: "calibration_not_applicable",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			request := testRequest(
				testClaim("one", "clear", "capture-1", "camera-1", 10),
				testClaim("two", "clear", "capture-2", "camera-2", 11),
			)
			test.mutate(&request)
			receipt, err := EvaluateAction(request)
			if err != nil {
				t.Fatal(err)
			}
			if receipt.Admitted || !hasGap(receipt, test.gap) {
				t.Fatalf("expected denial with %s, got admitted=%v gaps=%v", test.gap, receipt.Admitted, receipt.BeliefGaps)
			}
		})
	}
}

func TestZeroCoverageCannotAdmit(t *testing.T) {
	one := testClaim("one", "clear", "capture-1", "camera-1", 10)
	two := testClaim("two", "clear", "capture-2", "camera-2", 11)
	one.Visibility, two.Visibility = 0, 0
	receipt, err := EvaluateAction(testRequest(one, two))
	if err != nil {
		t.Fatal(err)
	}
	if receipt.Admitted || !hasGap(receipt, "low_coverage") || len(receipt.MeasurementRootIDs) != 0 {
		t.Fatalf("zero coverage must fail closed: %#v", receipt)
	}
}

func TestDeterministicReceiptAndTamperDetection(t *testing.T) {
	request := testRequest(
		testClaim("one", "clear", "capture-1", "camera-1", 10),
		testClaim("two", "clear", "capture-2", "camera-2", 11),
	)
	first, err := EvaluateAction(request)
	if err != nil {
		t.Fatal(err)
	}
	request.Claims[0], request.Claims[1] = request.Claims[1], request.Claims[0]
	second, err := EvaluateAction(request)
	if err != nil {
		t.Fatal(err)
	}
	firstJSON, _ := json.Marshal(first)
	secondJSON, _ := json.Marshal(second)
	if string(firstJSON) != string(secondJSON) {
		t.Fatalf("input order changed deterministic receipt:\n%s\n%s", firstJSON, secondJSON)
	}
	second.PBlocked = 0.99
	if err := VerifyGateReceipt(second); err == nil {
		t.Fatal("tampered receipt unexpectedly verified")
	}
}

func TestInvalidatePlanOnExpiryAndNewContradiction(t *testing.T) {
	gate, err := EvaluateAction(testRequest(
		testClaim("one", "clear", "capture-1", "camera-1", 10),
		testClaim("two", "clear", "capture-2", "camera-2", 11),
	))
	if err != nil || !gate.Admitted {
		t.Fatalf("setup gate: admitted=%v err=%v", gate.Admitted, err)
	}
	blocked := testClaim("new-blocked", "blocked", "capture-3", "camera-2", 21)
	receipt, err := InvalidatePlan(InvalidatePlanRequest{
		PreviousReceipt:  gate,
		CurrentStep:      22,
		TriggeringClaims: []RobotClaim{blocked},
	})
	if err != nil {
		t.Fatal(err)
	}
	if !receipt.Invalidated || !contains(receipt.Reasons, "new_contradicting_claim") || len(receipt.TriggeringClaimIDs) != 1 {
		t.Fatalf("expected contradiction invalidation: %#v", receipt)
	}
	if err := VerifyPlanInvalidationReceipt(receipt); err != nil {
		t.Fatalf("invalidation hash should verify: %v", err)
	}

	expiryReceipt, err := InvalidatePlan(InvalidatePlanRequest{PreviousReceipt: gate, CurrentStep: gate.ValidUntilStep + 1, TriggeringClaims: []RobotClaim{}})
	if err != nil {
		t.Fatal(err)
	}
	if !expiryReceipt.Invalidated || !contains(expiryReceipt.Reasons, "expired") {
		t.Fatalf("expected expiry invalidation: %#v", expiryReceipt)
	}
}

func TestInvalidateBlockedDetourPlanOnNewClearClaim(t *testing.T) {
	request := testRequest(
		testClaim("blocked-one", "blocked", "capture-1", "camera-1", 10),
		testClaim("blocked-two", "blocked", "capture-2", "camera-1", 11),
	)
	request.Contract.ContractID = "detour-region-v1"
	request.Contract.Action = "take_detour"
	request.Contract.RequiredPredictionSet = []string{"blocked"}
	gate, err := EvaluateAction(request)
	if err != nil || !gate.Admitted {
		t.Fatalf("setup blocked gate: admitted=%v err=%v", gate.Admitted, err)
	}
	clearClaim := testClaim("new-clear", "clear", "capture-3", "camera-1", 21)
	receipt, err := InvalidatePlan(InvalidatePlanRequest{
		PreviousReceipt:  gate,
		CurrentStep:      22,
		TriggeringClaims: []RobotClaim{clearClaim},
	})
	if err != nil {
		t.Fatal(err)
	}
	if !receipt.Invalidated || !contains(receipt.Reasons, "new_contradicting_claim") {
		t.Fatalf("new clear Claim must invalidate blocked detour plan: %#v", receipt)
	}
}

func TestProcessLineProtocolAndRecovery(t *testing.T) {
	request := testRequest(
		testClaim("one", "clear", "capture-1", "camera-1", 10),
		testClaim("two", "clear", "capture-2", "camera-2", 11),
	)
	payload, _ := json.Marshal(request)
	command, _ := json.Marshal(Command{SchemaVersion: CommandSchema, RequestID: "request-1", Op: OperationEvaluateAction, Payload: payload})
	response := ProcessLine(command)
	if !response.OK || response.RequestID != "request-1" || response.Error != nil {
		t.Fatalf("valid protocol request failed: %#v", response)
	}
	bad := ProcessLine([]byte(`{"schema_version":"purify.robotics.command.v1","request_id":"bad","op":"unknown","payload":{}}`))
	if bad.OK || bad.Error == nil || bad.Error.Code != "invalid_request" {
		t.Fatalf("bad op did not produce isolated protocol error: %#v", bad)
	}
	again := ProcessLine(command)
	if !again.OK {
		t.Fatalf("valid request after error should still work: %#v", again)
	}
}

func TestValidationRejectsMalformedInputs(t *testing.T) {
	request := testRequest(testClaim("one", "clear", "capture-1", "camera-1", 10))
	request.Claims[0].Confidence = 1.1
	if _, err := EvaluateAction(request); err == nil {
		t.Fatal("out-of-range confidence should fail validation")
	}

	response := ProcessLine([]byte(`{"schema_version":"purify.robotics.command.v1","request_id":"x","op":"evaluate_action","payload":{},"extra":true}`))
	if response.OK || response.Error == nil || response.Error.Code != "invalid_json" {
		t.Fatalf("unknown envelope field should fail strict decoding: %#v", response)
	}
}
