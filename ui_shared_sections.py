import streamlit as st
from consultation_schema import (
    DEFAULT_CRITICAL_ASSET_PROFILE,
    DEFAULT_SERVICE_RESILIENCE_PROFILE,
    DEFAULT_INFORMATION_PROTECTION,
    DEFAULT_IDENTITY_GOVERNANCE,
    DEFAULT_SAAS_GOVERNANCE,
    DEFAULT_ASSET_ASSURANCE,
    DEFAULT_MONITORING_ASSURANCE,
    DEFAULT_SUPPLIER_ASSURANCE,
    DEFAULT_THIRD_PARTY_ACCESS_PROFILE,
    DEFAULT_RECOVERY_ASSURANCE,
    DEFAULT_IR_ASSURANCE,
    ASSURANCE_STATUS_DEFAULT,
    BUSINESS_SERVICES_OPTIONS,
    SENSITIVE_DATA_OPTIONS,
    ASSESSMENT_STATUS_OPTIONS,
    RTO_OPTIONS,
    RPO_OPTIONS,
    MANUAL_WORKAROUND_OPTIONS,
    DEP_MAPPING_OPTIONS,
    RECOVERY_PRIORITIES_OPTIONS,
)


def _safe_index(options, value):
    """Return index of value in options; 0 if missing or invalid."""
    try:
        return options.index(value) if value in options else 0
    except Exception:
        return 0


def _with_custom_prefill(value, options):
    """
    Return (index, custom_default) for a selectbox with 'Other / Custom...' option.
    """
    try:
        if value in options:
            return options.index(value), ""
    except Exception:
        pass
    try:
        idx = options.index("Other / Custom...")
    except Exception:
        idx = 0
    return idx, (value or "")


def _resolve_custom(selection, custom):
    """
    Resolve final value for a selectbox with 'Other / Custom...'.
    """
    if isinstance(selection, str) and selection == "Other / Custom..." and isinstance(custom, str) and custom.strip():
        return custom.strip()
    return selection


def _coerce_multiselect_default(value, options, none_aliases=None, map_none_to=None):
    try:
        if isinstance(value, list):
            return [v for v in value if v in options]
        if isinstance(value, str):
            tokens = [t.strip() for t in value.split(",") if t.strip()]
            seq = tokens if tokens else ([value] if value else [])
            result = []
            for t in seq:
                if none_aliases and t in none_aliases and map_none_to:
                    result.append(map_none_to)
                elif t in options:
                    result.append(t)
            return [v for v in result if v in options]
    except Exception:
        pass
    return []


def render_ai_usage_and_governance():
    """
    Render AI Usage & Governance section and return a dict for client_inputs patch.
    Mirrors the maturity workflow's AI section to ensure parity.
    """
    defaults = (st.session_state.get('client_inputs', {}) or {})

    ai_policy_opts = ["Select AI Usage Policy...", "None", "Informal guidance", "Formalised policy enforced"]
    ai_usage_policy = st.selectbox(
        "AI Usage Policy",
        ai_policy_opts,
        index=_safe_index(ai_policy_opts, defaults.get('ai_usage_policy', 'None')),
        help="State of AI acceptable use policy and governance."
    )

    _approved_opts = ["Microsoft Copilot", "ChatGPT", "Google Gemini", "Claude", "Custom (in-house)", "None / Unapproved"]
    approved_defaults = _coerce_multiselect_default(
        defaults.get('approved_ai_tools', []),
        _approved_opts,
        none_aliases={"None"},
        map_none_to="None / Unapproved"
    )
    approved_ai_tools = st.multiselect(
        "Approved Company AI Tools",
        _approved_opts,
        default=approved_defaults,
        help="Approved AI assistants or models in use."
    )

    shadow_ai_opts = ["Select Shadow AI Monitoring...", "None", "Planned", "Enabled"]
    shadow_ai_monitoring = st.selectbox(
        "Shadow AI Monitoring",
        shadow_ai_opts,
        index=_safe_index(shadow_ai_opts, defaults.get('shadow_ai_monitoring', 'None')),
        help="Discovery and control of unsanctioned AI usage."
    )

    _dlp_opts = ["Microsoft Purview DLP", "Defender for Cloud Apps (CASB)", "CASB/SSE (Netskope)", "Proxy controls", "None"]
    dlp_defaults = _coerce_multiselect_default(
        defaults.get('ai_dlp_controls', []),
        _dlp_opts,
        none_aliases={"None"},
        map_none_to="None"
    )
    ai_dlp_controls = st.multiselect(
        "AI Data Loss Controls",
        _dlp_opts,
        default=dlp_defaults,
        help="Controls applied to prompts/responses and AI interactions."
    )

    return {
        "ai_usage_policy": ai_usage_policy,
        "approved_ai_tools": approved_ai_tools,
        "shadow_ai_monitoring": shadow_ai_monitoring,
        "ai_dlp_controls": ai_dlp_controls,
    }


