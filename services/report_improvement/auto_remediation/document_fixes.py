from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class TemplateResolutionContext:
    """
    Minimal scaffold for resolving template placeholders deterministically.

    This context is a data carrier only. Resolution logic should be invoked by
    the export/assembly layer and/or a future orchestrated template fixer.
    """
    customer_name: Optional[str] = None
    report_date: Optional[date] = None
    report_month_year: Optional[str] = None
    consultant_name: Optional[str] = None
    account_manager_name: Optional[str] = None
    approver_name: Optional[str] = None
    customer_logo_path: Optional[str] = None
    planet_branding_enabled: bool = True
    revision_number: Optional[str] = None

    def month_year(self) -> Optional[str]:
        """
        Resolve Month YYYY. If report_month_year provided, prefer it,
        otherwise derive from report_date when available.
        """
        if isinstance(self.report_month_year, str) and self.report_month_year.strip():
            return self.report_month_year.strip()
        try:
            if isinstance(self.report_date, date):
                return self.report_date.strftime("%B %Y")
        except Exception:
            return None
        return None

    def has_logo(self) -> bool:
        """
        Returns True if a logo path is set (existence check deferred to caller to avoid I/O here).
        """
        try:
            return bool(self.customer_logo_path and str(self.customer_logo_path).strip())
        except Exception:
            return False

# Deterministic template resolution helpers (Phase 1b)
# These functions do not perform I/O or mutate DOCX; they compute resolutions
# and surface unresolved fields for the UI layer to collect.
from typing import Dict, List, Tuple

def resolve_month_year(ctx: TemplateResolutionContext) -> Tuple[str | None, bool]:
    """
    Returns (Month YYYY string, resolved_flag).
    Prefers report_month_year; otherwise derives from report_date; else unresolved.
    """
    try:
        my = ctx.month_year()
        if isinstance(my, str) and my.strip():
            return my.strip(), True
        return None, False
    except Exception:
        return None, False

def resolve_logo_action(ctx: TemplateResolutionContext) -> Tuple[str, Dict[str, str]]:
    """
    Decide how to handle the 'INSERT CUSTOMER LOGO' placeholder.

    Returns:
      (action, meta) where action in {"insert","remove","request"} and meta may include {"logo_path": "..."}.
    Rules:
      - If customer_logo_path exists, action = "insert".
      - If no logo exists and logo-free layout is supported, action = "remove".
      - Otherwise, action = "request".
    """
    meta: Dict[str, str] = {}
    try:
        if ctx.has_logo():
            meta["logo_path"] = str(ctx.customer_logo_path).strip()
            return "insert", meta
        # Treat planet_branding_enabled as permitting logo-free layout collapse by default
        if bool(ctx.planet_branding_enabled):
            return "remove", meta
        return "request", meta
    except Exception:
        return "request", meta

def resolve_people(ctx: TemplateResolutionContext) -> Tuple[Dict[str, str], List[str]]:
    """
    Resolve [AM NAME] and [APPROVER NAME] from explicit application data.
    Do not infer; if missing, mark unresolved inputs.
    Returns:
      (resolved_fields, missing_fields)
    """
    resolved: Dict[str, str] = {}
    missing: List[str] = []
    try:
        if isinstance(ctx.account_manager_name, str) and ctx.account_manager_name.strip():
            resolved["account_manager_name"] = ctx.account_manager_name.strip()
        else:
            missing.append("account_manager_name")
        if isinstance(ctx.approver_name, str) and ctx.approver_name.strip():
            resolved["approver_name"] = ctx.approver_name.strip()
        else:
            missing.append("approver_name")
    except Exception:
        # If any exception, mark both as missing to avoid unsafe auto-fill
        if "account_manager_name" not in missing:
            missing.append("account_manager_name")
        if "approver_name" not in missing:
            missing.append("approver_name")
    return resolved, missing

def build_template_resolution(ctx: TemplateResolutionContext) -> Dict[str, object]:
    """
    Build a deterministic resolution bundle for template placeholders.
    This is consumed by the export/assembly layer and the Validation Review Panel.
    """
    out: Dict[str, object] = {
        "resolved": {},
        "actions": {},
        "missing_inputs": [],
    }
    # Month YYYY
    month_year, ok = resolve_month_year(ctx)
    if ok and month_year:
        out["resolved"]["report_month_year"] = month_year
    else:
        out["missing_inputs"].append("report_month_year")

    # Logo handling
    action, meta = resolve_logo_action(ctx)
    out["actions"]["logo"] = {"action": action, **meta}

    # People fields (AM/Approver)
    people, missing = resolve_people(ctx)
    if people:
        out["resolved"].update(people)
    if missing:
        out["missing_inputs"].extend(missing)

    # Revision number/date passthrough (populate if present)
    try:
        if isinstance(ctx.revision_number, str) and ctx.revision_number.strip():
            out["resolved"]["revision_number"] = ctx.revision_number.strip()
    except Exception:
        pass

    # Customer name passthrough for convenience
    try:
        if isinstance(ctx.customer_name, str) and ctx.customer_name.strip():
            out["resolved"]["customer_name"] = ctx.customer_name.strip()
    except Exception:
        pass

    return out
