package purifyrobotics

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"sort"
	"strings"
)

var allowedGapReasons = map[string]bool{
	"stale":                      true,
	"shared_root":                true,
	"insufficient_roots":         true,
	"modality_conflict":          true,
	"time_skew":                  true,
	"low_coverage":               true,
	"calibration_not_applicable": true,
}

type validationError struct{ message string }

func (e validationError) Error() string { return e.message }

func invalid(format string, args ...any) error {
	return validationError{message: fmt.Sprintf(format, args...)}
}

func validateScope(scope ClaimScope, path string) error {
	if scope.RobotID == "" || scope.PayloadID == "" || scope.RegionID == "" {
		return invalid("%s requires non-empty robot_id, payload_id, and region_id", path)
	}
	return nil
}

func validateClaim(claim RobotClaim, path string) error {
	if claim.SchemaVersion != RobotClaimSchema {
		return invalid("%s.schema_version must be %q", path, RobotClaimSchema)
	}
	if claim.ClaimID == "" || claim.FactID == "" || claim.Predicate == "" || claim.Modality == "" {
		return invalid("%s requires claim_id, fact_id, predicate, and modality", path)
	}
	if claim.Value != "clear" && claim.Value != "blocked" && claim.Value != "inconclusive" {
		return invalid("%s.value must be clear, blocked, or inconclusive", path)
	}
	if !finiteUnit(claim.Confidence) || !finiteUnit(claim.Quality) || !finiteUnit(claim.Visibility) {
		return invalid("%s confidence, quality, and visibility must be finite values in [0,1]", path)
	}
	if claim.ObservedStep < 0 || claim.ValidUntilStep < claim.ObservedStep || claim.TemporalSkew < 0 {
		return invalid("%s has invalid observation, validity, or skew steps", path)
	}
	if claim.ArtifactSHA256 != "" && !isSHA256(claim.ArtifactSHA256) {
		return invalid("%s.artifact_sha256 must be empty or a lowercase SHA-256", path)
	}
	return validateScope(claim.Scope, path+".scope")
}

func validateContract(contract ActionContract) error {
	if contract.SchemaVersion != ActionContractSchema {
		return invalid("contract.schema_version must be %q", ActionContractSchema)
	}
	if contract.ContractID == "" || contract.Action == "" || contract.FactID == "" || contract.Predicate == "" {
		return invalid("contract requires contract_id, action, fact_id, and predicate")
	}
	if err := validateScope(contract.Scope, "contract.scope"); err != nil {
		return err
	}
	if len(contract.RequiredPredictionSet) == 0 {
		return invalid("contract.required_prediction_set must not be empty")
	}
	seen := map[string]bool{}
	for _, value := range contract.RequiredPredictionSet {
		if value != "clear" && value != "blocked" {
			return invalid("contract.required_prediction_set values must be clear or blocked")
		}
		if seen[value] {
			return invalid("contract.required_prediction_set contains duplicate %q", value)
		}
		seen[value] = true
	}
	if contract.MaxEvidenceAge < 0 || contract.MinDistinctMeasurementRoots < 1 || contract.MaxModalitySkew < 0 || contract.MaxUnresolvedConflicts < 0 {
		return invalid("contract thresholds are outside their valid ranges")
	}
	return nil
}

