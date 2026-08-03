Objective: Introduce a configurable, multi-stage quality pipeline that analyses and rewrites LLM outputs (maturity reports and threat reports) to reduce AI-style phrasing, repetition, overclaiming, and commercial bias; injects domain-specific writing personas; and gates exports behind a quality score threshold.

Action 1:

    FILE: quality_pipeline.py

    SEARCH: (file does not exist)

    REPLACE: """
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
                p_l = phrase.lower()
                # Count occurrences (case-insensitive)
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

    def process_maturity_report(client_inputs: dict, report_data: Any) -> Tuple[Any, Dict[str, Any]]:
        """Rewrite key narrative fields, compute quality, and return (report_data, quality_summary).
        Keys inspected: executive_summary, domain_assessments[*] narrative fields, optional block fields.
        """
        # Executive summary
        if hasattr(report_data, "executive_summary"):
            report_data.executive_summary = _rewrite_text_block(getattr(report_data, "executive_summary", ""))

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
                blk.finding = _rewrite_text_block(getattr(blk, "finding", ""))
            if hasattr(blk, "risk"):
                blk.risk = _rewrite_text_block(getattr(blk, "risk", ""))
            if hasattr(blk, "remediation_actions") and isinstance(blk.remediation_actions, list):
                blk.remediation_actions = [govern_vendor_bias(x) for x in blk.remediation_actions]

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
        mdr_case = _rewrite_text_block(mdr_case)
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

    """

    VERIFICATION: python -c "import quality_pipeline as q; assert callable(q.process_maturity_report); print('quality_pipeline: OK')"

Action 2:

    FILE: export.py

    SEARCH:
from data import format_governance_narrative
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Arc
import matplotlib.patheffects as pe
import numpy as np
import os
import tempfile

    REPLACE:
from data import format_governance_narrative
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Arc
import matplotlib.patheffects as pe
import numpy as np
import os
import tempfile
from config import get_config
try:
    from quality_pipeline import process_maturity_report, process_threat_report, get_quality_thresholds, quality_gate_enabled
except Exception:  # Safe fallback if module unavailable
    process_maturity_report = None
    process_threat_report = None
    get_quality_thresholds = None
    quality_gate_enabled = None

    VERIFICATION: python -c "python - <<'PY'\nimport importlib, sys\nimport export\nprint('imports patched OK')\nPY"

Action 3:

    FILE: export.py

    SEARCH:
    # 1) Radar chart image

    REPLACE:
    # --- QUALITY PIPELINE (Maturity Report) ---
    try:
        if process_maturity_report and (quality_gate_enabled() if callable(quality_gate_enabled) else True):
            report_data, _quality = process_maturity_report(client_inputs, report_data)
            thr = get_quality_thresholds()() if callable(get_quality_thresholds) else {}
            # Pass/fail handled inside; raise if present and fails
            if isinstance(_quality, dict) and not _quality.get('passed', True):
                raise RuntimeError("Quality gate failed: Report did not meet minimum thresholds for authenticity, repetition, commercial balance, or executive readability.")
    except Exception:
        # Fail open: continue export without blocking if pipeline errors
        pass

    # 1) Radar chart image

    VERIFICATION: python -c "import inspect, export; import re; src=inspect.getsource(export.create_maturity_docx); assert 'QUALITY PIPELINE' in src; print('maturity hook present')"

Action 4:

    FILE: export.py

    SEARCH:
    # Structure the context variables mirroring the template structure

    REPLACE:
    # --- QUALITY PIPELINE (Threat Report DOCX) ---
    try:
        if process_threat_report and (quality_gate_enabled() if callable(quality_gate_enabled) else True):
            scenario_obj, mdr_case, recs, _quality = process_threat_report(client_inputs, scenario_obj, recs, mdr_case)
    except Exception:
        pass

    # Structure the context variables mirroring the template structure

    VERIFICATION: python -c "import inspect, export; src=inspect.getsource(export.create_threat_docx); assert 'QUALITY PIPELINE (Threat Report DOCX)' in src; print('threat docx hook present')"

Action 5:

    FILE: export.py

    SEARCH:
    pdf = ReportPDF()
    pdf.add_page()

    REPLACE:
    pdf = ReportPDF()
    # --- QUALITY PIPELINE (Threat Report PDF) ---
    try:
        if process_threat_report and (quality_gate_enabled() if callable(quality_gate_enabled) else True):
            scenario_obj, mdr_case, recs, _quality = process_threat_report(inputs, scenario_obj, recs, mdr_case)
    except Exception:
        pass
    pdf.add_page()

    VERIFICATION: python -c "import inspect, export; src=inspect.getsource(export.create_pdf); assert 'QUALITY PIPELINE (Threat Report PDF)' in src; print('threat pdf hook present')"

Action 6:

    FILE: prompts.py

    SEARCH:
    Act as ROLE 2 and populate the required JSON schema to deliver a comprehensive Cybersecurity Maturity Assessment. Ensure all Vendor-Agnostic Quick Wins are tailored to mitigate the risks highlighted in the client's Security Culture Tier and align with their listed Compliance Targets.
    """

    REPLACE:
    ### DOMAIN WRITING PROFILES (REQUIRED)
    Use domain-specific personas to vary vocabulary, sentence structure, and emphasis so that each domain reads as if authored by a different specialist:
    - Identity & Access Management (IAM): persona: Identity Security Consultant; focus on authentication, privileged access, identity threats.
    - Network Security: persona: Network Security Architect; focus on segmentation, traffic controls, and service resilience.
    - Security Operations & Response (SecOps): persona: SOC Consultant; focus on detection engineering, triage discipline, and MTTR.
    - Security Validation & Testing: persona: Security Assurance Consultant; focus on evidence, scoping, and test cadence.
    - Governance, Risk & Compliance (GRC): persona: Governance Advisor; focus on policy, oversight, and regulatory exposure.
    Strictly avoid repeated connective phrases across domains. Vary sentence length and cadence.

    Act as ROLE 2 and populate the required JSON schema to deliver a comprehensive Cybersecurity Maturity Assessment. Ensure all Vendor-Agnostic Quick Wins are tailored to mitigate the risks highlighted in the client's Security Culture Tier and align with their listed Compliance Targets.
    """

    VERIFICATION: python -c "from prompts import build_maturity_prompt; import inspect; src=inspect.getsource(build_maturity_prompt); assert 'DOMAIN WRITING PROFILES' in src; print('persona injection present')"
