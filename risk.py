"""
risk.py — Monte Carlo risk simulation for the Cybersecurity Maturity Assessment.

Design goals:
- Zero schema changes: consumes existing client_inputs and report_data (with radar_chart_data)
- Configuration via get_config: iterations, base event rate, default impact if not supplied by report
- Small, dependency‑light. Uses Python's random; NumPy optional but not required
- British English wording in any human‑readable text

Outputs a dict with:
    {
        'iterations': int,
        'breach_probability': float,              # 0–1
        'breach_probability_pct': float,          # 0–100
        'aal_gbp': float,                         # annualised average loss
        'p50_gbp': float,
        'p90_gbp': float,
        'p95_gbp': float,
        'assumptions': List[str],
        'summary': str
    }
"""

from typing import Any, Dict, List, Optional
import math
import random

try:
    import numpy as _np  # optional; used for percentiles if available
except Exception:  # pragma: no cover
    _np = None

from config import get_config


_DOMAIN_WEIGHTS: Dict[str, float] = {
    # Aligns with export.MATURITY_WEIGHTS for coherence (sums ≈ 1.0)
    # Identity
    "iam": 0.10,
    "privileged_access": 0.07,
    # Endpoint & Network
    "endpoint": 0.10,
    "network": 0.07,
    # Messaging & Cloud
    "email": 0.04,
    "cloud": 0.09,
    # SaaS & Data
    "saas": 0.06,
    "data_security": 0.07,
    # Operations & Assurance
    "secops": 0.12,
    "testing": 0.04,
    "supplier": 0.05,
    "resilience": 0.07,
    "culture": 0.05,
    "grc": 0.04,
    "ai": 0.03,
}


def _safe_radar_scores(report_data: Any) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    data = getattr(report_data, "radar_chart_data", None)
    if data is None:
        return scores
    try:
        if hasattr(data, "model_dump"):
            scores = dict(data.model_dump())
        elif isinstance(data, dict):
            scores = dict(data)
    except Exception:
        scores = {}
    # Coerce and clamp (respect 1–3 cap but allow 0 defensively)
    out: Dict[str, float] = {}
    for k, v in scores.items():
        try:
            f = float(v)
        except Exception:
            f = 1.0
        if f < 0:
            f = 0.0
        if f > 3:
            f = 3.0
        out[str(k)] = f
    return out


def _default_impact_gbp(report_data: Any) -> float:
    # Prefer LLM‑provided monetary_cost_of_inaction.amount_gbp if available
    try:
        mci = getattr(report_data, "monetary_cost_of_inaction", None)
        if mci is not None:
            amt = getattr(mci, "amount_gbp", None)
            if isinstance(amt, (int, float)) and amt >= 0:
                return float(amt)
    except Exception:
        pass
    try:
        return float(get_config("MC_DEFAULT_IMPACT_GBP", 500000))
    except Exception:
        return 500000.0


