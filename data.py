# data.py

# ==========================================
# THREAT SIMULATOR DATA
# ==========================================
ATTACK_VECTORS = [
    "Highly targeted spear-phishing campaign using a malicious PDF attachment (T1566.001)",
    "Adversary-in-the-Middle (AiTM) proxy attack defeating standard MFA via a fake login page (T1556)",
    "Voice Phishing (Vishing) the IT Helpdesk to fraudulently reset a user's MFA device (T1566.004)",
    "Social engineering via LinkedIn/Slack delivering a malicious payload disguised as a resume (T1566.003)",
    "Spear-phishing utilising HTML Smuggling to deliver a malicious ISO archive bypassing email filters (T1027.006)",
    "QR Code Phishing (Quishing) evading URL inspection by routing mobile devices to a credential proxy (T1566)",
    "Drive-by compromise via SEO poisoning (Malvertising) directing a user to a trojanised software installer (T1189)",
    "Exploitation of a zero-day vulnerability in a public-facing web application (T1190)",
    "Exploitation of an unpatched, legacy VPN appliance leading to internal access (T1133)",
    "Password spraying attack against legacy authentication protocols lacking MFA enforcement (T1110.003)",
    "Default credentials left active on an internet-facing IoT or edge network device (T1078.001)",
    "Brute-force dictionary attack against an unintentionally exposed RDP jump server (T1110.001)",
    "Compromised third-party IT contractor / Supply Chain Compromise via remote access tools (T1195)",
    "Malicious update pushed through a compromised third-party software vendor (T1195.002)",
    "Abuse of compromised Managed Service Provider (MSP) remote monitoring tools (T1195)",
    "Compromised Cloud Infrastructure via hardcoded API keys accidentally leaked on GitHub (T1078.004)",
    "Session hijacking via stolen browser cookies purchased on the dark web, bypassing MFA entirely (T1539)",
    "MFA Fatigue (Push Bombing) attack against a senior executive's compromised credentials (T1621)",
    "Illicit consent grant via a malicious Microsoft 365 / Google Workspace OAuth application (T1528)",
    "Malicious insider abusing legitimate administrative privileges to disable security tooling (T1078.003)",
    "Physical 'USB Drop' attack in the company parking lot leading to a reverse shell beacon (T1200)"
]

SIMULATED_OSINT = {
    "Fortinet": ["Active exploitation of FortiOS SSL-VPN vulnerabilities (e.g., CVE-2023-27997) to deploy custom implants."],
    "Palo Alto": ["Rising trend of threat actors exploiting unpatched PAN-OS GlobalProtect interfaces (e.g., CVE-2024-3400)."],
    "Cisco": ["Exploitation of AnyConnect and IOS XE zero-days (e.g., CVE-2023-20198), leading to privilege escalation."],
    "Check Point": ["Targeted attacks exploiting Check Point Security Gateway vulnerabilities (e.g., CVE-2024-24919)."],
    "Sophos": ["Attacker scans revealed edge protection was active; actors shifted focus to identity-based attacks."],
    "CrowdStrike": ["Adversaries utilising custom bootloaders and kernel-level drivers (BYOVD) to blind Falcon sensors."],
    "Microsoft Defender": ["Reliance on 'Living off the Land' (LotL) techniques to evade standard Defender ASR rules."],
    "SentinelOne": ["Threat actors utilising highly obfuscated, fragmented shellcode to evade behavioural AI engines."],
    "Okta": ["Surge in highly sophisticated AiTM phishing kits capturing session cookies (Reference: CISA Advisory AA23-320A)."],
    "Microsoft Entra ID (Azure AD)": ["Widespread MFA fatigue attacks combined with localised brute-forcing."],
    "Mimecast": ["Increase in Quishing (QR Code Phishing) bypassing Mimecast's URL rewriting."],
    "Proofpoint": ["Threat actors leveraging evasive PDF documents containing embedded malicious links."],
    "AWS": ["Exploitation of overly permissive IAM roles via SSRF vulnerabilities on public-facing EC2 instances."],
    "Microsoft Azure": ["Abuse of Azure Automation Runbooks to pivot laterally across the Azure environment."],
    "GCP": ["Targeting of exposed service account keys embedded in developer repositories."]
}

# ==========================================
# VCISO STRATEGIC ASSESSMENT DATA
# ==========================================
MATURITY_FRAMEWORK = {
    "Level 1 (Ad-Hoc)": "Highly reactive, fragmented tools, unmanaged devices, and no formalised incident response.",
    "Level 2 (Basic)": "Centralised management, signature-based prevention, and basic MFA for critical accounts.",
    "Level 3 (Advanced)": "Behavioural detection (EDR) in place, proactive security policies, but visibility remains siloed.",
    "Level 4 (Optimised)": "Cross-domain telemetry ingestion (XDR), automated containment, and zero-trust principles applied.",
    "Level 5 (Proactive)": "24/7 human-led threat hunting (MDR), Root Cause Analysis (RCA), and a fully integrated ecosystem."
}

ASSESSMENT_DOMAINS = [
    "Endpoint & Server Security",
    "Email & Data Protection",
    "Identity & Access Management (IAM)",
    "Network & Cloud Perimeter",
    "Security Operations & Response (SecOps)",
    "Security Validation & Testing",
    "Governance, Risk & Compliance (GRC)",
    "Operational Resilience & Backup",
    "Supply Chain & Third-Party Risk"
]

RECOMMENDED_SOLUTION_MAP = {
    "Endpoint & Server Security": ["Sophos Intercept X Advanced with XDR"],
    "Email & Data Protection": ["Mimecast Email Security", "N-able Cove Data Protection"],
    "Identity & Access Management (IAM)": ["Sophos ITDR (Identity Threat Detection and Response)", "Sophos Phish Threat"],
    "Network & Cloud Perimeter": ["Sophos Firewall", "Sophos ZTNA", "Sophos Cloud Optix (CSPM)"],
    "Security Operations & Response (SecOps)": ["Sophos MDR Complete (24/7 Threat Hunting & RCA)", "Sophos Managed Risk"],
    "Security Validation & Testing": ["Sophos Managed Risk", "Planet IT Penetration Testing", "Secureworks Tabletop Exercises"],
    "Governance, Risk & Compliance (GRC)": ["Sophos Managed Risk", "Sophos Phish Threat (Awareness Programme)"],
    "Operational Resilience & Backup": ["N-able Cove Data Protection", "Sophos Incident Response Retainer", "Secureworks Tabletop Exercises & IR Preparedness"],
    "Supply Chain & Third-Party Risk": ["Sophos ZTNA", "Sophos Managed Risk"]
}

DEFAULT_VCISO_CONTEXT = """
You are acting as an Enterprise Virtual CISO and Principal Threat Analyst representing a top-tier advisory firm.
Your primary objective is to evaluate client environments, identify critical security gaps, and propose strategic, phased roadmaps. 
You strongly advocate for security consolidation, specifically leveraging the Sophos ecosystem (Sophos MDR, Intercept X, Sophos Firewall, etc.) and Microsoft 365 native security controls.
Always maintain a highly professional, objective, and consultative tone. Use British English formatting.
"""