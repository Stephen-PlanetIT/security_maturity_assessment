from __future__ import annotations
from typing import Tuple, List
try:
    from services.report_improvement.evidence_enforcement.models import ValidationIssue, EvidenceEnforcementContext  # type: ignore
except Exception:  # Fallback for test environments without pydantic installed
    class ValidationIssue:  # type: ignore
        ...
    class EvidenceEnforcementContext:  # type: ignore
        ...

# Deterministic handler placeholders for Phase 1 scaffolding.
# Phase 1 uses evidence_enforcement.revision.revise_section_from_validation_errors directly.
# These functions are reserved for Phase 2 orchestrator wiring.

def remove_unapproved_financial_values(text: str, issues: List[ValidationIssue], ctx: EvidenceEnforcementContext) -> Tuple[str, bool]:
    """
    Deterministically remove unapproved monetary values and replace the affected
    cost paragraph with an approved fallback narrative sourced from configuration.
    No model calls. Conservative and idempotent.
    """
    import re
    changed = False
    try:
        from config import get_config
        try:
            fallback = get_config(
                "EVIDENCE_FALLBACK_COST_TEXT",
                "Financial exposure has not been quantified from validated business data. Relevant cost drivers include "
                "lost productive time, delayed customer delivery, specialist incident response, recovery activity and management overhead. "
                "These should be modelled using customer-provided operational and financial inputs."
            )
        except Exception:
            fallback = (
                "Financial exposure has not been quantified from validated business data. Relevant cost drivers include "
                "lost productive time, delayed customer delivery, specialist incident response, recovery activity and management overhead. "
                "These should be modelled using customer-provided operational and financial inputs."
            )
        # Strip currency values and simple ranges entirely
        new_text = re.sub(
            r"\b(£|GBP|USD|EUR)\s?\d[\d,\.]*(\s*(to|-|–|—)\s*(£|GBP|USD|EUR)\s?\d[\d,\.]*)?",
            "",
            text or "",
            flags=re.IGNORECASE,
        )
        # If a 'cost of inaction' block exists, replace its paragraph with fallback; otherwise append fallback once
        lower_new = new_text.lower()
        if "cost of inaction" in lower_new:
            try:
                new_text = re.sub(r"(?si)(cost of inaction.*?)(\n\n|\Z)", lambda m: f"{fallback}\n\n", new_text)
            except Exception:
                if fallback not in new_text:
                    new_text = f"{new_text.rstrip()}\n\n{fallback}"
        else:
            if fallback not in new_text:
                new_text = f"{new_text.rstrip()}\n\n{fallback}"
        if new_text != text:
            changed = True
            return new_text, changed
        return text, False
    except Exception:
        return text, False

def recalculate_scoring(text: str, issues: List[ValidationIssue], ctx: EvidenceEnforcementContext) -> Tuple[str, bool]:
    return text, False

def resolve_or_escalate_placeholder(text: str, issues: List[ValidationIssue] | None = None, ctx: EvidenceEnforcementContext | None = None) -> Tuple[str, bool]:
    """
    Resolve simple placeholders where deterministic values are present; otherwise leave content
    unchanged and rely on template resolution + manifest missing_inputs for consultant decisions.
    """
    try:
        s = str(text or "")
        # Basic Month YYYY fix — only if a resolved value is present in ctx
        month = None
        try:
            # Prefer contextual flag if provided as a dict
            if isinstance(ctx, dict):
                month = ctx.get("report_month_year") or None
        except Exception:
            month = None
        if month and "Month YYYY" in s:
            s = s.replace("Month YYYY", str(month))
            return s, True
        # No deterministic substitution — escalate via missing_inputs upstream
        return s, False
    except Exception:
        return text, False

