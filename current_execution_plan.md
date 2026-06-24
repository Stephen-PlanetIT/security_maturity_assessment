# Execution Plan: Fix Empty Template Tags in Word Export

## Date
24/06/2026

## Request
Investigate and fix three Jinja2/Word template tags that remain empty in the generated `.docx` regardless of data entered:
- `{{ partnership_details }}`
- `{{ partnership_details_render }}`
- `{{ threat_intelligence_context }}`

Also sanity-check the last git commit (V1.2.1).

---

## 1. ROOT CAUSE ANALYSIS

### 1.1 `{{ partnership_details }}` — Always Empty

**Pydantic model** (`prompts.py` line 120):
```python
partnership_details: Optional[str] = Field(description="Optional governance narrative or details for partnership engagement.")
```
The field exists on `MaturityReport`. However:

**Export mapping** (`export.py`, `create_vciso_docx()`):
The `context` dictionary (built around line 290-365) does **NOT** contain:
```python
context["partnership_details"] = ...
```
The field is never read from `report_data` and never passed to `doc.render(context)`. `docxtpl` treats an unset context key as an empty string.

### 1.2 `{{ partnership_details_render }}` — No Source Exists

- **No Pydantic field** named `partnership_details_render` exists anywhere in `prompts.py`.
- `format_governance_narrative()` in `data.py` (lines 60-81) is designed to combine a narrative string with a list of links into a formatted block, but **it is never called** within `export.py`.
- The `format_governance_narrative` import exists in `app.py` (line 5) and `prompts.py` (line 7) but is unused in both modules.
- `export.py` does not even import `format_governance_narrative`.

This tag is most likely intended to be a rendered combination of `partnership_details` + `partnership_links`, but the render step was never implemented.

### 1.3 `{{ threat_intelligence_context }}` — Always Empty

**Pydantic model** (`prompts.py` line 122):
```python
threat_intelligence_context: Optional[str] = Field(default=None, description="Threat intelligence context relevant to the governance narrative.")
```
The field exists on `MaturityReport`. However:

**Export mapping** (`export.py`):
The `context` dictionary does **NOT** contain:
```python
context["threat_intelligence_context"] = ...
```
Same failure as 1.1 — the field exists on the model but is never mapped to the template context.

### 1.4 LLM Prompt Gap (Compounding Factor)

Even if export mapping is fixed, the `build_vciso_prompt()` function in `prompts.py` (lines 274-344) contains **no instruction** telling the LLM to populate `partnership_details`, `partnership_links`, or `threat_intelligence_context`. The LLM will simply leave these `Optional` fields as `None`.

---

## 2. RECENT COMMIT SANITY CHECK (V1.2.1, HEAD~1 → HEAD)

The diff between `HEAD~1` and `HEAD` shows:

| Change | Location | Verdict |
|--------|----------|---------|
| `MonetaryCostGBP` Pydantic model added | `prompts.py` line 89 | ✅ Correct — properly typed, no open dicts |
| `ComplianceSection` / `GapRemediationPlan` models | `prompts.py` lines 94-111 | ✅ Correct — properly typed, strict item counts |
| `gap_remediation_steps` on `DomainAssessment` | `prompts.py` line 62 | ✅ Correct |
| `monetary_cost_of_inaction` mapped in context dict | `export.py` lines 350-365 | ✅ Correct — reads from report_data, formats GBP string |
| `partnership_outline` mapped in context dict | `export.py` lines 367-372 | ✅ Correct |
| `generate_radar_chart` renamed to `_generate_radar_chart_v1` | `export.py` line 193 | ⚠️ Potentially breaking — caller references need verification, but `create_vciso_docx` uses `generate_radar_chart_from_values` not this function |
| Radar hard-cap logic updated | `export.py` | ✅ Correct |
| `format_governance_narrative()` added to `data.py` | `data.py` lines 60-81 | ✅ Useful utility — but unused by export |
| Cost estimation utilities in `data.py` | `data.py` lines 95-138 | ✅ Useful — but unused in current export pipeline (export reads monetary data from LLM output, not from these estimators) |

