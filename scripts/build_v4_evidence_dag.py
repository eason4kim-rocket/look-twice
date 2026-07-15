#!/usr/bin/env python3
"""Build an auditable Graphviz DOT evidence lineage for one v4 episode.

Graphviz is not required: the output is plain UTF-8 DOT text that can be
reviewed, versioned, or rendered later.  Invalid episode JSON is rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from validate_v4_result import load_json_strict, validate_episode


def _escape(value: Any) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


def _node_id(kind: str, identity: str) -> str:
    digest = hashlib.sha256(f"{kind}:{identity}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}_{digest}"


def _claim_label(claim: Mapping[str, Any], *, submitted: bool = False) -> str:
    suffix = "\\nGATE-SUBMITTED TRANSFORM" if submitted else ""
    return (
        f"Claim {claim.get('claim_id')}\\n"
        f"{claim.get('modality')}: {claim.get('value')} "
        f"({float(claim.get('confidence', 0)):.3f})\\n"
        f"step={claim.get('observed_step')}{suffix}"
    )


def build_dot(document: Mapping[str, Any], title: str = "Look Twice v4 Evidence DAG") -> str:
    claims = {
        claim["claim_id"]: claim
        for claim in document.get("claims", [])
        if isinstance(claim, dict) and isinstance(claim.get("claim_id"), str)
    }
    submitted = {
        claim["claim_id"]: claim
        for claim in document.get("gate_submitted_claims", [])
        if isinstance(claim, dict) and isinstance(claim.get("claim_id"), str)
    }
    all_claims = dict(claims)
    all_claims.update(submitted)
    lines = [
        "digraph look_twice_v4 {",
        "  graph [rankdir=LR, bgcolor=\"white\", fontname=\"Helvetica\", labelloc=\"t\"];",
        f'  label="{_escape(title)}";',
        "  node [fontname=\"Helvetica\", fontsize=9];",
        "  edge [fontname=\"Helvetica\", fontsize=8];",
        "  subgraph cluster_online {",
        '    label="ONLINE EVIDENCE + ACTION QUALIFICATION";',
        '    color="#4c78a8";',
    ]

    for claim_id in sorted(all_claims):
        claim = all_claims[claim_id]
        transformed = claim_id in submitted and claim_id not in claims
        fill = "#fff1cc" if transformed else ("#e8f1fb" if claim.get("modality") != "static_map" else "#eeeeee")
        node = _node_id("claim", claim_id)
        lines.append(
            f'    {node} [shape=box, style="rounded,filled", fillcolor="{fill}", '
            f'label="{_escape(_claim_label(claim, submitted=transformed))}"];'
        )

    root_nodes: dict[str, str] = {}
    for claim_id in sorted(all_claims):
        claim = all_claims[claim_id]
        capture = str(claim.get("capture_root_id", "unknown"))
        root_identity = f"map:{capture}" if claim.get("modality") == "static_map" else capture
        if root_identity not in root_nodes:
            node = _node_id("root", root_identity)
            root_nodes[root_identity] = node
            style = 'shape=ellipse, style="filled", fillcolor="#dff2df"'
            if claim.get("modality") == "static_map":
                style = 'shape=ellipse, style="dashed,filled", fillcolor="#eeeeee"'
            lines.append(f'    {node} [{style}, label="root\\n{_escape(root_identity)}"];')
        lines.append(
            f'    {_node_id("claim", claim_id)} -> {root_nodes[root_identity]} '
            '[label="derived from", color="#4c78a8"];'
        )
        for parent_id in sorted(claim.get("parent_claim_ids", [])):
            if parent_id in all_claims:
                lines.append(
                    f'    {_node_id("claim", parent_id)} -> {_node_id("claim", claim_id)} '
                    '[label="parent", style=dashed, color="#8c6d31"];'
                )

    gate_nodes: dict[str, str] = {}
    receipts = document.get("gate_receipts", [])
    for index, receipt in enumerate(receipts):
        receipt_hash = str(receipt.get("receipt_sha256", f"index-{index}"))
        node = _node_id("gate", receipt_hash)
        gate_nodes[receipt_hash] = node
        fill = "#d8f0d2" if receipt.get("admitted") else "#f8d7da"
        label = (
            f"GateReceipt {index + 1}\\n{receipt.get('action')} → {receipt.get('decision')}\\n"
            f"set={receipt.get('prediction_set')} roots={len(receipt.get('measurement_root_ids', []))}\\n"
            f"step={receipt.get('evaluated_step')}\\nsha={receipt_hash[:12]}…"
        )
        lines.append(
            f'    {node} [shape=octagon, style="filled", fillcolor="{fill}", label="{_escape(label)}"];'
        )
        linked_roots: set[str] = set()
        for claim_id in receipt.get("used_claim_ids", []):
            claim = submitted.get(claim_id) or claims.get(claim_id)
            if claim is None:
                continue
            root_identity = (
                f"map:{claim.get('capture_root_id')}"
                if claim.get("modality") == "static_map"
                else str(claim.get("capture_root_id"))
            )
            root_node = root_nodes.get(root_identity)
            if root_node is not None and root_identity not in linked_roots:
                lines.append(f'    {root_node} -> {node} [label="used", penwidth=2, color="#2a6fbb"];')
                linked_roots.add(root_identity)
        for discounted in receipt.get("discounted_claims", []):
            claim_id = discounted.get("claim_id")
            if claim_id in all_claims:
                lines.append(
                    f'    {_node_id("claim", claim_id)} -> {node} '
                    f'[label="{_escape(discounted.get("reason"))}", style=dotted, color="#b22222"];'
                )
                reason = str(discounted.get("reason", ""))
                if reason.startswith("artifact_duplicate_of:"):
                    original = reason.split(":", 1)[1]
                    if original in all_claims:
                        lines.append(
                            f'    {_node_id("claim", original)} -> {_node_id("claim", claim_id)} '
                            '[label="exact artifact echo", style=dashed, color="#b22222"];'
                        )

    repair_nodes: list[tuple[int, str]] = []
    for index, repair in enumerate(document.get("repair_decisions", [])):
        step = int(repair.get("step", -1))
        node = _node_id("repair", f"{step}:{index}")
        selected = repair.get("selected_action") or {}
        label = (
            f"BeliefGap Repair {index + 1}\\n"
            f"gaps={repair.get('belief_gap')}\\n"
            f"action={selected.get('name', 'none')}\\nstep={step}"
        )
        lines.append(f'    {node} [shape=diamond, style="filled", fillcolor="#eadcf8", label="{_escape(label)}"];')
        earlier = [
            (int(receipt.get("evaluated_step", -1)), gate_nodes.get(str(receipt.get("receipt_sha256"))))
            for receipt in receipts
            if int(receipt.get("evaluated_step", -1)) <= step
        ]
        if earlier:
            _, gate_node = max(earlier)
            if gate_node:
                lines.append(f'    {gate_node} -> {node} [label="BeliefGap", color="#7b3294"];')
        repair_nodes.append((step, node))

    for index, invalidation in enumerate(document.get("plan_invalidation_receipts", [])):
        identity = str(invalidation.get("receipt_sha256", f"ablation-{index}"))
        node = _node_id("invalidation", identity)
        label = (
            f"PlanInvalidation {index + 1}\\n"
            f"invalidated={invalidation.get('invalidated')}\\n"
            f"reasons={invalidation.get('reasons')}"
        )
        lines.append(f'    {node} [shape=hexagon, style="filled", fillcolor="#ffd9b3", label="{_escape(label)}"];')
        previous = str(invalidation.get("previous_receipt_sha256", ""))
        if previous in gate_nodes:
            lines.append(f'    {gate_nodes[previous]} -> {node} [label="revokes/checks", penwidth=2, color="#d95f02"];')

    lines.extend(["  }", "  subgraph cluster_oracle {"])
    lines.extend(
        [
            '    label="EVALUATOR-ONLY ORACLE (NO OUTGOING EDGE)";',
            '    color="#777777";',
            '    style="dashed";',
        ]
    )
    oracle_scenario = document.get("oracle", {}).get("scenario", {})
    truth = oracle_scenario.get("world_truth", {})
    oracle_label = (
        f"Oracle evaluation only\\nprofile={oracle_scenario.get('profile')} "
        f"seed={oracle_scenario.get('seed')}\\n"
        f"initial_blocked={truth.get('initial_blocked')}\\n"
        f"observations={len(document.get('oracle', {}).get('observations', []))}"
    )
    lines.append(
        f'    {_node_id("oracle", str(oracle_scenario.get("scenario_id", "oracle")))} '
        f'[shape=note, style="dashed,filled", fillcolor="#f5f5f5", label="{_escape(oracle_label)}"];'
    )
    lines.extend(["  }", "}"])
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="validated v4 episode JSON")
    parser.add_argument("-o", "--output", type=Path, help="output .dot path")
    args = parser.parse_args(argv)
    try:
        document = load_json_strict(args.input)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    errors = validate_episode(document, str(args.input))
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    output = args.output or args.input.with_suffix(".evidence.dot")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_dot(document, title=f"Look Twice v4 — {args.input.name}"), encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
