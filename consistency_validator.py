from __future__ import annotations
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from evidence_extraction import AssessmentEvidence, TranscriptInsight

class ConsistencyIssue(BaseModel):
    category: str = Field(description="Issue category, e.g., 'Score Validation', 'Environment', 'Roadmap', 'Compliance', 'Commentary', 'Inheritance'.")
    message: str = Field(description="Human-readable description.")
    affected_sections: List[str] = Field(default_factory=list, min_items=0, max_items=10, description="Sections implicated.")
    severity: str = Field(description="One of: 'Info', 'Warning', 'Error'.")

def validate_all(
    updated_report: Dict[str, Any],
    evidence: AssessmentEvidence,
    insights: List[TranscriptInsight]
) -> List[ConsistencyIssue]:
    """
    Warning-only consistency checks (non-blocking).
    """
    issues: List[ConsistencyIssue] = []

    try:
        # 1) Score vs Findings (very conservative heuristic)
        pillar = str(updated_report.get("resiliency_matrix_mapping", "") or "")
        rating = None
        try:
            sr = updated_report.get("security_rating") or {}
            if isinstance(sr, dict):
                rating = sr.get("maturity_rating")
        except Exception:
            rating = None
        if "Pillar 1" in pillar and isinstance(rating, str) and any(w in rating for w in ("Managed", "Optimised", "Optimized", "Established")):
            issues.append(ConsistencyIssue(
                category="Score Validation",
                message="Pillar mapping suggests Pillar 1, but maturity rating appears higher. Review for optimism.",
                affected_sections=["resiliency_matrix_mapping", "security_rating"],
                severity="Warning"
            ))
    except Exception:
        pass

    try:
        # 2) Compliance vs Obligations: Standards recommended not present in obligations
        comp = updated_report.get("compliance_alignment") or []
        obligations = set([str(x).strip() for x in (evidence.compliance_requirements or []) if str(x).strip()])
        unknowns = []
        if isinstance(comp, list) and obligations:
            for entry in comp:
                try:
                    std = entry.get("standard")
                    if isinstance(std, str) and std.strip() and std.strip() not in obligations:
                        unknowns.append(std.strip())
                except Exception:
                    continue
        if unknowns:
            issues.append(ConsistencyIssue(
                category="Compliance",
                message=f"Compliance standards in report not found in stated obligations: {', '.join(sorted(set(unknowns)))}.",
                affected_sections=["compliance_alignment"],
                severity="Warning"
            ))
    except Exception:
        pass

    try:
        # 3) Environment inheritance — Crown Jewels naming consistency
        cj_report = str(updated_report.get("critical_infra", "") or "").strip()
        cj_evidence = ""
        try:
            cj_evidence = "; ".join([str(x).strip() for x in (evidence.crown_jewels or []) if str(x).strip()])
        except Exception:
            cj_evidence = ""
        if cj_report and cj_evidence and cj_report.split(";")[0].strip() not in cj_evidence:
            issues.append(ConsistencyIssue(
                category="Inheritance",
                message="Crown Jewels appear inconsistent between environment overview and evidence.",
                affected_sections=["environment", "critical_infra"],
                severity="Info"
            ))
    except Exception:
        pass

    try:
        # 4) Roadmap vs Findings: ensure roadmap references key gaps
        phases = updated_report.get("phased_roadmap") or []
        gaps = [str(x).strip() for x in (getattr(evidence, "confirmed_gaps", []) or []) if str(x).strip()]
        missing = []
        if isinstance(phases, list) and gaps:
            for g in gaps[:5]:  # bound work
                found = False
                for ph in phases:
                    try:
                        title = str(ph.get("phase_title", "") or "")
                        obj = str(ph.get("primary_objective", "") or "")
                        mils = ph.get("milestones", []) or []
                        hay = " ".join([title, obj] + [str(m) for m in mils]).lower()
                        if g.lower() in hay:
                            found = True
                            break
                    except Exception:
                        continue
                if not found:
                    missing.append(g)
        if missing:
            issues.append(ConsistencyIssue(
                category="Roadmap",
                message=f"Roadmap may not explicitly address these consultation-confirmed gaps: {', '.join(missing[:5])}.",
                affected_sections=["phased_roadmap", "main_findings"],
                severity="Warning"
            ))
    except Exception:
        pass

    try:
        # 5) Environment vs Recommendations: flag 'replace' suggestions targeting existing vendors
        vendors = []
        try:
            vendors.extend([str(x).strip() for x in (getattr(evidence, "existing_security_services", []) or []) if str(x).strip()])
        except Exception:
            pass
        try:
            vendors.extend([str(x).strip() for x in (getattr(evidence, "security_products", []) or []) if str(x).strip()])
        except Exception:
            pass
        vendors = [v for v in vendors if v]
        conflicts = []
        if vendors:
            # executive_summary_action_blocks remediation_actions
            try:
                esab = updated_report.get("executive_summary_action_blocks") or []
                for blk in esab:
                    try:
                        acts = blk.get("remediation_actions") or []
                        for a in acts:
                            s = str(a).lower()
                            if "replace" in s:
                                for v in vendors:
                                    if v and v.lower() in s:
                                        conflicts.append(v)
                    except Exception:
                        continue
            except Exception:
                pass
            # compliance fill plans (recommended_actions)
            try:
                comp = updated_report.get("compliance_alignment") or []
                for entry in comp:
                    try:
                        plans = entry.get("fill_plan") or []
                        for p in plans:
                            for act in (p.get("recommended_actions") or []):
                                s = str(act).lower()
                                if "replace" in s:
                                    for v in vendors:
                                        if v and v.lower() in s:
                                            conflicts.append(v)
                    except Exception:
                        continue
            except Exception:
                pass
        if conflicts:
            issues.append(ConsistencyIssue(
                category="Environment",
                message=f"Recommendations appear to replace existing vendor(s) without explicit justification: {', '.join(sorted(set(conflicts)))}.",
                affected_sections=["executive_summary_action_blocks", "compliance_alignment"],
                severity="Warning"
            ))
    except Exception:
        pass

    try:
        # 6) Executive commentary vs Evidence (heuristic)
        exec_sum = str(updated_report.get("executive_summary", "") or "")
        claims = exec_sum.lower()
        existing_controls = [str(x).lower().strip() for x in (getattr(evidence, "existing_controls", []) or []) if str(x).strip()]
        hints = []
        if "universal mfa" in claims or "mfa enforced for all" in claims:
            if not any("mfa" in c for c in existing_controls):
                hints.append("Universal MFA claim not corroborated by evidence of existing controls")
        if "immutable backup" in claims or "air-gapped backup" in claims:
            if not any("immutable" in c or "air-gapped" in c for c in existing_controls):
                hints.append("Immutable backup claim not corroborated by evidence of existing controls")
        if hints:
            issues.append(ConsistencyIssue(
                category="Commentary",
                message="; ".join(hints),
                affected_sections=["executive_summary"],
                severity="Warning"
            ))
    except Exception:
        pass

    return issues
