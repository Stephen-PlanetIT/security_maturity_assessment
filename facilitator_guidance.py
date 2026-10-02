from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import re

# Deterministic, facilitator-only guidance generator for each inject.
# This module NEVER writes facilitator guidance into participant-facing fields.
# British English spelling (facilitator, artefact) is used.


def _norm(s: str) -> str:
    try:
        return re.sub(r"\s+", " ", str(s or "")).strip()
    except Exception:
        return str(s or "")


def _choose_prompt(decision_threshold: str, expected_mature_response: str) -> str:
    dt = _norm(decision_threshold)
    emr = _norm(expected_mature_response)
    if dt and emr:
        return f"Steer towards validating evidence required to meet '{dt}'. Confirm authority to enact: {emr}."
    if dt:
        return f"Timebox discussion to reach the governance threshold: '{dt}'. Require explicit evidence and authority."
    if emr:
        return f"Guide the room to articulate the authority and steps for: {emr}."
    return "Steer towards evidence-backed decisions with clear authority and timebox enforcement."


def _probes_rationale(fpq: List[str]) -> Optional[str]:
    try:
        qs = [q for q in (fpq or []) if isinstance(q, str)]
        if not qs:
            return None
        # Compact rationale: connect probes to learning objectives
        return (
            "Use probes to validate evidence chains, test governance thresholds, "
            "confirm authority for containment, and shape communications. "
            "Include a 'what‑if' to address adverse branches."
        )
    except Exception:
        return None


def _derive_escalation_cues(decision_threshold: str, roles_to_engage: List[str]) -> List[str]:
    cues: List[str] = []
    dt = _norm(decision_threshold)
    if dt:
        cues.append(f"If discussion stalls, restate the decision threshold: {dt}.")
    try:
        for r in (roles_to_engage or [])[:3]:
            if r and r not in cues:
                cues.append(f"Prompt engagement of: {r}.")
    except Exception:
        pass
    # Cap 4 cues maximum
    return cues[:4]


def _wrap_if_deviation(common_pitfalls: List[str]) -> Optional[str]:
    try:
        pits = [p for p in (common_pitfalls or []) if isinstance(p, str)]
        if not pits:
            return "If the room deviates, introduce a short consequence and re-centre on governance thresholds."
        return f"If deviation occurs ({pits[0]}), pivot to consequences and re-centre on governance thresholds."
    except Exception:
        return "If the room deviates, introduce a short consequence and re-centre on governance thresholds."


def generate_inject_facilitation(plan: Dict[str, Any], blueprint: Optional[Dict[str, Any]] = None, audience: str = "Blended") -> Dict[str, Dict[str, str]]:
    """
    Build a facilitator-only guidance map keyed by scenario/inject indices:
      fac_map[(si, ji)] = {
        'guide_prompt': str,
        'probes_rationale': str|None,
        'escalation_cues': bullet string or empty,
        'wrap_if_deviation': str|None
      }
    This function consumes only participant-facing inject fields and derives compact facilitator notes.
    """
    fac_map: Dict[str, Dict[str, str]] = {}
    scenarios = plan.get("scenarios", []) or []
    for si, scn in enumerate(scenarios):
        injx = scn.get("injects", []) or []
        for ji, inj in enumerate(injx):
            def g(k, d=None):
                return inj.get(k, d) if isinstance(inj, dict) else d
            dt = g("decision_threshold", "") or ""
            emr = g("expected_mature_response", "") or ""
            fpq = g("facilitator_probe_questions", []) or []
            roles = g("roles_to_engage", []) or []
            pits = g("common_pitfalls", []) or []

            prompt = _choose_prompt(dt, emr)
            rationale = _probes_rationale(fpq)
            cues_list = _derive_escalation_cues(dt, roles)
            cues_text = "\n".join([f"- {c}" for c in cues_list]) if cues_list else ""
            wrap = _wrap_if_deviation(pits)

            key = f"{si}:{ji}"
            fac_map[key] = {
                "guide_prompt": prompt,
                "probes_rationale": rationale or "",
                "escalation_cues": cues_text,
                "wrap_if_deviation": wrap or "",
            }
    return fac_map


def attach_facilitation_to_plan(plan: Dict[str, Any], fac_map: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """
    Store facilitator-only guidance under a private plan key. This is consumed by export
    to map into PPTX speaker notes. Participant-facing content must never include this map.
    """
    plan["_facilitator_notes"] = fac_map or {}
    return plan


__all__ = ["generate_inject_facilitation", "attach_facilitation_to_plan"]