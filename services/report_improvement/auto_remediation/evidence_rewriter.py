from __future__ import annotations
from typing import List
from services.report_improvement.evidence_enforcement.models import ValidationIssue, EvidenceEnforcementContext
from services.report_improvement.auto_remediation.models import EGRevisedSection
from .evidence_selector import select_relevant_evidence
from .safe_language import SAFE_UNKNOWN_TO_VALIDATION

# Phase 2 scaffold: strict prompt contract documented; actual LLM call will be added later.
SYSTEM_INSTRUCTION = (
    "You are repairing a rejected cybersecurity maturity report section. Correct only the validation failures supplied. "
    "All factual statements, named entities, control assertions, recommendations, business impacts and scenario details must be supported by the supplied approved evidence. "
    "Unknown does not mean absent. Unvalidated does not mean ineffective. Existing controls must not be recommended as new implementations. "
    "Do not introduce facts from general cybersecurity knowledge. Do not add vendors, products, platforms, business systems, financial figures, CVEs, threat actors, "
    "attack tools, compliance consequences or maturity claims unless included in approved evidence. When evidence is insufficient, use proportionate validation language. "
    "Return a complete replacement section, not commentary about how to edit it."
)

async def rewrite_from_validation_issues(
    section_name: str,
    rejected_content: str,
    issues: List[ValidationIssue],
    context: EvidenceEnforcementContext,
    adjudication,
) -> EGRevisedSection:
    """
    Build a strict prompt with only the rejected section, structured issue list and selected approved evidence.
    Invoke LLMEngine with bounded tokens and parse into EGRevisedSection. Always revalidate upstream.
    """
    import json
    from core import LLMEngine
    from config import get_config, ConfigKey

    evidence = select_relevant_evidence(section_name, issues, adjudication)
    payload = {
        "section_name": section_name,
        "rejected_content": (rejected_content or "")[:6000],
        "issues": [getattr(i, "rule_id", "") for i in (issues or [])],
        "evidence": evidence,
        "safe_language_guidance": SAFE_UNKNOWN_TO_VALIDATION,
    }
    system = SYSTEM_INSTRUCTION
    user_prompt = json.dumps(payload, ensure_ascii=False)

    client = LLMEngine.get_client()
    if client is None:
        return EGRevisedSection(
            section_name=section_name,
            revised_content=rejected_content,
            addressed_rule_ids=[],
            unresolved_rule_ids=[getattr(i, "rule_id", "") for i in (issues or [])],
            evidence_ids_used=[],
            named_entities_used=[],
            recommendations_used=[],
        )

    deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o-mini")

    # Try structured parse path
    data = {}
    try:
        resp = LLMEngine.generate_structured_report(
            client=client,
            deployment=deployment,
            system_persona=system,
            user_prompt=user_prompt,
            response_model=None,  # fallback to text path if structured parse unavailable
        )
        if hasattr(resp, "model_dump"):
            data = resp.model_dump()
        elif isinstance(resp, dict):
            data = resp
        else:
            raise RuntimeError("Structured parse path unavailable")
    except Exception:
        # Fallback: text path expecting JSON object
        text = LLMEngine.generate_text_report(client, deployment, system, user_prompt, temperature=0.0)
        try:
            data = json.loads(text) if isinstance(text, str) else {}
        except Exception:
            data = {}

    # Safe parse into EGRevisedSection with fallbacks
    try:
        return EGRevisedSection(
            section_name=section_name,
            revised_content=str(data.get("revised_content", rejected_content) or ""),
            addressed_rule_ids=list(data.get("addressed_rule_ids", [])),
            unresolved_rule_ids=list(data.get("unresolved_rule_ids", [])),
            evidence_ids_used=list(data.get("evidence_ids_used", [])),
            named_entities_used=list(data.get("named_entities_used", [])),
            recommendations_used=list(data.get("recommendations_used", [])),
        )
    except Exception:
        return EGRevisedSection(
            section_name=section_name,
            revised_content=rejected_content,
            addressed_rule_ids=[],
            unresolved_rule_ids=[getattr(i, "rule_id", "") for i in (issues or [])],
            evidence_ids_used=[],
            named_entities_used=[],
            recommendations_used=[],
        )
