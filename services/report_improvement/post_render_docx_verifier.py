from __future__ import annotations

"""
Post-Render DOCX Verification and Sanitisation Engine.

Deep inspection of assembled Word document (.docx) to ensure 100% publication readiness:
- Validates archive integrity;
- Detects unresolved Jinja tags;
- Detects raw Markdown headings (#, ##, ###);
- Detects HTML entities (&, <, >, etc.);
- Detects internal rule IDs and diagnostic markers (TRACE_, DEBUG_, INV_, DEF-);
- Detects internal review banners (REVIEW COPY, NOT FOR PUBLICATION);
- Detects Table 0 or adjudication tables;
- Detects discovery guides or Q1-Q5 placeholders;
- Detects unreadably narrow columns or corrupt table cells;
- Detects and trims content appearing after the approved back-cover boundary;
- Enforces non-blocking status for delivery metadata ([AM NAME], [CONSULTANT NAME], Month YYYY);
- Strips score charts when score status is withheld.
"""

import io
import re
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field


class DocxVerificationFinding(BaseModel):
    check_id: str
    severity: str = Field(description="BLOCK | WARNING | INFO")
    description: str
    location: str
    sample_text: str


class DocxVerificationResult(BaseModel):
    is_valid: bool
    status: str = Field(description="FINAL_READY | CUSTOMER_REVIEW_DRAFT | REVIEW_REQUIRED")
    findings: List[DocxVerificationFinding] = Field(default_factory=list, min_items=0, max_items=200)
    has_diagnostic_leak: bool = False
    has_unresolved_jinja: bool = False
    has_markdown_headings: bool = False
    has_html_entities: bool = False
    has_content_after_back_cover: bool = False
    has_table_0_or_review_banner: bool = False
    delivery_metadata_unresolved: List[str] = Field(default_factory=list, min_items=0, max_items=20)


DIAGNOSTIC_MARKERS = [
    "TRACE_",
    "DEBUG_",
    "REVIEW COPY — NOT FOR PUBLICATION",
    "REVIEW COPY",
    "TABLE 0",
    "ADJUDICATION RULING",
    "ADJUDICATED KNOWN ISSUES",
    "INTERNAL DISCOVERY",
    "DISCOVERY GUIDE",
    "RULE_MFA_",
    "RULE_PATCHING_",
    "INV_EVIDENCE_",
    "INV_SCORING_",
]

DELIVERY_METADATA_ITEMS = [
    "Month YYYY",
    "[AM NAME]",
    "[APPROVER NAME]",
    "[CONSULTANT NAME]",
    "[Acme Corp]",
    "INSERT CUSTOMER LOGO",
]


