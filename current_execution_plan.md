Objective: Resolve compliance export blocking under diagnostics and harden UI against dict-based domain items.

Action [1]:

    FILE: app.py

    SEARCH:         for domain in getattr(maturity, 'domain_assessments', []):
                with st.expander(f"{domain.domain_name} — {domain.current_maturity_level}"):
                    st.markdown("**Technical Analysis:**")
                    st.markdown(domain.current_state_analysis)
                    
                    st.markdown("**Business Impact:**")
                    st.markdown(domain.business_impact_narrative)
                    
                    st.markdown("**Critical Gaps:**")
                    for gap in domain.critical_gaps:
                        st.markdown(f"- {gap}")
                        
                    st.markdown("**Remediation Rationale:**")
                    st.markdown(domain.remediation_rationale)
    
    REPLACE:         for domain in getattr(maturity, 'domain_assessments', []):
                name = domain.get("domain_name") if isinstance(domain, dict) else getattr(domain, "domain_name", "")
                level = domain.get("current_maturity_level") if isinstance(domain, dict) else getattr(domain, "current_maturity_level", "")
                with st.expander(f"{name} — {level}"):
                    st.markdown("**Technical Analysis:**")
                    tech = domain.get("current_state_analysis") if isinstance(domain, dict) else getattr(domain, "current_state_analysis", "")
                    st.markdown(tech)
                    
                    st.markdown("**Business Impact:**")
                    impact = domain.get("business_impact_narrative") if isinstance(domain, dict) else getattr(domain, "business_impact_narrative", "")
                    st.markdown(impact)
                    
                    st.markdown("**Critical Gaps:**")
                    gaps = domain.get("critical_gaps") if isinstance(domain, dict) else getattr(domain, "critical_gaps", [])
                    for gap in (gaps or []):
                        st.markdown(f"- {gap}")
                        
                    st.markdown("**Remediation Rationale:**")
                    rationale = domain.get("remediation_rationale") if isinstance(domain, dict) else getattr(domain, "remediation_rationale", "")
                    st.markdown(rationale)

    VERIFICATION: python -c "import app; print('app_import_ok')"

Action [2]:

    FILE: export.py

    SEARCH:     compliance_alignment_render = ""
    if not compliance_alignment_structured:
        raise PublicationBlockedError("Compliance rows empty", blocking_rule_ids=["COMPLIANCE_ROWS_EMPTY"])
    if compliance_alignment_structured:
    
    REPLACE:     compliance_alignment_render = ""
    if not compliance_alignment_structured:
        try:
            from config import get_config as _get_cfg
            sandbox = str(_get_cfg('DIAGNOSTIC_SANDBOX', 'false')).strip().lower() in ('1','true','yes','on')
        except Exception:
            sandbox = False
        if sandbox:
            # Allow export to proceed without compliance narrative under diagnostic sandbox
            pass
        else:
            raise PublicationBlockedError("Compliance rows empty", blocking_rule_ids=["COMPLIANCE_ROWS_EMPTY"])
    if compliance_alignment_structured:

    VERIFICATION: python -c "from export import create_maturity_docx; print('export_import_ok')"