def render_security_culture_sections():
    """
    Render Security Culture & Human Risk sections (programme controls + optional metrics),
    compute culture_score and derived savviness labels, and return a dict patch.
    """
    defaults = (st.session_state.get('client_inputs', {}) or {})

    _q1_opts = ["Never", "Annually", "Bi-Annually", "Quarterly", "Monthly"]
    _q2_opts = ["None", "Annual Compliance Video", "Annual with simulations", "Continuous with active coaching", "Continuous with nudges/micro-learning"]
    _reporting_opts = ["None", "Informal", "Documented clear routes", "Anonymous hotline", "One-click report (mail client)"]
    _coaching_opts = ["None", "Ad hoc", "Manager-led coaching", "Structured with tracking", "Just-in-time micro-coaching"]
    _role_opts = ["None", "High-risk roles only", "Partial key roles", "Comprehensive role-based"]
    _leadership_opts = ["None", "Ad hoc", "Monthly stand-up", "Quarterly / regular with OKRs", "Board KPIs/OKRs"]
    _policy_ack_opts = ["None", "Annual", "On hire and on-change", "Quarterly or on-change"]
    _q3_opts = ["Most users are Local Admins", "Only IT/Devs are Local Admins", "Zero Trust (No Local Admins/LAPS)"]

    with st.expander("Programme Controls", expanded=True):
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            q1 = st.radio("Phishing Simulations", _q1_opts, index=_safe_index(_q1_opts, defaults.get('culture_q1')))
        with col_c2:
            q2 = st.radio("Security Training Programme", _q2_opts, index=_safe_index(_q2_opts, defaults.get('culture_q2')))
        with col_c3:
            q3 = st.radio("Endpoint Privileges (telemetry)", _q3_opts, index=_safe_index(_q3_opts, defaults.get('culture_q3')))

        col_c4, col_c5, col_c6 = st.columns(3)
        with col_c4:
            reporting_routes = st.radio("Reporting Routes", _reporting_opts, index=_safe_index(_reporting_opts, defaults.get('culture_reporting_routes')))
        with col_c5:
            followup_coaching = st.radio("Follow-up Coaching", _coaching_opts, index=_safe_index(_coaching_opts, defaults.get('culture_followup_coaching')))
        with col_c6:
            role_training = st.radio("Role-based Training Coverage", _role_opts, index=_safe_index(_role_opts, defaults.get('culture_role_training')))

        col_c7, col_c8 = st.columns(2)
        with col_c7:
            leadership = st.radio("Leadership Engagement", _leadership_opts, index=_safe_index(_leadership_opts, defaults.get('culture_leadership_engagement')))
        with col_c8:
            policy_ack = st.radio("Policy Acknowledgement", _policy_ack_opts, index=_safe_index(_policy_ack_opts, defaults.get('culture_policy_ack')))

    with st.expander("Programme Metrics (optional)", expanded=False):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            phish_fail = st.number_input("Phish Failure Rate (last 90 days, %)", min_value=0, max_value=100, value=int(defaults.get('culture_phish_fail_pct_90d', 0)))
        with col_m2:
            report_rate = st.number_input("Report Rate (last 90 days, %)", min_value=0, max_value=100, value=int(defaults.get('culture_report_rate_pct_90d', 0)))

    def _score(map_opts, sel):
        try:
            if map_opts == "q1":
                return {"Never": 0, "Annually": 1, "Bi-Annually": 1, "Quarterly": 2, "Monthly": 2}.get(sel, 0)
            if map_opts == "q2":
                return {"None": 0, "Annual Compliance Video": 1, "Annual with simulations": 1, "Continuous with active coaching": 2, "Continuous with nudges/micro-learning": 2}.get(sel, 0)
            if map_opts == "report":
                return {"None": 0, "Informal": 1, "Documented clear routes": 2, "Anonymous hotline": 2, "One-click report (mail client)": 2}.get(sel, 0)
            if map_opts == "coach":
                return {"None": 0, "Ad hoc": 1, "Manager-led coaching": 1, "Structured with tracking": 2, "Just-in-time micro-coaching": 2}.get(sel, 0)
            if map_opts == "role":
                return {"None": 0, "High-risk roles only": 1, "Partial key roles": 1, "Comprehensive role-based": 2}.get(sel, 0)
            if map_opts == "lead":
                return {"None": 0, "Ad hoc": 1, "Monthly stand-up": 2, "Quarterly / regular with OKRs": 2, "Board KPIs/OKRs": 2}.get(sel, 0)
            if map_opts == "ack":
                return {"None": 0, "Annual": 1, "On hire and on-change": 2, "Quarterly or on-change": 2}.get(sel, 0)
            return 0
        except Exception:
            return 0

    culture_score = 0
    culture_score += _score("q1", q1)
    culture_score += _score("q2", q2)
    culture_score += _score("report", reporting_routes)
    culture_score += _score("coach", followup_coaching)
    culture_score += _score("role", role_training)
    culture_score += _score("lead", leadership)
    culture_score += _score("ack", policy_ack)

    if culture_score <= 5:
        savviness_label = "Pillar 1: Reactive Culture"
    elif culture_score <= 10:
        savviness_label = "Pillar 2: Proactive Culture"
    else:
        savviness_label = "Pillar 3: Adaptive Culture"

    savviness_profiles = {
        "Pillar 1: Reactive Culture": "Currently developing baseline awareness. Build reporting routes, establish structured coaching, and adopt role-based training.",
        "Pillar 2: Proactive Culture": "Strong baseline awareness. Programmes include clear routes, consistent coaching, and role-targeted content.",
        "Pillar 3: Adaptive Culture": "Highly optimised, zero-trust mindset. Users actively report threats; leadership drives OKRs; training is continuous and role-specific."
    }

    st.info(f"**Calculated Score: {culture_score}/14** | Result: {savviness_label} — *{savviness_profiles[savviness_label]}*")
    savviness = f"{savviness_label} - {savviness_profiles[savviness_label]}"

    return {
        "savviness": savviness,
        "savviness_label": savviness_label,
        "culture_score": culture_score,
        "culture_q1": q1,
        "culture_q2": q2,
        "culture_q3": q3,  # telemetry only; excluded from culture_score
        "culture_reporting_routes": reporting_routes,
        "culture_followup_coaching": followup_coaching,
        "culture_role_training": role_training,
        "culture_leadership_engagement": leadership,
        "culture_policy_ack": policy_ack,
        "culture_phish_fail_pct_90d": phish_fail,
        "culture_report_rate_pct_90d": report_rate,
    }


