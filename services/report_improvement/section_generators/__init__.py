from __future__ import annotations

"""
Specialist Section Generators Package

Exports shared models and deterministic generators implemented in this package.
"""

# Shared typed models
from . import models as _models  # noqa: F401
from .models import (  # explicit re-exports
    SpecialistSectionInput,
    GeneratedClaim,
    SectionGenerationMetadata,
    DomainScoreInput,
    DomainScoreResult,
    SecurityRatingOutput,
    AttackScenarioOutput,
    FrameworkRequirement,
    FrameworkAlignmentRow,
    ComplianceAlignmentOutput,
    CostDriver,
    ApprovedFinancialModel,
    CostOfInactionOutput,
    DomainEvidence,
    DomainAssessmentOutput,
    CrossSectionNarrativeMap,
    SectionExemplar,
)

# Evidence selector
from .evidence_selector import select_section_evidence  # noqa: F401

# Deterministic generators (as they are added)
try:
    from .security_rating import calculate_security_rating  # noqa: F401
except Exception:  # pragma: no cover
    calculate_security_rating = None  # type: ignore

try:
    from .cost_of_inaction import generate_cost_of_inaction  # noqa: F401
except Exception:  # pragma: no cover
    generate_cost_of_inaction = None  # type: ignore

try:
    from .executive_summary import generate_executive_summary  # noqa: F401
except Exception:  # pragma: no cover
    generate_executive_summary = None  # type: ignore

try:
    from .domain_assessments import generate_domain_assessment  # noqa: F401
except Exception:  # pragma: no cover
    generate_domain_assessment = None  # type: ignore

try:
    from .attack_scenario import generate_attack_scenario  # noqa: F401
except Exception:  # pragma: no cover
    generate_attack_scenario = None  # type: ignore

try:
    from .compliance_alignment import generate_compliance_alignment  # noqa: F401
except Exception:  # pragma: no cover
    generate_compliance_alignment = None  # type: ignore