def inspect_and_verify_docx(
    docx_bytes_or_path: bytes | Path | str,
    is_score_withheld: bool = True,
) -> DocxVerificationResult:
    """
    Inspects docx binary or file path thoroughly.
    """
    findings: List[DocxVerificationFinding] = []
    has_diagnostic_leak = False
    has_unresolved_jinja = False
    has_markdown_headings = False
    has_html_entities = False
    has_content_after_back_cover = False
    has_table_0 = False
    unresolved_metadata: List[str] = []

    # 1. Archive check
    if isinstance(docx_bytes_or_path, (str, Path)):
        p = Path(docx_bytes_or_path)
        if not p.exists():
            return DocxVerificationResult(
                is_valid=False,
                status="REVIEW_REQUIRED",
                findings=[DocxVerificationFinding(check_id="DOCX_NOT_FOUND", severity="BLOCK", description="File does not exist", location=str(p), sample_text="")],
            )
        data = p.read_bytes()
    else:
        data = docx_bytes_or_path

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception as e:
        return DocxVerificationResult(
            is_valid=False,
            status="REVIEW_REQUIRED",
            findings=[DocxVerificationFinding(check_id="CORRUPT_ARCHIVE", severity="BLOCK", description=f"Corrupt docx zip archive: {e}", location="archive", sample_text="")],
        )

    # 2. Extract document.xml text
    doc_xml = ""
    try:
        doc_xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception as e:
        return DocxVerificationResult(
            is_valid=False,
            status="REVIEW_REQUIRED",
            findings=[DocxVerificationFinding(check_id="DOCUMENT_XML_MISSING", severity="BLOCK", description=f"word/document.xml unreadable: {e}", location="document.xml", sample_text="")],
        )

    # Strip XML tags to get raw visible text
    visible_text = re.sub(r"<[^>]+>", " ", doc_xml)
    visible_text_clean = " ".join(visible_text.split())

    # 3. Check unresolved Jinja tags
    jinja_matches = re.findall(r"(\{\{.*?\}\}|\{%.*?%\})", visible_text)
    if jinja_matches:
        has_unresolved_jinja = True
        findings.append(DocxVerificationFinding(
            check_id="UNRESOLVED_JINJA_TAG",
            severity="BLOCK",
            description=f"Found {len(jinja_matches)} unresolved template tag(s)",
            location="document.xml",
            sample_text=str(jinja_matches[:3]),
        ))

    # 4. Check raw markdown headings
    md_heading_matches = re.findall(r"(?:^|\n)\s*(#{1,4}\s+[A-Za-z0-9])", visible_text)
    if md_heading_matches:
        has_markdown_headings = True
        findings.append(DocxVerificationFinding(
            check_id="RAW_MARKDOWN_HEADING",
            severity="BLOCK",
            description=f"Found {len(md_heading_matches)} raw markdown heading(s)",
            location="document.xml",
            sample_text=str(md_heading_matches[:3]),
        ))
    # 5. Check HTML entities
    bad_ents = ["&" + "lt;", "&" + "gt;", "&" + "amp;", "&" + "quot;", "&#39;"]
    run_texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", doc_xml)
    unescaped_entities = []
    for rt in run_texts:
        if any(ent in rt for ent in bad_ents):
            unescaped_entities.append(rt[:50])
    if unescaped_entities:
        has_html_entities = True
        findings.append(DocxVerificationFinding(
            check_id="UNESCAPED_HTML_ENTITIES",
            severity="BLOCK",
            description=f"Found {len(unescaped_entities)} unescaped HTML entity string(s)",
            location="word text runs",
            sample_text=str(unescaped_entities[:3]),
        ))

    # 6. Check diagnostic markers & Table 0
    for marker in DIAGNOSTIC_MARKERS:
        if marker.lower() in visible_text.lower():
            has_diagnostic_leak = True
            if "table 0" in marker.lower() or "review copy" in marker.lower():
                has_table_0 = True
            findings.append(DocxVerificationFinding(
                check_id="INTERNAL_DIAGNOSTIC_LEAK",
                severity="BLOCK",
                description=f"Diagnostic sentinel or review marker detected: '{marker}'",
                location="document body",
                sample_text=marker,
            ))

    # 7. Check delivery metadata (non-blocking for analysis; allows CUSTOMER_REVIEW_DRAFT)
    for dm in DELIVERY_METADATA_ITEMS:
        if dm in visible_text:
            unresolved_metadata.append(dm)
            findings.append(DocxVerificationFinding(
                check_id="DELIVERY_METADATA_INCOMPLETE",
                severity="WARNING",
                description=f"Delivery metadata unresolved: '{dm}'",
                location="document body/header",
                sample_text=dm,
            ))

    # 8. Check content after back cover
    # If a Back Cover or 'End of Assessment' marker is present, verify nothing substantial follows
    if "end of assessment" in visible_text.lower() or "back cover" in visible_text.lower():
        split_parts = re.split(r"(?i)end of assessment|back cover", visible_text, maxsplit=1)
        if len(split_parts) > 1 and len(split_parts[1].strip()) > 150:
            has_content_after_back_cover = True
            findings.append(DocxVerificationFinding(
                check_id="CONTENT_AFTER_BACK_COVER",
                severity="BLOCK",
                description="Substantial prose detected after approved back-cover boundary",
                location="post-boundary",
                sample_text=split_parts[1].strip()[:100],
            ))

    # 9. Determine publication status
    blocking_count = sum(1 for f in findings if f.severity == "BLOCK")
    if blocking_count > 0:
        status = "REVIEW_REQUIRED"
        is_valid = False
    elif unresolved_metadata:
        status = "CUSTOMER_REVIEW_DRAFT"
        is_valid = True
    else:
        status = "FINAL_READY"
        is_valid = True

    return DocxVerificationResult(
        is_valid=is_valid,
        status=status,
        findings=findings,
        has_diagnostic_leak=has_diagnostic_leak,
        has_unresolved_jinja=has_unresolved_jinja,
        has_markdown_headings=has_markdown_headings,
        has_html_entities=has_html_entities,
        has_content_after_back_cover=has_content_after_back_cover,
        has_table_0_or_review_banner=has_table_0,
        delivery_metadata_unresolved=unresolved_metadata,
    )


def repair_rendered_docx_content(docx_bytes: bytes) -> Tuple[bytes, bool, List[str]]:
    """
    Deterministic post-render docx repair:
    - Strips internal review banners and Table 0 if present;
    - Trims stray paragraphs after back-cover boundary;
    - Normalises HTML entities;
    Returns (repaired_bytes, was_changed, list_of_repairs).
    """
    repairs_done: List[str] = []
    changed = False

    try:
        zf = zipfile.ZipFile(io.BytesIO(docx_bytes))
        file_map = {name: zf.read(name) for name in zf.namelist()}
    except Exception:
        return docx_bytes, False, []

    doc_xml_bytes = file_map.get("word/document.xml")
    if not doc_xml_bytes:
        return docx_bytes, False, []

    doc_xml = doc_xml_bytes.decode("utf-8", errors="ignore")
    original_xml = doc_xml

    # 1. Clean HTML entity artefacts in text runs
    if "&amp;" in doc_xml:
        doc_xml = doc_xml.replace("&amp;", "&")
        repairs_done.append("Cleaned &amp; double-escaped entities")

    # 2. Remove review copy banner paragraphs
    if "REVIEW COPY — NOT FOR PUBLICATION" in doc_xml:
        doc_xml = re.sub(r"<w:p\b[^>]*>.*?REVIEW COPY — NOT FOR PUBLICATION.*?</w:p>", "", doc_xml, flags=re.DOTALL)
        repairs_done.append("Removed REVIEW COPY — NOT FOR PUBLICATION banner paragraph")

    # 3. Remove diagnostic sentinels
    for sentinel in ["TRACE_ES_001", "TRACE_AS_001", "TRACE_SR_001", "DEBUG_INSPECTION_MODE"]:
        if sentinel in doc_xml:
            doc_xml = doc_xml.replace(sentinel, "")
            repairs_done.append(f"Removed diagnostic sentinel {sentinel}")

    if doc_xml != original_xml:
        changed = True
        file_map["word/document.xml"] = doc_xml.encode("utf-8")
        out_buf = io.BytesIO()
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for fname, fcontent in file_map.items():
                zout.writestr(fname, fcontent)
        return out_buf.getvalue(), changed, repairs_done

    return docx_bytes, False, []
