"""
quality_pipeline.py — Quality & Humanisation Pipeline

Stages implemented (configurable via env using config.get_config):
  - Phrase Frequency Analysis & Repetition Rewriter
  - Overclaim Detector & Softener
  - Vendor Phrase Governor (commercial balance)
  - AI Rhythm Detector (repeated openings / transitions)
  - Quality Scoring (human_authenticity, repetition, commercial_balance, executive_readability, technical_accuracy placeholder)

Thresholds (env with sensible defaults):
  QUALITY_GATE_ENABLED = '1' | '0' (default '1')
  QUALITY_MIN_HUMAN_AUTHENTICITY = 8
  QUALITY_MIN_REPETITION = 8
  QUALITY_MIN_COMMERCIAL_BALANCE = 8
  QUALITY_MIN_EXEC_READABILITY = 8
"""

import re
from typing import Dict, List, Tuple, Any
from config import get_config

# --- Phrase catalogue (expandable) ---
PHRASES = [
    "strong foundation",
    "solid foundation",
    "cross-domain visibility",
    "future-state",
    "further maturity",
    "Planet IT can support",
    "where selected",
    "where appropriate",
    "This provides",
    "Further maturity",
]

REPETITION_ALTERNATIVES = {
    "strong foundation": ["useful baseline", "established control set", "credible starting position", "existing arrangements"],
    "solid foundation": ["solid baseline", "reliable groundwork", "credible starting position", "established controls"],
    "cross-domain visibility": ["cross‑stack telemetry", "estate‑wide visibility", "end‑to‑end observability", "broader situational awareness"],
    "further maturity": ["next stage of improvement", "continued progression", "subsequent optimisation", "incremental advancement"],
    "This provides": ["This yields", "This enables", "This affords", "In practice, this delivers"],
    "Planet IT can support": ["Planet IT can assist", "Planet IT can facilitate", "Planet IT can advise", "Support can be provided via Planet IT"],
    "where selected": ["if implemented", "when in place", "where deployed", "once adopted"],
    "where appropriate": ["where justified", "as suitable", "when proportionate", "where it makes sense"],
}

OVERCLAIM_PATTERNS = {
    "prevention": re.compile(r"\b(prevents?|stops?|eliminates?|ensures?|guarantees?|neutralises?)\b", re.IGNORECASE),
    "absolute": re.compile(r"\b(fully secure|fully protected|cannot be compromised|guaranteed security)\b", re.IGNORECASE),
}

OVERCLAIM_REWRITES = {
    "prevents": "reduces likelihood of",
    "stops": "disrupts",
    "eliminates": "reduces exposure to",
    "ensures": "supports",
    "guarantees": "cannot guarantee; it aims to",
    "neutralises": "contains and mitigates",
    "fully secure": "substantially hardened",
    "fully protected": "well protected",
    "cannot be compromised": "is significantly harder to compromise",
    "guaranteed security": "risk reduction objectives",
}

VENDOR_PHRASES = [
    "Planet IT can support",
    "Planet IT can assist",
    "Planet IT can facilitate",
]

def quality_gate_enabled() -> bool:
    val = get_config("QUALITY_GATE_ENABLED", "1")
    return str(val).strip() == "1"

def get_quality_thresholds() -> Dict[str, int]:
    return {
        "human_authenticity": int(get_config("QUALITY_MIN_HUMAN_AUTHENTICITY", 8)),
        "repetition": int(get_config("QUALITY_MIN_REPETITION", 8)),
        "commercial_balance": int(get_config("QUALITY_MIN_COMMERCIAL_BALANCE", 8)),
        "executive_readability": int(get_config("QUALITY_MIN_EXEC_READABILITY", 8)),
    }

# --- Stage toggles (env-backed) ---
def stage_enabled(key: str, default: str = "1") -> bool:
    return str(get_config(key, default)).strip() == "1"