func validateCalibration(artifact CalibrationArtifact) error {
	if artifact.SchemaVersion != CalibrationArtifactSchema {
		return invalid("calibration.schema_version must be %q", CalibrationArtifactSchema)
	}
	if artifact.ArtifactID == "" || artifact.GitCommit == "" || !isSHA256(artifact.DatasetSHA256) {
		return invalid("calibration requires artifact_id, git_commit, and lowercase dataset_sha256")
	}
	if !(artifact.Alpha > 0 && artifact.Alpha < 1) || math.IsNaN(artifact.Alpha) {
		return invalid("calibration.alpha must be in (0,1)")
	}
	if len(artifact.ClassQuantiles) != 2 {
		return invalid("calibration.class_quantiles must contain exactly clear and blocked")
	}
	for _, className := range []string{"clear", "blocked"} {
		value, ok := artifact.ClassQuantiles[className]
		if !ok || !finiteUnit(value) {
			return invalid("calibration.class_quantiles.%s must be in [0,1]", className)
		}
	}
	if !isFinite(artifact.MinNoiseIntensity) || !isFinite(artifact.MaxNoiseIntensity) || artifact.MinNoiseIntensity > artifact.MaxNoiseIntensity {
		return invalid("calibration noise range is invalid")
	}
	if len(artifact.ApplicableProfiles) == 0 || len(artifact.SensorVersions) == 0 || len(artifact.SeedRanges) == 0 {
		return invalid("calibration requires applicable_profiles, sensor_versions, and seed_ranges")
	}
	for index, seedRange := range artifact.SeedRanges {
		if seedRange.Start < 0 || seedRange.End < seedRange.Start {
			return invalid("calibration.seed_ranges[%d] is invalid", index)
		}
	}
	return nil
}

func validateEvaluateRequest(request EvaluateActionRequest) error {
	if err := validateContract(request.Contract); err != nil {
		return err
	}
	if err := validateCalibration(request.Calibration); err != nil {
		return err
	}
	if request.Context.CurrentStep < 0 || request.Context.Profile == "" || !isFinite(request.Context.NoiseIntensity) || request.Context.SensorVersion == "" {
		return invalid("context requires non-negative current_step, profile, finite noise_intensity, and sensor_version")
	}
	seen := map[string]bool{}
	for index, claim := range request.Claims {
		if err := validateClaim(claim, fmt.Sprintf("claims[%d]", index)); err != nil {
			return err
		}
		if seen[claim.ClaimID] {
			return invalid("claims contain duplicate claim_id %q", claim.ClaimID)
		}
		seen[claim.ClaimID] = true
	}
	return nil
}

func finiteUnit(value float64) bool { return isFinite(value) && value >= 0 && value <= 1 }
func isFinite(value float64) bool   { return !math.IsNaN(value) && !math.IsInf(value, 0) }

func isSHA256(value string) bool {
	if len(value) != 64 {
		return false
	}
	for _, character := range value {
		if !((character >= '0' && character <= '9') || (character >= 'a' && character <= 'f')) {
			return false
		}
	}
	return true
}

func sameScope(left, right ClaimScope) bool {
	return left.RobotID == right.RobotID && left.PayloadID == right.PayloadID && left.RegionID == right.RegionID
}

func knownRoot(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "", "unknown", "unavailable", "none":
		return false
	default:
		return true
	}
}

type disjointSet struct{ parent []int }

func newDisjointSet(size int) *disjointSet {
	parent := make([]int, size)
	for index := range parent {
		parent[index] = index
	}
	return &disjointSet{parent: parent}
}

func (set *disjointSet) find(index int) int {
	if set.parent[index] != index {
		set.parent[index] = set.find(set.parent[index])
	}
	return set.parent[index]
}

func (set *disjointSet) union(left, right int) {
	leftRoot, rightRoot := set.find(left), set.find(right)
	if leftRoot == rightRoot {
		return
	}
	if leftRoot < rightRoot {
		set.parent[rightRoot] = leftRoot
	} else {
		set.parent[leftRoot] = rightRoot
	}
}

type claimComponent struct {
	claims       []RobotClaim
	captureRoots []string
	deviceRoots  []string
	rootID       string
	logOdds      float64
	hasClear     bool
	hasBlocked   bool
	decisive     bool
}

