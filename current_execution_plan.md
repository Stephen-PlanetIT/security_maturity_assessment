Objective: Move the AI Usage & Governance controls from the sidebar into the main body of the Cybersecurity Maturity Assessment UI without altering data flow, schemas, or downstream logic.

Action 1:

    FILE: app.py

    SEARCH:
        st.markdown("### 🤖 AI Usage & Governance")
        ai_policy_opts = ["Select AI Usage Policy...", "None", "Informal guidance", "Formalised policy enforced"]
        ai_usage_policy = st.selectbox(
            "AI Usage Policy",
            ai_policy_opts,
            index=(ai_policy_opts.index(TEST_DATA.get('ai_usage_policy', 'None')) if dev else 0),
            help="State of AI acceptable use policy and governance."
        )

        approved_ai_tools = st.multiselect(
            "Approved Company AI Tools",
            ["Microsoft Copilot", "ChatGPT", "Google Gemini", "Claude", "Custom (in-house)", "None / Unapproved"],
            default=(TEST_DATA.get('approved_ai_tools', []) if dev else []),
            help="Approved AI assistants or models in use."
        )

        shadow_ai_opts = ["Select Shadow AI Monitoring...", "None", "Planned", "Enabled"]
        shadow_ai_monitoring = st.selectbox(
            "Shadow AI Monitoring",
            shadow_ai_opts,
            index=(shadow_ai_opts.index(TEST_DATA.get('shadow_ai_monitoring', 'None')) if dev else 0),
            help="Discovery and control of unsanctioned AI usage."
        )

        ai_dlp_controls = st.multiselect(
            "AI Data Loss Controls",
            ["Microsoft Purview DLP", "Defender for Cloud Apps (CASB)", "CASB/SSE (Netskope)", "Proxy controls", "None"],
            default=(TEST_DATA.get('ai_dlp_controls', []) if dev else []),
            help="Controls applied to prompts/responses and AI interactions."
        )
            st.markdown("### 🤖 AI Usage & Governance")
            ai_policy_opts = ["Select AI Usage Policy...", "None", "Informal guidance", "Formalised policy enforced"]
            ai_usage_policy = st.selectbox(
                "AI Usage Policy",
                ai_policy_opts,
                index=(ai_policy_opts.index(TEST_DATA.get('ai_usage_policy', 'None')) if dev else 0),
                help="State of AI acceptable use policy and governance."
            )

            approved_ai_tools = st.multiselect(
                "Approved Company AI Tools",
                ["Microsoft Copilot", "ChatGPT", "Google Gemini", "Claude", "Custom (in-house)", "None / Unapproved"],
                default=(TEST_DATA.get('approved_ai_tools', []) if dev else []),
                help="Approved AI assistants or models in use."
            )

            shadow_ai_opts = ["Select Shadow AI Monitoring...", "None", "Planned", "Enabled"]
            shadow_ai_monitoring = st.selectbox(
                "Shadow AI Monitoring",
                shadow_ai_opts,
                index=(shadow_ai_opts.index(TEST_DATA.get('shadow_ai_monitoring', 'None')) if dev else 0),
                help="Discovery and control of unsanctioned AI usage."
            )

            ai_dlp_controls = st.multiselect(
                "AI Data Loss Controls",
                ["Microsoft Purview DLP", "Defender for Cloud Apps (CASB)", "CASB/SSE (Netskope)", "Proxy controls", "None"],
                default=(TEST_DATA.get('ai_dlp_controls', []) if dev else []),
                help="Controls applied to prompts/responses and AI interactions."
            )

    REPLACE:
        # [Moved] AI Usage & Governance controls relocated to main body under the Cybersecurity Maturity Assessment UI.

    VERIFICATION:
        /bin/sh -c "test $(grep -n '\#\#\# 🤖 AI Usage & Governance' app.py | wc -l) -eq 1 && echo Action1_OK"

Action 2:

    FILE: app.py

    SEARCH:
st.divider()

## --- SECURITY CULTURE CALCULATOR ---
st.markdown("### 🧮 Security Culture Calculator")
        

    REPLACE:
st.markdown("### 🤖 AI Usage & Governance")
ai_policy_opts = ["Select AI Usage Policy...", "None", "Informal guidance", "Formalised policy enforced"]
ai_usage_policy = st.selectbox(
    "AI Usage Policy",
    ai_policy_opts,
    index=(ai_policy_opts.index(TEST_DATA.get('ai_usage_policy', 'None')) if dev else 0),
    help="State of AI acceptable use policy and governance."
)

approved_ai_tools = st.multiselect(
    "Approved Company AI Tools",
    ["Microsoft Copilot", "ChatGPT", "Google Gemini", "Claude", "Custom (in-house)", "None / Unapproved"],
    default=(TEST_DATA.get('approved_ai_tools', []) if dev else []),
    help="Approved AI assistants or models in use."
)

shadow_ai_opts = ["Select Shadow AI Monitoring...", "None", "Planned", "Enabled"]
shadow_ai_monitoring = st.selectbox(
    "Shadow AI Monitoring",
    shadow_ai_opts,
    index=(shadow_ai_opts.index(TEST_DATA.get('shadow_ai_monitoring', 'None')) if dev else 0),
    help="Discovery and control of unsanctioned AI usage."
)

ai_dlp_controls = st.multiselect(
    "AI Data Loss Controls",
    ["Microsoft Purview DLP", "Defender for Cloud Apps (CASB)", "CASB/SSE (Netskope)", "Proxy controls", "None"],
    default=(TEST_DATA.get('ai_dlp_controls', []) if dev else []),
    help="Controls applied to prompts/responses and AI interactions."
)

st.divider()

## --- SECURITY CULTURE CALCULATOR ---
st.markdown("### 🧮 Security Culture Calculator")
        

    VERIFICATION:
        /bin/sh -c "grep -n '\#\#\# 🤖 AI Usage & Governance' app.py; grep -n '\#\#\# 🧮 Security Culture Calculator' app.py && echo Action2_OK"
