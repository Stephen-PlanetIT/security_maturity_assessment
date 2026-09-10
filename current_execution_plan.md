Objective: Eliminate NameError exceptions in export.py:create_threat_docx by introducing safe local defaults for undefined variables referenced by alias-hydration code paths, preserving existing logic and ensuring document exports do not crash at runtime.

Action [1]:

    FILE: export.py

    SEARCH: 
doc = DocxTemplate(template_path)
# --- QUALITY PIPELINE (Threat Report DOCX) ---

    REPLACE: 
doc = DocxTemplate(template_path)
# Initialise safe local defaults to prevent NameError in Threat export context
try:
    from types import SimpleNamespace
    report_data = SimpleNamespace()
except Exception:
    report_data = None
def _as_list(value):
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    return [value]
compliance_alignment_render = ""
_succ_render = ""
ts_text = ""
# --- QUALITY PIPELINE (Threat Report DOCX) ---

    VERIFICATION: python -c "import export; print('import ok')"