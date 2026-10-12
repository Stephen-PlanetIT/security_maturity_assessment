from __future__ import annotations
from typing import List, Optional, Literal, Tuple
from pydantic import BaseModel, Field
from config import get_config, ConfigKey
from core import LLMEngine

# Models: strictly typed, no open dicts, list bounds enforced
class AssessmentEvidence(BaseModel):
    customer_name: Optional[str] = Field(default=None, description="Client name, if explicitly stated.")
    industry: Optional[str] = Field(default=None, description="Industry (verbatim).")
    headcount: Optional[int] = Field(default=None, ge=0, description="Total headcount if explicitly stated.")
    sites: List[str] = Field(default_factory=list, min_items=0, max_items=100, description="Physical or logical sites mentioned.")
    technologies: List[str] = Field(default_factory=list, min_items=0, max_items=200, description="Key technologies mentioned (generic).")
    security_products: List[str] = Field(default_factory=list, min_items=0, max_items=200, description="Named security products mentioned (facts only).")
    suppliers: List[str] = Field(default_factory=list, min_items=0, max_items=100, description="Suppliers/MSPs explicitly referenced.")
    cloud_platforms: List[str] = Field(default_factory=list, min_items=0, max_items=20, description="Cloud platforms referenced.")
    crown_jewels: List[str] = Field(default_factory=list, min_items=0, max_items=50, description="Crown jewels / critical assets as stated.")
    business_priorities: List[str] = Field(default_factory=list, min_items=0, max_items=50, description="Business priorities stated in the meeting.")
    downtime_requirements: List[str] = Field(default_factory=list, min_items=0, max_items=20, description="RTO/RPO or downtime tolerance notes.")
    compliance_requirements: List[str] = Field(default_factory=list, min_items=0, max_items=30, description="Compliance obligations explicitly mentioned.")
    existing_controls: List[str] = Field(default_factory=list, min_items=0, max_items=200, description="Existing controls confirmed as present.")
    confirmed_strengths: List[str] = Field(default_factory=list, min_items=0, max_items=100, description="Strengths confirmed by transcript/summary.")
    confirmed_gaps: List[str] = Field(default_factory=list, min_items=0, max_items=100, description="Gaps confirmed by transcript/summary (facts only).")
    customer_concerns: List[str] = Field(default_factory=list, min_items=0, max_items=100, description="Concerns stated by customer (verbatim if possible).")
    active_projects: List[str] = Field(default_factory=list, min_items=0, max_items=100, description="In-flight projects mentioned.")
    existing_security_services: List[str] = Field(default_factory=list, min_items=0, max_items=100, description="Existing managed services/retainers stated.")
    unknowns: List[str] = Field(default_factory=list, min_items=0, max_items=100, description="Items explicitly unknown/unclear from the meeting.")

AllowedInsightCategory = Literal[
    "Business Priority",
    "Board Concern",
    "Operational Concern",
    "Downtime Concern",
    "Technology Decision",
    "Budget Concern",
    "Compliance Requirement",
    "Security Concern",
    "Recovery Concern",
    "Supplier Concern",
]

class TranscriptInsight(BaseModel):
    category: AllowedInsightCategory = Field(description="Fixed categories only.")
    speaker: str = Field(description="Speaker identifier as stated (role/name).")
    quote: str = Field(description="Short quote or paraphrase of key point (<= 280 chars).")
    relevance_score: int = Field(ge=1, le=5, description="1=low, 5=critical relevance to report improvements.")

class CombinedExtraction(BaseModel):
    evidence: AssessmentEvidence
    insights: List[TranscriptInsight] = Field(default_factory=list, min_items=0, max_items=200)

_SYSTEM_PERSONA_EVIDENCE = (
    "You are a disciplined note-taker. Extract only facts that were explicitly stated."
    " Do NOT infer weaknesses, do NOT make recommendations, do NOT score maturity."
    " Preserve unknowns as unknown. Output must conform to the provided Pydantic schema."
    " Use British English and concise phrasing."
)

def _sample_transcript(text: str, max_chars: int) -> str:
    try:
        s = (text or "").strip()
        if len(s) <= max_chars:
            return s
        # Take head/middle/tail slices to preserve spread without multiple passes
        head = max_chars // 3
        mid = max_chars // 3
        tail = max_chars - head - mid
        seg1 = s[:head]
        seg2_start = max(len(s)//2 - (mid//2), 0)
        seg2 = s[seg2_start: seg2_start + mid]
        seg3 = s[-tail:]
        return seg1 + "\n...\n" + seg2 + "\n...\n" + seg3
    except Exception:
        return (text or "")[:max_chars]

def build_evidence_extraction_prompt(assessment_profile: dict, transcript_text: str, meeting_summary: str) -> str:
    # Keep the input human-readable; the model returns strict JSON via parse
    non_auth_note = ""
    try:
        # Structured sample-fixture quarantine advisory (advisory only; adjudication enforces deterministically)
        if bool(assessment_profile.get("__sample_non_authoritative", False)):
            auth = assessment_profile.get("__source_authority", {})
            non_auth_note = (
                "- Source precedence (per fact): consultant_approved > transcript > summary > customer_profile; sample fixtures only when explicitly marked as demo.\n"
                f"- Profile authority: authoritative={bool(auth.get('authoritative', False))}; reason={auth.get('authority_reason','')}\n"
                "- Do NOT convert profile products into current controls unless independently corroborated by transcript/summary or consultant approval.\n"
            )
    except Exception as exc:
        non_auth_note = f"(authority advisory unavailable: {exc})"
    return (
        "Extract structured AssessmentEvidence and a prioritized list of TranscriptInsights.\n"
        "Rules:\n"
        "- Facts only; no recommendations, no maturity scoring, no policy judgements.\n"
        "- Do not infer controls; only record existing_controls if explicitly stated.\n"
        "- Keep unknowns unknown; do not guess.\n"
        "- Insights: keep only salient items using the allowed categories; cap quotes at ~280 chars.\n"
        + non_auth_note +
        "Input A (Assessment Profile; free text/dict):\n"
        f"{assessment_profile}\n\n"
        "Input B (Meeting Summary; short):\n"
        f"{meeting_summary}\n\n"
        "Input C (Transcript; sampled):\n"
        f"{transcript_text}\n"
    )

def extract_evidence_once(
    transcript: str,
    summary: str,
    assessment_profile: dict
) -> Optional[CombinedExtraction]:
    client = LLMEngine.get_client()
    if not client:
        return None
    deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
    try:
        max_chars_raw = get_config("EVIDENCE_EXTRACTION_MAX_TRANSCRIPT_CHARS", 12000)
        max_chars = int(max_chars_raw) if int(max_chars_raw) > 1000 else 12000
    except Exception:
        max_chars = 12000
    sampled = _sample_transcript(transcript or "", max_chars=max_chars)
    prompt = build_evidence_extraction_prompt(assessment_profile or {}, sampled, summary or "")
    # Use structured parse path to get a CombinedExtraction Pydantic instance
    result = LLMEngine.generate_structured_report(
        client=client,
        deployment=deployment,
        system_persona=_SYSTEM_PERSONA_EVIDENCE,
        user_prompt=prompt,
        response_model=CombinedExtraction
    )
    return result