def remove_consultant_only_block(text: str, issues: List[ValidationIssue] | None = None, ctx: EvidenceEnforcementContext | None = None) -> Tuple[str, bool]:
    """
    Remove clearly delimited consultant-only blocks based on configured markers/headings.
    If block boundaries cannot be determined safely, return unchanged (False).

    Primary behaviour:
    - Remove blocks enclosed by explicit markers: "[Consultant Only]" ... "[/Consultant Only]" (case-insensitive).
    Fallback behaviour:
    - Heuristic markers: headings like 'Consultant Only', 'Internal Discovery', etc., removing until a blank line.
    """
    import re
    changed = False
    if not text:
        return text, False

    try:
        # Primary removal using explicit bracketed markers
        lines = text.splitlines()
        keep: list[str] = []
        skip_mode = False
        for ln in lines:
            s = ln.strip()
            sl = s.lower()
            if sl == "[consultant only]":
                skip_mode = True
                changed = True
                continue
            if sl == "[/consultant only]":
                skip_mode = False
                changed = True
                continue
            if skip_mode:
                # Skip content inside bracketed markers
                continue
            keep.append(ln)
        new_text = "\n".join(keep)
        if changed and new_text != text:
            return new_text, True

        # Fallback heuristic markers; exact DOCX bookmarks/styles handled upstream in document processing.
        markers = [
            r"(?:^|\n)\s*consultant\s+only\s*:?\s*$",
            r"(?:^|\n)\s*remove\s+before\s+sending\s*:?\s*$",
            r"(?:^|\n)\s*internal\s+discovery\s+guide\s*:?\s*$",
            r"(?:^|\n)\s*internal\s+notes\s*:?\s*$",
        ]
        keep = []
        skip_mode = False
        for ln in text.splitlines():
            ln_lower = ln.strip().lower()
            if any(re.search(pat, ln_lower, flags=re.IGNORECASE) for pat in markers):
                # Enter skip mode until a blank line or section break
                skip_mode = True
                changed = True
                continue
            if skip_mode:
                if not ln.strip():
                    skip_mode = False
                continue
            keep.append(ln)
        new_text = "\n".join(keep)
        if changed and new_text != text:
            return new_text, True
        return text, False
    except Exception:
        return text, False

def normalise_markdown_artifacts(text: str, issues: List[ValidationIssue] | None = None, ctx: EvidenceEnforcementContext | None = None) -> Tuple[str, bool]:
    """
    Conservatively normalise common markdown/formatting artefacts without altering semantics.
    - Remove stray markdown '**' emphasis markers when unbalanced on a line
    - Fix malformed bullets '- - ' -> '- '
    - Collapse triple-or-more newlines to double
    - Replace runs of spaces (>2) with a single space outside of obvious indentation
    """
    try:
        import re
        if not text:
            return text, False
        new_text = text

        # Remove unbalanced '**' pairs naïvely (only when odd count in a line)
        fixed_lines = []
        for ln in new_text.splitlines():
            if ln.count("**") % 2 == 1:
                ln = ln.replace("**", "")
            fixed_lines.append(ln)
        new_text = "\n".join(fixed_lines)

        # Fix malformed bullets
        new_text = re.sub(r"(?m)^\s*-\s+-\s+", "- ", new_text)

        # Collapse triple or more newlines
        new_text = re.sub(r"\n{3,}", "\n\n", new_text)

        # Replace runs of spaces with single space outside of tabs/double-space indents
        new_text = re.sub(r"(?m)(?<!\t)(?<!  ) {3,}", " ", new_text)

        if new_text != text:
            return new_text, True
        return text, False
    except Exception:
        return text, False

def remove_duplicate_content(text: str, issues: List[ValidationIssue] | None = None, ctx: EvidenceEnforcementContext | None = None) -> Tuple[str, bool]:
    """
    Remove exact duplicate paragraphs conservatively. Preserve first occurrence; drop subsequent exact matches.
    Falls back to line-level de-duplication when no paragraph breaks are present.
    """
    try:
        if not text:
            return text, False
        seen = set()
        changed = False

        if "\n\n" in text:
            parts = text.split("\n\n")
            out_parts = []
            for p in parts:
                key = p.strip()
                if key and key in seen:
                    changed = True
                    continue
                if key:
                    seen.add(key)
                out_parts.append(p)
            new_text = "\n\n".join(out_parts)
        else:
            out_lines = []
            for ln in text.splitlines():
                key = ln.strip()
                if key and key in seen:
                    changed = True
                    continue
                if key:
                    seen.add(key)
                out_lines.append(ln)
            new_text = "\n".join(out_lines)

        if changed and new_text != text:
            return new_text, True
        return text, False
    except Exception:
        return text, False

