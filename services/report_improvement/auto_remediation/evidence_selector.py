from __future__ import annotations
from typing import Dict, List
from services.report_improvement.evidence_adjudicator import EvidenceAdjudicationResult


def select_relevant_evidence(section_name: str, issues, adjudication: EvidenceAdjudicationResult) -> Dict[str, List[str]]:
    """
    Deterministically select minimal, relevant evidence for the target section:
      - supported_claims (verbatim claim_text)
      - existing_controls (control_name)
      - known_unknowns (statement)
      - contradicted_claims (claim_text)
      - approved_attack_inputs (confirmed lists)
    Returns a dict of lists (strings) suitable for strict prompt inclusion.
    """
    out: Dict[str, List[str]] = {
        "supported_claims": [],
        "existing_controls": [],
        "known_unknowns": [],
        "contradicted": [],
        "confirmed_crown_jewels": [],
        "confirmed_technologies": [],
        "confirmed_attack_paths": [],
        # Phase 2 minimal extensions (placeholders for future enrichment)
        "approved_recommendations": [],
        "approved_entities": [],
    }
    try:
        for c in adjudication.supported_claims or []:
            try:
                out["supported_claims"].append((c.claim_text or "")[:400])
            except Exception:
                continue
    except Exception:
        pass
    try:
        for ec in adjudication.existing_controls or []:
            try:
                out["existing_controls"].append((ec.control_name or "")[:200])
            except Exception:
                continue
    except Exception:
        pass
    try:
        for ku in adjudication.known_unknowns or []:
            try:
                out["known_unknowns"].append((ku.statement or "")[:300])
            except Exception:
                continue
    except Exception:
        pass
    try:
        for cc in adjudication.contradicted_claims or []:
            try:
                out["contradicted"].append((cc.claim_text or "")[:400])
            except Exception:
                continue
    except Exception:
        pass
    try:
        aai = adjudication.approved_attack_inputs
        out["confirmed_crown_jewels"].extend([str(x) for x in (aai.confirmed_crown_jewels or [])])
        out["confirmed_technologies"].extend([str(x) for x in (aai.confirmed_technologies or [])])
        out["confirmed_attack_paths"].extend([str(x) for x in (aai.confirmed_attack_paths or [])])
    except Exception:
        pass
    # Approved recommendations/entities (minimal strings; no transcripts)
    try:
        for r in getattr(adjudication, "approved_recommendations", []) or []:
            out["approved_recommendations"].append(str(getattr(r, "text", r))[:300])
    except Exception:
        pass
    try:
        for ent in getattr(adjudication, "approved_entities", []) or []:
            out["approved_entities"].append(str(getattr(ent, "name", ent))[:200])
    except Exception:
        pass
    return out
