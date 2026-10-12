from __future__ import annotations
from typing import Tuple, List, Dict, Any
from section_improvers.shared_rules import ReportImprovementRules, ReviewerChange
from evidence_extraction import AssessmentEvidence, TranscriptInsight

# Import improver stubs
from .executive_summary import improve_executive_summary
from .security_rating import improve_security_rating
from .environment import improve_environment_overview
from .attack_scenario import improve_attack_scenario
from .roadmap import improve_roadmap
from .compliance import improve_compliance
from .main_findings import improve_main_findings

def improve_all_sections(
    report_dict: Dict[str, Any],
    evidence: AssessmentEvidence,
    insights: List[TranscriptInsight],
    adjudication,
    rules: ReportImprovementRules
) -> Tuple[Dict[str, Any], List[ReviewerChange]]:
    """
    Run all section improvers independently, returning a new report dict and aggregated change log.
    Note: By default, stubs preserve content (no-op) until specific logic is implemented.
    """
    changes: List[ReviewerChange] = []
    out = dict(report_dict or {})

    # Executive Summary
    new_exec, chg = improve_executive_summary(out.get("executive_summary"), evidence, adjudication, insights, rules)
    if chg:
        out["executive_summary"] = new_exec
        changes.extend(chg)

    # Security Rating (if present)
    if "security_rating" in out and out.get("security_rating") is not None:
        new_rating, chg2 = improve_security_rating(out.get("security_rating"), evidence, adjudication, insights, rules)
        if chg2:
            out["security_rating"] = new_rating
            changes.extend(chg2)

    # Environment Overview (source of truth) — may set scalar fields
    env_src, chg3 = improve_environment_overview(out, evidence, adjudication, insights, rules)
    if chg3:
        out.update(env_src)
        changes.extend(chg3)

    # Main Findings
    new_main, chg4 = improve_main_findings(out.get("main_findings"), evidence, adjudication, insights, rules)
    if chg4:
        out["main_findings"] = new_main
        changes.extend(chg4)

    # Attack Scenario / Threat Intelligence Context
    new_attack, chg5 = improve_attack_scenario(out.get("threat_scenarios") or out.get("threat_intelligence_context"), evidence, adjudication, insights, rules)
    if chg5:
        if "threat_scenarios" in out:
            out["threat_scenarios"] = new_attack
        else:
            out["threat_intelligence_context"] = new_attack
        changes.extend(chg5)

    # Compliance
    new_comp, chg6 = improve_compliance(out.get("compliance_alignment"), evidence, adjudication, insights, rules)
    if chg6:
        out["compliance_alignment"] = new_comp
        changes.extend(chg6)

    # Roadmap
    new_roadmap, chg7 = improve_roadmap(out.get("phased_roadmap"), evidence, adjudication, insights, rules)
    if chg7:
        out["phased_roadmap"] = new_roadmap
        changes.extend(chg7)

    return out, changes