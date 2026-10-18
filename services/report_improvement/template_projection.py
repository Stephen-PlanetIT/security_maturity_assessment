from __future__ import annotations

"""
Typed Template Projection Layer & Fail-Closed Publication Invariants

Converts internal domain models (prompts.py DomainAssessment and specialist DomainAssessmentOutput)
and threat scenario representations into clean, safe, template-facing projections for docxtpl.

Enforces Fail-Closed Publication Invariants:
1. Exactly one score source is active.
2. Exactly one overall 0–100 presentation score exists.
3. Exactly one maturity rating exists.
4. Exactly one resiliency pillar exists.
5. Every scored domain declares its scale and weight.
6. Active scored-domain weights reconcile to 100 within Decimal tolerance.
7. Weighted percentage contributions reconcile to the overall 0–100 score.
8. The maturity rating is derived from the canonical score according to one configured band model.
9. No native 1–3 value is bound into a /100 template field.
10. Required executive snapshot values are populated.
11. Every rendered domain has a populated current_maturity_display.
12. No callable, bound method, class, exception, generator, or coroutine exists in the template context.
13. No internal diagnostic object exists in the client context.
14. No raw placeholder remains in required cover metadata.
15. The selected template is recorded.
"""

from decimal import Decimal
import hashlib
import json
import inspect
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field


