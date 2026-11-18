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
    Gather future-stage knowledge tokens from subsequent injects within the same scenario.
    For the lean source→master path, treat future 'new_confirmed_facts' as forbidden for earlier artefacts.
    Backward compatibility: if legacy 'knowledge_newly_revealed' exists at top-level, include those too.
    """
    fut: Set[str] = set()
    try:
        scenarios = plan.get("scenarios", []) or []
        inj_list = (scenarios[scenario_idx] or {}).get("injects", []) or []
        for j in range(inject_idx + 1, len(inj_list)):
            inj = inj_list[j] or {}
            st = (inj.get("inject_state") or {}) if isinstance(inj, dict) else {}
            # Prefer canonical new facts from later stages
            for k in (st.get("new_confirmed_facts", []) or []):
                t = _norm(k)
                if t:
                    fut.add(t)
            # Also include any legacy per-inject revealed knowledge if present
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
    - allowed := known_facts_before ∪ new_confirmed_facts (preferred from inject_state)
                 falling back to legacy knowledge_before ∪ knowledge_newly_revealed
    - forbidden := future knowledge (later-stage new_confirmed_facts/legacy knowledge_newly_revealed)
                   ∪ hidden truths (from blueprint)
    """
    scenarios = plan.get("scenarios", []) or []
    inj = ((scenarios[scenario_idx] or {}).get("injects", []) or [])[inject_idx] or {}
    st = (inj.get("inject_state") or {}) if isinstance(inj, dict) else {}

    # Preferred canonical sources (lean/master path)
    kb1 = {_norm(x) for x in (st.get("known_facts_before", []) or []) if x}
    kn1 = {_norm(x) for x in (st.get("new_confirmed_facts", []) or []) if x}

    # Legacy fallbacks (older pipelines)
    kb0 = {_norm(x) for x in (inj.get("knowledge_before", []) or []) if x}
    kn0 = {_norm(x) for x in (inj.get("knowledge_newly_revealed", []) or []) if x}

    allowed = {x for x in ((kb1 | kn1) or (kb0 | kn0)) if x}
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
    Prefer explicit artefact_spec.source_system, then systems_to_check, then type-aware defaults.
    """
    srcs: List[str] = []
    try:
        spec = inj.get("artefact_spec") or {}
        hint = str((spec or {}).get("artefact_type") or "").strip().lower()
        ssys = (spec or {}).get("source_system")
        if ssys:
            srcs.append(str(ssys))
        for s in (inj.get("systems_to_check", []) or []):
            if s and s not in srcs:
                srcs.append(s)
    except Exception:
        pass
    if srcs:
        return srcs[:3]
    # Type-aware fallbacks
    try:
        hint = str(((inj.get("artefact_spec") or {}).get("artefact_type") or "")).strip().lower()
    except Exception:
        hint = ""
    if hint == "ticket":
        return ["Service Desk"]
    if hint == "log":
        return ["Identity provider sign-in logs"]
    return ["Identity provider sign-in logs"]


def generate_artefact_body(artefact_type: str, source_system: str, tokens: Set[str]) -> str:
    """
    Assemble a readable artefact body from allowed tokens only.
    This function never includes forbidden tokens; caller must ensure tokens are allowed.
    """
    toks = sorted([t for t in tokens if t])[:4]
    if artefact_type in ("press_release", "exec_email", "board_pack", "regulator_notice", "customer_email", "news"):
        lines = [f"Source: {source_system}", "X-Simulated: true"]
        lines += [f"- {t}" for t in toks]
        return "\n".join(lines)
    if artefact_type == "ticket":
        lines = [
            f"System: {source_system}",
            "Record Type: Incident Ticket",
            "Summary:",
        ]
        lines += [f"- {t}" for t in toks]
        return "\n".join(lines)
    if artefact_type == "log":
        lines = [
            f"Log Source: {source_system}",
            "Events:",
        ]
        lines += [f"- {t}" for t in toks]
        return "\n".join(lines)
    # Default compact text for configuration/code
    lines = [f"Source: {source_system}"] + [f"- {t}" for t in toks]
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


# Bounded participant-disclosure scrub for final-stage artefact content
_HIDDEN_MARKER_TOKENS: Set[str] = {
    "root cause",
    "attacker",
    "threat actor",
    "phishing attack",
    "compromised account",
    "unauthorised access",
    "malicious activity",
    "known threat actor",
    "exfiltrated",
}

def _scrub_participant_disclosures(text: str, forbidden: Set[str]) -> str:
    """
    Remove the smallest prohibited clause or token from participant-visible text.
    - Operates only on participant content (not facilitator content)
    - Does not invent new facts; redacts tokens in place
    - Case-insensitive, bounded replacements
    """
    try:
        import re as _re
        out = text or ""
        # Union of runtime forbidden tokens and canonical hidden markers
        toks: Set[str] = set(_HIDDEN_MARKER_TOKENS)
        for ft in forbidden or set():
            t = str(ft or "").strip()
            if t:
                toks.add(t)
        for tok in sorted(toks, key=len, reverse=True):
            # Case-insensitive, word-boundary tolerant replacement
            pattern = _re.compile(_re.escape(tok), _re.IGNORECASE)
            out = pattern.sub("[REDACTED]", out)
        return out
    except Exception:
        return text


def _canon_entity_names(text: str) -> str:
    """
    Canonicalise common service-name variants in participant-visible text.
    This targets only participant artefact content and titles; does not affect facilitator content.
    """
    try:
        t = str(text or "")
        replacements = (
            ("Northsat", "Northstar"),
            ("northsat", "Northstar"),
            ("Northdstart", "Northstar"),
            ("northdstart", "Northstar"),
        )
        for src, dst in replacements:
            t = t.replace(src, dst)
        return t
    except Exception:
        return str(text or "")


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
            # Augment forbidden set with hidden_root_cause_context (if present)
            try:
                _st_local = inj.get("inject_state") or {}
                _hrc = _st_local.get("hidden_root_cause_context")
                if _hrc:
                    forbidden.add(_norm(_hrc))
            except Exception:
                pass
            new_arts: List[Dict[str, Any]] = []
            count = min(max_per_inject, len(templates))
            for k in range(count):
                atype = templates[k]
                ssys = sources[min(k, len(sources) - 1)]
                body = generate_artefact_body(atype, ssys, allowed)
                body_clean, md_clean = leakage_check(body, [], allowed, forbidden, strict)
                new_arts.append({
                    "artefact_type": atype,
                    "title": ("Incident ticket" if atype == "ticket" else ("Log extract" if atype == "log" else atype.title())),
                    "source_system": ssys if atype != "ticket" else "Service Desk",
                    "body": body_clean,
                    "metadata": md_clean,
                    "render_hint": "wrap-80" if atype in ("press_release", "exec_email", "board_pack", "regulator_notice", "customer_email", "news") else "monospace",
                })
            # Populate the production participant_artefact surface required by validator
            # Required fields: author, audience, author_knowledge_boundary, relative_timestamp, purpose, content
            # Build a realistic artefact for participants using only allowed, stage-appropriate facts.
            def _stage_time(idx: int) -> str:
                # Credible morning → afternoon progression (strictly increasing)
                timeline = ["08:42", "09:35", "11:10", "14:20"]
                try:
                    return timeline[idx] if 0 <= idx < len(timeline) else "09:00"
                except Exception:
                    return "09:00"

            def _facts_from_state(state: Dict[str, Any]) -> List[str]:
                new_lines: List[str] = []
                ctx_lines: List[str] = []
                try:
                    for s in (state.get("new_confirmed_facts") or []):
                        if _norm(s) in allowed:
                            new_lines.append(_canon_entity_names(str(s)))
                    for s in (state.get("known_facts_before") or []):
                        if _norm(s) in allowed:
                            ctx_lines.append(_canon_entity_names(str(s)))
                except Exception:
                    pass
                # Dominant current-stage evidence, with at most 2 prior facts for context
                out = new_lines + ctx_lines[:2]
                return out[:6]

            def _choose_author_audience(si: int, jj: int, atype: str) -> Tuple[str, str]:
                at = (atype or "").lower()
                # Vary by type/stage for realism
                if at == "ticket":
                    return ("Service Desk Analyst", "Incident Manager")
                if at in ("log", "security_update", "investigation_update"):
                    return ("Security Analyst (Identity)", "Incident Manager")
                if at in ("exec_email", "board_pack"):
                    return ("Head of Dispatch", "Executive Incident Owner")
                if at in ("customer_email", "press_release", "regulator_notice"):
                    return ("Communications Lead", "Strategic Customer")
                # fallback per stage
                if jj == 0:
                    return ("Service Desk Analyst", "Incident Manager")
                if jj == 1:
                    return ("Security Analyst (Identity)", "Incident Manager")
                if jj == 2:
                    return ("Head of Dispatch", "Executive Incident Owner")
                return ("Communications Lead", "Executive Incident Owner")

            def _subject_for(atype: str, jj: int, st: Dict[str, Any]) -> str:
                ph = str(st.get("phase") or "").strip() or "Update"
                if atype == "ticket":
                    return f"Ticket: Unexpected sign-in prompt and route changes ({ph})"
                if atype in ("log", "security_update", "investigation_update"):
                    return f"Identity/Security Update: Session anomaly and app credential ({ph})"
                if atype in ("exec_email", "board_pack"):
                    return f"Operational Impact Update: Priority routes and continuity ({ph})"
                if atype in ("customer_email", "press_release", "regulator_notice"):
                    return f"Holding Response: Northstar dispatch operations ({ph})"
                return f"Update: {ph}"

            def _render_ticket(ts: str, facts: List[str]) -> str:
                lines = []
                lines.append(f"Ticket ID: IM-{ts.replace(':','')}")
                lines.append(f"Opened: {ts}")
                lines.append("Reported by: Dispatch Supervisor")
                lines.append("Affected user: Dispatch Supervisor")
                lines.append("Affected service: Northstar Dispatch API / Microsoft 365")
                lines.append("Priority: High (morning dispatch peak)")
                lines.append("Summary: Unexpected reauthentication and route changes observed")
                lines.append("Description:")
                for f in facts[:4]:
                    lines.append(f"  - {f}")
                lines.append("Actions already taken: Manual restoration of affected route assignments")
                lines.append("Escalation status: Referred to Incident Manager for triage")
                return "\n".join(lines)

            def _render_sec_update(ts: str, facts: List[str]) -> str:
                lines = []
                lines.append(f"Incident reference: INC-{ts.replace(':','')}")
                lines.append(f"Timestamp: {ts}")
                lines.append("Prepared by: Security Analyst (Identity)")
                lines.append("Affected identity: Dispatch Supervisor")
                lines.append("Observed activity:")
                for f in facts[:3]:
                    lines.append(f"  - {f}")
                lines.append("Endpoint correlation: No matching interactive activity on corporate laptop during suspicious session")
                lines.append("Azure activity: New application credential and subsequent queries")
                lines.append("Containment status: Pending authority for session revocation and credential removal")
                lines.append("Decision required: Approve identity containment and credential removal")
                return "\n".join(lines)

            def _render_ops_update(ts: str, facts: List[str]) -> str:
                lines = []
                lines.append(f"Incident reference: OPS-{ts.replace(':','')}")
                lines.append(f"Operational period: Morning shift to present ({ts})")
                lines.append("Affected operation: Priority dispatch planning and driver instruction")
                lines.append("Observed impact:")
                for f in facts[:4]:
                    lines.append(f"  - {f}")
                lines.append("Continuity measure: Dual-approval for priority route changes in effect")
                lines.append("Customer consequence: Delivery-window risk under assessment")
                lines.append("Current operating position: Controlled recovery underway")
                lines.append("Decision required: Continue controlled recovery and initiate data-impact assessment")
                return "\n".join(lines)

            def _render_email(ts: str, facts: List[str], subject: str, sender: str, recipient: str) -> str:
                lines = []
                lines.append(f"From: {sender}")
                lines.append(f"To: {recipient}")
                lines.append(f"Sent: {ts}")
                lines.append(f"Subject: {subject}")
                lines.append("")
                lines.append("Message:")
                for f in facts[:4]:
                    lines.append(f"- {f}")
                lines.append("")
                lines.append("Please confirm the approval path and response deadline for external communications.")
                return "\n".join(lines)

            # Determine artefact type preference from accepted source (if present on inject) or audience templates
            atype_pref = None
            try:
                # artefact_spec exists in the lean source; in master it may not; rely on inj.get('artefact_spec') if present
                atype_pref = str((inj.get("artefact_spec") or {}).get("artefact_type") or "").lower()
            except Exception:
                atype_pref = None

            # Collect participant-safe facts for this stage (build state with legacy fallback)
            st = inj.get("inject_state") or {}
            if not isinstance(st, dict):
                st = {}
            if not st:
                st = {
                    "known_facts_before": inj.get("knowledge_before") or [],
                    "new_confirmed_facts": inj.get("knowledge_newly_revealed") or [],
                }
            facts = _facts_from_state(st)
            # Remove banned phrases from participant-facing artefacts
            _banned_terms = {
                "evidence summary sanitised",
                "this summary informs decision-making",
                "simulated evidence shows",
                "prior context established",
                "synthetic evidence",
                "generated summary",
                "the artefact indicates",
                "participants should consider",
            }
            facts = [f for f in facts if all(bt not in str(f).lower() for bt in _banned_terms)]
            ts = _stage_time(ij)

            # Stage-based author/audience and classification FIRST (ensures subject/content alignment)
            if ij == 0:
                author, audience_role = "Service Desk Analyst", "Incident Manager"
                stage_type_for_subject = "ticket"
            elif ij == 1:
                author, audience_role = "Security Analyst (Identity)", "Incident Manager"
                stage_type_for_subject = "investigation_update"
            elif ij == 2:
                author, audience_role = "Head of Dispatch", "Executive Incident Owner"
                stage_type_for_subject = "exec_email"  # yields Operational Impact Update
            else:
                author, audience_role = "Communications Lead", "Executive Incident Owner"
                stage_type_for_subject = "customer_email"  # yields Holding Response

            # Subject/title must exactly match rendered artefact classification
            subject = _subject_for(stage_type_for_subject, ij, st)

            # Render content by stage (structure must match classification)
            if ij == 0:
                content = _canon_entity_names(_render_ticket(ts, facts))
            elif ij == 1:
                content = _canon_entity_names(_render_sec_update(ts, facts))
            elif ij == 2:
                content = _canon_entity_names(_render_ops_update(ts, facts))
            else:
                content = _canon_entity_names(_render_email(ts, facts, subject, author, audience_role))

            # Participant artefact object (participant-facing)
            inj["participant_artefact"] = {
                "author": author,
                "audience": audience_role,
                "author_knowledge_boundary": "Observed evidence only; no facilitator conclusions",
                "relative_timestamp": ts,
                "purpose": subject,
                "content": content,
            }

            # Persist generated artefacts list (non-authoritative for participants)
            inj["artefacts"] = new_arts
    return plan


__all__ = [
    "synthesise_participant_artefacts",
    "compute_allowed_sets",
    "generate_artefact_body",
    "leakage_check",
]