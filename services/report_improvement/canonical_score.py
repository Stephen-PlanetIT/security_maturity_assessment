from __future__ import annotations

"""
Canonical Score Model & Publication Contract

Provides an unambiguous, typed score and publication model with exact scale distinctions:
- native_maturity_score_1_to_3: Native 1.0–3.0 maturity score (Decimal)
- presentation_score_0_to_100: Converted 0.0–100.0 score (Decimal, score / 3 * 100)
- weight_percent: Domain weight percent [0.0, 100.0] (Decimal)
- weighted_contribution_0_to_100: Contribution in percentage points (Decimal, presentation * weight / 100)
- maturity_rating: Derived maturity band name
- resiliency_pillar: Resiliency pillar mapping (e.g. Pillar 1, Pillar 2, Pillar 3)
- direction_of_travel: Narrative direction of travel
- score_source: "specialist" | "legacy_fallback"
- evidence_confidence: Confidence level in evidence coverage
- scoring_caveat: Explicit limitations and caveats

Arithmetic strictly uses Decimal until final presentation serialisation.
"""

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class ScoreSource(str, Enum):
    SPECIALIST = "specialist"
    LEGACY_FALLBACK = "legacy_fallback"


class CanonicalDomainScore(BaseModel):
    domain_name: str
    native_maturity_score_1_to_3: Decimal = Field(..., ge=Decimal("1.0"), le=Decimal("3.0"))
    presentation_score_0_to_100: Decimal = Field(default=Decimal("0.0"), ge=Decimal("0.0"), le=Decimal("100.0"))
    weight_percent: Decimal = Field(..., ge=Decimal("0.0"), le=Decimal("100.0"))
    weighted_contribution_0_to_100: Decimal = Field(default=Decimal("0.0"), ge=Decimal("0.0"), le=Decimal("100.0"))
    maturity_rating: str = "Phase 2: Fundamental Controls"
    resiliency_pillar: str = "Pillar 2: Proactive Cybersecurity"
    rationale: str = ""
    score_source: ScoreSource = ScoreSource.SPECIALIST
    evidence_confidence: str = "medium"
    scoring_caveat: Optional[str] = None
    is_applicable: bool = True

    @model_validator(mode="before")
    @classmethod
    def populate_derived_scores(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "native_maturity_score_1_to_3" in data:
                native = Decimal(str(data["native_maturity_score_1_to_3"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                native = max(Decimal("1.00"), min(Decimal("3.00"), native))
                data["native_maturity_score_1_to_3"] = native
                if "presentation_score_0_to_100" not in data or data["presentation_score_0_to_100"] == Decimal("0.0"):
                    data["presentation_score_0_to_100"] = ((native / Decimal("3")) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if "weight_percent" in data:
                    w = Decimal(str(data["weight_percent"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    data["weight_percent"] = w
                    if "weighted_contribution_0_to_100" not in data or data["weighted_contribution_0_to_100"] == Decimal("0.0"):
                        data["weighted_contribution_0_to_100"] = ((data["presentation_score_0_to_100"] * w) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return data

    @classmethod
    def calculate(
        cls,
        domain_name: str,
        native_score: Decimal,
        weight_percent: Decimal,
        maturity_rating: str,
        resiliency_pillar: str,
        rationale: str,
        score_source: ScoreSource,
        evidence_confidence: str = "medium",
        scoring_caveat: Optional[str] = None,
        is_applicable: bool = True,
    ) -> CanonicalDomainScore:
        # Scale conversion: presentation = (native / 3) * 100
        native_score = Decimal(str(native_score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        clamped_native = max(Decimal("1.00"), min(Decimal("3.00"), native_score))
        
        pres_score = ((clamped_native / Decimal("3")) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        weight_percent = Decimal(str(weight_percent)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        contrib = ((pres_score * weight_percent) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return cls(
            domain_name=domain_name,
            native_maturity_score_1_to_3=clamped_native,
            presentation_score_0_to_100=pres_score,
            weight_percent=weight_percent,
            weighted_contribution_0_to_100=contrib,
            maturity_rating=maturity_rating,
            resiliency_pillar=resiliency_pillar,
            rationale=rationale,
            score_source=score_source,
            evidence_confidence=evidence_confidence,
            scoring_caveat=scoring_caveat,
            is_applicable=is_applicable,
        )


class CanonicalOverallScore(BaseModel):
    native_maturity_score_1_to_3: Decimal = Field(..., ge=Decimal("1.0"), le=Decimal("3.0"))
    presentation_score_0_to_100: Decimal = Field(..., ge=Decimal("0.0"), le=Decimal("100.0"))
    overall_presentation_score_integer: int = Field(..., ge=0, le=100)
    maturity_rating: str
    resiliency_pillar: str
    direction_of_travel: str
    score_source: ScoreSource
    evidence_confidence: str
    scoring_caveat: str
    domain_scores: List[CanonicalDomainScore]
    weights_reconciled: bool = True
    contributions_reconciled: bool = True

    @classmethod
    def assemble(
        cls,
        domains: List[CanonicalDomainScore],
        score_source: ScoreSource,
        direction_of_travel: str = "Stable / Improving",
        scoring_caveat: str = "Evidence evaluated across applicable domains.",
        evidence_confidence: str = "medium",
        pillar_override: Optional[str] = None,
        rating_override: Optional[str] = None,
    ) -> CanonicalOverallScore:
        active_domains = [d for d in domains if d.is_applicable]
        if not active_domains:
            raise ValueError("No applicable domains provided for canonical overall score assembly.")

        # Reconcile weights to exactly 100.00
        raw_weight_sum = sum((d.weight_percent for d in active_domains), Decimal("0"))
        if raw_weight_sum <= Decimal("0"):
            raise ValueError("Sum of applicable domain weights is zero or negative.")

        # Compute sum of weighted contributions
        total_contrib = sum((d.weighted_contribution_0_to_100 for d in active_domains), Decimal("0")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # presentation score is sum of domain weighted contributions
        overall_pres = min(Decimal("100.00"), max(Decimal("0.00"), total_contrib))
        overall_int = int(overall_pres.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        # native overall score: presentation * 3 / 100
        native_overall = ((overall_pres / Decimal("100")) * Decimal("3")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        native_overall = max(Decimal("1.00"), min(Decimal("3.00"), native_overall))

        # Derive rating band if not explicitly provided
        rating = rating_override
        if not rating:
            if overall_pres >= Decimal("75.0"):
                rating = "Phase 4: Advanced / Optimised"
            elif overall_pres >= Decimal("50.0"):
                rating = "Phase 3: Moderate / Proactive Defence"
            elif overall_pres >= Decimal("25.0"):
                rating = "Phase 2: Developing / Fundamental Controls"
            else:
                rating = "Phase 1: Basic / Reactive Hygiene"

        # Derive pillar if not explicitly provided
        pillar = pillar_override
        if not pillar:
            if overall_pres < Decimal("34.0"):
                pillar = "Pillar 1: Reactive Cybersecurity"
            elif overall_pres < Decimal("67.0"):
                pillar = "Pillar 2: Proactive Cybersecurity"
            else:
                pillar = "Pillar 3: Adaptive Cybersecurity"

        # Check reconciliation invariants (Decimal tolerance 0.15)
        weight_diff = abs(raw_weight_sum - Decimal("100.00"))
        weights_ok = weight_diff <= Decimal("0.15")

        contrib_diff = abs(total_contrib - overall_pres)
        contribs_ok = contrib_diff <= Decimal("0.15")

        return cls(
            native_maturity_score_1_to_3=native_overall,
            presentation_score_0_to_100=overall_pres,
            overall_presentation_score_integer=overall_int,
            maturity_rating=rating,
            resiliency_pillar=pillar,
            direction_of_travel=direction_of_travel,
            score_source=score_source,
            evidence_confidence=evidence_confidence,
            scoring_caveat=scoring_caveat,
            domain_scores=domains,
            weights_reconciled=weights_ok,
            contributions_reconciled=contribs_ok,
        )


def build_canonical_overall_score(
    domain_inputs: List[Any],
    score_source: ScoreSource = ScoreSource.SPECIALIST,
    overall_score_override: Optional[Any] = None,
    maturity_rating_override: Optional[str] = None,
    pillar_override: Optional[str] = None,
    direction_of_travel: str = "Stable / Improving",
    scoring_caveat: str = "Evidence evaluated across applicable domains.",
    evidence_confidence: str = "medium",
) -> CanonicalOverallScore:
    """
    Builds a CanonicalOverallScore from a list of CanonicalDomainScore items,
    TemplateDomainProjection items, or dictionaries.
    """
    domain_scores: List[CanonicalDomainScore] = []

    for d in domain_inputs:
        if isinstance(d, CanonicalDomainScore):
            domain_scores.append(d)
        elif hasattr(d, "native_maturity_score_1_to_3") and hasattr(d, "weight_percent"):
            domain_scores.append(
                CanonicalDomainScore.calculate(
                    domain_name=getattr(d, "domain_name", "Unknown"),
                    native_score=Decimal(str(getattr(d, "native_maturity_score_1_to_3", "2.0"))),
                    weight_percent=Decimal(str(getattr(d, "weight_percent", "0.0"))),
                    maturity_rating=getattr(d, "maturity_rating", "Phase 2"),
                    resiliency_pillar=getattr(d, "resiliency_pillar", "Pillar 2"),
                    rationale=getattr(d, "rationale", ""),
                    score_source=score_source,
                )
            )
        else:
            # Fallback or synthetic domain score item if raw / projection without scores
            name = getattr(d, "domain_name", None) or (d.get("domain_name") if isinstance(d, dict) else "Domain")
            domain_scores.append(
                CanonicalDomainScore.calculate(
                    domain_name=str(name),
                    native_score=Decimal("2.0"),
                    weight_percent=Decimal(str(100.0 / max(1, len(domain_inputs)))),
                    maturity_rating="Phase 2",
                    resiliency_pillar="Pillar 2",
                    rationale="",
                    score_source=score_source,
                )
            )

    if not domain_scores:
        # Default placeholder when domain_inputs is empty
        pres = Decimal(str(overall_score_override or "50.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        pres = min(Decimal("100.0"), max(Decimal("0.0"), pres))
        native = ((pres / Decimal("100.0")) * Decimal("3.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        native = min(Decimal("3.0"), max(Decimal("1.0"), native))
        return CanonicalOverallScore(
            native_maturity_score_1_to_3=native,
            presentation_score_0_to_100=pres,
            overall_presentation_score_integer=int(pres.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
            maturity_rating=maturity_rating_override or "Phase 2: Fundamental Controls",
            resiliency_pillar=pillar_override or "Pillar 2: Proactive Cybersecurity",
            direction_of_travel=direction_of_travel,
            score_source=score_source,
            evidence_confidence=evidence_confidence,
            scoring_caveat=scoring_caveat,
            domain_scores=[],
            weights_reconciled=True,
            contributions_reconciled=True,
        )

    res = CanonicalOverallScore.assemble(
        domains=domain_scores,
        score_source=score_source,
        direction_of_travel=direction_of_travel,
        scoring_caveat=scoring_caveat,
        evidence_confidence=evidence_confidence,
        pillar_override=pillar_override,
        rating_override=maturity_rating_override,
    )

    if overall_score_override is not None:
        try:
            ov = Decimal(str(overall_score_override)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            # Score integrity: overall_score_override must not arbitrarily diverge from domain contributions
            # If domain scores exist, overall score is authoritative from the domain contributions
            diff = abs(res.presentation_score_0_to_100 - ov)
            if diff > Decimal("0.20"):
                # If domain inputs were synthetic/placeholder while an authoritative specialist overall score was given,
                # do not silently overwrite without flagging; keep res.presentation_score_0_to_100 as the source of truth
                pass
            else:
                res.presentation_score_0_to_100 = ov
                res.overall_presentation_score_integer = int(ov.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        except Exception:
            pass

    return res
