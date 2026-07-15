package purifyrobotics

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
)

// CanonicalJSON produces compact JSON with lexicographically ordered object
// keys and without HTML escaping. Values are first normalized through JSON so
// structs and maps share one deterministic representation.
func CanonicalJSON(value any) ([]byte, error) {
	raw, err := json.Marshal(value)
	if err != nil {
		return nil, fmt.Errorf("normalize canonical JSON: %w", err)
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var normalized any
	if err := decoder.Decode(&normalized); err != nil {
		return nil, fmt.Errorf("decode normalized JSON: %w", err)
	}
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(normalized); err != nil {
		return nil, fmt.Errorf("encode canonical JSON: %w", err)
	}
	return bytes.TrimSuffix(buffer.Bytes(), []byte("\n")), nil
}

func hashCanonical(value any) (string, error) {
	data, err := CanonicalJSON(value)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:]), nil
}

func signGateReceipt(receipt *GateReceipt) error {
	receipt.ReceiptID = ""
	receipt.ReceiptSHA256 = ""
	identityHash, err := hashCanonical(receipt)
	if err != nil {
		return err
	}
	receipt.ReceiptID = "gate:" + identityHash[:16]
	receipt.ReceiptSHA256 = ""
	receiptHash, err := hashCanonical(receipt)
	if err != nil {
		return err
	}
	receipt.ReceiptSHA256 = receiptHash
	return nil
}

// VerifyGateReceipt checks the canonical content hash embedded in a receipt.
func VerifyGateReceipt(receipt GateReceipt) error {
	expected := receipt.ReceiptSHA256
	if !isSHA256(expected) {
		return fmt.Errorf("receipt_sha256 is not a lowercase SHA-256")
	}
	receipt.ReceiptSHA256 = ""
	actual, err := hashCanonical(receipt)
	if err != nil {
		return err
	}
	if actual != expected {
		return fmt.Errorf("receipt hash mismatch: expected %s, got %s", expected, actual)
	}
	return nil
}

func signInvalidationReceipt(receipt *PlanInvalidationReceipt) error {
	receipt.ReceiptID = ""
	receipt.ReceiptSHA256 = ""
	identityHash, err := hashCanonical(receipt)
	if err != nil {
		return err
	}
	receipt.ReceiptID = "invalidation:" + identityHash[:16]
	receipt.ReceiptSHA256 = ""
	receiptHash, err := hashCanonical(receipt)
	if err != nil {
		return err
	}
	receipt.ReceiptSHA256 = receiptHash
	return nil
}

// VerifyPlanInvalidationReceipt checks the embedded canonical content hash.
func VerifyPlanInvalidationReceipt(receipt PlanInvalidationReceipt) error {
	expected := receipt.ReceiptSHA256
	if !isSHA256(expected) {
		return fmt.Errorf("receipt_sha256 is not a lowercase SHA-256")
	}
	receipt.ReceiptSHA256 = ""
	actual, err := hashCanonical(receipt)
	if err != nil {
		return err
	}
	if actual != expected {
		return fmt.Errorf("receipt hash mismatch: expected %s, got %s", expected, actual)
	}
	return nil
}
