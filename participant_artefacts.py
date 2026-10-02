from __future__ import annotations
from typing import List, Optional, Tuple, Set, Dict, Any
from config import get_config
import re

# Knowledge-bound participant artefact synthesis (deterministic; no LLM)
# This stage must only include information permitted by the inject's participant knowledge state.
# British English spelling is used (artefact).


def _norm(s: str) -> str:
    """
    Normalise a string for leakage checks:
    - Lowercase
    - Collapse whitespace
    - Strip most punctuation except word chars, whitespace, hyphen, dot, colon
    """
    try:
        s2 = re.sub(r"\s+", " ", str(s or "")).strip().lower()
        return re.sub(r"[^\w\s\-\.\:]", "", s2)
    except Exception:
        return str(s or "")


def _collect_future_knowledge(plan: Dict[str, Any], scenario_idx: int, inject_idx: int) -> Set[str]:
    """
    Gather knowledge_newly_revealed tokens from subsequent injects within the same scenario.
    These are forbidden for earlier inject artefacts.
    """
    fut: Set[str] = set()
    try:
        scenarios = plan.get("scenarios", []) or []
        inj_list = (scenarios[scenario_idx] or {}).get("injects", []) or []
        for j in range(inject_idx + 1, len(inj_list)):
            inj = inj_list[j] or {}
            for k in (inj.get("knowledge_newly_revealed", []) or []):
                t = _norm(k)
                if t:
                    fut.add(t)
    except Exception:
        pass
    return fut


def _collect_hidden_truths(blueprint: Optional[Dict[str, Any]]) -> Set[str]:
    """
    Collect facilitator-only truths from an ExerciseBlueprint, if provided.
    These strings must never appear in participant artefacts.
    """
    hid: Set[str] = set()
    try:
        fg = (blueprint or {}).get("facilitation_guide") or {}
        for ht in (fg.get("hidden_truths") or []):
            t = _norm((ht or {}).get("truth_narrative", ""))
            if t:
                hid.add(t)
    except Exception:
        pass
    return hid


def compute_allowed_sets(
    plan: Dict[str, Any],
    blueprint: Optional[Dict[str, Any]],
    scenario_idx: int,
    inject_idx: int
) -> Tuple[Set[str], Set[str]]:
    """
    Compute allowed and forbidden token sets for an inject:
    - allowed := knowledge_before ∪ knowledge_newly_revealed
    - forbidden := future knowledge (later injects) ∪ hidden truths (from blueprint)
    """
    scenarios = plan.get("scenarios", []) or []
    inj = ((scenarios[scenario_idx] or {}).get("injects", []) or [])[inject_idx] or {}
    kb = {_norm(x) for x in (inj.get("knowledge_before", []) or []) if x}
    kn = {_norm(x) for x in (inj.get("knowledge_newly_revealed", []) or []) if x}
    allowed = {x for x in (kb | kn) if x}
    forbidden = set()
    forbidden |= _collect_future_knowledge(plan, scenario_idx, inject_idx)
    forbidden |= _collect_hidden_truths(blueprint)
    return allowed, forbidden


def _choose_templates(audience: str) -> List[str]:
    """
    Select artefact types by audience profile.
    - Board: concept communications only
    - Technical: logs/tickets/config/code
    - Blended: a small mix favouring logs/tickets and one concept item
    """
    aud = (audience or "Blended").strip().lower()
    if aud == "board":
        return ["press_release", "exec_email", "board_pack", "regulator_notice", "customer_email", "news"]
    elif aud == "technical":
        return ["log", "ticket", "configuration", "code"]
    return ["log", "ticket", "press_release", "exec_email"]


def _derive_source_systems(inj: Dict[str, Any]) -> List[str]:
    """
    Derive plausible source_system values from systems_to_check for placement in artefacts.
    """
    srcs: List[str] = []
    try:
        for s in (inj.get("systems_to_check", []) or []):
            if s and s not in srcs:
                srcs.append(s)
    except Exception:
        pass
    return srcs[:3] or ["SIEM console"]


def generate_artefact_body(artefact_type: str, source_system: str, tokens: Set[str]) -> str:
    """
    Assemble a short, deterministic artefact body from allowed tokens only.
    This function never includes forbidden tokens; caller must ensure tokens are allowed.
    """
    toks = [t for t in tokens if t][:4]
    if artefact_type in ("press_release", "exec_email", "board_pack", "regulator_notice", "customer_email", "news"):
        lines = [f"Source: {source_system}", "X-Simulated: true"]
        lines += [f"- {t}" for t in toks]
        return "\n".join(lines)
    # Default log/ticket/config/code templates (compact)
    lines = [f"type={artefact_type}", f"source={source_system}"]
    for t in toks:
        lines.append(f"token={t}")
    return "\n".join(lines)


def _redact(txt: str, forbidden: Set[str]) -> str:
    out = txt
    for ft in forbidden:
        if ft and ft in out:
            out = out.replace(ft, "[REDACTED]")
    return out


def leakage_check(
    body: str,
    metadata: Optional[List[str]],
    allowed: Set[str],
    forbidden: Set[str],
    strict: bool
) -> Tuple[str, List[str]]:
    """
    Ensure body/metadata contain no forbidden tokens.
    - In strict mode: raise ValueError on any forbidden token present.
    - Otherwise: redact in place and return cleaned content.
    """
    bnorm = _norm(body)
    mdnorm = [_norm(x) for x in (metadata or [])]
    bclean = _redact(bnorm, forbidden)
    mclean = [_redact(x, forbidden) for x in mdnorm]
    if strict:
        for ft in forbidden:
            if ft and (ft in bclean or any(ft in x for x in mclean)):
                raise ValueError("Participant artefact leakage detected")
    return bclean, mclean


def synthesise_participant_artefacts(
    plan: Dict[str, Any],
    blueprint: Optional[Dict[str, Any]] = None,
    audience: str = "Blended",
    max_per_inject: int = 2
) -> Dict[str, Any]:
    """
    Populate missing inject['artefacts'] lists deterministically from allowed knowledge tokens.
    Respects existing artefacts if already present (editor/LLM may have set them).
    """
    strict = str(get_config("TABLETOP_ARTEFACT_STRICT", "false")).strip().lower() in ("1", "true", "yes", "on")
    scenarios = plan.get("scenarios", []) or []
    for si, scn in enumerate(scenarios):
        injx = scn.get("injects", []) or []
        for ij, inj in enumerate(injx):
            arts = inj.get("artefacts", [])
            if isinstance(arts, list) and arts:
                # Respect existing artefacts; do not overwrite
                continue
            allowed, forbidden = compute_allowed_sets(plan, blueprint, si, ij)
            templates = _choose_templates(audience)
            sources = _derive_source_systems(inj)
            new_arts: List[Dict[str, Any]] = []
            count = min(max_per_inject, len(templates))
            for k in range(count):
                atype = templates[k]
                ssys = sources[min(k, len(sources) - 1)]
                body = generate_artefact_body(atype, ssys, allowed)
                body_clean, md_clean = leakage_check(body, [], allowed, forbidden, strict)
                new_arts.append({
                    "artefact_type": atype,
                    "title": None,
                    "source_system": ssys,
                    "body": body_clean,
                    "metadata": md_clean,
                    "render_hint": "wrap-80" if atype in ("press_release", "exec_email", "board_pack", "regulator_notice", "customer_email", "news") else "monospace",
                })
            inj["artefacts"] = new_arts
    return plan


__all__ = [
    "synthesise_participant_artefacts",
    "compute_allowed_sets",
    "generate_artefact_body",
    "leakage_check",
]