// EvaluateAction performs root-aware evidence fusion, class-conditional
// conformal qualification, and fail-closed Action Contract evaluation.
func EvaluateAction(request EvaluateActionRequest) (GateReceipt, error) {
	if err := validateEvaluateRequest(request); err != nil {
		return GateReceipt{}, err
	}

	claims := append([]RobotClaim(nil), request.Claims...)
	// When several derived Claims carry the same artifact, retain the closest
	// lineage source (fewest declared parents) before discounting its echoes.
	// Sorting only by claim_id could otherwise keep a forwarded derivative and
	// then reject it because its original parent was just discounted.
	sort.Slice(claims, func(i, j int) bool {
		if claims[i].ArtifactSHA256 == claims[j].ArtifactSHA256 && len(claims[i].ParentClaimIDs) != len(claims[j].ParentClaimIDs) {
			return len(claims[i].ParentClaimIDs) < len(claims[j].ParentClaimIDs)
		}
		return claims[i].ClaimID < claims[j].ClaimID
	})
	contract := request.Contract
	currentStep := request.Context.CurrentStep
	discounted := make([]DiscountedClaim, 0)
	staleIDs := make([]string, 0)
	relevantPhysicalCount := 0
	selected := make([]RobotClaim, 0)
	seenArtifacts := map[string]string{}

	for _, claim := range claims {
		if claim.FactID != contract.FactID || claim.Predicate != contract.Predicate {
			discounted = append(discounted, DiscountedClaim{ClaimID: claim.ClaimID, Reason: "fact_mismatch"})
			continue
		}
		if !sameScope(claim.Scope, contract.Scope) {
			discounted = append(discounted, DiscountedClaim{ClaimID: claim.ClaimID, Reason: "scope_mismatch"})
			continue
		}
		if claim.Modality != "static_map" && claim.CalibrationID != request.Context.SensorVersion {
			discounted = append(discounted, DiscountedClaim{ClaimID: claim.ClaimID, Reason: "calibration_version_mismatch"})
			continue
		}
		if claim.Modality != "static_map" {
			relevantPhysicalCount++
		}
		if claim.ObservedStep > currentStep {
			discounted = append(discounted, DiscountedClaim{ClaimID: claim.ClaimID, Reason: "future_claim"})
			continue
		}
		if claim.ValidUntilStep < currentStep {
			staleIDs = append(staleIDs, claim.ClaimID)
			discounted = append(discounted, DiscountedClaim{ClaimID: claim.ClaimID, Reason: "stale"})
			continue
		}
		if claim.ArtifactSHA256 != "" {
			if original, exists := seenArtifacts[claim.ArtifactSHA256]; exists {
				discounted = append(discounted, DiscountedClaim{ClaimID: claim.ClaimID, Reason: "artifact_duplicate_of:" + original})
				continue
			}
			seenArtifacts[claim.ArtifactSHA256] = claim.ClaimID
		}
		selected = append(selected, claim)
	}

	physical := make([]RobotClaim, 0)
	mapClaims := make([]RobotClaim, 0)
	for _, claim := range selected {
		if claim.Modality == "static_map" {
			mapClaims = append(mapClaims, claim)
		} else {
			physical = append(physical, claim)
		}
	}

	components, unknownIDs, err := buildComponents(physical)
	if err != nil {
		return GateReceipt{}, err
	}
	for _, claimID := range unknownIDs {
		discounted = append(discounted, DiscountedClaim{ClaimID: claimID, Reason: "unknown_root_not_independent"})
	}

	usedIDs := make([]string, 0)
	measurementRoots := make([]string, 0)
	deviceRootsSet := map[string]bool{}
	totalLogOdds := 0.0
	rootSigns := make([]int, 0)
	unresolvedConflicts := 0
	maxSkew := int64(0)
	var maxAge *int64
	validUntil := currentStep
	validUntilSet := false

	for _, component := range components {
		if component.rootID == "" || !component.decisive {
			continue
		}
		totalLogOdds += component.logOdds
		measurementRoots = append(measurementRoots, component.rootID)
		rootSigns = append(rootSigns, sign(component.logOdds))
		if component.hasClear && component.hasBlocked {
			unresolvedConflicts++
		}
		for _, deviceRoot := range component.deviceRoots {
			deviceRootsSet[deviceRoot] = true
		}
		for _, claim := range component.claims {
			if claim.Value == "inconclusive" || claim.Quality == 0 {
				continue
			}
			usedIDs = append(usedIDs, claim.ClaimID)
			age := currentStep - claim.ObservedStep
			if maxAge == nil || age > *maxAge {
				ageCopy := age
				maxAge = &ageCopy
			}
			if claim.TemporalSkew > maxSkew {
				maxSkew = claim.TemporalSkew
			}
			candidateExpiry := claim.ValidUntilStep
			ageExpiry := claim.ObservedStep + contract.MaxEvidenceAge
			if ageExpiry < candidateExpiry {
				candidateExpiry = ageExpiry
			}
			if !validUntilSet || candidateExpiry < validUntil {
				validUntil, validUntilSet = candidateExpiry, true
			}
		}
	}

	mapLogOdds, mapUsedIDs, mapHasClear, mapHasBlocked := fuseClaims(mapClaims)
	if len(mapUsedIDs) > 0 {
		totalLogOdds += mapLogOdds
		usedIDs = append(usedIDs, mapUsedIDs...)
		if (mapHasClear && anyPositive(rootSigns)) || (mapHasBlocked && anyNegative(rootSigns)) {
			unresolvedConflicts++
		}
	}
	if anyPositive(rootSigns) && anyNegative(rootSigns) {
		unresolvedConflicts++
	}

	sort.Strings(usedIDs)
	sort.Strings(measurementRoots)
	deviceRoots := sortedKeys(deviceRootsSet)
	sort.Slice(discounted, func(i, j int) bool {
		if discounted[i].ClaimID == discounted[j].ClaimID {
			return discounted[i].Reason < discounted[j].Reason
		}
		return discounted[i].ClaimID < discounted[j].ClaimID
	})

	pBlocked := sigmoid(totalLogOdds)
	calibrationApplicable := calibrationApplies(request.Calibration, request.Context)
	predictionSet := []string{"clear", "blocked"}
	if calibrationApplicable {
		predictionSet = conformalPredictionSet(pBlocked, request.Calibration.ClassQuantiles)
	}
	scopeMatched := len(physical) > 0
	agePassed := maxAge != nil && *maxAge <= contract.MaxEvidenceAge
	rootPassed := len(measurementRoots) >= contract.MinDistinctMeasurementRoots
	skewPassed := maxSkew <= contract.MaxModalitySkew
	conflictPassed := unresolvedConflicts <= contract.MaxUnresolvedConflicts
	calibrationPassed := !contract.RequireCalibrationApplicable || calibrationApplicable
	predictionPassed := equalStringSets(predictionSet, contract.RequiredPredictionSet)

	var actualAge any
	if maxAge != nil {
		actualAge = *maxAge
	}
	clauses := []ClauseResult{
		{Clause: "prediction_set", Required: sortedCopy(contract.RequiredPredictionSet), Actual: predictionSet, Passed: predictionPassed},
		{Clause: "evidence_age", Required: contract.MaxEvidenceAge, Actual: actualAge, Passed: agePassed},
		{Clause: "distinct_measurement_roots", Required: contract.MinDistinctMeasurementRoots, Actual: len(measurementRoots), Passed: rootPassed},
		{Clause: "modality_skew", Required: contract.MaxModalitySkew, Actual: maxSkew, Passed: skewPassed},
		{Clause: "unresolved_conflicts", Required: contract.MaxUnresolvedConflicts, Actual: unresolvedConflicts, Passed: conflictPassed},
		{Clause: "calibration_applicable", Required: contract.RequireCalibrationApplicable, Actual: calibrationApplicable, Passed: calibrationPassed},
		{Clause: "scope_match", Required: true, Actual: scopeMatched, Passed: scopeMatched},
	}
	admitted := true
	for _, clause := range clauses {
		admitted = admitted && clause.Passed
	}
	if !admitted {
		validUntil = currentStep
	} else if !validUntilSet {
		validUntil = currentStep
	}

	gaps := buildBeliefGaps(staleIDs, physical, relevantPhysicalCount, len(measurementRoots), contract.MinDistinctMeasurementRoots, unresolvedConflicts, conflictPassed, maxSkew, skewPassed, predictionSet, calibrationApplicable)
	decision := "denied"
	if admitted {
		decision = "admitted"
	}
	receipt := GateReceipt{
		SchemaVersion:         GateReceiptSchema,
		ContractID:            contract.ContractID,
		Action:                contract.Action,
		FactID:                contract.FactID,
		Predicate:             contract.Predicate,
		Scope:                 contract.Scope,
		EvaluatedStep:         currentStep,
		ValidUntilStep:        validUntil,
		Admitted:              admitted,
		Decision:              decision,
		PBlocked:              pBlocked,
		PredictionSet:         predictionSet,
		CalibrationArtifactID: request.Calibration.ArtifactID,
		CalibrationApplicable: calibrationApplicable,
		Clauses:               clauses,
		UsedClaimIDs:          usedIDs,
		DiscountedClaims:      discounted,
		MeasurementRootIDs:    measurementRoots,
		DeviceRootIDs:         deviceRoots,
		UnresolvedConflicts:   unresolvedConflicts,
		BeliefGaps:            gaps,
		Assumptions: []string{
			"a measurement root counts only when both capture_root_id and device_root_id are known",
			"static_map contributes prior evidence but never a physical measurement root",
			"claims connected by capture, artifact, or declared parent lineage form one conservative evidence component",
			"an empty conformal set is normalized to {clear, blocked} to fail closed",
		},
	}
	if err := signGateReceipt(&receipt); err != nil {
		return GateReceipt{}, err
	}
	return receipt, nil
}

