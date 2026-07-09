# catalog.py

PLANET_IT_PORTFOLIO = {
    "Managed_Detection_and_Response": [
        {
            "vendor": "Sophos MDR",
            "category": "Managed Security Operations (SOC) — AI-Native Cyber Defense System",
            "tier": "SME to Enterprise (Standard Default)",
            "recommended_for_domains": ["Security Operations & Response (SecOps)"],
            "trigger_conditions": ["No 24/7 internal SOC", "Lack of dedicated threat hunters", "Small IT team"],
            "core_features": [
                "24/7/365 Human-led Threat Hunting",
                "Agentic AI-led Continuous Threat Hunting",
                "Automated Remediation & SOAR Playbooks",
                "Third-party Telemetry Integration",
                "Secureworks Counter Threat Unit Intelligence",
                "Vendor-Agnostic Email Monitoring (EMS)",
                "Expanded Two-Way Third-Party Response Actions",
                "Next-Gen SIEM Add-On (Compliance Retention 1–10 Years)"
            ],
            "planet_it_value_add": "24/7 human-led threat hunting powered by the Sophos AI-Native Cyber Defense System, where endpoint, network, email, cloud, identity, SIEM, threat intelligence, and MDR operate as one system within Sophos Central. Includes agentic AI-led continuous threat hunting, SOAR automation playbooks, vendor-agnostic email monitoring (EMS), and thousands of additional detectors from the Secureworks Counter Threat Unit. Triaged and escalated by Planet IT's security operations team. Recommended as the foundational security operations capability for organisations lacking an internal 24/7 SOC function."
        },
        {
            "vendor": "Sophos MDR Plus",
            "category": "Managed Security Operations (SOC) — Full IR Included",
            "tier": "SME to Enterprise (Full Incident Response)",
            "recommended_for_domains": ["Security Operations & Response (SecOps)"],
            "trigger_conditions": ["No 24/7 internal SOC", "Need full-scale incident response included", "Require dedicated IR lead"],
            "core_features": [
                "Everything in Sophos MDR",
                "Full-Scale Incident Response Included",
                "Dedicated Incident Response Lead",
                "Root Cause Analysis (RCA)",
                "Direct Call-In Support During Active Incidents",
                "Sophos Breach Protection Warranty (up to $1M)"
            ],
            "planet_it_value_add": "All the capabilities of Sophos MDR plus full-scale incident response with a dedicated IR lead, root cause analysis, and direct call-in support—all included as part of the service. Powered by the Sophos AI-Native Cyber Defense System. Planet IT manages deployment, tuning, and ongoing operational oversight, ensuring the client benefits from both proactive threat hunting and comprehensive reactive IR without separate retainer costs."
        },
        {
            "vendor": "Microsoft Defender Experts for XDR",
            "category": "Managed Threat Hunting (Microsoft Ecosystem)",
            "tier": "Enterprise (Microsoft E5 Required)",
            "recommended_for_domains": ["Security Operations & Response (SecOps)"],
            "trigger_conditions": ["Existing Microsoft E5 estate", "Heavily invested in Azure Sentinel / Microsoft XDR", "Need Microsoft-native threat hunting"],
            "core_features": ["Managed Threat Hunting on Microsoft XDR Telemetry", "Azure Sentinel SIEM Integration", "Microsoft DART Escalation Pathway"],
            "planet_it_value_add": "Planet IT enhances Microsoft Defender Experts coverage with cross-vendor telemetry integration (firewalls, network, non-Microsoft identity) and foundational operational hygiene management—capabilities the Microsoft-native service does not address. Recommended for organisations with deep Microsoft E5 investment requiring a managed bridge between Microsoft and non-Microsoft security layers."
        },
        {
            "vendor": "Adlumin MDR",
            "category": "Vendor-Agnostic SIEM/SOAR MDR",
            "tier": "SME to Mid-Market (Transparent Co-Managed)",
            "recommended_for_domains": ["Security Operations & Response (SecOps)"],
            "trigger_conditions": ["Multi-vendor stack in place", "Need native SIEM and automated compliance reporting", "Desire co-managed transparency"],
            "core_features": [
                "Cloud SIEM/SOAR foundation (vendor-agnostic)",
                "AI-driven automation playbooks (70%+ routine alert handling)",
                "Full client access to the same dashboard and raw SIEM logs",
                "Native UEBA, vulnerability scanning, darknet monitoring",
                "Automated compliance reporting templates (e.g., PCI, HIPAA)"
            ],
            "planet_it_value_add": "Planet IT deploys and tunes Adlumin as a transparent, co-managed SOC platform layered over the client’s existing tools, enabling rapid time-to-value without rip-and-replace. Strong fit for clients prioritising SIEM-native reporting and predictable, SIEM-inclusive MDR costs."
        }
    ],
    "Endpoint_and_Server_Security": [
        {
            "vendor": "Sophos Intercept X Advanced with XDR (→ XDR powered by Secureworks)",
            "category": "Next-Gen Endpoint Protection — AI-Native Cyber Defense System",
            "tier": "Enterprise ONLY (with in-house 24/7 SOC)",
            "recommended_for_domains": ["Endpoint & Server Security"],
            "trigger_conditions": ["Client has their own 24/7 SOC team", "Client requires raw data lake access"],
            "core_features": [
                "Cross-Product XDR",
                "Data Lake Queries",
                "Live Response",
                "AI Detection Analysis",
                "SOAR Automation Playbooks",
                "Custom Rule Builder",
                "Vendor-Agnostic Email Monitoring (EMS) Included",
                "Secureworks Counter Threat Unit Detectors"
            ],
            "planet_it_value_add": "Agent deployment and tuning are managed by Planet IT, with the client assuming 24/7 operational responsibility. Powered by the Sophos AI-Native Cyber Defense System, the enhanced XDR solution provides a superior analyst experience via the new Security Operations interface in Sophos Central, thousands of additional detectors from Secureworks, SOAR automation playbooks, and vendor-agnostic email monitoring. Recommended only where an established internal SOC function exists to manage the data lake."
        }
    ],
    "Network_and_Edge_Security": [
        {
            "vendor": "Sophos Firewall",
            "category": "Next-Gen Firewall (NGFW)",
            "tier": "SME to Mid-Market",
            "recommended_for_domains": ["Network & Cloud Perimeter"],
            "trigger_conditions": ["Consolidated stack desired", "Under 1000 users"],
            "core_features": ["Xstream Architecture", "Synchronized Security", "Deep Packet Inspection"],
            "planet_it_value_add": "Unified management via Sophos Central provides consolidated visibility, policy orchestration, and synchronised threat intelligence across the entire security fabric."
        },
        {
            "vendor": "Fortinet FortiGate",
            "category": "Enterprise Secure SD-WAN & NGFW",
            "tier": "Enterprise (1000+ Users)",
            "recommended_for_domains": ["Network & Cloud Perimeter"],
            "trigger_conditions": ["Enterprise scale", "Advanced SD-WAN requirements", "Existing Fortinet footprint"],
            "core_features": ["Purpose-built ASICs for high throughput", "Native Secure SD-WAN"],
            "planet_it_value_add": "Enterprise-grade SD-WAN and NGFW architecture designed and implemented by Planet IT for complex routing and highly available edge clusters."
        },
        {
            "vendor": "Sophos ZTNA (Zero Trust Network Access)",
            "category": "Secure Remote Access",
            "tier": "All Sizes",
            "recommended_for_domains": ["Network & Cloud Perimeter", "Supply Chain & Third-Party Risk"],
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
            "recommended_for_domains": ["Email & Data Protection"],
            "trigger_conditions": ["M365 environment", "Standard compliance"],
            "core_features": ["Post-delivery quarantine", "Predictive cloud sandboxing"],
            "planet_it_value_add": "Consolidated telemetry feeds email threat data directly into the Sophos data lake for cross-product correlation and automated response."
        },
        {
            "vendor": "Mimecast",
            "category": "Advanced Email & Collaboration Security",
            "tier": "Enterprise & Regulated",
            "recommended_for_domains": ["Email & Data Protection"],
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
            "recommended_for_domains": ["Identity & Access Management (IAM)"],
            "trigger_conditions": ["Using Microsoft Entra ID or Okta", "Lack of visibility into compromised credentials"],
            "core_features": ["Active Directory telemetry correlation", "Compromised credential detection", "Anomalous authentication alerting"],
            "planet_it_value_add": "Identity provider integration into Sophos MDR enables real-time detection of credential-based attacks, with Active Directory telemetry correlation and anomalous authentication alerting."
        },
        {
            "vendor": "Microsoft 365 Business Premium / E5",
            "category": "Identity Licensing Architecture",
            "tier": "All Sizes",
            "recommended_for_domains": ["Identity & Access Management (IAM)"],
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
            "recommended_for_domains": [
                "Security Validation & Testing",
                "Governance, Risk & Compliance (GRC)",
                "Supply Chain & Third-Party Risk",
                "Security Operations & Response (SecOps)"
            ],
            "trigger_conditions": ["Never perform vulnerability scanning", "Ad-Hoc scanning only", "Lack of external attack surface visibility"],
            "core_features": ["Continuous External Attack Surface Monitoring (EASM)", "Risk-based vulnerability prioritization", "Tenable integration"],
            "planet_it_value_add": "Continuous discovery and prioritisation of unpatched internet-facing assets via external attack surface monitoring, reducing the window of exploitation before adversaries can act."
        }
    ],
    "Security_Awareness_and_Training": [
        {
            "vendor": "Hoxhunt",
            "category": "Human Risk Management & Security Awareness",
            "tier": "All Sizes",
            "recommended_for_domains": [
                "Identity & Access Management (IAM)",
                "Governance, Risk & Compliance (GRC)"
            ],
            "trigger_conditions": ["High click rates on phishing", "No current training", "Need measurable human risk reduction"],
            "core_features": ["Personalised, Gamified Phishing Simulations", "Real-Time Micro-Training", "Human Risk Scoring & Reporting"],
            "planet_it_value_add": "Deployment and management of Hoxhunt's adaptive human risk platform by Planet IT, delivering personalised phishing simulations and just-in-time micro-training to measurably reduce employee susceptibility to social engineering."
        }
    ],
    "Cloud_Security_and_Posture": [
        {
            "vendor": "Barracuda",
            "category": "Cloud Email & Data Security",
            "tier": "Enterprise",
            "recommended_for_domains": ["Email & Data Protection"],
            "trigger_conditions": ["Regulatory compliance needs", "High-volume email threat protection", "Data loss prevention requirements"],
            "core_features": ["Email threat protection", "Data Loss Prevention (DLP)", "Archiving & eDiscovery"],
            "planet_it_value_add": "Barracuda provides enhanced email security with DLP and compliant archiving, complementing Planet IT's cross-product telemetry and governance."
        }
    ],
    "IT_Operations_and_Resilience": [
        {
            "vendor": "N-able N-central",
            "category": "Remote Monitoring & Patch Management (RMM)",
            "tier": "Mid-Market to Enterprise",
            "recommended_for_domains": ["Endpoint & Server Security"],
            "trigger_conditions": ["Manual patching processes", "Lack of asset visibility"],
            "core_features": ["Automated Patching OS/Third-Party", "Network Topology Mapping"],
            "planet_it_value_add": "Deployment, tuning, and management of the N-central backend by Planet IT for automated patching and asset visibility."
        },
        {
            "vendor": "N-able Cove Data Protection",
            "category": "Backup & Disaster Recovery",
            "tier": "All Sizes",
            "recommended_for_domains": [
                "Email & Data Protection",
                "Operational Resilience & Backup"
            ],
            "trigger_conditions": ["On-premise only backups", "No M365 backup"],
            "core_features": ["Cloud-first architecture", "Automated recovery testing", "M365 & Server Integration"],
            "planet_it_value_add": "Active backup success monitoring and automated recovery testing by Planet IT, ensuring data integrity and rapid restoration capability."
        }
    ],
    "Security_Validation_and_Testing": [
        {
            "vendor": "Sophos Penetration Testing",
            "category": "Security Validation & Testing Services",
            "tier": "All Sizes",
            "recommended_for_domains": ["Security Validation & Testing"],
            "trigger_conditions": ["Compliance-mandated annual testing", "First-time baseline assessment", "New external exposure or major change"],
            "core_features": ["CREST-aligned external & internal testing", "Web App/API testing", "Clear vulnerability reproduction steps"],
            "planet_it_value_add": "Planet IT scopes and coordinates vendor testing, ensuring evidence is captured and remediation is prioritised and tracked to closure across the estate."
        },
        {
            "vendor": "Planet IT Penetration Testing",
            "category": "Security Validation & Testing Services",
            "tier": "SME to Mid-Market",
            "recommended_for_domains": ["Security Validation & Testing"],
            "trigger_conditions": ["No regular testing cadence", "Mergers & Acquisitions", "Critical application release"],
            "core_features": ["External/Internal testing", "Web App/API assessments", "Red team style scenarios by agreement"],
            "planet_it_value_add": "End-to-end testing engagement delivered by Planet IT with a remediation workshop, retest window, and evidence suitable for board and auditor consumption."
        }
    ],
    "Governance_Risk_and_Compliance_Services": [
        {
            "vendor": "Planet IT IR/DR Roundtables",
            "category": "Incident Response & Disaster Recovery Consultancy",
            "tier": "All Sizes",
            "recommended_for_domains": ["Governance, Risk & Compliance (GRC)"],
            "trigger_conditions": ["No formal plan", "Untested plans", "Leadership turnover"],
            "core_features": ["Quarterly tabletop exercises", "RACI and comms tree validation", "Scenario planning mapped to top threats"],
            "planet_it_value_add": "Facilitated roundtables led by Planet IT to validate IR/DR readiness, document decisions, and capture action owners and timelines."
        },
        {
            "vendor": "Planet IT IR/DR Planning Workshop",
            "category": "Incident Response & Disaster Recovery Consultancy",
            "tier": "All Sizes",
            "recommended_for_domains": ["Governance, Risk & Compliance (GRC)"],
            "trigger_conditions": ["Greenfield IR/DR", "Policy refresh required", "Cyber insurance mandate"],
            "core_features": ["IR plan development", "DR runbooks with RTO/RPO mapping", "Quarterly testing schedule"],
            "planet_it_value_add": "Structured workshops to build or refresh IR and DR plans aligned to business RTO/RPO, with deliverables integrated into the client's governance model."
        }
    ]
}