"""v5 policies: naive, purify-passive, purify-active."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

POLICY_NAIVE = "naive"
POLICY_PURIFY_PASSIVE = "purify-passive"
POLICY_PURIFY_ACTIVE = "purify-active"
POLICIES = (POLICY_NAIVE, POLICY_PURIFY_PASSIVE, POLICY_PURIFY_ACTIVE)


@dataclass(frozen=True, slots=True)
class PolicyDescriptor:
    name: str
    requires_go_gate: bool
    allows_repair: bool


DESCRIPTORS = {
    POLICY_NAIVE: PolicyDescriptor(POLICY_NAIVE, False, False),
    POLICY_PURIFY_PASSIVE: PolicyDescriptor(POLICY_PURIFY_PASSIVE, True, False),
    POLICY_PURIFY_ACTIVE: PolicyDescriptor(POLICY_PURIFY_ACTIVE, True, True),
}


def get_policy_descriptor(policy: str) -> PolicyDescriptor:
    if policy not in DESCRIPTORS:
        raise ValueError(f"unsupported v5 policy: {policy}")
    return DESCRIPTORS[policy]


def naive_decision_from_claims(claims: list[Mapping[str, Any]]) -> str:
    """Majority vote on clear/blocked among non-map claims; default unresolved."""
    votes = {"clear": 0, "blocked": 0}
    for claim in claims:
        if claim.get("modality") == "static_map":
            continue
        value = claim.get("value")
        if value in votes:
            votes[value] += 1
    if votes["clear"] > votes["blocked"] and votes["clear"] > 0:
        return "clear"
    if votes["blocked"] > votes["clear"] and votes["blocked"] > 0:
        return "blocked"
    return "unresolved"


__all__ = (
    "POLICY_NAIVE",
    "POLICY_PURIFY_PASSIVE",
    "POLICY_PURIFY_ACTIVE",
    "POLICIES",
    "PolicyDescriptor",
    "get_policy_descriptor",
    "naive_decision_from_claims",
)