func buildComponents(claims []RobotClaim) ([]claimComponent, []string, error) {
	if len(claims) == 0 {
		return []claimComponent{}, []string{}, nil
	}
	set := newDisjointSet(len(claims))
	byID := map[string]int{}
	byCapture := map[string]int{}
	byArtifact := map[string]int{}
	for index, claim := range claims {
		byID[claim.ClaimID] = index
		if knownRoot(claim.CaptureRootID) {
			if previous, exists := byCapture[claim.CaptureRootID]; exists {
				set.union(index, previous)
			} else {
				byCapture[claim.CaptureRootID] = index
			}
		}
		if claim.ArtifactSHA256 != "" {
			if previous, exists := byArtifact[claim.ArtifactSHA256]; exists {
				set.union(index, previous)
			} else {
				byArtifact[claim.ArtifactSHA256] = index
			}
		}
	}
	for index, claim := range claims {
		for _, parentID := range claim.ParentClaimIDs {
			if parentIndex, exists := byID[parentID]; exists {
				set.union(index, parentIndex)
			}
		}
	}
	groups := map[int][]RobotClaim{}
	for index, claim := range claims {
		root := set.find(index)
		groups[root] = append(groups[root], claim)
	}
	groupKeys := make([]int, 0, len(groups))
	for key := range groups {
		groupKeys = append(groupKeys, key)
	}
	sort.Ints(groupKeys)
	components := make([]claimComponent, 0, len(groups))
	unknownIDs := make([]string, 0)
	for _, key := range groupKeys {
		groupClaims := groups[key]
		sort.Slice(groupClaims, func(i, j int) bool { return groupClaims[i].ClaimID < groupClaims[j].ClaimID })
		captureSet, deviceSet := map[string]bool{}, map[string]bool{}
		unresolvedParentLineage := false
		for _, claim := range groupClaims {
			for _, parentID := range claim.ParentClaimIDs {
				if _, exists := byID[parentID]; !exists {
					unresolvedParentLineage = true
				}
			}
			if knownRoot(claim.CaptureRootID) {
				captureSet[claim.CaptureRootID] = true
			}
			if knownRoot(claim.DeviceRootID) {
				deviceSet[claim.DeviceRootID] = true
			}
		}
		captures, devices := sortedKeys(captureSet), sortedKeys(deviceSet)
		component := claimComponent{claims: groupClaims, captureRoots: captures, deviceRoots: devices}
		if len(captures) == 0 || len(devices) == 0 || unresolvedParentLineage {
			for _, claim := range groupClaims {
				unknownIDs = append(unknownIDs, claim.ClaimID)
			}
			components = append(components, component)
			continue
		}
		if len(captures) == 1 {
			component.rootID = captures[0]
		} else {
			digest, err := hashCanonical(captures)
			if err != nil {
				return nil, nil, err
			}
			component.rootID = "lineage:" + digest[:16]
		}
		component.logOdds, _, component.hasClear, component.hasBlocked = fuseClaims(groupClaims)
		component.decisive = component.hasClear || component.hasBlocked
		components = append(components, component)
	}
	sort.Slice(components, func(i, j int) bool { return components[i].rootID < components[j].rootID })
	sort.Strings(unknownIDs)
	return components, unknownIDs, nil
}