# -------- Feature 1: Phrase Frequency Analysis --------
def analyse_phrase_frequency(text: str) -> Dict[str, Dict[str, Any]]:
    """Return a frequency map { phrase: {count:int, severity:str} }.
    Severity rules: >4 in document => high; >2 in any notional section (paragraph) => medium/high.
    """
    if not isinstance(text, str) or not text:
        return {}
    lower = text.lower()
    para_splits = [p.strip() for p in re.split(r"\n{2,}", lower) if p.strip()]
    result: Dict[str, Dict[str, Any]] = {}
    for phrase in PHRASES:
        p = phrase.lower()
        count = len(re.findall(re.escape(p), lower))
        per_section_exceeds = any(para.count(p) > 2 for para in para_splits)
        severity = "low"
        if count > 4 or per_section_exceeds and count > 3:
            severity = "high"
        elif count > 2 or per_section_exceeds:
            severity = "medium"
        if count > 0:
            result[phrase] = {"count": count, "severity": severity}
    return result

# -------- Feature 2: Repetition Rewriter --------
def _cycle_alternatives(phrase: str) -> List[str]:
    alts = REPETITION_ALTERNATIVES.get(phrase, [])
    if not alts:
        return []
    return alts

def rewrite_repetitions(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    # Work paragraph by paragraph to enforce per-section limits
    paragraphs = re.split(r"(\n{2,})", text)
    out: List[str] = []
    for i in range(0, len(paragraphs), 2):
        para = paragraphs[i]
        sep = paragraphs[i+1] if i+1 < len(paragraphs) else ""
        working = para
        for phrase in PHRASES:
            matches = list(re.finditer(re.escape(phrase), working, flags=re.IGNORECASE))
            if not matches:
                continue
            limit = 2  # per section
            if len(matches) > limit:
                alts = _cycle_alternatives(phrase)
                alt_idx = 0
                # Replace occurrences beyond the limit
                def repl(m):
                    nonlocal alt_idx
                    if m is None:
                        return ""
                    alt_idx += 1
                    if alt_idx <= limit:
                        return m.group(0)
                    if alts:
                        return alts[(alt_idx - limit - 1) % len(alts)]
                    return m.group(0)
                working = re.sub(re.escape(phrase), repl, working, flags=re.IGNORECASE)
        out.append(working)
        out.append(sep)
    return "".join(out)

# -------- Feature 3: Overclaim Detector --------
def detect_overclaims(text: str) -> Tuple[str, Dict[str, int]]:
    if not isinstance(text, str) or not text:
        return text, {}
    flags = {"prevention": 0, "absolute": 0}
    # Token-level replacement preserving case where possible
    def softener(match: re.Match) -> str:
        token = match.group(0)
        key = token.lower()
        flags["prevention"] += 1
        return OVERCLAIM_REWRITES.get(key, OVERCLAIM_REWRITES.get(key.rstrip('s'), token))

    def absolute_softener(match: re.Match) -> str:
        token = match.group(0)
        flags["absolute"] += 1
        return OVERCLAIM_REWRITES.get(token.lower(), token)

    text2 = OVERCLAIM_PATTERNS["prevention"].sub(softener, text)
    text3 = OVERCLAIM_PATTERNS["absolute"].sub(absolute_softener, text2)
    return text3, flags

# -------- Feature 6: Commercial Bias Governor --------
def govern_vendor_bias(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    # Limit to max 1 occurrence per paragraph/section
    paragraphs = re.split(r"(\n{2,})", text)
    out: List[str] = []
    for i in range(0, len(paragraphs), 2):
        para = paragraphs[i]
        sep = paragraphs[i+1] if i+1 < len(paragraphs) else ""
        for v in VENDOR_PHRASES:
            # Keep first occurrence, vary/remove the rest
            occurrences = list(re.finditer(re.escape(v), para))
            if len(occurrences) > 1:
                # Replace extras with variants cycling
                alts = [x for x in REPETITION_ALTERNATIVES.get("Planet IT can support", []) if x != v]
                idx = 0
                def repl(m):
                    nonlocal idx
                    idx += 1
                    if idx == 1:
                        return m.group(0)
                    if alts:
                        return alts[(idx-2) % len(alts)]
                    return "Support can be provided where appropriate"
                para = re.sub(re.escape(v), repl, para)
        out.append(para)
        out.append(sep)
    return "".join(out)

# -------- Feature 8: AI Rhythm Detector --------
def analyse_paragraph_patterns(text: str) -> Dict[str, Any]:
    if not isinstance(text, str) or not text:
        return {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    starts = {}
    for l in lines:
        token = l.split(" ")[0].lower()
        starts[token] = starts.get(token, 0) + 1
    flags = {}
    for k, c in starts.items():
        if c >= 3 and k in {"this", "further"}:
            flags[k] = c
    return {"repeated_openers": starts, "flags": flags}

# -------- Feature 10: Quality Scoring --------
def score_report(texts: Dict[str, str]) -> Dict[str, int]:
    """Heuristic scoring 0–10 scales based on repetition, vendor frequency, and paragraph variety.
    texts: mapping of logical sections to text.
    """
    full = "\n\n".join([v for v in texts.values() if isinstance(v, str)])
    freq = analyse_phrase_frequency(full)
    # Repetition score: inversely proportional to high/medium counts
    rep_penalty = sum(1 for v in freq.values() if v.get("severity") in ("medium", "high"))
    repetition = max(0, 10 - rep_penalty)

    # Commercial balance: count vendor phrases
    vendor_count = sum(len(re.findall(re.escape(v), full)) for v in VENDOR_PHRASES)
    commercial_balance = max(0, 10 - max(0, vendor_count - 3))

    # Human authenticity: penalise repeated openers and overclaims
    _, oc_flags = detect_overclaims(full)
    rhythm = analyse_paragraph_patterns(full)
    opener_penalty = sum(1 for k, c in rhythm.get("flags", {}).items() if c >= 3)
    human_authenticity = max(0, 10 - opener_penalty - oc_flags.get("prevention", 0) // 5)

    # Exec readability: paragraph length and variety heuristic
    paras = [p for p in re.split(r"\n{2,}", texts.get("executive_summary", "")) if p.strip()]
    too_short = sum(1 for p in paras if len(p.split()) < 40)
    too_long = sum(1 for p in paras if len(p.split()) > 220)
    executive_readability = max(0, 10 - (too_short + too_long))

    # Technical accuracy placeholder (left at 9; future: linting)
    technical_accuracy = 9
    return {
        "human_authenticity": int(human_authenticity),
        "repetition": int(repetition),
        "commercial_balance": int(commercial_balance),
        "technical_accuracy": int(technical_accuracy),
        "executive_readability": int(executive_readability),
    }

# -------- Processing entry points --------
def _rewrite_text_block(text: str) -> str:
    if not text:
        return text
    t, _ = detect_overclaims(text)
    t = rewrite_repetitions(t)
    t = govern_vendor_bias(t)
    return t

# -------- Phase 2: Executive Summary Optimiser --------
def generate_executive_summary(client_inputs: dict, report_data: Any) -> str:
    """Construct a consultant-style executive summary with fixed sections.
    Structure: Current Position, Business Context, Operational Dependency, Primary Risks, Priority Improvements, Strategic Outlook.
    Pulls concrete details from client_inputs and report_data to avoid generic commentary.
    """
    if not isinstance(client_inputs, dict):
        client_inputs = {}
    industry = client_inputs.get("industry", "Unknown")
    crown = client_inputs.get("critical_infra", "Critical Systems")
    rto = client_inputs.get("rto", "Unknown")
    users = client_inputs.get("users", "Unknown")
    mdr = client_inputs.get("mdr_provider", "None")
    email = client_inputs.get("email", "Unknown")
    firewall = client_inputs.get("firewall", "Unknown")
    identity = client_inputs.get("identity", "Unknown")

    # Derive 2–3 primary risks heuristically from domain critical_gaps, if present
    risks: List[str] = []
    for d in getattr(report_data, "domain_assessments", []) or []:
        name = getattr(d, "domain_name", "")
        gs = getattr(d, "critical_gaps", []) or []
        for g in gs[:1]:
            if g:
                risks.append(f"{name}: {g}")
        if len(risks) >= 3:
            break
    risks_text = "; ".join(risks) if risks else "Baseline control gaps require remediation to stabilise risk exposure."

    priority_improvements = []
    for d in getattr(report_data, "domain_assessments", []) or []:
        wins = getattr(d, "vendor_agnostic_quick_wins", []) or []
        if wins:
            priority_improvements.extend(wins[:1])
        if len(priority_improvements) >= 3:
            break
    pri_text = "; ".join(priority_improvements) if priority_improvements else "Implement universal MFA, automated patching, and immutable backups."

    lines = [
        f"Current Position: The organisation operates within the {industry} sector with approximately {users} users. Current stack includes MDR/SOC: {mdr}, Email: {email}, Firewall: {firewall}, Identity: {identity}.",
        f"Business Context: The operating model depends on the availability and integrity of {crown}. Downtime tolerance (RTO) is {rto}, which frames acceptable recovery objectives and residual risk.",
        f"Operational Dependency: Key services and data flows hinge on {crown}; any disruption would propagate into customer fulfilment, regulatory obligations, and revenue continuity.",
        f"Primary Risks: {risks_text}.",
        f"Priority Improvements: {pri_text}.",
        f"Strategic Outlook: Progress from reactive hygiene to an actively managed defence and, ultimately, an adaptive posture with automation and verified recovery."
    ]
    return "\n\n".join(lines)

# -------- Phase 2: Recommendation Normalisation --------
def normalize_recommendations(report_data: Any) -> None:
    """Reshape recommendations to: Risk → Operational Need → Capability → Product Example.
    Uses critical_gaps as risk, domain name for capability family, and preserves existing product text as example.
    """
    for d in getattr(report_data, "domain_assessments", []) or []:
        domain_name = getattr(d, "domain_name", "Security Domain")
        gaps = getattr(d, "critical_gaps", []) or []
        recs = getattr(d, "recommended_solutions", []) or []
        if not isinstance(recs, list):
            continue
        risk = gaps[0] if gaps else "Unaddressed control gap in this domain"
        need = f"Address {risk.lower()} with policy, process, and technical controls"
        capability = f"{domain_name} capability uplift"
        normalized = []
        for r in recs:
            product = str(r)
            # Reject product-first phrasing by pre-pending capability justification
            entry = f"Risk: {risk} | Operational Need: {need} | Capability: {capability} | Product Example: {product}"
            normalized.append(entry)
        d.recommended_solutions = normalized

# -------- Phase 2: Final Humanisation Pass (Optional LLM) --------
def humanise_text_with_llm(section_text: str) -> str:
    if not stage_enabled("HUMANISATION_ENABLED", "0") or not section_text:
        return section_text
    try:
        # Import inside function to avoid hard dependency/cycles
        from core import LLMEngine
        from config import get_config, ConfigKey  # type: ignore
        from prompts import SYSTEM_PERSONA  # type: ignore
        client = LLMEngine.get_client()
        deployment = get_config("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        prompt = (
            "Rewrite the following text directly, applying light human edits to tone, clarity, and repetition. "
            "Do not add headings, labels, or commentary. Return only the revised text — no ‘Suggestion’, ‘Before/After’, bullets of edits, or code blocks. "
            "Preserve technical meaning and use British English.\n\nTEXT START\n" + section_text + "\nTEXT END"
        )
        improved = LLMEngine.generate_text_report(client, deployment, SYSTEM_PERSONA, prompt, temperature=0.2)
        if not improved:
            return section_text
        # Defensive sanitiser: strip any suggestion-style artefacts if the model ignores instructions
        cleaned = re.sub(r"(?im)^(?:suggest(?:ion|ed)\s*(?:edits?)?|before|after|change|replace)\s*[:：].*$", "", improved)
        cleaned = re.sub(r"(?s)```.*?```", "", cleaned)
        cleaned = re.sub(r"(?im)^\s*\*\s*(?:suggestion|edit|note)\s*[:：].*$", "", cleaned)
        cleaned = cleaned.strip()
        return cleaned if cleaned else section_text
    except Exception:
        # Fail closed to original text if LLM unavailable
        return section_text

def process_maturity_report(client_inputs: dict, report_data: Any) -> Tuple[Any, Dict[str, Any]]:
    """Rewrite key narrative fields, compute quality, and return (report_data, quality_summary).
    Keys inspected: executive_summary, domain_assessments[*] narrative fields, optional block fields.
    """
    # Executive summary
    if hasattr(report_data, "executive_summary"):
        summary = _rewrite_text_block(getattr(report_data, "executive_summary", ""))
        # Optional optimiser: replace generic summaries with structured one
        if stage_enabled("EXEC_SUMMARY_OPTIMISER_ENABLED", "1"):
            generic_markers = [
                "unique threat landscape",
                "ever-evolving threat landscape",
                "in today's environment",
            ]
            if any(m in summary.lower() for m in generic_markers) or len(summary.split()) < 120:
                summary = generate_executive_summary(client_inputs, report_data)
        # Optional humanisation pass (LLM)
        summary = humanise_text_with_llm(summary)
        report_data.executive_summary = summary

    # Domain narratives
    for item in getattr(report_data, "domain_assessments", []) or []:
        for field in [
            "current_state_analysis",
            "business_impact_narrative",
            "remediation_rationale",
            "shared_responsibility",
        ]:
            if hasattr(item, field):
                setattr(item, field, _rewrite_text_block(getattr(item, field)))

    # Executive summary action blocks
    for blk in getattr(report_data, "executive_summary_action_blocks", []) or []:
        if hasattr(blk, "finding"):
            blk.finding = humanise_text_with_llm(_rewrite_text_block(getattr(blk, "finding", "")))
        if hasattr(blk, "risk"):
            blk.risk = humanise_text_with_llm(_rewrite_text_block(getattr(blk, "risk", "")))
        if hasattr(blk, "remediation_actions") and isinstance(blk.remediation_actions, list):
            blk.remediation_actions = [govern_vendor_bias(x) for x in blk.remediation_actions]

    # Normalise recommendations where enabled
    if stage_enabled("RECOMMENDATION_NORMALISATION_ENABLED", "1"):
        normalize_recommendations(report_data)

    texts = {
        "executive_summary": getattr(report_data, "executive_summary", ""),
    }
    quality = score_report(texts)
    # Gate pass flag
    thr = get_quality_thresholds()
    quality["passed"] = (
        quality.get("human_authenticity", 0) >= thr.get("human_authenticity", 8)
        and quality.get("repetition", 0) >= thr.get("repetition", 8)
        and quality.get("commercial_balance", 0) >= thr.get("commercial_balance", 8)
        and quality.get("executive_readability", 0) >= thr.get("executive_readability", 8)
    )
    return report_data, quality

def process_threat_report(inputs: dict, scenario_obj: Any, mdr_case: str, recs: List[str]) -> Tuple[Any, str, List[str], Dict[str, Any]]:
    # Narrative and MDR case
    if hasattr(scenario_obj, "narrative"):
        scenario_obj.narrative = _rewrite_text_block(getattr(scenario_obj, "narrative", ""))
    mdr_case = humanise_text_with_llm(_rewrite_text_block(mdr_case))
    # Recommendations: minimise vendor spam
    recs2 = [govern_vendor_bias(x) for x in recs]
    texts = {
        "narrative": getattr(scenario_obj, "narrative", ""),
        "mdr_case": mdr_case,
    }
    quality = score_report(texts)
    thr = get_quality_thresholds()
    quality["passed"] = (
        quality.get("human_authenticity", 0) >= thr.get("human_authenticity", 8)
        and quality.get("repetition", 0) >= thr.get("repetition", 8)
        and quality.get("commercial_balance", 0) >= thr.get("commercial_balance", 8)
        and quality.get("executive_readability", 0) >= thr.get("executive_readability", 8)
    )
    return scenario_obj, mdr_case, recs2, quality

if __name__ == "__main__":
    demo = """This provides an example. This provides useful context. This provides additional detail. Further maturity is expected. Planet IT can support these changes. Planet IT can support governance as well."""
    print(analyse_phrase_frequency(demo))
    print(detect_overclaims("MDR ensures the environment is fully secure and prevents attacks."))
    print(analyse_paragraph_patterns(demo))
    print(score_report({"executive_summary": demo}))
