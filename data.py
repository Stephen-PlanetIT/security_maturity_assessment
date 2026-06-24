# data.py
import os
from typing import Optional, List

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
    "Microsoft Defender Experts": [
        "Attacker dwell time remains significant in Microsoft-only estates where cross-vendor telemetry (firewall, OT, non-Microsoft identity) is not integrated, creating visibility gaps exploited by LOTL techniques."
    ],
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
# GOVERNANCE: Partnership & Tag Catalogue URLs
# ==========================================
# Official governance URLs for partner engagement models. Used to render UI and template context
FULLY_MANAGED_URL = "https://planet-it.example.com/partnerships/fully-managed"
CO_MANAGED_URL = "https://planet-it.example.com/partnerships/co-managed"

def format_governance_narrative(narrative: Optional[str], links: Optional[List[str]]) -> str:
    """Return a consolidated governance narrative with optional bullet links.

    This helper centralises governance narrative assembly for VCISO outputs.

    - If a narrative exists, it will be used as the base.
    - If links are provided, they will be rendered as a bullet list to facilitate
      Word rendering where bullets are supported. If the rendering backend does not
      support bullets, the links will be joined with semicolons.
    """
    parts: List[str] = []
    if narrative:
        parts.append(narrative.strip())
    if links:
        try:
            bullets = "\n".join([f"• {l}" for l in list(links)])
            parts.append(bullets)
        except Exception:
            # Fallback: semicolon-delimited in case of rendering limitations
            parts.append("; ".join(list(links)))
    return "\n\n".join(parts).strip()

# ==========================================
# VCISO STRATEGIC ASSESSMENT DATA
# ==========================================

def derive_risk_adjustment(risk_level: int) -> float:
    """Return a conservative adjustment factor based on risk level.

    - 1 (low) -> 0.9
    - 2 (medium) -> 1.0
    - 3 (high) -> 1.15
    """
    if risk_level == 1:
        return 0.9
    if risk_level == 2:
        return 1.0
    if risk_level == 3:
        return 1.15
    return 1.0


def estimate_cost_of_inaction_gbp(risk_level: int, workforce_size: int = 50, industry_multiplier: float = 1.0):
    """Estimate the yearly GBP cost of inaction for a given risk level.

    - risk_level: 1 (low), 2 (medium), 3 (high)
    - workforce_size: number of employees to scale the baseline up with. Default 50.
    - industry_multiplier: contextual multiplier to reflect industry factors.

    Returns MonetaryCostGBP object.
    The value is kept deliberately conservative to avoid over-estimation.
    """
    # Base costs by risk level
    base_costs = {1: 1000, 2: 5000, 3: 15000}
    base = base_costs.get(int(risk_level), 1000)

    # Scale with workforce and context, then apply a conservative adjustment
    scale = max(1.0, float(workforce_size) / 50.0)
    amount = base * scale * float(industry_multiplier) * derive_risk_adjustment(int(risk_level))

    # Prevent over-estimation
    cap = 1_000_000
    if amount > cap:
        amount = cap

    from prompts import MonetaryCostGBP
    return MonetaryCostGBP(
        amount_gbp=round(amount, 2),
        source="Industry baselines (UK), adjusted for workforce and context",
        rationale="Conservative middle-ground estimate; avoids over-estimation; uses real-world baselines."
    )
MATURITY_FRAMEWORK = {
    "Phase 1: Reactive Cybersecurity (Don't Be Here)": "Basic controls (Anti-Virus, Backup & Recovery, MFA, Firewalls, Log Collection). Focused on baseline compliance like Cyber Essentials. Highly vulnerable to modern threats.",
    "Phase 2: Proactive Cybersecurity": "Advanced tooling and managed services (EDR, XDR, MDR, SIEM, Penetration Testing, Security Awareness Training). Aligns with CE+ and ISO:27001.",
    "Phase 3: Adaptive Cybersecurity (Be Here)": "Automated and intelligence-led (Zero-Trust Architecture, SOAR, Proactive Threat Hunting, Automated Disaster Recovery, Microsegmentation)."
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

def _build_solution_map():
    """Auto-generate RECOMMENDED_SOLUTION_MAP from PLANET_IT_PORTFOLIO.
    
    Each product's 'recommended_for_domains' field declares which assessment
    domains it serves. This function scans all products and builds the map
    automatically, so adding a product to catalog.py is the only step needed.
    """
    from catalog import PLANET_IT_PORTFOLIO
    solution_map = {}
    for products in PLANET_IT_PORTFOLIO.values():
        for product in products:
            for domain in product.get("recommended_for_domains", []):
                solution_map.setdefault(domain, []).append(product["vendor"])
    return solution_map

RECOMMENDED_SOLUTION_MAP = _build_solution_map()

# ==========================================
# KNOWLEDGE BASE — LOADED FROM DISK
# ==========================================

def _load_mdr_context():
    """Load and condense the MDR operations knowledge base from context.txt."""
    ctx_path = os.path.join(os.path.dirname(__file__), "context.txt")
    try:
        with open(ctx_path, "r") as f:
            text = f.read()
        # Condense to ~500 words by taking the first meaningful paragraphs
        lines = text.split('\n')
        condensed = []
        word_count = 0
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('Table of Contents') or stripped.startswith(' '):
                continue
            words = stripped.split()
            if word_count + len(words) > 500:
                break
            condensed.append(stripped)
            word_count += len(words)
        return ' '.join(condensed)
    except FileNotFoundError:
        return "MDR context file not available."


def _serialise_portfolio():
    """Build a compact Markdown reference table from PLANET_IT_PORTFOLIO."""
    # Import here to avoid circular dependency at module level
    from catalog import PLANET_IT_PORTFOLIO
    
    lines = ["## Planet IT Solution Portfolio", ""]
    for category_key, products in PLANET_IT_PORTFOLIO.items():
        category_name = category_key.replace('_', ' ')
        lines.append(f"### {category_name}")
        for product in products:
            vendor = product['vendor']
            tier = product['tier']
            value = product['planet_it_value_add']
            features = "; ".join(product['core_features'])
            triggers = "; ".join(product['trigger_conditions'])
            lines.append(f"- **{vendor}** (Tier: {tier})")
            lines.append(f"  - Features: {features}")
            lines.append(f"  - Best for: {triggers}")
            lines.append(f"  - Value: {value}")
        lines.append("")
    return '\n'.join(lines)


# Load MDR context at module import time
LOADED_MDR_CONTEXT = _load_mdr_context()

# Build the portfolio reference table at module import time
PORTFOLIO_KNOWLEDGE = _serialise_portfolio()

# ==========================================
# MASTER VCISO CONTEXT (Knowledge-Injected)
# ==========================================
DEFAULT_VCISO_CONTEXT = f"""
You are acting as an Enterprise Virtual CISO and Principal Threat Analyst representing a top-tier advisory firm.
Your primary objective is to evaluate client environments, identify critical security gaps, and propose strategic, phased roadmaps. 
You strongly advocate for security consolidation, specifically leveraging the Sophos ecosystem (Sophos MDR, Intercept X, Sophos Firewall, etc.) and Microsoft 365 native security controls.
Always maintain a highly professional, objective, and consultative tone. Use British English formatting.

### MDR Operations Knowledge Base
{LOADED_MDR_CONTEXT}

### Authorised Solution Portfolio
{PORTFOLIO_KNOWLEDGE}

When generating domain assessments and roadmap recommendations, reference the Authorised Solution Portfolio above to recommend specific products. Match the product tier to the client's size and environment. Always explain why a specific product is appropriate for the client's context.
"""