func fuseClaims(claims []RobotClaim) (float64, []string, bool, bool) {
	weightedSum, totalWeight := 0.0, 0.0
	used := make([]string, 0)
	hasClear, hasBlocked := false, false
	for _, claim := range claims {
		if claim.Value == "inconclusive" || claim.Quality <= 0 {
			continue
		}
		weight := claim.Quality * claim.Visibility
		if weight <= 0 {
			continue
		}
		probabilityBlocked := claim.Confidence
		if claim.Value == "clear" {
			probabilityBlocked = 1 - claim.Confidence
			hasClear = true
		} else {
			hasBlocked = true
		}
		probabilityBlocked = math.Max(1e-6, math.Min(1-1e-6, probabilityBlocked))
		weightedSum += weight * math.Log(probabilityBlocked/(1-probabilityBlocked))
		totalWeight += weight
		used = append(used, claim.ClaimID)
	}
	if totalWeight == 0 {
		return 0, []string{}, false, false
	}
	sort.Strings(used)
	return weightedSum / totalWeight, used, hasClear, hasBlocked
}

func calibrationApplies(artifact CalibrationArtifact, context EvaluationContext) bool {
	return contains(artifact.ApplicableProfiles, context.Profile) &&
		context.NoiseIntensity >= artifact.MinNoiseIntensity &&
		context.NoiseIntensity <= artifact.MaxNoiseIntensity &&
		contains(artifact.SensorVersions, context.SensorVersion)
}