**Summary:** V1.2.1 is sound and introduced no regressions. The three empty tags are a **pre-existing defect** that predates V1.2.1 — the commit sensibly added `partnership_outline` and `monetary_cost_of_inaction` mapping, which are separate fields from the three broken ones.

---

## 3. FIX PLAN

### 3.1 File: `export.py` — Add Missing Context Mappings

**Location:** `create_vciso_docx()` function, after the existing `partnership_outline` block (around line 372).

**Modification 1:** Import `format_governance_narrative` at the top of `export.py`.
```python
from data import format_governance_narrative
```

**Modification 2:** Add context keys for the three missing tags. Insert after the existing `partnership_outline` block:

```python
# --- Partnership governance rendering ---
partnership_details = getattr(report_data, "partnership_details", None)
context["partnership_details"] = partnership_details or ""

partnership_links = getattr(report_data, "partnership_links", None)
# Build the rendered version: narrative + link bullets
context["partnership_details_render"] = format_governance_narrative(partnership_details, partnership_links) if (partnership_details or partnership_links) else ""

threat_intel = getattr(report_data, "threat_intelligence_context", None)
context["threat_intelligence_context"] = threat_intel or ""
```

### 3.2 File: `prompts.py` — Add LLM Prompt Instructions

**Location:** `build_vciso_prompt()` function, inside the `rules` string (around line 342, before "Act as ROLE 2").

**Modification:** Append a section instructing the LLM to populate the governance and threat intelligence fields:

```python
### PARTNERSHIP GOVERNANCE & THREAT INTELLIGENCE CONTEXT
You MUST populate the following optional fields with substantive, consultative content:
- **partnership_details:** A dedicated section describing co-managed or fully managed partnership arrangements. Reference the official partnership URLs: Fully Managed ({FULLY_MANAGED_URL}) and Co-Managed ({CO_MANAGED_URL}). Explain what Planet IT delivers under each model, the shared responsibility matrix, and SLAs. Minimum 2 paragraphs. Bullet points are strictly prohibited.
- **partnership_links:** A list of 2-3 official Planet IT governance or partnership resource URLs. Use the two official URLs above plus one additional Planet IT resource URL.
- **threat_intelligence_context:** A threat intelligence contextualisation specific to the client's industry and Crown Jewels. Summarise the current threat actor landscape, relevant APT groups, and how the client's assets are targeted. Minimum 1 paragraph. Bullet points are strictly prohibited.
```

**Note:** `FULLY_MANAGED_URL` and `CO_MANAGED_URL` are already imported in `prompts.py` at line 7, so no new import is needed.

### 3.3 File: `app.py` — Clean Up Unused Import (Optional, Non-blocking)

`format_governance_narrative` is imported at line 5 of `app.py` but never called. This produces a linting warning but no runtime error. While technically outside the scope of the three empty tags, it should be cleaned up for hygiene:

```python
# Line 5 — remove format_governance_narrative from the import
from data import FULLY_MANAGED_URL, CO_MANAGED_URL
```

---

## 4. VERIFICATION STEPS (To Be Run in Act Mode)

1. **Syntax check:** `python -c "import export; import prompts; print('Imports OK')"` — verifies no import errors from the new mapping
2. **Unit test (dry run):** `python -c "from data import format_governance_narrative; print(format_governance_narrative('Test narrative', ['https://a.com', 'https://b.com']))"` — verifies the utility produces expected output
3. **Integration test:** Run `streamlit run app.py`, generate a vCISO report, download the Word document, and verify the three tags render content

---

## 5. FILES MODIFIED

| File | Lines Changed | Nature |
|------|---------------|--------|
| `export.py` | +5 (import) + 8 (context mapping) | Add missing template context keys |
| `prompts.py` | +10 (prompt instructions) | Instruct LLM to populate governance fields |
| `app.py` | 1 line changed (import) | Remove unused `format_governance_narrative` import |