# catalog.py

PLANET_IT_PORTFOLIO = {
    "Managed_Detection_and_Response": [
        {
            "vendor": "Sophos MDR",
            "category": "Managed Security Operations (SOC)",
            "tier": "SME to Enterprise (Standard Default)",
            "trigger_conditions": ["No 24/7 internal SOC", "Lack of dedicated threat hunters", "Small IT team"],
            "core_features": ["24/7/365 Human-led Threat Hunting", "Automated Remediation", "Third-party Telemetry Integration"],
            "planet_it_value_add": "24/7 human-led threat hunting with automated remediation, triaged and escalated by Planet IT's security operations team. Recommended as the foundational security operations capability for organisations lacking an internal 24/7 SOC function."
        }
    ],
    "Endpoint_and_Server_Security": [
        {
            "vendor": "Sophos Intercept X Advanced with XDR",
            "category": "Next-Gen Endpoint Protection",
            "tier": "Enterprise ONLY (with in-house 24/7 SOC)",
            "trigger_conditions": ["Client has their own 24/7 SOC team", "Client requires raw data lake access"],
            "core_features": ["Cross-Product XDR", "Data Lake Queries", "Live Response"],
            "planet_it_value_add": "Agent deployment and tuning are managed by Planet IT, with the client assuming 24/7 operational responsibility. Recommended only where an established internal SOC function exists to manage the data lake."
        }
    ],
    "Network_and_Edge_Security": [
        {
            "vendor": "Sophos Firewall",
            "category": "Next-Gen Firewall (NGFW)",
            "tier": "SME to Mid-Market",
            "trigger_conditions": ["Consolidated stack desired", "Under 1000 users"],
            "core_features": ["Xstream Architecture", "Synchronized Security", "Deep Packet Inspection"],
            "planet_it_value_add": "Unified management via Sophos Central provides consolidated visibility, policy orchestration, and synchronised threat intelligence across the entire security fabric."
        },
        {
            "vendor": "Fortinet FortiGate",
            "category": "Enterprise Secure SD-WAN & NGFW",
            "tier": "Enterprise (1000+ Users)",
            "trigger_conditions": ["Enterprise scale", "Advanced SD-WAN requirements", "Existing Fortinet footprint"],
            "core_features": ["Purpose-built ASICs for high throughput", "Native Secure SD-WAN"],
            "planet_it_value_add": "Enterprise-grade SD-WAN and NGFW architecture designed and implemented by Planet IT for complex routing and highly available edge clusters."
        },
        {
            "vendor": "Sophos ZTNA (Zero Trust Network Access)",
            "category": "Secure Remote Access",
            "tier": "All Sizes",
            "trigger_conditions": ["Hybrid or Remote workforce", "Replacing legacy VPNs"],
            "core_features": ["Clientless & Client-based Access", "Identity-based micro-segmentation"],
            "planet_it_value_add": "Transition from perimeter-based VPNs to identity-driven Zero Trust architectures, enabling secure, clientless access to internal resources."
        }
    ],
    "Email_Security": [
        {
            "vendor": "Sophos Email",
            "category": "Cloud Email Security",
            "tier": "SME to Mid-Market",
            "trigger_conditions": ["M365 environment", "Standard compliance"],
            "core_features": ["Post-delivery quarantine", "Predictive cloud sandboxing"],
            "planet_it_value_add": "Consolidated telemetry feeds email threat data directly into the Sophos data lake for cross-product correlation and automated response."
        },
        {
            "vendor": "Mimecast",
            "category": "Advanced Email & Collaboration Security",
            "tier": "Enterprise & Regulated",
            "trigger_conditions": ["Finance, Healthcare, Legal", "Strict compliance needs"],
            "core_features": ["7-year Immutable Archiving", "Targeted Threat Protection"],
            "planet_it_value_add": "Compliance-aligned retention policies mapped to industry-specific regulatory standards, with 7-year immutable archiving for e-discovery and legal hold requirements."
        }
    ],
    "Identity_and_Access_Management": [
        {
            "vendor": "Sophos ITDR (Identity Threat Detection and Response)",
            "category": "Identity Security & Telemetry",
            "tier": "All Sizes",
            "trigger_conditions": ["Using Microsoft Entra ID or Okta", "Lack of visibility into compromised credentials"],
            "core_features": ["Active Directory telemetry correlation", "Compromised credential detection", "Anomalous authentication alerting"],
            "planet_it_value_add": "Identity provider integration into Sophos MDR enables real-time detection of credential-based attacks, with Active Directory telemetry correlation and anomalous authentication alerting."
        },
        {
            "vendor": "Microsoft 365 Business Premium / E5",
            "category": "Identity Licensing Architecture",
            "tier": "All Sizes",
            "trigger_conditions": ["Using Basic/Standard M365", "Need Conditional Access"],
            "core_features": ["Entra ID P1/P2 (Conditional Access)", "Intune (MDM/MAM)"],
            "planet_it_value_add": "Licensing optimisation and Conditional Access policy configuration to enforce strict identity-based access controls and device management."
        }
    ],
    "Vulnerability_and_Exposure_Management": [
        {
            "vendor": "Sophos Managed Risk",
            "category": "Attack Surface Management",
            "tier": "All Sizes",
            "trigger_conditions": ["Never perform vulnerability scanning", "Ad-Hoc scanning only", "Lack of external attack surface visibility"],
            "core_features": ["Continuous External Attack Surface Monitoring (EASM)", "Risk-based vulnerability prioritization", "Tenable integration"],
            "planet_it_value_add": "Continuous discovery and prioritisation of unpatched internet-facing assets via external attack surface monitoring, reducing the window of exploitation before adversaries can act."
        }
    ],
    "Security_Awareness_and_Training": [
        {
            "vendor": "Sophos Phish Threat",
            "category": "User Awareness Testing",
            "tier": "All Sizes",
            "trigger_conditions": ["High click rates on phishing", "No current training"],
            "core_features": ["Automated Phishing Simulations", "Integrated training modules"],
            "planet_it_value_add": "Quarterly, customised phishing simulation campaigns with integrated just-in-time training modules to measurably reduce employee susceptibility to social engineering attacks."
        }
    ],
    "Cloud_Security_and_Posture": [
        {
            "vendor": "Sophos Cloud Optix",
            "category": "Cloud Security Posture Management (CSPM)",
            "tier": "Cloud-Native & Hybrid Environments",
            "trigger_conditions": ["AWS, Azure, or GCP footprint", "Complex cloud infrastructure (Kubernetes, Serverless)"],
            "core_features": ["Automated compliance checks", "IAM privilege analysis"],
            "planet_it_value_add": "Translation of Cloud Optix alerts into actionable remediation steps, with automated compliance checks and IAM privilege analysis for cloud-native environments."
        }
    ],
    "IT_Operations_and_Resilience": [
        {
            "vendor": "N-able N-central",
            "category": "Remote Monitoring & Patch Management (RMM)",
            "tier": "Mid-Market to Enterprise",
            "trigger_conditions": ["Manual patching processes", "Lack of asset visibility"],
            "core_features": ["Automated Patching OS/Third-Party", "Network Topology Mapping"],
            "planet_it_value_add": "Deployment, tuning, and management of the N-central backend by Planet IT for automated patching and asset visibility."
        },
        {
            "vendor": "N-able Cove Data Protection",
            "category": "Backup & Disaster Recovery",
            "tier": "All Sizes",
            "trigger_conditions": ["On-premise only backups", "No M365 backup"],
            "core_features": ["Cloud-first architecture", "Automated recovery testing", "M365 & Server Integration"],
            "planet_it_value_add": "Active backup success monitoring and automated recovery testing by Planet IT, ensuring data integrity and rapid restoration capability."
        }
    ]
}