func conformalPredictionSet(pBlocked float64, quantiles map[string]float64) []string {
	result := make([]string, 0, 2)
	if pBlocked <= quantiles["clear"] {
		result = append(result, "clear")
	}
	if 1-pBlocked <= quantiles["blocked"] {
		result = append(result, "blocked")
	}
	if len(result) == 0 {
		return []string{"clear", "blocked"}
	}
	return result
}

func buildBeliefGaps(staleIDs []string, physical []RobotClaim, relevantCount, roots, requiredRoots, conflicts int, conflictPassed bool, skew int64, skewPassed bool, predictionSet []string, calibrationApplicable bool) []BeliefGap {
	gaps := make([]BeliefGap, 0)
	add := func(reason, detail string, claimIDs []string) {
		if !allowedGapReasons[reason] {
			panic("internal invalid BeliefGap reason: " + reason)
		}
		ids := append([]string(nil), claimIDs...)
		sort.Strings(ids)
		gaps = append(gaps, BeliefGap{SchemaVersion: BeliefGapSchema, Reason: reason, ClaimIDs: ids, Detail: detail})
	}
	// Expired Claims remain audited as discounted inputs.  They constitute a
	// current BeliefGap only when fresh roots cannot satisfy the contract; old
	// history must not poison a later, independently repaired fact forever.
	if len(staleIDs) > 0 && roots < requiredRoots {
		add("stale", "one or more relevant Claims expired before evaluation", staleIDs)
	}
	if relevantCount > roots && roots < requiredRoots {
		ids := make([]string, 0, len(physical))
		for _, claim := range physical {
			ids = append(ids, claim.ClaimID)
		}
		add("shared_root", "Claim count exceeds the number of independent physical measurement roots", ids)
	}
	if roots < requiredRoots {
		add("insufficient_roots", fmt.Sprintf("need at least %d independent measurement roots; found %d", requiredRoots, roots), nil)
	}
	if !conflictPassed || conflicts > 0 {
		add("modality_conflict", fmt.Sprintf("found %d unresolved evidence conflicts", conflicts), nil)
	}
	if !skewPassed {
		add("time_skew", fmt.Sprintf("modality skew %d exceeds the contract", skew), nil)
	}
	lowCoverageIDs := make([]string, 0)
	for _, claim := range physical {
		if claim.Value == "inconclusive" || claim.Quality == 0 || claim.Visibility == 0 {
			lowCoverageIDs = append(lowCoverageIDs, claim.ClaimID)
		}
	}
	if len(lowCoverageIDs) > 0 || (len(predictionSet) == 2 && roots == 0) {
		add("low_coverage", "available physical evidence is inconclusive or has zero usable quality/visibility", lowCoverageIDs)
	}
	if !calibrationApplicable {
		add("calibration_not_applicable", "runtime profile, intensity, or sensor version is outside the Calibration Artifact", nil)
	}
	return gaps
}

