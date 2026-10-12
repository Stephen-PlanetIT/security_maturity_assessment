from __future__ import annotations

"""
Cross‑Section Context Builder (Phase 4 scaffolding)

Provides a deterministic builder to create CrossSectionNarrativeMap from a report dict
when structured specialist outputs are not directly available at runtime. This
keeps coherence validation decoupled from UI/export layers and avoids model calls.

Notes:
- Uses conservative heuristics over strings; prefers present specialist outputs if provided.
- Deterministic, side‑effect free; no IO or network.
"""

from typing import Any, Dict, List

from services.report_improvement.section_generators.models import (  # type: ignore
    CrossSectionNarrativeMap,
)


def _extract_list_from_prefixed_line(block: str, prefix: str) -> List[str]:
    """
    Extract a CSV list from a single line starting with a given prefix in a multi‑line block.
    Returns a list of items split by comma, trimmed.
    """
    try:
        for ln in (block or "").splitlines():
            s = ln.strip()
            if s.lower().startswith(prefix.lower()):
                rest = s[len(prefix):].strip()
                return [itm.strip() for itm in rest.split(",") if itm.strip()]
    except Exception:
        pass
    return []


def _extract_exec_overview(block: str) -> str:
    """
    Return the first non‑empty paragraph from the Executive Summary block (business context proxy).
    """
    try:
        paras = [p.strip() for p in (block or "").split("\n\n") if p.strip()]
        return paras[0] if paras else ""
    except Exception:
        return ""


def build_cross_section_map_from_report(report: Dict[str, Any]) -> CrossSectionNarrativeMap:
    """
    Build CrossSectionNarrativeMap using conservative parsing of improved/final report sections.
    This is a placeholder builder for Phase 4 coherence validator and can be expanded to
    support structured specialist outputs when available.
    """
    exec_block = str(report.get("executive_summary", "") or "")
    sr_block = str(report.get("security_rating", "") or "")
    scenario_block = str(report.get("threat_scenarios", "") or "")
    compliance_block = str(report.get("compliance_alignment", "") or "")
    coi_block = str(report.get("cost_of_inaction", "") or "")

    # Executive overview proxy
    overview = _extract_exec_overview(exec_block)

    # Strengths/gaps proxies
    strengths = _extract_list_from_prefixed_line(exec_block, "Key strengths:")
    gaps = _extract_list_from_prefixed_line(exec_block, "Priority gaps:")

    # Approved frameworks proxy: collect lines that look like "NAME — AREA: ..."
    approved_frameworks: List[str] = []
    try:
        for ln in compliance_block.splitlines():
            if " — " in ln:
                name = ln.split(" — ", 1)[0].strip()
                if name:
                    approved_frameworks.append(name)
    except Exception:
        pass
    # Dedupe while preserving order
    seen = set()
    approved_frameworks = [x for x in approved_frameworks if not (x in seen or seen.add(x))]

    # Cost drivers proxy: lines beginning with "- "
    cost_drivers: List[str] = []
    try:
        for ln in coi_block.splitlines():
            s = ln.strip()
            if s.startswith("- "):
                # expect "- Driver: description"
                name = s[2:]
                # Split on ":" to extract name
                if ":" in name:
                    name = name.split(":", 1)[0].strip()
                if name:
                    cost_drivers.append(name)
    except Exception:
        pass

    # Scenario priorities proxy: capture simple MITRE code tokens like Txxxx
    scenario_priorities: List[str] = []
    try:
        import re
        for tok in re.findall(r"\bT\d{4}(?:\.\d{3})?\b", scenario_block):
            scenario_priorities.append(tok)
        # Dedupe
        seen2 = set()
        scenario_priorities = [x for x in scenario_priorities if not (x in seen2 or seen2.add(x))]
    except Exception:
        pass

    return CrossSectionNarrativeMap(
        customer_profile_summary=overview,
        primary_strengths=strengths[:5],
        primary_gaps=gaps[:5],
        critical_findings=gaps[:5],  # proxy from Exec/SR; deterministic placeholder
        approved_recommendations=[],  # populated in a richer Phase 4 integration
        roadmap_priorities=[],  # populated in a richer Phase 4 integration
        approved_frameworks=approved_frameworks[:10],
        cost_drivers=cost_drivers[:10],
        scenario_priorities=scenario_priorities[:8],
    )