def render_governance_assurance_sections():
    """
    Render the Governance & Assurance evidence sections and return a tuple of structured dicts.
    Mirrors the Maturity workflow to ensure parity, while relying on session defaults where present.
    """
    client_defaults = st.session_state.get('client_inputs', {}) or {}

    # Critical Asset Profile
    with st.expander("Critical Asset Profile", expanded=False):
        st.subheader("Critical Asset Profile")
        _cap_def = client_defaults.get('critical_asset_profile', DEFAULT_CRITICAL_ASSET_PROFILE) or DEFAULT_CRITICAL_ASSET_PROFILE
        _cap_bs_defaults = [v for v in (_cap_def.get('business_services') or []) if v in BUSINESS_SERVICES_OPTIONS]
        _cap_bs_custom_list = [v for v in (_cap_def.get('business_services') or []) if v not in BUSINESS_SERVICES_OPTIONS]
        cap_bs = st.multiselect("Business Services", BUSINESS_SERVICES_OPTIONS, default=_cap_bs_defaults)
        cap_bs_custom = st.text_input("Custom Business Services (separate by ';')", value="; ".join(_cap_bs_custom_list))
        cap_bs_final = cap_bs + [s.strip() for s in cap_bs_custom.split(';') if s.strip()]
        cap_sp = st.text_input("Systems/Platforms", value=_cap_def.get('systems_platforms', ''))
        _cap_sd_defaults = [v for v in (_cap_def.get('sensitive_data_types') or []) if v in SENSITIVE_DATA_OPTIONS]
        _cap_sd_custom_list = [v for v in (_cap_def.get('sensitive_data_types') or []) if v not in SENSITIVE_DATA_OPTIONS]
        cap_sd = st.multiselect("Sensitive Data Types", SENSITIVE_DATA_OPTIONS, default=_cap_sd_defaults)
        cap_sd_custom = st.text_input("Custom Sensitive Data Types (separate by ';')", value="; ".join(_cap_sd_custom_list))
        cap_sd_final = cap_sd + [s.strip() for s in cap_sd_custom.split(';') if s.strip()]
        cap_extra = st.text_area("Additional Context", value=_cap_def.get('additional_context', ''))
        cap_dict = {
            "business_services": cap_bs_final,
            "systems_platforms": cap_sp,
            "sensitive_data_types": cap_sd_final,
            "additional_context": cap_extra,
        }

    # Service Resilience Profile
    with st.expander("Service Resilience Profile", expanded=False):
        st.subheader("Service Resilience Profile")
        _sr_def = client_defaults.get('service_resilience_profile', DEFAULT_SERVICE_RESILIENCE_PROFILE) or DEFAULT_SERVICE_RESILIENCE_PROFILE
        sr_assess = st.selectbox("Assessment Status", ASSESSMENT_STATUS_OPTIONS, index=_safe_index(ASSESSMENT_STATUS_OPTIONS, _sr_def.get('assessment_status')))
        sr_crit = st.text_input("Most Critical Service", value=_sr_def.get('most_critical_service', ''))
        sr_rto = st.selectbox("Service-specific RTO", RTO_OPTIONS, index=_safe_index(RTO_OPTIONS, _sr_def.get('service_specific_rto')))
        sr_rpo = st.selectbox("Service-specific RPO", RPO_OPTIONS, index=_safe_index(RPO_OPTIONS, _sr_def.get('service_specific_rpo')))
        sr_mw = st.selectbox("Manual Workaround", MANUAL_WORKAROUND_OPTIONS, index=_safe_index(MANUAL_WORKAROUND_OPTIONS, _sr_def.get('manual_workaround')))
        sr_dep = st.selectbox("Dependency Mapping", DEP_MAPPING_OPTIONS, index=_safe_index(DEP_MAPPING_OPTIONS, _sr_def.get('dependency_mapping')))
        sr_pri = st.selectbox("Recovery Priorities", RECOVERY_PRIORITIES_OPTIONS, index=_safe_index(RECOVERY_PRIORITIES_OPTIONS, _sr_def.get('recovery_priorities')))
        sr_notes = st.text_area("Notes", value=_sr_def.get('notes', ''))
        sr_dict = {
            "assessment_status": sr_assess,
            "most_critical_service": sr_crit,
            "service_specific_rto": sr_rto,
            "service_specific_rpo": sr_rpo,
            "manual_workaround": sr_mw,
            "dependency_mapping": sr_dep,
            "recovery_priorities": sr_pri,
            "notes": sr_notes,
        }

    # Information Protection
    with st.expander("Information Protection", expanded=False):
        st.subheader("Information Protection")
        _ip_def = client_defaults.get('information_protection_profile', DEFAULT_INFORMATION_PROTECTION) or DEFAULT_INFORMATION_PROTECTION
        ip_cls_opts = ["Sensitivity labels partially deployed", "None", "Unknown", "Other / Custom..."]
        idx_ip_cls, ip_cls_custom_def = _with_custom_prefill(_ip_def.get('data_classification_status', 'Unknown'), ip_cls_opts)
        ip_cls_sel = st.selectbox("Data Classification Status", ip_cls_opts, index=idx_ip_cls)
        ip_cls_custom = st.text_input("Custom Classification", value=ip_cls_custom_def if ip_cls_sel == "Other / Custom..." else "")
        ip_cls = _resolve_custom(ip_cls_sel, ip_cls_custom)

        ip_share_opts = ["Restricted and regularly reviewed", "Broadly enabled", "Unknown", "Other / Custom..."]
        idx_ip_share, ip_share_custom_def = _with_custom_prefill(_ip_def.get('external_sharing_posture', 'Unknown'), ip_share_opts)
        ip_share_sel = st.selectbox("External Sharing Posture", ip_share_opts, index=idx_ip_share)
        ip_share_custom = st.text_input("Custom External Sharing", value=ip_share_custom_def if ip_share_sel == "Other / Custom..." else "")
        ip_share = _resolve_custom(ip_share_sel, ip_share_custom)

        ip_dlp_opts = ["Deployed for selected sensitive data", "None", "Unknown", "Other / Custom..."]
        idx_ip_dlp, ip_dlp_custom_def = _with_custom_prefill(_ip_def.get('dlp_status', 'Unknown'), ip_dlp_opts)
        ip_dlp_sel = st.selectbox("DLP Status", ip_dlp_opts, index=idx_ip_dlp)
        ip_dlp_custom = st.text_input("Custom DLP", value=ip_dlp_custom_def if ip_dlp_sel == "Other / Custom..." else "")
        ip_dlp = _resolve_custom(ip_dlp_sel, ip_dlp_custom)

        ip_ret_opts = ["Retention controls configured", "Unknown", "Other / Custom..."]
        idx_ip_ret, ip_ret_custom_def = _with_custom_prefill(_ip_def.get('retention_governance', 'Unknown'), ip_ret_opts)
        ip_ret_sel = st.selectbox("Retention Governance", ip_ret_opts, index=idx_ip_ret)
        ip_ret_custom = st.text_input("Custom Retention Governance", value=ip_ret_custom_def if ip_ret_sel == "Other / Custom..." else "")
        ip_ret = _resolve_custom(ip_ret_sel, ip_ret_custom)

        ip_dict = {
            "data_classification_status": ip_cls,
            "external_sharing_posture": ip_share,
            "dlp_status": ip_dlp,
            "retention_governance": ip_ret,
        }

    # Identity Governance
    with st.expander("Identity Governance", expanded=False):
        st.subheader("Identity Governance")
        _idg_def = client_defaults.get('identity_governance_profile', DEFAULT_IDENTITY_GOVERNANCE) or DEFAULT_IDENTITY_GOVERNANCE
        idg_lc = st.text_input("Identity Lifecycle Maturity", value=_idg_def.get('identity_lifecycle_maturity', ''))
        idg_leaver = st.text_input("Leaver Deprovisioning", value=_idg_def.get('leaver_deprovisioning', ''))
        idg_ar = st.text_input("Access Review Status", value=_idg_def.get('access_review_status', ''))
        idg_pam = st.text_input("Privileged Access Model", value=_idg_def.get('privileged_access_model', ''))

        idg_pim_opts = ["Just-in-time access for major platforms", "None", "Planned", "Unknown", "Other / Custom..."]
        idx_idg_pim, idg_pim_custom_def = _with_custom_prefill(_idg_def.get('pim_pam_status', 'Unknown'), idg_pim_opts)
        idg_pim_sel = st.selectbox("PIM/PAM Status", idg_pim_opts, index=idx_idg_pim)
        idg_pim_custom = st.text_input("Custom PIM/PAM", value=idg_pim_custom_def if idg_pim_sel == "Other / Custom..." else "")
        idg_pim = _resolve_custom(idg_pim_sel, idg_pim_custom)

        idg_bg = st.text_input("Break Glass Governance", value=_idg_def.get('break_glass_governance', ''))

        idg_sag_opts = ["Ownership and credential rotation defined", "Informally managed", "Unknown", "Other / Custom..."]
        idx_idg_sag, idg_sag_custom_def = _with_custom_prefill(_idg_def.get('service_account_governance', 'Unknown'), idg_sag_opts)
        idg_sag_sel = st.selectbox("Service Account Governance", idg_sag_opts, index=idx_idg_sag)
        idg_sag_custom = st.text_input("Custom Service Account Governance", value=idg_sag_custom_def if idg_sag_sel == "Other / Custom..." else "")
        idg_sag = _resolve_custom(idg_sag_sel, idg_sag_custom)

        idg_shared_opts = ["Restricted and documented", "Widespread", "Unknown", "Other / Custom..."]
        idx_idg_shared, idg_shared_custom_def = _with_custom_prefill(_idg_def.get('shared_account_usage', 'Unknown'), idg_shared_opts)
        idg_shared_sel = st.selectbox("Shared Account Usage", idg_shared_opts, index=idx_idg_shared)
        idg_shared_custom = st.text_input("Custom Shared Account Usage", value=idg_shared_custom_def if idg_shared_sel == "Other / Custom..." else "")
        idg_shared = _resolve_custom(idg_shared_sel, idg_shared_custom)

        idg_legacy_opts = ["Restricted for selected dependencies", "Enabled and not reviewed", "Unknown", "Other / Custom..."]
        idx_idg_legacy, idg_legacy_custom_def = _with_custom_prefill(_idg_def.get('legacy_authentication_status', 'Unknown'), idg_legacy_opts)
        idg_legacy_sel = st.selectbox("Legacy Authentication Status", idg_legacy_opts, index=idx_idg_legacy)
        idg_legacy_custom = st.text_input("Custom Legacy Authentication Status", value=idg_legacy_custom_def if idg_legacy_sel == "Other / Custom..." else "")
        idg_legacy = _resolve_custom(idg_legacy_sel, idg_legacy_custom)

        idg_notes = st.text_area("Notes", value=_idg_def.get('notes', ''), key="idg_notes")
        idg_dict = {
            "identity_lifecycle_maturity": idg_lc,
            "leaver_deprovisioning": idg_leaver,
            "access_review_status": idg_ar,
            "privileged_access_model": idg_pam,
            "pim_pam_status": idg_pim,
            "break_glass_governance": idg_bg,
            "service_account_governance": idg_sag,
            "shared_account_usage": idg_shared,
            "legacy_authentication_status": idg_legacy,
            "notes": idg_notes,
        }

    # SaaS Governance
    with st.expander("SaaS Governance", expanded=False):
        st.subheader("SaaS Governance")
        _saas_def = client_defaults.get('saas_governance_profile', DEFAULT_SAAS_GOVERNANCE) or DEFAULT_SAAS_GOVERNANCE
        saas_inv_opts = ["Register with owners and data classification", "No authoritative inventory", "Unknown", "Other / Custom..."]
        idx_sg_inv, sg_inv_custom_def = _with_custom_prefill(_saas_def.get('inventory_status', 'Unknown'), saas_inv_opts)
        sg_inv_sel = st.selectbox("Inventory Status", saas_inv_opts, index=idx_sg_inv)
        sg_inv_custom = st.text_input("Custom Inventory Status", value=sg_inv_custom_def if sg_inv_sel == "Other / Custom..." else "")
        sg_inv = _resolve_custom(sg_inv_sel, sg_inv_custom)

        sg_cp = st.text_input("Critical Platforms", value=_saas_def.get('critical_platforms', ''))

        saas_sso_opts = ["Most supported applications", "Limited", "Unknown", "Other / Custom..."]
        idx_sg_sso, sg_sso_custom_def = _with_custom_prefill(_saas_def.get('sso_coverage', 'Unknown'), saas_sso_opts)
        sg_sso_sel = st.selectbox("SSO Coverage", saas_sso_opts, index=idx_sg_sso)
        sg_sso_custom = st.text_input("Custom SSO Coverage", value=sg_sso_custom_def if sg_sso_sel == "Other / Custom..." else "")
        sg_sso = _resolve_custom(sg_sso_sel, sg_sso_custom)

        saas_mfa_opts = ["All technically capable platforms", "Unknown", "Other / Custom..."]
        idx_sg_mfa, sg_mfa_custom_def = _with_custom_prefill(_saas_def.get('mfa_coverage', 'Unknown'), saas_mfa_opts)
        sg_mfa_sel = st.selectbox("MFA Coverage", saas_mfa_opts, index=idx_sg_mfa)
        sg_mfa_custom = st.text_input("Custom MFA Coverage", value=sg_mfa_custom_def if sg_mfa_sel == "Other / Custom..." else "")
        sg_mfa = _resolve_custom(sg_mfa_sel, sg_mfa_custom)

        sg_off = st.text_input("Offboarding Process", value=_saas_def.get('offboarding_process', ''))

        saas_rec_opts = ["Documented for critical platforms", "Unknown", "Other / Custom..."]
        idx_sg_rec, sg_rec_custom_def = _with_custom_prefill(_saas_def.get('recovery_responsibility', 'Unknown'), saas_rec_opts)
        sg_rec_sel = st.selectbox("Recovery Responsibility", saas_rec_opts, index=idx_sg_rec)
        sg_rec_custom = st.text_input("Custom Recovery Responsibility", value=sg_rec_custom_def if sg_rec_sel == "Other / Custom..." else "")
        sg_rec = _resolve_custom(sg_rec_sel, sg_rec_custom)

        saas_shadow_opts = ["CASB discovery", "Unknown", "Other / Custom..."]
        idx_sg_shadow, sg_shadow_custom_def = _with_custom_prefill(_saas_def.get('shadow_it_visibility', 'Unknown'), saas_shadow_opts)
        sg_shadow_sel = st.selectbox("Shadow IT Visibility", saas_shadow_opts, index=idx_sg_shadow)
        sg_shadow_custom = st.text_input("Custom Shadow IT Visibility", value=sg_shadow_custom_def if sg_shadow_sel == "Other / Custom..." else "")
        sg_shadow = _resolve_custom(sg_shadow_sel, sg_shadow_custom)

        saas_oauth_opts = ["Applications periodically reviewed", "User consent unrestricted or unknown", "Unknown", "Other / Custom..."]
        idx_sg_oauth, sg_oauth_custom_def = _with_custom_prefill(_saas_def.get('oauth_app_governance', 'Unknown'), saas_oauth_opts)
        sg_oauth_sel = st.selectbox("OAuth App Governance", saas_oauth_opts, index=idx_sg_oauth)
        sg_oauth_custom = st.text_input("Custom OAuth Governance", value=sg_oauth_custom_def if sg_oauth_sel == "Other / Custom..." else "")
        sg_oauth = _resolve_custom(sg_oauth_sel, sg_oauth_custom)

        sg_notes = st.text_area("Notes", value=_saas_def.get('notes', ''), key="saas_notes")
        saas_dict = {
            "inventory_status": sg_inv,
            "critical_platforms": sg_cp,
            "sso_coverage": sg_sso,
            "mfa_coverage": sg_mfa,
            "offboarding_process": sg_off,
            "recovery_responsibility": sg_rec,
            "shadow_it_visibility": sg_shadow,
            "oauth_app_governance": sg_oauth,
            "notes": sg_notes,
        }

    # Asset Assurance
    with st.expander("Asset Assurance", expanded=False):
        st.subheader("Asset Assurance")
        _aa_def = client_defaults.get('asset_assurance_profile', DEFAULT_ASSET_ASSURANCE) or DEFAULT_ASSET_ASSURANCE
        aa_inv_opts = ["Hardware, software and cloud assets centrally recorded", "Incomplete or unknown", "Unknown", "Other / Custom..."]
        idx_aa_inv, aa_inv_custom_def = _with_custom_prefill(_aa_def.get('asset_inventory_maturity', 'Unknown'), aa_inv_opts)
        aa_inv_sel = st.selectbox("Asset Inventory Maturity", aa_inv_opts, index=idx_aa_inv)
        aa_inv_custom = st.text_input("Custom Asset Inventory", value=aa_inv_custom_def if aa_inv_sel == "Other / Custom..." else "")
        aa_inv = _resolve_custom(aa_inv_sel, aa_inv_custom)

        aa_eas = st.text_input("External Attack Surface Visibility", value=_aa_def.get('external_attack_surface_visibility', ''))
        aa_vrm_opts = ["Tracker with priorities and dates", "Findings reported but not centrally tracked", "Unknown", "Other / Custom..."]
        idx_aa_vrm, aa_vrm_custom_def = _with_custom_prefill(_aa_def.get('vulnerability_remediation_maturity', 'Unknown'), aa_vrm_opts)
        aa_vrm_sel = st.selectbox("Vulnerability Remediation Maturity", aa_vrm_opts, index=idx_aa_vrm)
        aa_vrm_custom = st.text_input("Custom Vulnerability Remediation", value=aa_vrm_custom_def if aa_vrm_sel == "Other / Custom..." else "")
        aa_vrm = _resolve_custom(aa_vrm_sel, aa_vrm_custom)

        aa_cfg = st.text_input("Secure Configuration Baseline", value=_aa_def.get('secure_configuration_baseline', ''))
        aa_change = st.text_input("Security Change Assurance", value=_aa_def.get('security_change_assurance', ''))
        aa_uts = st.text_input("Unsupported Technology Status", value=_aa_def.get('unsupported_technology_status', ''))
        aa_dict = {
            "asset_inventory_maturity": aa_inv,
            "external_attack_surface_visibility": aa_eas,
            "vulnerability_remediation_maturity": aa_vrm,
            "secure_configuration_baseline": aa_cfg,
            "security_change_assurance": aa_change,
            "unsupported_technology_status": aa_uts,
        }

    # Monitoring Assurance
    with st.expander("Monitoring Assurance", expanded=False):
        st.subheader("Monitoring Assurance")
        _mon_def = client_defaults.get('monitoring_assurance_profile', DEFAULT_MONITORING_ASSURANCE) or DEFAULT_MONITORING_ASSURANCE
        mon_cov_opts = ["24/7 alert monitoring", "Business hours only", "Critical alerts outside hours", "Unknown", "Other / Custom..."]
        idx_mon_cov, mon_cov_custom_def = _with_custom_prefill(_mon_def.get('monitoring_coverage', 'Unknown'), mon_cov_opts)
        mon_cov_sel = st.selectbox("Monitoring Coverage", mon_cov_opts, index=idx_mon_cov)
        mon_cov_custom = st.text_input("Custom Monitoring Coverage", value=mon_cov_custom_def if mon_cov_sel == "Other / Custom..." else "")
        mon_cov = _resolve_custom(mon_cov_sel, mon_cov_custom)

        mon_logs_options = ["Endpoint", "Identity", "Microsoft 365", "Firewall", "SIEM", "Cloud"]
        _mon_logs_defaults = [v for v in (_mon_def.get('log_sources_monitored') or []) if v in mon_logs_options]
        _mon_logs_custom_list = [v for v in (_mon_def.get('log_sources_monitored') or []) if v not in mon_logs_options]
        mon_logs = st.multiselect("Log Sources Monitored", options=mon_logs_options, default=_mon_logs_defaults)
        mon_logs_custom = st.text_input("Custom Log Sources Monitored (separate by ';')", value="; ".join(_mon_logs_custom_list))
        mon_logs_final = mon_logs + [s.strip() for s in mon_logs_custom.split(';') if s.strip()]

        mon_ret = st.text_input("Log Retention", value=_mon_def.get('log_retention', ''))
        mon_esc = st.text_input("Out-of-hours Escalation", value=_mon_def.get('out_of_hours_escalation', ''))

        mon_auth_opts = ["Isolate and remediate", "Investigate and recommend", "Notify only", "Unknown", "Other / Custom..."]
        idx_mon_auth, mon_auth_custom_def = _with_custom_prefill(_mon_def.get('response_authority', 'Unknown'), mon_auth_opts)
        mon_auth_sel = st.selectbox("Response Authority", mon_auth_opts, index=idx_mon_auth)
        mon_auth_custom = st.text_input("Custom Response Authority", value=mon_auth_custom_def if mon_auth_sel == "Other / Custom..." else "")
        mon_auth = _resolve_custom(mon_auth_sel, mon_auth_custom)

        mon_test = st.text_input("Detection Testing", value=_mon_def.get('detection_testing', ''))
        mon_rep = st.text_input("Security Reporting Cadence", value=_mon_def.get('security_reporting_cadence', ''))
        mon_gaps = st.text_input("Known Coverage Gaps", value=_mon_def.get('known_coverage_gaps', ''))
        mon_dict = {
            "monitoring_coverage": mon_cov,
            "log_sources_monitored": mon_logs_final,
            "log_retention": mon_ret,
            "out_of_hours_escalation": mon_esc,
            "response_authority": mon_auth,
            "detection_testing": mon_test,
            "security_reporting_cadence": mon_rep,
            "known_coverage_gaps": mon_gaps,
        }

    # Supplier Assurance & Third-Party Access
    with st.expander("Supplier Assurance & Third-Party Access", expanded=False):
        st.subheader("Supplier Assurance & Third-Party Access")
        _sup_def = client_defaults.get('supplier_assurance_profile', DEFAULT_SUPPLIER_ASSURANCE) or DEFAULT_SUPPLIER_ASSURANCE
        sup_maturity_opts = ["Periodic review of critical suppliers", "None", "Unknown", "Other / Custom..."]
        idx_sup_mat, sup_mat_custom_def = _with_custom_prefill(_sup_def.get('supplier_assurance_maturity', 'Unknown'), sup_maturity_opts)
        sup_maturity_sel = st.selectbox("Supplier Assurance Maturity", sup_maturity_opts, index=idx_sup_mat)
        sup_maturity_custom = st.text_input("Custom Supplier Assurance Maturity", value=sup_mat_custom_def if sup_maturity_sel == "Other / Custom..." else "")
        sup_maturity = _resolve_custom(sup_maturity_sel, sup_maturity_custom)
        sup_dict = {"supplier_assurance_maturity": sup_maturity}

        _tpa_def = client_defaults.get('third_party_access_profile', DEFAULT_THIRD_PARTY_ACCESS_PROFILE) or DEFAULT_THIRD_PARTY_ACCESS_PROFILE
        tpa_access_opts = ["Access exists", "Unknown", "Other / Custom..."]
        idx_tpa_acc, tpa_acc_custom_def = _with_custom_prefill(_tpa_def.get('access_present', 'Unknown'), tpa_access_opts)
        tpa_access_sel = st.selectbox("Third-Party Access Present", tpa_access_opts, index=idx_tpa_acc)
        tpa_access_custom = st.text_input("Custom Third-Party Access Present", value=tpa_acc_custom_def if tpa_access_sel == "Other / Custom..." else "")
        tpa_access = _resolve_custom(tpa_access_sel, tpa_access_custom)

        tpa_model_opts = ["Named accounts with MFA", "Shared accounts", "Unknown", "Other / Custom..."]
        idx_tpa_model, tpa_model_custom_def = _with_custom_prefill(_tpa_def.get('identity_model', 'Unknown'), tpa_model_opts)
        tpa_model_sel = st.selectbox("Identity Model", tpa_model_opts, index=idx_tpa_model)
        tpa_model_custom = st.text_input("Custom Identity Model", value=tpa_model_custom_def if tpa_model_sel == "Other / Custom..." else "")
        tpa_model = _resolve_custom(tpa_model_sel, tpa_model_custom)

        tpa_mfa_opts = ["Universal for supplier access", "Not enforced", "Unknown", "Other / Custom..."]
        idx_tpa_mfa, tpa_mfa_custom_def = _with_custom_prefill(_tpa_def.get('mfa_status', 'Unknown'), tpa_mfa_opts)
        tpa_mfa_sel = st.selectbox("MFA Status", tpa_mfa_opts, index=idx_tpa_mfa)
        tpa_mfa_custom = st.text_input("Custom Third-Party MFA", value=tpa_mfa_custom_def if tpa_mfa_sel == "Other / Custom..." else "")
        tpa_mfa = _resolve_custom(tpa_mfa_sel, tpa_mfa_custom)

        tpa_time_opts = ["Yes", "No", "Not applicable"]
        tpa_time = st.selectbox("Time-limited", tpa_time_opts, index=_safe_index(tpa_time_opts, _tpa_def.get('time_limited', 'Not applicable')))
        tpa_mon_opts = ["Yes", "No", "Not applicable"]
        tpa_mon = st.selectbox("Monitored", tpa_mon_opts, index=_safe_index(tpa_mon_opts, _tpa_def.get('monitored', 'Not applicable')))
        tpa_review_opts = ["Yes", "No", "Not applicable"]
        tpa_review = st.selectbox("Periodically Reviewed", tpa_review_opts, index=_safe_index(tpa_review_opts, _tpa_def.get('periodically_reviewed', 'Not applicable')))

        tpa_deps = st.text_input("Critical Supplier Dependencies", value=_tpa_def.get('critical_supplier_dependencies', ''))

        tpa_contract_opts = ["Standard requirements for critical suppliers", "None or unknown", "Other / Custom..."]
        idx_tpa_contract, tpa_contract_custom_def = _with_custom_prefill(_tpa_def.get('contractual_security_requirements', 'None or unknown'), tpa_contract_opts)
        tpa_contract_sel = st.selectbox("Contractual Security Requirements", tpa_contract_opts, index=idx_tpa_contract)
        tpa_contract_custom = st.text_input("Custom Contractual Requirements", value=tpa_contract_custom_def if tpa_contract_sel == "Other / Custom..." else "")
        tpa_contract = _resolve_custom(tpa_contract_sel, tpa_contract_custom)

        tpa_notify = st.text_input("Incident Notification", value=_tpa_def.get('incident_notification', ''))
        tpa_exit = st.text_input("Exit Planning", value=_tpa_def.get('exit_planning', ''))
        tpa_conc = st.text_input("Concentration Risk", value=_tpa_def.get('concentration_risk', ''))
        tpa_notes = st.text_area("Notes", value=_tpa_def.get('notes', ''), key="tpa_notes")
        tpa_dict = {
            "access_present": tpa_access, "identity_model": tpa_model, "mfa_status": tpa_mfa, "time_limited": tpa_time,
            "monitored": tpa_mon, "periodically_reviewed": tpa_review, "critical_supplier_dependencies": tpa_deps,
            "contractual_security_requirements": tpa_contract, "incident_notification": tpa_notify, "exit_planning": tpa_exit,
            "concentration_risk": tpa_conc, "notes": tpa_notes,
        }

    # Recovery Assurance
    with st.expander("Recovery Assurance", expanded=False):
        st.subheader("Recovery Assurance")
        _rec_def = client_defaults.get('recovery_assurance_profile', DEFAULT_RECOVERY_ASSURANCE) or DEFAULT_RECOVERY_ASSURANCE
        rec_rt_opts = ["Regular representative restores", "Ad hoc", "Never", "Unknown", "Other / Custom..."]
        idx_rec_rt, rec_rt_custom_def = _with_custom_prefill(_rec_def.get('restore_testing', 'Unknown'), rec_rt_opts)
        rec_rt_sel = st.selectbox("Restore Testing", rec_rt_opts, index=idx_rec_rt)
        rec_rt_custom = st.text_input("Custom Restore Testing", value=rec_rt_custom_def if rec_rt_sel == "Other / Custom..." else "")
        rec_rt = _resolve_custom(rec_rt_sel, rec_rt_custom)

        rec_imm_opts = ["Immutable or air-gapped for critical backups", "None", "Unknown", "Other / Custom..."]
        idx_rec_imm, rec_imm_custom_def = _with_custom_prefill(_rec_def.get('immutability_status', 'Unknown'), rec_imm_opts)
        rec_imm_sel = st.selectbox("Immutability Status", rec_imm_opts, index=idx_rec_imm)
        rec_imm_custom = st.text_input("Custom Immutability", value=rec_imm_custom_def if rec_imm_sel == "Other / Custom..." else "")
        rec_imm = _resolve_custom(rec_imm_sel, rec_imm_custom)

        rec_sep = st.text_input("Administrative Separation", value=_rec_def.get('administrative_separation', ''))
        rec_srv = st.text_input("Service Recovery Testing", value=_rec_def.get('service_recovery_testing', ''))
        rec_evd = st.text_input("Evidence Retained", value=_rec_def.get('evidence_retained', ''))
        rec_owner = st.text_input("Recovery Ownership", value=_rec_def.get('recovery_ownership', ''))
        rec_notes = st.text_area("Notes", value=_rec_def.get('notes', ''), key="rec_notes")
        rec_dict = {
            "restore_testing": rec_rt, "immutability_status": rec_imm, "administrative_separation": rec_sep,
            "service_recovery_testing": rec_srv, "evidence_retained": rec_evd, "recovery_ownership": rec_owner, "notes": rec_notes,
        }

    # Incident Response Assurance
    with st.expander("Incident Response Assurance", expanded=False):
        st.subheader("Incident Response Assurance")
        _ir_def = client_defaults.get('incident_response_assurance_profile', DEFAULT_IR_ASSURANCE) or DEFAULT_IR_ASSURANCE
        ir_roles_opts = ["Technical and business roles documented", "Informal", "Unknown", "Other / Custom..."]
        idx_ir_roles, ir_roles_custom_def = _with_custom_prefill(_ir_def.get('roles_defined', 'Unknown'), ir_roles_opts)
        ir_roles_sel = st.selectbox("Roles Defined", ir_roles_opts, index=idx_ir_roles)
        ir_roles_custom = st.text_input("Custom Roles Defined", value=ir_roles_custom_def if ir_roles_sel == "Other / Custom..." else "")
        ir_roles = _resolve_custom(ir_roles_sel, ir_roles_custom)

        ir_bauth_opts = ["Documented", "Unknown", "Other / Custom..."]
        idx_ir_bauth, ir_bauth_custom_def = _with_custom_prefill(_ir_def.get('business_decision_authority', 'Unknown'), ir_bauth_opts)
        ir_bauth_sel = st.selectbox("Business Decision Authority", ir_bauth_opts, index=idx_ir_bauth)
        ir_bauth_custom = st.text_input("Custom Business Decision Authority", value=ir_bauth_custom_def if ir_bauth_sel == "Other / Custom..." else "")
        ir_bauth = _resolve_custom(ir_bauth_sel, ir_bauth_custom)

        ir_tech_opts = ["Endpoint isolation authorised", "Unknown", "Other / Custom..."]
        idx_ir_tech, ir_tech_custom_def = _with_custom_prefill(_ir_def.get('technical_response_authority', 'Unknown'), ir_tech_opts)
        ir_tech_sel = st.selectbox("Technical Response Authority", ir_tech_opts, index=idx_ir_tech)
        ir_tech_custom = st.text_input("Custom Technical Response Authority", value=ir_tech_custom_def if ir_tech_sel == "Other / Custom..." else "")
        ir_tech = _resolve_custom(ir_tech_sel, ir_tech_custom)

        ir_tt_opts = ["Within the past year", "More than one year ago", "Never", "Unknown", "Other / Custom..."]
        idx_ir_tt, ir_tt_custom_def = _with_custom_prefill(_ir_def.get('tabletop_status', 'Unknown'), ir_tt_opts)
        ir_tt_sel = st.selectbox("Tabletop Status", ir_tt_opts, index=idx_ir_tt)
        ir_tt_custom = st.text_input("Custom Tabletop Status", value=ir_tt_custom_def if ir_tt_sel == "Other / Custom..." else "")
        ir_tt = _resolve_custom(ir_tt_sel, ir_tt_custom)

        ir_oob = st.text_input("Out-of-band Communications", value=_ir_def.get('out_of_band_communications', ''))
        ir_cris = st.text_input("Crisis Communications", value=_ir_def.get('crisis_communications', ''))
        ir_reg_opts = ["Decision process and templates prepared", "Included in exercises", "Unknown", "Other / Custom..."]
        idx_ir_reg, ir_reg_custom_def = _with_custom_prefill(_ir_def.get('regulatory_notification_readiness', 'Unknown'), ir_reg_opts)
        ir_reg_sel = st.selectbox("Regulatory Notification Readiness", ir_reg_opts, index=idx_ir_reg)
        ir_reg_custom = st.text_input("Custom Regulatory Notification Readiness", value=ir_reg_custom_def if ir_reg_sel == "Other / Custom..." else "")
        ir_reg = _resolve_custom(ir_reg_sel, ir_reg_custom)

        ir_sup = st.text_input("Supplier Coordination", value=_ir_def.get('supplier_coordination', ''))
        ir_less = st.text_input("Lessons Learned Process", value=_ir_def.get('lessons_learned_process', ''))
        ir_notes = st.text_area("Notes", value=_ir_def.get('notes', ''), key="ir_notes")
        ir_dict = {
            "roles_defined": ir_roles, "business_decision_authority": ir_bauth, "technical_response_authority": ir_tech,
            "tabletop_status": ir_tt, "out_of_band_communications": ir_oob, "crisis_communications": ir_cris,
            "regulatory_notification_readiness": ir_reg, "supplier_coordination": ir_sup, "lessons_learned_process": ir_less, "notes": ir_notes,
        }

    # Assurance Status (map)
    with st.expander("Assurance Status", expanded=False):
        st.subheader("Assurance Status")
        _as_def = client_defaults.get('assurance_status', ASSURANCE_STATUS_DEFAULT) or ASSURANCE_STATUS_DEFAULT
        _status_opts = ["Confirmed during consultation", "Reported, evidence not reviewed", "Requires supplier confirmation", "Not applicable", "Unknown"]

        def _status_select(label_key, current):
            return st.selectbox(label_key, _status_opts, index=_safe_index(_status_opts, current or "Unknown"))

        as_default = _status_select("Default Assurance", (_as_def or {}).get("default", "Unknown"))
        as_ip = _status_select("Information Protection", (_as_def or {}).get("information_protection", ""))
        as_idg = _status_select("Identity Governance", (_as_def or {}).get("identity_governance", ""))
        as_saas = _status_select("SaaS Governance", (_as_def or {}).get("saas_governance", ""))
        as_mon = _status_select("Monitoring", (_as_def or {}).get("monitoring", ""))
        as_sup = _status_select("Supplier Security", (_as_def or {}).get("supplier_security", ""))
        as_rec = _status_select("Recovery", (_as_def or {}).get("recovery", ""))
        as_ir = _status_select("Incident Response", (_as_def or {}).get("incident_response", ""))
        as_ot = _status_select("OT & IoT", (_as_def or {}).get("ot_iot", ""))
        as_pf = _status_select("Payment Fraud", (_as_def or {}).get("payment_fraud", ""))
        as_app = _status_select("Application Security", (_as_def or {}).get("application_security", ""))
        as_int = _status_select("Integration Assurance", (_as_def or {}).get("integration_assurance", ""))

        as_map = {
            "default": as_default,
            "information_protection": as_ip,
            "identity_governance": as_idg,
            "saas_governance": as_saas,
            "monitoring": as_mon,
            "supplier_security": as_sup,
            "recovery": as_rec,
            "incident_response": as_ir,
            "ot_iot": as_ot,
            "payment_fraud": as_pf,
            "application_security": as_app,
            "integration_assurance": as_int,
        }

    return cap_dict, sr_dict, ip_dict, idg_dict, saas_dict, aa_dict, mon_dict, sup_dict, tpa_dict, rec_dict, ir_dict, as_map