def _percentile(data: List[float], q: float) -> float:
    if not data:
        return 0.0
    if _np is not None:
        try:
            return float(_np.percentile(data, q))
        except Exception:
            pass
    # Fallback percentile (nearest-rank interpolation)
    s = sorted(data)
    k = (len(s) - 1) * (q / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(s[int(k)])
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return float(d0 + d1)


def run_monte_carlo(client_inputs: Dict[str, Any], report_data: Any, *, iterations: int = 5000, seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Run a simple Monte Carlo simulation of annual loss.

    Probability model:
    - Convert each radar score (1–3) to a vulnerability factor vf in [0,1]: vf = (4 - score) / 3
    - Per‑domain incident prob: p_i = BASE_RATE * weight_i * vf
    - Combined breach prob per iteration: p_any = 1 - Π(1 - p_i)

    Impact model:
    - Triangular(0.5*M, M, 2.0*M), where M is monetary_cost_of_inaction.amount_gbp if provided,
      else MC_DEFAULT_IMPACT_GBP (default 500k)

    Returns summary metrics; does not mutate inputs; does not alter maturity scores.
    """
    try:
        iterations = int(iterations)
    except Exception:
        iterations = 5000

    if iterations <= 0:
        iterations = 1000

    try:
        base_rate = float(get_config("MC_BASE_EVENT_RATE", 0.15))  # 15% annual baseline, apportioned by weights
    except Exception:
        base_rate = 0.15
    # Optional AI governance driver (feature‑flagged)
    try:
        ai_flag = str(get_config("MC_AI_DRIVER_ENABLED", "false")).strip().lower() in ("1","true","yes","on")
        ai_factor = float(get_config("MC_AI_DRIVER_FACTOR", 1.10))
    except Exception:
        ai_flag = False
        ai_factor = 1.10

    if seed is None:
        try:
            s = get_config("MC_RANDOM_SEED")
            seed = int(s) if s is not None else None
        except Exception:
            seed = None
    if seed is not None:
        random.seed(seed)

    scores = _safe_radar_scores(report_data)
    if not scores:
        return {
            "iterations": iterations,
            "breach_probability": 0.0,
            "breach_probability_pct": 0.0,
            "aal_gbp": 0.0,
            "p50_gbp": 0.0,
            "p90_gbp": 0.0,
            "p95_gbp": 0.0,
            "cvar95_gbp": 0.0,
            "assumptions": [
                "No radar scores available; simulation skipped.",
            ],
            "summary": "Monte Carlo simulation skipped due to missing input scores.",
            "explanation": "",
            "drivers": [],
        }

    # Optional AI governance driver: if enabled and AI score is 1, slightly increase base event rate
    if 'ai' in scores:
        try:
            if ai_flag and float(scores.get('ai', 3.0)) <= 1.0:
                base_rate = base_rate * ai_factor
        except Exception:
            pass

    # Build per‑domain probabilities
    probs: Dict[str, float] = {}
    for domain, weight in _DOMAIN_WEIGHTS.items():
        score = float(scores.get(domain, 1.0))
        vf = max(0.0, min(1.0, (4.0 - score) / 3.0))  # 1->1.0 riskier, 3->0.333
        p_i = max(0.0, min(1.0, base_rate * weight * vf))
        probs[domain] = p_i

    # Precompute combined breach probability (used only for reporting sanity)
    prod = 1.0
    for p in probs.values():
        prod *= (1.0 - p)
    p_any_combined = 1.0 - prod

    M = float(_default_impact_gbp(report_data))
    low, mode, high = 0.5 * M, 1.0 * M, 2.0 * M

    losses: List[float] = []
    breaches = 0
    for _ in range(iterations):
        # Simulate breach occurrence
        prod_iter = 1.0
        for p in probs.values():
            prod_iter *= (1.0 - p)
        p_any = 1.0 - prod_iter
        if random.random() < p_any:
            breaches += 1
            # Triangular impact draw (GBP)
            try:
                loss = random.triangular(low, high, mode)
            except Exception:
                # Fallback: simple pert‑like draw
                u = random.random()
                loss = low + (high - low) * (u ** 2)
            losses.append(float(max(0.0, loss)))
        else:
            losses.append(0.0)

    breach_probability = breaches / float(iterations)
    aal = sum(losses) / float(iterations)
    p50 = _percentile(losses, 50)
    p90 = _percentile(losses, 90)
    p95 = _percentile(losses, 95)
    # CVaR (Expected Shortfall) at 95% — mean of worst 5% outcomes
    threshold_95 = p95
    tail_losses = [x for x in losses if x >= threshold_95]
    cvar95 = (sum(tail_losses) / float(len(tail_losses))) if tail_losses else float(threshold_95)

    # Human-readable exposure drivers (top 3 by p_i)
    drivers_sorted = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    drivers_human = [f"{k}: exposure index {v*100:.2f}% (relative breach likelihood contribution)" for k, v in drivers_sorted[:3]]

    assumptions = [
        f"Base annual event rate apportioned by domain weights: {base_rate:.2f}",
        f"Impact model: Triangular(low=£{low:,.0f}, mode=£{mode:,.0f}, high=£{high:,.0f})",
        f"Combined breach probability (analytic): {p_any_combined*100:.1f}%",
        f"Iterations: {iterations}",
    ]

    summary = (
        f"Estimated annual breach probability {breach_probability*100:.1f}% with AAL £{aal:,.0f}; "
        f"P50 £{p50:,.0f}, P90 £{p90:,.0f}, P95 £{p95:,.0f}, CVaR95 £{cvar95:,.0f}."
    )

    explanation = (
        "AAL is the annualised average loss across all simulations, including years with no breach (loss £0). "
        "Percentiles (e.g., P50/P90/P95) are thresholds not exceeded in that share of simulated years. "
        "CVaR95 is the average loss within the worst 5% of simulated years, highlighting tail risk."
    )

    return {
        "iterations": int(iterations),
        "breach_probability": float(breach_probability),
        "breach_probability_pct": float(breach_probability * 100.0),
        "aal_gbp": float(aal),
        "p50_gbp": float(p50),
        "p90_gbp": float(p90),
        "p95_gbp": float(p95),
        "cvar95_gbp": float(cvar95),
        "assumptions": assumptions,
        "summary": summary,
        "explanation": explanation,
        "drivers": drivers_human,
    }
