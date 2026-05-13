# catalog.py

PLANET_IT_PORTFOLIO = {
    "Managed_Detection_and_Response": [
        {
            "vendor": "Sophos MDR",
            "category": "Managed Security Operations (SOC)",
            "tier": "All Sizes",
            "trigger_conditions": ["Lack of 24/7 monitoring", "Overstretched IT team", "Need for immediate incident response"],
            "core_features": ["24/7/365 Human-led Threat Hunting", "Automated Remediation", "Third-party Telemetry Integration"],
            "planet_it_value_add": "Planet IT Managed SOC: We act as the overlay and escalation point, tuning the MDR service to your specific operational reality."
        }
    ],
    "Endpoint_and_Server_Security": [
        {
            "vendor": "Sophos Intercept X Advanced with XDR",
            "category": "Next-Gen Endpoint Protection",
            "tier": "All Sizes",
            "trigger_conditions": ["Legacy antivirus in use", "Need for deep forensic visibility", "Ransomware concerns"],
            "core_features": ["Anti-Ransomware (CryptoGuard)", "Deep Learning Malware Detection", "Cross-Product Extended Detection and Response (XDR)"],
            "planet_it_value_add": "Planet IT Deployment & Tuning: We ensure exclusions are perfectly mapped so security does not impact server performance."
        }
    ],
    "Network_and_Edge_Security": [
        {
            "vendor": "Sophos Firewall",
            "category": "Next-Gen Firewall (NGFW)",
            "tier": "SME to Mid-Market",
            "trigger_conditions": ["Consolidated stack desired", "Need for Synchronized Security"],
            "core_features": ["Xstream Architecture", "Synchronized Security", "Deep Packet Inspection"],
            "planet_it_value_add": "Unified Management: Seamless integration with the Sophos Central dashboard for singular visibility."
        },
        {
            "vendor": "Fortinet FortiGate",
            "category": "Enterprise Secure SD-WAN & NGFW",
            "tier": "Enterprise (1000+ Users)",
            "trigger_conditions": ["Enterprise scale", "Advanced SD-WAN requirements", "Existing Fortinet footprint"],
            "core_features": ["Purpose-built ASICs for high throughput", "Native Secure SD-WAN", "Advanced Routing Protocols"],
            "planet_it_value_add": "Planet IT Enterprise Architecture: We design and implement complex routing and highly available edge clusters."
        }
    ],
    "Email_Security": [
        {
            "vendor": "Sophos Email",
            "category": "Cloud Email Security",
            "tier": "SME to Mid-Market",
            "trigger_conditions": ["M365 environment", "Desire for single-pane-of-glass management"],
            "core_features": ["Post-delivery quarantine", "Predictive cloud sandboxing", "Native M365 API integration"],
            "planet_it_value_add": "Consolidated Telemetry: Directly feeds email threat data into your Sophos XDR/MDR data lake."
        },
        {
            "vendor": "Mimecast",
            "category": "Advanced Email & Collaboration Security",
            "tier": "Enterprise & Regulated",
            "trigger_conditions": ["Finance, Healthcare, Legal", "Strict compliance needs", "Advanced eDiscovery required"],
            "core_features": ["7-year Immutable Archiving", "Targeted Threat Protection", "Continuity (Always-on email)"],
            "planet_it_value_add": "Planet IT Compliance Mapping: We align your retention and archiving policies with industry-specific regulatory standards."
        }
    ],
    "IT_Operations_and_Resilience": [
        {
            "vendor": "N-able N-central",
            "category": "Remote Monitoring & Patch Management (RMM)",
            "tier": "Mid-Market to Enterprise (Co-Managed IT)",
            "trigger_conditions": ["Manual patching processes", "Lack of asset visibility", "Overworked in-house IT team"],
            "core_features": ["Automated Patching OS/Third-Party", "Network Topology Mapping", "Proactive Alerting & Self-Healing Scripts"],
            "planet_it_value_add": "Planet IT Co-Managed IT Service: We deploy, tune, and manage the N-central backend so your team can focus on user support."
        },
        {
            "vendor": "N-able Cove Data Protection",
            "category": "Backup & Disaster Recovery",
            "tier": "All Sizes",
            "trigger_conditions": ["On-premise only backups", "No M365 backup", "Untested recovery plans"],
            "core_features": ["Cloud-first architecture", "Automated recovery testing", "M365 & Server Integration", "Ransomware-safe immutable storage"],
            "planet_it_value_add": "Planet IT Managed BaaS (Backup as a Service): We actively monitor backup success and perform routine recovery drills."
        }
    ]
}