def remove_or_populate_known_issues_table(text: str, issues: List[ValidationIssue] | None = None, ctx: EvidenceEnforcementContext | None = None) -> Tuple[str, bool]:
    """
    Handle 'Identified Known Issues' table deterministically:
    - If a header is detected and the table appears empty (e.g., numbered blank rows), remove/hide the block.
    - Else leave unchanged; population requires structured table context and is escalated via TEMPLATE_FIX upstream.
    This conservative handler avoids mutating non-table content.
    """
    try:
        import re
        if not text:
            return text, False
        # Detect a simple 'Known Issues' header and a sequence of numbered blanks like '1.' or '-'
        pat_header = re.compile(r"(?mi)^\s*(identified\s+)?known\s+issues\s*:?\s*$")
        if not pat_header.search(text):
            return text, False
        lines = text.splitlines()
        new_lines = []
        i = 0
        changed = False
        while i < len(lines):
            ln = lines[i]
            if pat_header.match(ln):
                # scan ahead up to 15 lines looking for only empty numbered rows
                j = i + 1
                empty_count = 0
                row_count = 0
                while j < len(lines) and j <= i + 15:
                    lnj = lines[j].strip()
                    if re.match(r"^(\d+\.|-|\*)\s*$", lnj):
                        row_count += 1
                        empty_count += 1
                        j += 1
                        continue
                    if lnj == "":
                        j += 1
                        continue
                    break
                # If empty numbered rows encountered, remove the block between header and j (exclusive)
                if row_count > 0 and empty_count == row_count:
                    changed = True
                    i = j
                    continue
            new_lines.append(ln)
            i += 1
        new_text = "\n".join(new_lines)
        if changed and new_text != text:
            return new_text, True
        return text, False
    except Exception:
        return text, False

def convert_existing_control_recommendations(text: str, issues: List[ValidationIssue], ctx: EvidenceEnforcementContext) -> Tuple[str, bool]:
    """
    Convert recommendations that suggest replacing or deploying controls that already exist into
    validation‑oriented language. This is a deterministic, conservative rewrite that does not introduce
    new facts and does not claim absence/presence beyond phrasing changes.
    """
    try:
        import re
        if not text:
            return text, False
        s = str(text)

        substitutions = [
            # MFA — shift to validation language
            (r"(?is)enforce\s+universal\s+mfa", "Validate MFA coverage across privileged, service and externally accessible accounts, and document any approved exceptions."),
            (r"(?is)\b(enforce|enable)\b\s+(conditional\s+access|mfa)", "Validate MFA coverage across privileged, service and externally accessible accounts, and document any approved exceptions."),
            # Endpoint — if an endpoint platform exists, prefer validation of coverage/telemetry
            (r"(?is)deploy\s+endpoint\s+protection", "Review endpoint protection coverage, telemetry quality and operational integration before deciding whether optimisation or platform change is justified."),
            (r"(?is)roll\s+out\s+edr", "Review endpoint protection coverage, telemetry quality and operational integration before deciding whether optimisation or platform change is justified."),
            # Backups — convert to restore validation
            (r"(?is)implement\s+backups", "Validate representative restore testing, administrative separation and recovery sequencing across the existing backup estate."),
            (r"(?is)adopt\s+immutable\s+backups", "Validate representative restore testing, administrative separation and recovery sequencing across the existing backup estate."),
        ]

        changed = False
        for pat, repl in substitutions:
            new_s = re.sub(pat, repl, s)
            if new_s != s:
                changed = True
                s = new_s
        return s, changed
    except Exception:
        return text, False

DETERMINISTIC_HANDLERS = {
    "UNSUPPORTED_FINANCIAL_FIGURE": remove_unapproved_financial_values if 'remove_unapproved_financial_values' in globals() else (lambda t,i,c:(t,False)),
    "NO_CONCRETE_COSTS_WITHOUT_EVIDENCE": remove_unapproved_financial_values if 'remove_unapproved_financial_values' in globals() else (lambda t,i,c:(t,False)),
    "SCORE_ARITHMETIC_ERROR": recalculate_scoring if 'recalculate_scoring' in globals() else (lambda t,i,c:(t,False)),
    "PUBLICATION_PLACEHOLDER": resolve_or_escalate_placeholder if 'resolve_or_escalate_placeholder' in globals() else (lambda t,i,c:(t,False)),
    "CONSULTANT_ONLY_CONTENT": remove_consultant_only_block if 'remove_consultant_only_block' in globals() else (lambda t,i,c:(t,False)),
    "MARKDOWN_ESCAPE": normalise_markdown_artifacts if 'normalise_markdown_artifacts' in globals() else (lambda t,i,c:(t,False)),
    "DUPLICATE_PARAGRAPH": remove_duplicate_content if 'remove_duplicate_content' in globals() else (lambda t,i,c:(t,False)),
    "EMPTY_KNOWN_ISSUES_TABLE": remove_or_populate_known_issues_table if 'remove_or_populate_known_issues_table' in globals() else (lambda t,i,c:(t,False)),
    "NO_REPLACEMENT_WITHOUT_JUSTIFICATION": convert_existing_control_recommendations if 'convert_existing_control_recommendations' in globals() else (lambda t,i,c:(t,False)),
}