func sigmoid(value float64) float64 {
	if value >= 0 {
		exp := math.Exp(-value)
		return 1 / (1 + exp)
	}
	exp := math.Exp(value)
	return exp / (1 + exp)
}

func sign(value float64) int {
	if value > 1e-12 {
		return 1
	}
	if value < -1e-12 {
		return -1
	}
	return 0
}

func anyPositive(values []int) bool {
	for _, value := range values {
		if value > 0 {
			return true
		}
	}
	return false
}

func anyNegative(values []int) bool {
	for _, value := range values {
		if value < 0 {
			return true
		}
	}
	return false
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func sortedKeys(values map[string]bool) []string {
	result := make([]string, 0, len(values))
	for value := range values {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}

func sortedCopy(values []string) []string {
	result := append([]string(nil), values...)
	sort.Strings(result)
	return result
}

func equalStringSets(left, right []string) bool {
	leftSorted, rightSorted := sortedCopy(left), sortedCopy(right)
	if len(leftSorted) != len(rightSorted) {
		return false
	}
	for index := range leftSorted {
		if leftSorted[index] != rightSorted[index] {
			return false
		}
	}
	return true
}

// InvalidatePlan validates the prior receipt and revokes an admitted plan when
// it expires or when a newer Claim contradicts its singleton clear decision.
func InvalidatePlan(request InvalidatePlanRequest) (PlanInvalidationReceipt, error) {
	if request.CurrentStep < 0 {
		return PlanInvalidationReceipt{}, invalid("current_step must be non-negative")
	}
	if request.PreviousReceipt.SchemaVersion != GateReceiptSchema {
		return PlanInvalidationReceipt{}, invalid("previous_receipt.schema_version must be %q", GateReceiptSchema)
	}
	if err := VerifyGateReceipt(request.PreviousReceipt); err != nil {
		return PlanInvalidationReceipt{}, invalid("previous_receipt is not authentic: %v", err)
	}
	seen := map[string]bool{}
	for index, claim := range request.TriggeringClaims {
		if err := validateClaim(claim, fmt.Sprintf("triggering_claims[%d]", index)); err != nil {
			return PlanInvalidationReceipt{}, err
		}
		if seen[claim.ClaimID] {
			return PlanInvalidationReceipt{}, invalid("triggering_claims contain duplicate claim_id %q", claim.ClaimID)
		}
		seen[claim.ClaimID] = true
	}

	reasons := make([]string, 0)
	triggerIDs := make([]string, 0)
	if request.PreviousReceipt.Admitted && request.CurrentStep > request.PreviousReceipt.ValidUntilStep {
		reasons = append(reasons, "expired")
	}
	claims := append([]RobotClaim(nil), request.TriggeringClaims...)
	sort.Slice(claims, func(i, j int) bool { return claims[i].ClaimID < claims[j].ClaimID })
	for _, claim := range claims {
		if !request.PreviousReceipt.Admitted || claim.ObservedStep <= request.PreviousReceipt.EvaluatedStep || claim.ObservedStep > request.CurrentStep {
			continue
		}
		if claim.FactID != request.PreviousReceipt.FactID || claim.Predicate != request.PreviousReceipt.Predicate || !sameScope(claim.Scope, request.PreviousReceipt.Scope) {
			continue
		}
		if claim.ValidUntilStep < request.CurrentStep {
			continue
		}
		contradicts := claim.Value == "inconclusive"
		if equalStringSets(request.PreviousReceipt.PredictionSet, []string{"clear"}) {
			contradicts = contradicts || claim.Value == "blocked"
		} else if equalStringSets(request.PreviousReceipt.PredictionSet, []string{"blocked"}) {
			contradicts = contradicts || claim.Value == "clear"
		}
		if contradicts {
			triggerIDs = append(triggerIDs, claim.ClaimID)
		}
	}
	if len(triggerIDs) > 0 {
		reasons = append(reasons, "new_contradicting_claim")
	}
	if !request.PreviousReceipt.Admitted {
		reasons = append(reasons, "previous_action_not_admitted")
	}
	sort.Strings(reasons)
	sort.Strings(triggerIDs)
	receipt := PlanInvalidationReceipt{
		SchemaVersion:         PlanInvalidationReceiptSchema,
		PreviousReceiptSHA256: request.PreviousReceipt.ReceiptSHA256,
		CurrentStep:           request.CurrentStep,
		Invalidated:           request.PreviousReceipt.Admitted && len(reasons) > 0,
		Reasons:               reasons,
		TriggeringClaimIDs:    triggerIDs,
	}
	if err := signInvalidationReceipt(&receipt); err != nil {
		return PlanInvalidationReceipt{}, err
	}
	return receipt, nil
}

// ProcessLine handles one request while keeping protocol errors isolated to the
// current NDJSON line. The caller may continue processing later lines.
func ProcessLine(line []byte) Response {
	response := Response{SchemaVersion: ResponseSchema, OK: false, Result: nil, Error: nil}
	var command Command
	decoder := json.NewDecoder(bytes.NewReader(line))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&command); err != nil {
		response.Error = &ProtocolError{Code: "invalid_json", Message: err.Error()}
		return response
	}
	var trailing any
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		if err == nil {
			response.Error = &ProtocolError{Code: "invalid_json", Message: "multiple JSON values are not allowed"}
		} else {
			response.Error = &ProtocolError{Code: "invalid_json", Message: err.Error()}
		}
		return response
	}
	response.RequestID = command.RequestID
	if command.SchemaVersion != CommandSchema {
		response.Error = &ProtocolError{Code: "invalid_request", Message: fmt.Sprintf("schema_version must be %q", CommandSchema)}
		return response
	}
	if command.RequestID == "" {
		response.Error = &ProtocolError{Code: "invalid_request", Message: "request_id must not be empty"}
		return response
	}
	var result any
	var err error
	switch command.Op {
	case OperationEvaluateAction:
		var request EvaluateActionRequest
		err = decodePayload(command.Payload, &request)
		if err == nil {
			result, err = EvaluateAction(request)
		}
	case OperationInvalidatePlan:
		var request InvalidatePlanRequest
		err = decodePayload(command.Payload, &request)
		if err == nil {
			result, err = InvalidatePlan(request)
		}
	default:
		err = invalid("unsupported op %q", command.Op)
	}
	if err != nil {
		code := "internal_error"
		var validation validationError
		if errors.As(err, &validation) || strings.Contains(err.Error(), "unknown field") || strings.Contains(err.Error(), "JSON") || strings.Contains(err.Error(), "json") {
			code = "invalid_request"
		}
		response.Error = &ProtocolError{Code: code, Message: err.Error()}
		return response
	}
	response.OK = true
	response.Result = result
	return response
}

func decodePayload(data []byte, destination any) error {
	if len(data) == 0 || string(data) == "null" {
		return invalid("payload must be an object")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(destination); err != nil {
		return invalid("decode payload: %v", err)
	}
	var trailing any
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		if err == nil {
			return invalid("payload contains multiple JSON values")
		}
		return invalid("decode trailing payload: %v", err)
	}
	return nil
}