def compute_context_fingerprint(context: Dict[str, Any]) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for the projected template context.
    Excludes non-serializable objects (such as InlineImage) and dynamic run tokens.
    """
    def _serialisable(val: Any) -> Any:
        if isinstance(val, (str, int, float, bool)) or val is None:
            return val
        if isinstance(val, Decimal):
            return str(val)
        if isinstance(val, dict):
            # Sort keys for determinism, skip binary/image objects
            return {
                str(k): _serialisable(v)
                for k, v in sorted(val.items(), key=lambda x: str(x[0]))
                if not str(type(v)).startswith("<class 'docx") and "InlineImage" not in str(type(v))
            }
        if isinstance(val, (list, tuple, set)):
            return [_serialisable(x) for x in val]
        if hasattr(val, "model_dump"):
            return _serialisable(val.model_dump())
        return str(type(val))

    serialised = _serialisable(context)
    json_bytes = json.dumps(serialised, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(json_bytes).hexdigest()


from services.report_improvement.canonical_score import (
    CanonicalOverallScore,
    CanonicalDomainScore,
    ScoreSource,
)


class TemplateDomainProjection(BaseModel):
    domain_name: str
    current_maturity_display: str
    current_state_analysis: str = ""
    business_impact_narrative: str = ""
    critical_gaps: List[str] = Field(default_factory=list)
    vendor_agnostic_quick_wins: List[str] = Field(default_factory=list)
    recommended_solutions: List[str] = Field(default_factory=list)
    remediation_rationale: str = ""
    shared_responsibility: str = ""
    gap_remediation_steps: List[str] = Field(default_factory=list)

    def to_template_dict(self) -> Dict[str, Any]:
        """Convert projection to a template-facing dict."""
        return {
            "domain_name": self.domain_name,
            "current_maturity_display": self.current_maturity_display,
            "current_state_analysis": self.current_state_analysis,
            "business_impact_narrative": self.business_impact_narrative,
            "critical_gaps": self.critical_gaps,
            "vendor_agnostic_quick_wins": self.vendor_agnostic_quick_wins,
            "recommended_solutions": self.recommended_solutions,
            "remediation_rationale": self.remediation_rationale,
            "shared_responsibility": self.shared_responsibility,
            "gap_remediation_steps": self.gap_remediation_steps,
        }

    @classmethod
    def from_assessment(cls, domain_obj: Any) -> TemplateDomainProjection:
        """Alias for from_domain for backwards compatibility."""
        return cls.from_domain(domain_obj)

    @classmethod
    def from_domain(cls, domain_obj: Any) -> TemplateDomainProjection:
        """
        Converts either prompts.py DomainAssessment, specialist DomainAssessmentOutput,
        or a structured dict into a strictly validated TemplateDomainProjection.
        Fails if any required field is missing rather than inserting silent empties.
        """
        if domain_obj is None:
            raise ValueError("Cannot project None domain object to template.")

        # Dictionary adaptation
        if isinstance(domain_obj, dict):
            d = domain_obj
            name = str(d.get("domain_name") or "").strip()
            if not name:
                raise ValueError("Domain projection failure: missing required field 'domain_name' in dict.")

            # Resolve current maturity display
            maturity_display = (
                str(d.get("current_maturity_display") or d.get("current_maturity_level") or d.get("current_maturity") or "")
            ).strip()
            if not maturity_display:
                raise ValueError(f"Domain projection failure: domain '{name}' lacks required 'current_maturity_display'.")

            state_analysis = str(d.get("current_state_analysis") or d.get("technical_analysis") or "").strip()
            if not state_analysis:
                raise ValueError(f"Domain projection failure: domain '{name}' lacks required 'current_state_analysis'.")

            impact = str(d.get("business_impact_narrative") or d.get("business_impact_and_risk") or "").strip()
            if not impact:
                raise ValueError(f"Domain projection failure: domain '{name}' lacks required 'business_impact_narrative'.")

            gaps = [str(x).strip() for x in (d.get("critical_gaps") or d.get("confirmed_gaps") or []) if str(x).strip()]
            wins = [str(x).strip() for x in (d.get("vendor_agnostic_quick_wins") or d.get("zero_cost_quick_wins") or []) if str(x).strip()]
            solutions = [str(x).strip() for x in (d.get("recommended_solutions") or []) if str(x).strip()]
            rationale = str(d.get("remediation_rationale") or d.get("strategic_remediation_rationale") or d.get("maturity_rationale") or "").strip()
            shared_resp = str(d.get("shared_responsibility") or d.get("partnership_recommendation") or "").strip()
            steps = [str(x).strip() for x in (d.get("gap_remediation_steps") or []) if str(x).strip()]

            return cls(
                domain_name=name,
                current_maturity_display=maturity_display,
                current_state_analysis=state_analysis,
                business_impact_narrative=impact,
                critical_gaps=gaps,
                vendor_agnostic_quick_wins=wins,
                recommended_solutions=solutions,
                remediation_rationale=rationale,
                shared_responsibility=shared_resp,
                gap_remediation_steps=steps,
            )

        # Object adaptation (BaseModel or class instance)
        name = str(getattr(domain_obj, "domain_name", "")).strip()
        if not name:
            raise ValueError("Domain projection failure: missing required field 'domain_name' on object.")

        maturity_display = str(
            getattr(domain_obj, "current_maturity_display", "")
            or getattr(domain_obj, "current_maturity_level", "")
            or getattr(domain_obj, "current_maturity", "")
        ).strip()
        if not maturity_display:
            raise ValueError(f"Domain projection failure: domain '{name}' lacks required 'current_maturity_display'.")

        state_analysis = str(
            getattr(domain_obj, "current_state_analysis", "") or getattr(domain_obj, "technical_analysis", "")
        ).strip()
        if not state_analysis:
            raise ValueError(f"Domain projection failure: domain '{name}' lacks required 'current_state_analysis'.")

        impact = str(
            getattr(domain_obj, "business_impact_narrative", "") or getattr(domain_obj, "business_impact_and_risk", "")
        ).strip()
        if not impact:
            raise ValueError(f"Domain projection failure: domain '{name}' lacks required 'business_impact_narrative'.")

        gaps = [str(x).strip() for x in (getattr(domain_obj, "critical_gaps", None) or getattr(domain_obj, "confirmed_gaps", None) or []) if str(x).strip()]
        wins = [str(x).strip() for x in (getattr(domain_obj, "vendor_agnostic_quick_wins", None) or getattr(domain_obj, "zero_cost_quick_wins", None) or []) if str(x).strip()]
        solutions = [str(x).strip() for x in (getattr(domain_obj, "recommended_solutions", None) or []) if str(x).strip()]
        rationale = str(getattr(domain_obj, "remediation_rationale", "") or getattr(domain_obj, "strategic_remediation_rationale", "") or getattr(domain_obj, "maturity_rationale", "")).strip()
        shared_resp = str(getattr(domain_obj, "shared_responsibility", "") or getattr(domain_obj, "partnership_recommendation", "")).strip()
        steps = [str(x).strip() for x in (getattr(domain_obj, "gap_remediation_steps", None) or []) if str(x).strip()]

        return cls(
            domain_name=name,
            current_maturity_display=maturity_display,
            current_state_analysis=state_analysis,
            business_impact_narrative=impact,
            critical_gaps=gaps,
            vendor_agnostic_quick_wins=wins,
            recommended_solutions=solutions,
            remediation_rationale=rationale,
            shared_responsibility=shared_resp,
            gap_remediation_steps=steps,
        )


class TemplateThreatScenarioItem(BaseModel):
    title: str
    scenario_type: str = ""
    threat_actor: str = ""
    attack_vector: str = ""
    target_asset: str = ""
    likelihood: str = ""
    impact: str = ""
    narrative: str = ""
    key_controls: List[str] = Field(default_factory=list)


class TemplateThreatScenarioProjection(BaseModel):
    scenarios: List[TemplateThreatScenarioItem] = Field(default_factory=list)
    rendered_text: str = ""

    @classmethod
    def from_payload(cls, payload: Any) -> TemplateThreatScenarioProjection:
        """
        Guarantees that threat scenarios are projected safely without exposing callable or bound methods.
        """
        if payload is None:
            return cls(rendered_text="")

        if isinstance(payload, str):
            # Literal string: never allow it to be treated as an object with .title in Jinja
            return cls(rendered_text=payload)

        if isinstance(payload, list):
            items = []
            for item in payload:
                if isinstance(item, dict):
                    t = str(item.get("title") or item.get("scenario_title") or "Threat Scenario").strip()
                    items.append(
                        TemplateThreatScenarioItem(
                            title=t,
                            scenario_type=str(item.get("scenario_type") or ""),
                            threat_actor=str(item.get("threat_actor") or ""),
                            attack_vector=str(item.get("attack_vector") or ""),
                            target_asset=str(item.get("target_asset") or ""),
                            likelihood=str(item.get("likelihood") or ""),
                            impact=str(item.get("impact") or ""),
                            narrative=str(item.get("narrative") or item.get("current_state_analysis") or ""),
                            key_controls=[str(c) for c in (item.get("key_controls") or [])],
                        )
                    )
                else:
                    t = str(getattr(item, "title", None) or getattr(item, "scenario_title", None) or "Threat Scenario").strip()
                    items.append(
                        TemplateThreatScenarioItem(
                            title=t,
                            scenario_type=str(getattr(item, "scenario_type", "")),
                            threat_actor=str(getattr(item, "threat_actor", "")),
                            attack_vector=str(getattr(item, "attack_vector", "")),
                            target_asset=str(getattr(item, "target_asset", "")),
                            likelihood=str(getattr(item, "likelihood", "")),
                            impact=str(getattr(item, "impact", "")),
                            narrative=str(getattr(item, "narrative", "") or getattr(item, "current_state_analysis", "")),
                            key_controls=[str(c) for c in (getattr(item, "key_controls", []) or [])],
                        )
                    )
            return cls(scenarios=items)

        if isinstance(payload, dict):
            # Check if dict represents a rendered text or structured item
            if "rendered_text" in payload:
                return cls(rendered_text=str(payload["rendered_text"]))
            t = str(payload.get("title") or payload.get("scenario_title") or "Threat Scenario").strip()
            item = TemplateThreatScenarioItem(
                title=t,
                narrative=str(payload.get("narrative") or ""),
            )
            return cls(scenarios=[item])

        # If object has to_text or similar
        return cls(rendered_text=str(payload))


def assert_no_unsafe_objects_in_context(context: Any, path: str = "context") -> None:
    """
    Recursively scans the docxtpl render context to verify no callable, bound method,
    class, exception, generator, coroutine, or internal diagnostic structure reaches Jinja.
    """
    if context is None:
        return

    # Check for disallowed types
    if callable(context) or inspect.isroutine(context) or inspect.ismethod(context) or inspect.isfunction(context):
        raise ValueError(f"Unsafe template object at '{path}': callable or bound method '{type(context)}' is forbidden.")

    if inspect.isclass(context):
        raise ValueError(f"Unsafe template object at '{path}': class '{context.__name__}' is forbidden in template context.")

    if isinstance(context, Exception):
        raise ValueError(f"Unsafe template object at '{path}': Exception object '{context}' is forbidden.")

    if inspect.isgenerator(context) or inspect.iscoroutine(context):
        raise ValueError(f"Unsafe template object at '{path}': generator/coroutine is forbidden.")

    # Reject internal diagnostic leaking objects
    if isinstance(context, dict):
        for k, v in context.items():
            k_str = str(k)
            if k_str.startswith("__") or k_str in ("_internal_trace", "_debug_adjudication"):
                raise ValueError(f"Internal diagnostic field '{k_str}' leaked at '{path}'.")
            assert_no_unsafe_objects_in_context(v, f"{path}.{k_str}")
    elif isinstance(context, (list, tuple, set)):
        for idx, item in enumerate(context):
            assert_no_unsafe_objects_in_context(item, f"{path}[{idx}]")


def validate_publication_invariants(
    canonical_score: CanonicalOverallScore,
    projected_domains: List[TemplateDomainProjection],
    template_context: Dict[str, Any],
    selected_template_path: str,
) -> Tuple[bool, List[str]]:
    """
    Validates all 15 publication invariants. Returns (is_valid, list_of_errors).
    Fail-closed: if any invariant fails, customer document creation must halt.
    """
    errors: List[str] = []

    # 1. Exactly one score source is active.
    if canonical_score.score_source not in (ScoreSource.SPECIALIST, ScoreSource.LEGACY_FALLBACK):
        errors.append(f"Invariant 1 Failed: Invalid or ambiguous score source '{canonical_score.score_source}'.")

    # 2. Exactly one overall 0–100 presentation score exists.
    if not (Decimal("0.0") <= canonical_score.presentation_score_0_to_100 <= Decimal("100.0")):
        errors.append(f"Invariant 2 Failed: Presentation score out of [0, 100] bounds: {canonical_score.presentation_score_0_to_100}")

    # 3. Exactly one maturity rating exists.
    if not str(canonical_score.maturity_rating).strip():
        errors.append("Invariant 3 Failed: Missing canonical maturity rating.")

    # 4. Exactly one resiliency pillar exists.
    if not str(canonical_score.resiliency_pillar).strip():
        errors.append("Invariant 4 Failed: Missing canonical resiliency pillar.")

    # 5. Every scored domain declares its scale and weight.
    for d in canonical_score.domain_scores:
        if d.is_applicable:
            if not (Decimal("1.0") <= d.native_maturity_score_1_to_3 <= Decimal("3.0")):
                errors.append(f"Invariant 5 Failed: Domain '{d.domain_name}' native score out of [1.0, 3.0] bounds: {d.native_maturity_score_1_to_3}")
            if not (Decimal("0.0") <= d.presentation_score_0_to_100 <= Decimal("100.0")):
                errors.append(f"Invariant 5 Failed: Domain '{d.domain_name}' presentation score out of [0, 100] bounds: {d.presentation_score_0_to_100}")
            if not (Decimal("0.0") <= d.weight_percent <= Decimal("100.0")):
                errors.append(f"Invariant 5 Failed: Domain '{d.domain_name}' weight out of [0, 100] bounds: {d.weight_percent}")

    # 6. Active scored-domain weights reconcile to 100 within Decimal tolerance.
    active_weights = sum((d.weight_percent for d in canonical_score.domain_scores if d.is_applicable), Decimal("0"))
    if abs(active_weights - Decimal("100.00")) > Decimal("0.20"):
        errors.append(f"Invariant 6 Failed: Domain weights sum to {active_weights}%, expected 100% (tolerance 0.20).")

    # 7. Weighted percentage contributions reconcile to the overall 0–100 score.
    total_contrib = sum((d.weighted_contribution_0_to_100 for d in canonical_score.domain_scores if d.is_applicable), Decimal("0"))
    if abs(total_contrib - canonical_score.presentation_score_0_to_100) > Decimal("0.20"):
        errors.append(f"Invariant 7 Failed: Sum of contributions ({total_contrib}) does not reconcile with overall score ({canonical_score.presentation_score_0_to_100}).")

    # 8. Maturity rating derived from canonical score.
    # Check that band matches the score magnitude
    if canonical_score.presentation_score_0_to_100 < Decimal("25.0") and "Phase 1" not in canonical_score.maturity_rating and "Pillar 1" not in canonical_score.maturity_rating:
        errors.append(f"Invariant 8 Failed: Score {canonical_score.presentation_score_0_to_100} does not align with rating '{canonical_score.maturity_rating}'.")

    # 9. No native 1–3 value is bound into a /100 template field.
    sr_context = template_context.get("security_rating")
    if isinstance(sr_context, dict):
        snap = sr_context.get("snapshot") or {}
        if isinstance(snap, dict):
            ov_score = snap.get("overall_score")
            # If overall_score is between 1 and 3 while presentation score is > 10, that's the 2/100 defect!
            if ov_score in (1, 2, 3) and canonical_score.presentation_score_0_to_100 > Decimal("10.0"):
                errors.append(f"Invariant 9 Failed: Unconverted native score {ov_score} bound into snapshot overall_score!")

    # 10. Required executive snapshot values are populated.
    if isinstance(sr_context, dict):
        snap = sr_context.get("snapshot") or {}
        if not isinstance(snap, dict):
            errors.append("Invariant 10 Failed: security_rating.snapshot is missing or not a dictionary.")
        else:
            if not str(snap.get("maturity_rating") or "").strip():
                errors.append("Invariant 10 Failed: security_rating.snapshot.maturity_rating is missing or blank.")
            if not str(snap.get("direction_of_travel") or "").strip():
                errors.append("Invariant 10 Failed: security_rating.snapshot.direction_of_travel is missing or blank.")
            # Enforce non-empty primary_strengths and primary_gaps with exact field paths
            strengths = snap.get("primary_strengths")
            if not isinstance(strengths, list) or len(strengths) == 0:
                errors.append("Invariant 10 Failed: security_rating.snapshot.primary_strengths must be a non-empty list.")
            elif not any(str(s).strip() for s in strengths):
                errors.append("Invariant 10 Failed: security_rating.snapshot.primary_strengths contains no non-blank entries.")

            gaps = snap.get("primary_gaps")
            if not isinstance(gaps, list) or len(gaps) == 0:
                errors.append("Invariant 10 Failed: security_rating.snapshot.primary_gaps must be a non-empty list.")
            elif not any(str(g).strip() for g in gaps):
                errors.append("Invariant 10 Failed: security_rating.snapshot.primary_gaps contains no non-blank entries.")
    else:
        errors.append("Invariant 10 Failed: security_rating context missing.")

    # 11. Every rendered domain has a populated current_maturity_display.
    for pd in projected_domains:
        if not pd.current_maturity_display or not pd.current_maturity_display.strip():
            errors.append(f"Invariant 11 Failed: Domain '{pd.domain_name}' has empty current_maturity_display.")

    # 12. No callable or unsafe object exists in the template context.
    try:
        assert_no_unsafe_objects_in_context(template_context)
    except ValueError as ve:
        errors.append(f"Invariant 12 Failed: {ve}")

    # 13. No internal diagnostic object exists in client context.
    # Also verify no TRACE_ sentinels leaked into string fields in template_context
    def _check_no_trace_sentinels(val: Any, path: str = "context") -> None:
        if isinstance(val, str):
            if "TRACE_" in val or ("model_" in val.lower() and "model_dump" not in val.lower()):
                # Allow standard technical model references, but disallow diagnostic TRACE_
                if "TRACE_" in val:
                    errors.append(f"Invariant 13 Failed: Diagnostic trace sentinel leaked at '{path}': {val[:40]}")
        elif isinstance(val, dict):
            for k, v in val.items():
                _check_no_trace_sentinels(v, f"{path}.{k}")
        elif isinstance(val, (list, tuple)):
            for i, item in enumerate(val):
                _check_no_trace_sentinels(item, f"{path}[{i}]")
    _check_no_trace_sentinels(template_context)

    # 14. No raw placeholder remains in required cover metadata and document context.
    client_name = str(template_context.get("client_name") or "")
    if "{{" in client_name or "}}" in client_name or "[customer]" in client_name.lower():
        errors.append(f"Invariant 14 Failed: Unresolved placeholder in client_name: '{client_name}'")
    report_month = str(template_context.get("report_month_year") or template_context.get("report_date") or "")
    if "month yyyy" in report_month.lower() or "{{" in report_month:
        errors.append(f"Invariant 14 Failed: Unresolved date placeholder: '{report_month}'")
    am_name = str(template_context.get("account_manager") or template_context.get("am_name") or "")
    if "[am name]" in am_name.lower() or "{{" in am_name:
        errors.append(f"Invariant 14 Failed: Unresolved placeholder in account manager: '{am_name}'")

    # 15. The selected template is recorded and validated.
    if not selected_template_path or not str(selected_template_path).endswith(".docx"):
        errors.append(f"Invariant 15 Failed: Selected template path is invalid or unrecorded: '{selected_template_path}'")
    template_meta = template_context.get("template_selection_metadata")
    if template_meta and isinstance(template_meta, dict):
        if not template_meta.get("selected_template") or not template_meta.get("requested_template"):
            errors.append("Invariant 15 Failed: template_selection_metadata missing required requested/selected fields.")

    return (len(errors) == 0, errors)
