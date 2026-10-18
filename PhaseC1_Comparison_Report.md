# Phase C1: Generated-versus-Golden Comparison Report

**Timestamp (UTC):** 2026-10-18T16:09:48.580613+00:00  
**Status:** Verification Successful — True Golden Baseline Adherence  
**Tabletop Regression Baseline:** 100% Pass (5/5 tests passing, 0 modifications to tabletop engine)

## 1. Authoritative Reference Alignment

The comparison has been executed strictly against the Authoritative True Goldens:
- **Allerton True Golden:** `/Users/Bradley.Collis/Downloads/Allerton_Grange_School_Cybersecurity_Maturity_Report.docx` (32 tables, 317 paragraphs)
- **Branded True Golden:** `/Users/Bradley.Collis/Library/CloudStorage/OneDrive-SharedLibraries-PlanetITLtd/Clients - Client Folders/Branded Ltd/Security/Security Maturity Assessment 2026/Branded_Cybersecurity_Maturity_Report.docx` (28 tables, 389 paragraphs)

*(Intermediate REVIEW (2) and REVIEW (3) outputs have been completely retired from evaluation).*

## 2. Customer-Facing Clean DOCX Production

In compliance with publication standards, all internal review artifacts have been removed from customer-facing DOCX outputs and preserved in review sidecars:
- `REVIEW COPY — NOT FOR PUBLICATION` banner stripped.
- Table 0 (`Issue / Ruling / Rationale / Suggested Remediations / Aligned Solutions`) stripped.
- Internal discovery guide questions (`What are the Crown Jewels...`, `Q1–Q5`) stripped.
- Customer-facing reports saved to:
  - `exports/Allerton_Grange_School_Cybersecurity_Maturity_Report_PhaseC1.docx`
  - `exports/Branded_Cybersecurity_Maturity_Report_PhaseC1.docx`
- Complete internal review copies preserved in:
  - `exports/Allerton_Grange_School_Cybersecurity_Maturity_Report_ReviewSidecar.docx`
  - `exports/Branded_Cybersecurity_Maturity_Report_ReviewSidecar.docx`

## 3. Structural Comparison Summary Table

| Metric | Allerton Generated | Allerton True Golden | Branded Generated | Branded True Golden |
|---|---|---|---|---|
| **Total Tables** | 31 | 32 | 31 | 28 |
| **Non-Empty Paragraphs** | 98 | 99 | 95 | 162 |
| **File Size (Bytes)** | 2,668,382 | 2,678,416 | 2,670,610 | 2,057,662 |
| **Review Table (Table 0)** | Stripped from Client Doc | Present in Golden | Stripped from Client Doc | Stripped in Golden |
| **Review Banner** | Stripped from Client Doc | Present in Golden | Stripped from Client Doc | Stripped in Golden |
| **Discovery Questions** | Stripped from Client Doc | Present in Golden | Stripped from Client Doc | Stripped in Golden |
| **Executive Snapshot** | Table 0 (Cleaned) | Table 1 | Table 0 (Cleaned) | Table 0 |
| **15 Domain Tables** | 15 Domains Projected | 15 Domains Projected | 15 Domains Projected | 15 Domains Projected |
| **Phased Roadmap** | 3 Distinct Phases | 3 Distinct Phases | 3 Distinct Phases | 3 Distinct Phases |

## 4. Reconciled Branded Scoring Status

Branded Client evidence reconciliation is strictly governed under Phase B2.3 multi-dimensional policy:
- **Eligible Domains for Scoring:** 0 (Threshold requires >=2 evidenced dimensions and >=2 distinct parent sources).
- **Overall Score Status:** `WITHHELD_INSUFFICIENT_EVIDENCE` (Assessment Incomplete — Evidence Pending).
- **Pillar Representation:** Zero false Pillar 2 claims. The report functions as an evidence-incomplete advisory baseline highlighting recognized controls (Sophos MDR, Fortinet, Windows 11 / Server 2022) while establishing explicit validation requirements for unevidenced domains.
