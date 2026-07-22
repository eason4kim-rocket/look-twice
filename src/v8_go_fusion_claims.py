"""Helpers for Go fusion evidence: claim polarity + unique roots for Purify."""
from __future__ import annotations
from typing import Any

# Audit-only keys must never be sent to purify-robotics-core (strict JSON decode).
GO_WIRE_AUDIT_KEYS = (
    "_conformal_value_original",
    "_p_blocked_raw",
)


def decisive_value_from_p(p_blocked: float, conformal_value: str) -> str:
    """Map claim value for Go settlement.

    When conformal returns dual/inconclusive due to extreme thresholds but p is
    decisive, use polarity so Go can form measurement roots. Does not invent
    conformal thresholds (no 0.5 fill of quantiles).
    """
    p = float(p_blocked)
    if conformal_value in ("clear", "blocked"):
        return conformal_value
    # inconclusive / dual set: polarity for evidence consumption
    if p >= 0.5:
        return "blocked"
    return "clear"


def patch_claim_wire_for_go(
    wire: dict[str, Any],
    *,
    p_blocked: float,
    capture_root_id: str,
    device_root_id: str,
) -> dict[str, Any]:
    """Return Go-safe wire + keep audit fields only under _audit (stripped before send)."""
    w = dict(wire)
    original = str(w.get("value") or "")
    value_go = decisive_value_from_p(p_blocked, original)
    w["value"] = value_go
    # unique physical roots
    w["capture_root_id"] = capture_root_id
    w["device_root_id"] = device_root_id
    # confidence aligned with polarity for Go quality path
    if value_go == "blocked":
        w["confidence"] = max(float(w.get("confidence") or 0.5), float(p_blocked))
    elif value_go == "clear":
        w["confidence"] = max(float(w.get("confidence") or 0.5), 1.0 - float(p_blocked))
    # ensure quality/visibility not zero (inconclusive heads often zero)
    w["quality"] = max(float(w.get("quality") or 0.0), 0.6)
    w["visibility"] = max(float(w.get("visibility") or 0.0), 0.6)
    # stash audit offline only — strip_for_go removes these
    w["_conformal_value_original"] = original
    w["_p_blocked_raw"] = float(p_blocked)
    return w


def strip_claim_wire_for_go(wire: dict[str, Any]) -> dict[str, Any]:
    """Drop audit-only keys so purify core JSON decode accepts the payload."""
    out = {k: v for k, v in wire.items() if not str(k).startswith("_")}
    for k in GO_WIRE_AUDIT_KEYS:
        out.pop(k, None)
    return out
