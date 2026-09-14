__all__ = ["LLMEngine"]
import streamlit as st
import openai
from openai import AzureOpenAI
import time
import random
import logging
from config import get_config, ConfigKey

_logger = logging.getLogger(__name__)


class LLMEngine:
    @staticmethod
    def get_client():
        try:
            # Pre-flight credential validation to surface misconfig quickly
            endpoint = get_config(ConfigKey.AZURE_ENDPOINT)
            api_key = get_config(ConfigKey.AZURE_API_KEY)
            if not endpoint or "your-resource-name" in endpoint or "<your-resource-name>" in endpoint:
                raise ValueError("Azure OpenAI endpoint placeholder. Please set AZURE_OPENAI_ENDPOINT to your real resource URL.")
            if not api_key or "REDACTED" in str(api_key):
                raise ValueError("Azure OpenAI API key placeholder.")
            # Configurable timeout for resilience; default 300s; bounded to 0-600s
            timeout_sec = 300.0
            try:
                timeout_raw = get_config("AZURE_CLIENT_TIMEOUT_SEC", 300.0)
                timeout_sec = float(timeout_raw)
                if timeout_sec <= 0 or timeout_sec > 600:
                    timeout_sec = 300.0
            except Exception:
                timeout_sec = 300.0
            return AzureOpenAI(
                api_key=api_key,
                api_version=get_config(ConfigKey.AZURE_API_VERSION, "2024-02-15-preview"),
                azure_endpoint=endpoint,
                timeout=timeout_sec
            )
        except Exception as e:
            _logger.error("Client initialisation failed: %s", e, exc_info=True)
            st.error("🚨 Unable to initialise the advisory engine. Please check the configuration and try again.")
            return None

    @staticmethod
    def _build_extra_params(streaming: bool = False):
        """Build the extra_params dict for Azure OpenAI.

        When streaming, max_completion_tokens is omitted as the streaming
        protocol handles token limits differently.
        """
        try:
            temp_raw = get_config("AZURE_TEMPERATURE", 0.6)
            temperature = float(temp_raw)
            if temperature < 0.0 or temperature > 1.0:
                temperature = 0.6
        except Exception:
            temperature = 0.6

        extra_params = {
            "temperature": temperature
        }
        if not streaming:
            try:
                # Raise default and remove fixed 8192 clamp; let config drive the limit.
                # Still guard against nonsensical values (<=0). Azure will enforce its own hard caps.
                mct_raw = get_config("AZURE_MAX_COMPLETION_TOKENS", 16384)
                mct = int(mct_raw)
                if mct <= 0:
                    mct = 16384
                # Optional soft ceiling for safety if provided (e.g. 32768)
                try:
                    allowed_max_raw = get_config("AZURE_ALLOWED_MAX_COMPLETION_TOKENS", 32768)
                    allowed_max = int(allowed_max_raw)
                    if allowed_max > 0:
                        mct = min(mct, allowed_max)
                except Exception:
                    pass
            except Exception:
                mct = 16384
            extra_params["max_completion_tokens"] = mct
        return extra_params

    @staticmethod
    def _count_tokens(model: str, text: str) -> int:
        """Approximate token count using tiktoken if available; fallback to len(text)//4."""
        try:
            import tiktoken  # type: ignore
            enc = tiktoken.encoding_for_model(model) if hasattr(tiktoken, "encoding_for_model") else tiktoken.get_encoding("p50k_base")
            return len(enc.encode(text or ""))
        except Exception:
            return max(1, int(len(text or "") / 4))

    @staticmethod
    def _debug_prompt_metrics(model: str, system_persona: str, user_prompt: str, streaming: bool = False):
        """Emit prompt metrics when LLM_DEBUG is enabled via config/secrets."""
        try:
            dbg = str(get_config("LLM_DEBUG", "false")).strip().lower() in ("1","true","yes","on")
        except Exception:
            dbg = False
        if not dbg:
            return
        try:
            sys_toks = LLMEngine._count_tokens(model, system_persona)
            usr_toks = LLMEngine._count_tokens(model, user_prompt)
            total = sys_toks + usr_toks
            mode = "STREAM" if streaming else "STRUCTURED"
            mct = None if streaming else LLMEngine._build_extra_params().get("max_completion_tokens")
            msg = f"LLM DEBUG [{mode}] — system={sys_toks} toks, user={usr_toks} toks, total={total} toks, max_completion_tokens={mct}"
            _logger.info(msg)
            try:
                st.caption(msg)
            except Exception:
                pass
        except Exception:
            _logger.debug("LLM DEBUG: metrics calculation failed", exc_info=True)

    @staticmethod
    def _dbg_phase(label: str):
        """
        Emit a lightweight phase caption when LLM_DEBUG is enabled.
        Safe to call anywhere; no-ops when LLM_DEBUG is false.
        """
        try:
            dbg = str(get_config("LLM_DEBUG", "false")).strip().lower() in ("1", "true", "yes", "on")
        except Exception:
            dbg = False
        if not dbg:
            return
        msg = f"PHASE: {label}"
        _logger.info(msg)
        try:
            st.caption(msg)
        except Exception:
            pass

    @staticmethod
    def generate_structured_report(client, deployment, system_persona, user_prompt, response_model):
        if not client:
            return None
        try:
            extra_params = LLMEngine._build_extra_params()

            # Composite-mode hard defaults (keep concise, consultative output)
            _composite_max_tokens = 900
            _max_para = 2
            _max_chars = 900
            _light_per_domain = True  # always use uniform light enrichment unless lean_mode

            def _local_extra():
                """Lower the token ceiling for composite enrichment calls (hard cap)."""
                loc = dict(extra_params)
                loc["max_completion_tokens"] = _composite_max_tokens
                return loc

            def _clip_text(txt: str) -> str:
                """Clip to a small number of paragraphs and max characters to keep reports concise."""
                try:
                    s = (txt or "").strip()
                    parts = [p.strip() for p in s.split("\n\n") if p.strip()]
                    s = "\n\n".join(parts[:_max_para])
                    if len(s) > _max_chars:
                        s = s[:_max_chars].rsplit(" ", 1)[0].rstrip() + "…"
                    return s
                except Exception:
                    return txt or ""

            def _light_enrich_domain(name: str) -> dict:
                """
                One-shot JSON enrichment for a domain with strict size limits.
                Returns {'analysis': str, 'impact': str, 'remediation': str}.
                """
                LLMEngine._dbg_phase(f"Composite:domain[{name}]_light start")
                _t = time.perf_counter()
                instruction = (
                    f"You are producing concise advisory text for the domain '{name}'. "
                    "British English, consultative, third-person. Avoid first/second person. "
                    "Return strict JSON with keys: analysis (<=120 words, 1 paragraph), "
                    "business_impact (<=90 words, 1 paragraph), remediation_bullets (exactly 3 items, each <=12 words)."
                )
                prompt = f"""{instruction}

CONTEXT (sanitised):
{client_inputs}

Respond ONLY as JSON: {{"analysis":"...","business_impact":"...","remediation_bullets":["...","...","..."]}}"""  # noqa: E501
                try:
                    resp = client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"},
                        **_local_extra()
                    )
                    content = getattr(resp.choices[0].message, "content", "") or ""
                    import json as _json
                    data = {}
                    try:
                        data = _json.loads(content)
                    except Exception:
                        s = str(content)
                        end_idx = s.rfind("}")
                        if end_idx != -1:
                            data = _json.loads(s[:end_idx+1])
                    analysis = _clip_text(str(data.get("analysis", "")))
                    impact = _clip_text(str(data.get("business_impact", "")))
                    bullets = data.get("remediation_bullets", []) or []
                    bullets = [str(b).strip() for b in bullets if str(b).strip()]
                    if len(bullets) > 3:
                        bullets = bullets[:3]
                    paragraph = analysis or _clip_text(f"{name}: Prioritised remediation for measurable uplift.")
                    remediation = paragraph + ("\n" + "\n".join([f"- {b}" for b in bullets]) if bullets else "")
                    LLMEngine._dbg_phase(f"Composite:domain[{name}]_light in {time.perf_counter() - _t:.1f}s")
                    return {"analysis": analysis, "impact": impact, "remediation": remediation}
                except Exception:
                    LLMEngine._dbg_phase(f"Composite:domain[{name}]_light failed")
                    return {"analysis": "", "impact": "", "remediation": ""}

            # Composite-mode hard defaults (keep concise, consultative output)
            _composite_max_tokens = 900
            _max_para = 2
            _max_chars = 900
            try:
                _light_per_domain = str(get_config("COMPOSITE_LIGHT_PER_DOMAIN", "true")).strip().lower() in ("1","true","yes","on")
            except Exception:
                _light_per_domain = True

            def _local_extra():
                """Lower the token ceiling for composite enrichment calls (hard cap)."""
                loc = dict(extra_params)
                loc["max_completion_tokens"] = _composite_max_tokens
                return loc

            def _clip_text(txt: str) -> str:
                """Clip to a small number of paragraphs and max characters to keep reports concise."""
                try:
                    s = (txt or "").strip()
                    parts = [p.strip() for p in s.split("\n\n") if p.strip()]
                    parts = parts[:_max_para]
                    s = "\n\n".join(parts)
                    if len(s) > _max_chars:
                        s = s[:_max_chars].rsplit(" ", 1)[0].rstrip() + "…"
                    return s
                except Exception:
                    return txt or ""

            def _light_enrich_domain(name: str) -> dict:
                """
                One-shot JSON enrichment for a domain with strict size limits.
                Returns {'analysis': str, 'impact': str, 'remediation': str}.
                """
                LLMEngine._dbg_phase(f"Composite:domain[{name}]_light start")
                _t = time.perf_counter()
                instruction = (
                    f"You are producing concise advisory text for the domain '{name}'. "
                    "British English, consultative, third-person. Avoid first/second person. "
                    "Return strict JSON with keys: analysis (<=120 words, 1 paragraph), "
                    "business_impact (<=90 words, 1 paragraph), remediation_bullets (exactly 3 items, each <=12 words)."
                )
                prompt = f"""{instruction}

CONTEXT (sanitised):
{client_inputs}

Respond ONLY as JSON: {{"analysis":"...","business_impact":"...","remediation_bullets":["...","...","..."]}}"""  # noqa: E501
                try:
                    resp = client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"},
                        **_local_extra()
                    )
                    content = getattr(resp.choices[0].message, "content", "") or ""
                    import json as _json
                    data = {}
                    try:
                        data = _json.loads(content)
                    except Exception:
                        s = str(content)
                        end_idx = s.rfind("}")
                        if end_idx != -1:
                            data = _json.loads(s[:end_idx+1])
                    analysis = _clip_text(str(data.get("analysis", "")))
                    impact = _clip_text(str(data.get("business_impact", "")))
                    bullets = data.get("remediation_bullets", []) or []
                    bullets = [str(b).strip() for b in bullets if str(b).strip()]
                    if len(bullets) > 3:
                        bullets = bullets[:3]
                    paragraph = analysis or _clip_text(f"{name}: Prioritised remediation for measurable uplift.")
                    remediation = paragraph + ("\n" + "\n".join([f"- {b}" for b in bullets]) if bullets else "")
                    LLMEngine._dbg_phase(f"Composite:domain[{name}]_light in {time.perf_counter() - _t:.1f}s")
                    return {"analysis": analysis, "impact": impact, "remediation": remediation}
                except Exception:
                    LLMEngine._dbg_phase(f"Composite:domain[{name}]_light failed")
                    return {"analysis": "", "impact": "", "remediation": ""}
            LLMEngine._debug_prompt_metrics(deployment, system_persona, user_prompt, streaming=False)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Use the beta parse path for structured outputs backed by Pydantic models
                    response = client.beta.chat.completions.parse(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format=response_model,
                        **extra_params
                    )
                    # The beta.parse path returns a parsed BaseModel directly when the
                    # response_model is a Pydantic model class.
                    # If available, prefer the parsed attribute; otherwise fall back to content.
                    if hasattr(response.choices[0].message, "parsed"):
                        return response.choices[0].message.parsed
                    return getattr(response.choices[0].message, "content", None)
                except Exception as e:
                    if attempt == max_retries - 1:
                        _logger.error("Structured generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                        st.error("Report generation failed after multiple attempts. Please try again.")
                        return None
                    time.sleep((2 ** attempt))
        except Exception as e:
            _logger.error("LLM structured generation error: %s", e, exc_info=True)
            st.error("An error occurred during report generation. Please try again.")
            return None

    @staticmethod
    def generate_text_report(client, deployment, system_persona, user_prompt, temperature=0.7):
        if not client:
            return None
        try:
            extra_params = LLMEngine._build_extra_params()
            extra_params["temperature"] = temperature
            LLMEngine._debug_prompt_metrics(deployment, system_persona, user_prompt, streaming=False)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": user_prompt}
                        ],
                        **extra_params
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    if attempt == max_retries - 1:
                        _logger.error("Text generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                        st.error("Text generation failed after multiple attempts. Please try again.")
                        return None
                    time.sleep((2 ** attempt))
        except Exception as e:
            _logger.error("LLM text generation error: %s", e, exc_info=True)
            st.error("An error occurred during text generation. Please try again.")
            return None

    @staticmethod
    def generate_text_report_streaming(client, deployment, system_persona, user_prompt, temperature=0.7):
        if not client:
            yield "Error: LLM client not initialised."
            return
        max_retries = 3
        for attempt in range(max_retries):
            try:
                extra_params = LLMEngine._build_extra_params(streaming=True)
                extra_params["temperature"] = temperature
                extra_params["stream"] = True
                LLMEngine._debug_prompt_metrics(deployment, system_persona, user_prompt, streaming=True)
                response = client.chat.completions.create(
                    model=deployment,
                    messages=[
                        {"role": "system", "content": system_persona},
                        {"role": "user", "content": user_prompt}
                    ],
                    **extra_params
                )
                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            yield delta.content
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    _logger.error("Streaming generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                    yield "\n\n[An error occurred during streaming. Please try again.]"
                    return
                time.sleep((2 ** attempt) + random.random())
 
    @staticmethod
    def generate_maturity_report_hybrid(client, deployment, system_persona, user_prompt, response_model):
        """
        Hybrid single-click generator for the Maturity Assessment:
          1) Try historic beta.parse structured path (Pydantic model class).
          2) If it fails (e.g., length/parse issues), use JSON-object response and tolerant last-brace recovery.
        Azure-only constraints preserved via max_completion_tokens; never use max_tokens.
        """
        if not client:
            return None

        # 1) Historic beta.parse path
        try:
            extra_params = LLMEngine._build_extra_params()
            LLMEngine._debug_prompt_metrics(deployment, system_persona, user_prompt, streaming=False)
            response = client.beta.chat.completions.parse(
                model=deployment,
                messages=[
                    {"role": "system", "content": system_persona},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=response_model,
                **extra_params
            )
            if hasattr(response.choices[0].message, "parsed"):
                return response.choices[0].message.parsed
        except Exception:
            pass

        # 2) JSON-object path with tolerant recovery
        try:
            extra_params = LLMEngine._build_extra_params()
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": system_persona},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                **extra_params
            )
            content = getattr(response.choices[0].message, "content", None)
            if content and str(content).strip():
                try:
                    parsed = response_model.model_validate_json(content)
                    return parsed
                except Exception:
                    s = str(content)
                    end_idx = s.rfind("}")
                    if end_idx != -1:
                        recovered = s[:end_idx + 1]
                        try:
                            parsed = response_model.model_validate_json(recovered)
                            return parsed
                        except Exception:
                            pass
        except Exception:
            pass

        _logger.error("Maturity generation failed after hybrid strategies.")
        st.error("Maturity generation failed after hybrid strategies.")
        return None
 
    @staticmethod
    def generate_maturity_report_json_monolithic(client, deployment, system_persona, user_prompt, response_model):
        """
        Robust monolithic generation for Maturity Assessment: use Azure JSON-object responses and parse into Pydantic.
        Falls back to last-balanced-brace JSON recovery if initial parse fails.
        NOTE: Do not call this from Tabletop flows.
        """
        if not client:
            return None
        try:
            extra_params = LLMEngine._build_extra_params()
            LLMEngine._debug_prompt_metrics(deployment, system_persona, user_prompt, streaming=False)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format={"type": "json_object"},
                        **extra_params
                    )
                    content = getattr(response.choices[0].message, "content", None)
                    if not content or not str(content).strip():
                        raise ValueError("Empty content from Azure JSON-object response.")
                    # Primary parse path: strict Pydantic v2 validation from JSON string
                    try:
                        parsed = response_model.model_validate_json(content)
                        return parsed
                    except Exception:
                        # Recovery: attempt to trim to last closing brace to recover a complete JSON object
                        s = str(content)
                        end_idx = s.rfind("}")
                        if end_idx != -1:
                            recovered = s[:end_idx + 1]
                            try:
                                parsed = response_model.model_validate_json(recovered)
                                return parsed
                            except Exception:
                                pass
                    if attempt == max_retries - 1:
                        _logger.error("Monolithic maturity JSON generation exhausted retries (%d attempts): content parse failed", max_retries)
                        st.error("Monolithic maturity generation failed to produce valid structured content. Please try again.")
                        return None
                except Exception as e:
                    if attempt == max_retries - 1:
                        _logger.error("Monolithic maturity JSON generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                        st.error("Report generation failed after multiple attempts. Please try again.")
                        return None
                    time.sleep((2 ** attempt))
        except Exception as e:
            _logger.error("Monolithic maturity JSON generation error: %s", e, exc_info=True)
            st.error("An error occurred during report generation. Please try again.")
            return None

    @staticmethod
    def generate_maturity_report_composite(client, deployment, system_persona, client_inputs, response_model):
        """
        Deterministic single-click composite generator:
          - Build skeleton fields from client_inputs.
          - Generate per-section narratives via compact prompts to ensure rich LLM content for all mandated narrative fields.
          - Batch domain_assessments with schema-compliant items (≥15).
          - Build exactly 3 roadmap phases with required lists.
          - Validate assembled dict via response_model.model_validate(); return BaseModel or None.
        """
        if not client:
            return None
        try:
            extra_params = LLMEngine._build_extra_params()

            # Composite-mode hard defaults (keep concise, consultative output)
            _composite_max_tokens = 900
            _max_para = 2
            _max_chars = 900
            _light_per_domain = True  # always use uniform light enrichment unless lean_mode

            def _local_extra():
                """Lower the token ceiling for composite enrichment calls (hard cap)."""
                loc = dict(extra_params)
                loc["max_completion_tokens"] = _composite_max_tokens
                return loc

            def _clip_text(txt: str) -> str:
                """Clip to a small number of paragraphs and max characters to keep reports concise."""
                try:
                    s = (txt or "").strip()
                    parts = [p.strip() for p in s.split("\n\n") if p.strip()]
                    s = "\n\n".join(parts[:_max_para])
                    if len(s) > _max_chars:
                        s = s[:_max_chars].rsplit(" ", 1)[0].rstrip() + "…"
                    return s
                except Exception:
                    return txt or ""

            def _light_enrich_domain(name: str) -> dict:
                """
                One-shot JSON enrichment for a domain with strict size limits.
                Returns {'analysis': str, 'impact': str, 'remediation': str}.
                """
                LLMEngine._dbg_phase(f"Composite:domain[{name}]_light start")
                _t = time.perf_counter()
                instruction = (
                    f"You are producing concise advisory text for the domain '{name}'. "
                    "British English, consultative, third-person. Avoid first/second person. "
                    "Return strict JSON with keys: analysis (<=120 words, 1 paragraph), "
                    "business_impact (<=90 words, 1 paragraph), remediation_bullets (exactly 3 items, each <=12 words)."
                )
                prompt = f"""{instruction}

CONTEXT (sanitised):
{client_inputs}

Respond ONLY as JSON: {{"analysis":"...","business_impact":"...","remediation_bullets":["...","...","..."]}}"""  # noqa: E501
                try:
                    resp = client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"},
                        **_local_extra()
                    )
                    content = getattr(resp.choices[0].message, "content", "") or ""
                    import json as _json
                    data = {}
                    try:
                        data = _json.loads(content)
                    except Exception:
                        s = str(content)
                        end_idx = s.rfind("}")
                        if end_idx != -1:
                            data = _json.loads(s[:end_idx+1])
                    analysis = _clip_text(str(data.get("analysis", "")))
                    impact = _clip_text(str(data.get("business_impact", "")))
                    bullets = data.get("remediation_bullets", []) or []
                    bullets = [str(b).strip() for b in bullets if str(b).strip()]
                    if len(bullets) > 3:
                        bullets = bullets[:3]
                    paragraph = analysis or _clip_text(f"{name}: Prioritised remediation for measurable uplift.")
                    remediation = paragraph + ("\n" + "\n".join([f"- {b}" for b in bullets]) if bullets else "")
                    LLMEngine._dbg_phase(f"Composite:domain[{name}]_light in {time.perf_counter() - _t:.1f}s")
                    return {"analysis": analysis, "impact": impact, "remediation": remediation}
                except Exception:
                    LLMEngine._dbg_phase(f"Composite:domain[{name}]_light failed")
                    return {"analysis": "", "impact": "", "remediation": ""}

            # Section-aware clipping and normalisation helpers
            def _clip_sections(text: str, max_paras: int, max_chars: int) -> str:
                try:
                    s = (text or "").strip()
                    parts = [p.strip() for p in s.split("\n\n") if p.strip()]
                    s = "\n\n".join(parts[:max_paras])
                    if len(s) > max_chars:
                        s = s[:max_chars].rsplit(" ", 1)[0].rstrip() + "."
                    return s
                except Exception:
                    return text or ""

            def _normalise(text: str) -> str:
                try:
                    s = (text or "").strip()
                    if not s or s.upper() in ("N/A", "NA"):
                        return ""
                    if s.endswith("…") or s.endswith("..."):
                        s = s.rstrip(" .…") + "."
                    return s
                except Exception:
                    return text or ""

            # Enriched blocks (light JSON) for top findings, compliance, partnership
            def _light_top_findings() -> list:
                """Return 3 enriched action blocks via a compact JSON call; fallback to empty on failure."""
                try:
                    prompt = (
                        "Return JSON with exactly 3 items under 'blocks'. Each item has: "
                        "heading (≤ 10 words), finding (2 short paragraphs, total ≤ 220 words), risk (≤ 120 words), "
                        "remediation_actions (5–6 concise bullets, ≤ 16 words each). British English."
                    )
                    resp = client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": f"{prompt}\n\nCONTEXT:\n{client_inputs}"}
                        ],
                        response_format={"type": "json_object"},
                        **_local_extra()
                    )
                    import json as _json
                    data = _json.loads(getattr(resp.choices[0].message, "content", "{}") or "{}")
                    out = []
                    for it in (data.get("blocks") or [])[:3]:
                        hd = _normalise(str(it.get("heading", "")))
                        fd = _normalise(str(it.get("finding", "")))
                        rk = _normalise(str(it.get("risk", "")))
                        acts = [ _normalise(str(a)) for a in (it.get("remediation_actions") or []) if _normalise(str(a)) ]
                        if not acts:
                            acts = ["Define quick wins", "Assign accountable owners", "Track progress monthly", "Report to governance"]
                        out.append({
                            "heading": hd or "Priority Uplift Required",
                            "finding": fd or "Evidence indicates material hygiene and governance gaps.",
                            "risk": rk or "Increased likelihood of compromise and business disruption.",
                            "remediation_actions": (acts[:6] if len(acts) >= 5 else (acts[:4] if acts else ["Define quick wins","Assign accountable owners","Track progress monthly","Report to governance","Capture evidence"]))
                        })
                    if len(out) == 3:
                        return out
                except Exception:
                    pass
                return []

            def _build_compliance_alignment_list() -> list:
                """
                Return a structured compliance_alignment list meeting the schema:
                List[ComplianceSection] with 1–3 items. Each item includes:
                  - standard: str
                  - critical_gaps: 2–6 strings
                  - fill_plan: 2–6 GapRemediationPlan dicts (gap_description, recommended_actions 2–6, owner/due_by optional)
                """
                comp_raw = str(client_inputs.get("compliance", "") or "").strip()
                standards = [s.strip() for s in comp_raw.split(",") if s.strip()] if comp_raw and comp_raw.lower() not in ("none", "unknown") else []
                if not standards:
                    standards = ["NIST CSF"]  # default baseline when unspecified

                def _mk_fill_plan(gap_text: str) -> list:
                    return [
                        {
                            "gap_description": gap_text,
                            "recommended_actions": [
                                "Document scope, owners and acceptance criteria",
                                "Execute remediation with evidence capture"
                            ],
                            "owner": "Client IT",
                            "due_by": None
                        },
                        {
                            "gap_description": gap_text,
                            "recommended_actions": [
                                "Schedule validation test and governance review",
                                "Retain artefacts for auditability"
                            ],
                            "owner": "Planet IT",
                            "due_by": None
                        },
                    ]

                sections = []
                for std in standards[:3]:
                    if std.lower().startswith("iso"):
                        crit = [
                            "ISMS control coverage and evidence trail incomplete",
                            "Risk treatment and supplier due diligence not consistently embedded"
                        ]
                    elif "cyber essentials" in std.lower():
                        crit = [
                            "Boundary firewall and secure configuration controls require validation",
                            "Patch management and access control evidence incomplete"
                        ]
                    elif "pci" in std.lower():
                        crit = [
                            "Cardholder data environment segmentation and logging controls unclear",
                            "Vulnerability management cadence misaligned with PCI requirements"
                        ]
                    elif "dfe" in std.lower() or "education" in std.lower():
                        crit = [
                            "Web filtering and safeguarding monitoring not evidenced against DfE 2026",
                            "Incident response thresholds and notification pathways under‑defined"
                        ]
                    else:
                        crit = [
                            "Detect/Respond runbooks lack authority pathways and evidence retention",
                            "Backup immutability and recovery testing cadence not consistently demonstrated"
                        ]
                    sections.append({
                        "standard": std,
                        "critical_gaps": crit[:6],
                        "fill_plan": _mk_fill_plan(crit[0])
                    })
                return sections

            def _light_partnership() -> str:
                """Return 1 medium paragraph + 3 bullets describing partnership value."""
                try:
                    prompt = (
                        "Return JSON with: narrative (1 paragraph, 90–120 words), bullets (exactly 3 concise bullets). "
                        "British English, consultative; avoid first/second person."
                    )
                    resp = client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": f"{prompt}\n\nCONTEXT:\n{client_inputs}"}
                        ],
                        response_format={"type": "json_object"},
                        **_local_extra()
                    )
                    import json as _json
                    data = _json.loads(getattr(resp.choices[0].message, "content", "{}") or "{}")
                    narrative = _clip_sections(_normalise(str(data.get("narrative", ""))), 1, 900)
                    blts = [ _normalise(str(b)) for b in (data.get("bullets") or []) if _normalise(str(b)) ][:3]
                    if not narrative:
                        narrative = ("Partnership focuses on measurable security outcomes through governance cadence, "
                                     "transparent reporting, and prioritised remediation aligned to business impact.")
                    if not blts:
                        blts = ["Outcome-focused governance", "Transparent reporting", "Prioritised remediation"]
                    return narrative + "\n" + "\n".join([f"- {b}" for b in blts])
                except Exception:
                    return ("Partnership focuses on measurable security outcomes through governance cadence, "
                            "transparent reporting, and prioritised remediation aligned to business impact.\n"
                            "- Outcome-focused governance\n- Transparent reporting\n- Prioritised remediation")

            def _build_simulated_attack_block(ci: dict) -> str:
                """Deterministically render a simulated attack block from scenario_selection."""
                try:
                    from scenario_selection import select_scenario_candidate
                    cand = select_scenario_candidate(ci) or {}
                except Exception:
                    cand = {}
                title = cand.get("name") or "Multi‑Stage Intrusion via Business Email Compromise"
                reasons = cand.get("reasons") or []
                why = "; ".join([r for r in reasons if r]) or "Selected due to observed identity, hygiene, or monitoring gaps."
                path = cand.get("attack_vector") or "Adversary leverages social engineering and weak governance to gain foothold and escalate towards critical assets."
                reqs = cand.get("required_conditions") or ["Exposed identities or shared accounts", "Limited monitoring/authority outside hours"]
                mitig = ["Enforce universal MFA and conditional access", "Implement PIM/PAM with JIT", "Adopt immutable backups and restore testing", "Pre‑authorise 24/7 containment"]
                block = []
                block.append(f"Simulated Attack Path — {title}")
                block.append(f"Why Selected: {why}")
                block.append(f"Attack Path: {_clip_sections(path, 2, 900)}")
                block.append("Required Conditions: " + "; ".join(reqs[:3]) + ".")
                block.append("Mitigations:\n" + "\n".join([f"- {m}" for m in mitig[:4]]))
                return "\n".join([_normalise(x) for x in block if _normalise(x)])

            def gen_text(instruction: str) -> str:
                prompt = f"{instruction}\n\nCONTEXT (sanitised):\n{client_inputs}"
                try:
                    resp = client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": prompt}
                        ],
                        **_local_extra()
                    )
                    raw = getattr(resp.choices[0].message, "content", "") or ""
                    return _clip_text(raw)
                except Exception:
                    return ""
            
            def _gen_text_limited(instruction: str, max_paras: int, max_chars: int) -> str:
                base = gen_text(instruction)
                return _normalise(_clip_sections(base, max_paras, max_chars))
            
            def _gen_timed_limited(label: str, instruction: str, max_paras: int, max_chars: int) -> str:
                LLMEngine._dbg_phase(f"Composite:{label} start")
                _t = time.perf_counter()
                txt = _gen_text_limited(instruction, max_paras, max_chars)
                LLMEngine._dbg_phase(f"Composite:{label} in {time.perf_counter() - _t:.1f}s len={len(txt or '')}")
                return txt

            def _gen_timed(label: str, instruction: str) -> str:
                LLMEngine._dbg_phase(f"Composite:{label} start")
                _t = time.perf_counter()
                txt = gen_text(instruction)
                LLMEngine._dbg_phase(f"Composite:{label} in {time.perf_counter() - _t:.1f}s len={len(txt or '')}")
                return txt

            # Lean-mode signal (from client_inputs) — reduces LLM calls for reliability
            lean_mode = bool(client_inputs.get("lean_mode", False))

            # Deterministic monetary cost range (GBP)
            try:
                users = int(client_inputs.get("users", 0) or 0)
            except Exception:
                users = 0
            size_factor = 1.0 + (users / 500.0)
            hygiene_penalty = 1.0
            if str(client_inputs.get("mfa_status","")).strip() in ("None","Privileged Accounts Only"):
                hygiene_penalty += 0.4
            if str(client_inputs.get("backups","")).strip() in ("No Formal Backups","On-Premise Only"):
                hygiene_penalty += 0.6
            if str(client_inputs.get("patching","")).strip() == "Manual / Ad-hoc":
                hygiene_penalty += 0.4
            base_low = 200000.0 * size_factor * hygiene_penalty
            base_high = 450000.0 * size_factor * hygiene_penalty
            def _round10k(v: float) -> int:
                return int(round(v / 10000.0) * 10000)
            low_gbp = _round10k(base_low)
            high_gbp = max(_round10k(base_high), low_gbp + 10000)
            financial_range_str = f"£{low_gbp:,}–£{high_gbp:,}"
            sim_block = _build_simulated_attack_block(client_inputs)

            assembled = {
                "executive_summary": (
                    "Executive summary: the organisation requires hygiene stabilisation (patching/backups), identity hardening (universal MFA), and resilience assurance. A phased roadmap reduces breach likelihood and improves mean time to respond."
                    if lean_mode else _gen_timed_limited("exec_summary", "Write 4-6 substantial paragraphs (110-180 words each) in British English, consultative, third-person. Avoid first/second person. Do not end mid-sentence.", 6, 4800)
                ),
                "executive_summary_actions": [
                    "Enforce universal MFA (Conditional Access) across identities",
                    "Adopt immutable, offsite backups with representative restore testing",
                    "Automate patching across OS and third‑party applications with governance"
                ],
                "executive_summary_action_blocks": (_light_top_findings() or [
                    {
                        "heading": "Identity Hardening Required",
                        "finding": "Privileged access and legacy authentication present risks to the Crown Jewels. Evidence suggests inconsistent MFA enforcement and limited governance.",
                        "risk": "Credential compromise can lead to lateral movement and business disruption. This is material to RTO and insurance obligations.",
                        "remediation_actions": [
                            "Enforce Conditional Access MFA for all users",
                            "Disable legacy authentication protocols",
                            "Implement break‑glass governance with rotation",
                            "Define Just‑In‑Time privileged access with reviews"
                        ]
                    },
                    {
                        "heading": "Data Resilience Gaps",
                        "finding": "Backups are not immutable or routinely tested. Administrative separation and restore cadence are unclear.",
                        "risk": "Ransomware and destructive attacks could lead to unrecoverable data loss and prolonged downtime.",
                        "remediation_actions": [
                            "Adopt offsite immutable backups",
                            "Run monthly representative restore tests",
                            "Separate backup administration from production",
                            "Document recovery runbooks and evidence retention"
                        ]
                    },
                    {
                        "heading": "Patch Management Automation",
                        "finding": "Manual or ad‑hoc patching leaves a window for exploit of publicly disclosed CVEs.",
                        "risk": "Exploitation of unpatched services enables footholds and escalation, increasing operational risk.",
                        "remediation_actions": [
                            "Deploy automated patch management tooling",
                            "Include third‑party application patching",
                            "Track remediation SLAs and exceptions",
                            "Report monthly status to governance forums"
                        ]
                    }
                ]),
                "resiliency_matrix_mapping": "Pillar 1",
                "radar_chart_data": {
                    "iam": 1 if str(client_inputs.get("mfa_status","")).strip() in ("None","Privileged Accounts Only") else 2,
                    "privileged_access": 2,
                    "endpoint": 1 if str(client_inputs.get("patching","")).strip() == "Manual / Ad-hoc" or str(client_inputs.get("endpoint_posture","")).strip() == "Legacy AV Only (Signatures/Heuristics)" else 2,
                    "network": 1 if str(client_inputs.get("remote_access","")).strip() in ("Legacy VPN (Client-based)","None / Cloud Only") else 2,
                    "email": 2,
                    "cloud": 1 if str(client_inputs.get("saas_backup","")).strip() == "None (Relying on Microsoft/Google)" else 2,
                    "saas": 2,
                    "data_security": 2,
                    "secops": 1 if str(client_inputs.get("ir_readiness","")).strip() == "No Formal Plan" else 2,
                    "testing": 1 if str(client_inputs.get("pentest_status","")).strip() == "None" or str(client_inputs.get("vuln_scanning","")).strip() == "None" else 2,
                    "supplier": 2,
                    "resilience": 1 if str(client_inputs.get("backups","")).strip() in ("No Formal Backups","On-Premise Only") else 2,
                    "culture": 2,
                    "grc": 1 if str(client_inputs.get("ir_readiness","")).strip() in ("No Formal Plan","Documented IR Plan (Untested)") else 2,
                    "ai": 1 if str(client_inputs.get("ai_usage_policy","")).strip() in ("None","Unknown") or str(client_inputs.get("shadow_ai_monitoring","")).strip() in ("None","Unknown") else 2
                },
                "cost_of_inaction": _gen_timed_limited(
                    "cost_of_inaction",
                    f"Write exactly 5 short-to-medium paragraphs (80–120 words each) explaining the cost of inaction tied to downtime tolerance (RTO), backups, and MFA posture. Include the estimated annual financial exposure range {financial_range_str} with a brief justification. British English, consultative; avoid first/second person.",
                    5,
                    2200
                ),
                "monetary_cost_of_inaction": {
                    "amount_gbp": float((low_gbp + high_gbp) / 2.0),
                    "source": "Derived from user count and hygiene posture (MFA, patching, backups).",
                    "rationale": f"Estimated annual exposure based on size factor and hygiene penalties; range {financial_range_str}."
                },
                "domain_assessments": [],
                "phased_roadmap": [],
                "success_metrics": [
                    "Reduce mean time to respond (MTTR) through improved monitoring and runbooks",
                    "Increase MFA enforcement coverage across all identities",
                    "Improve backup immutability and restore assurance through regular testing",
                ],
                "engagement_cadence": [
                    "Monthly governance review",
                    "Quarterly roadmap checkpoint",
                    "Annual strategic reset with the Board",
                ],
                "consultant_discovery_guide": [
                    "What are the Crown Jewels and their data flows?",
                    "What is the acceptable downtime tolerance (RTO)?",
                    "Where is MFA enforced across identities and services?",
                    "How are backups validated and how often?",
                    "What is the IR authority and quarterly test cadence?"
                ],
                "partnership_details": _light_partnership(),
                "partnership_links": None,
                "compliance_alignment": _build_compliance_alignment_list(),
                "threat_intelligence_context": (
                    (sim_block if sim_block else "Simulated Attack Path — Baseline scenario")
                    + ("\n\n" if sim_block else "\n\n")
                    + _gen_timed_limited("threat_context", "Provide a short threat intelligence context relevant to the client's industry and stack.", 1, 900)
                ),
                # Deterministic threat scenarios for export rendering (at least one item)
                "threat_scenarios": [
                    {
                        "id": "ts-maturity-1",
                        "name": (sim_block.split("\n", 1)[0].replace("Simulated Attack Path — ", "") if sim_block else "Multi‑Stage Intrusion via Business Email Compromise"),
                        "incident_type": "Pillar 2",
                        "narrative": (sim_block if sim_block else "Adversary leverages social engineering and weak governance to gain foothold and escalate towards critical assets. Include MFA hardening, immutability, and 24/7 containment authority in the roadmap.")
                    }
                ],
                "microsoft_healthchecks_recommendations": _gen_timed_limited("ms_healthchecks", "Provide brief Microsoft healthchecks and hardening recommendations where applicable.", 1, 900),
                "proactive_testing_programme": _gen_timed_limited("proactive_testing", "Write 2-3 paragraphs (120-180 words each) describing a proactive security validation and testing programme with cadence and evidence management. British English; consultative. No bullet points. Do not end mid-sentence.", 3, 1800),
                "incident_response_plan_outline": _gen_timed_limited("ir_plan_outline", "Write 2-3 paragraphs (120-180 words each) outlining an incident response plan with authority pathways, playbooks, and governance cadence. British English; consultative. No bullet points. Do not end mid-sentence.", 3, 1800),
                "disaster_recovery_plan_outline": _gen_timed_limited("dr_plan_outline", "Write 2-3 paragraphs (120-180 words each) outlining a disaster recovery plan tied to RTO/RPO, immutable backups, runbooks, test cadence, and evidence retention. British English; consultative. No bullet points. Do not end mid-sentence.", 3, 1800),
            }

            # Compute resiliency mapping deterministically (Capability Mismatch rule preserved)
            mfa = str(client_inputs.get("mfa_status", "Unknown"))
            patching = str(client_inputs.get("patching", "Unknown"))
            backups = str(client_inputs.get("backups", "Unknown"))
            sav_label = str(client_inputs.get("savviness_label", ""))

            if mfa in ["None", "Privileged Accounts Only"] or patching == "Manual / Ad-hoc" or backups in ["No Formal Backups", "On-Premise Only"]:
                assembled["resiliency_matrix_mapping"] = "Pillar 1"
            else:
                assembled["resiliency_matrix_mapping"] = "Pillar 2" if "Proactive" in sav_label else "Pillar 3" if "Adaptive" in sav_label else "Pillar 2"

            # Domain assessments (≥15) with compact per-domain narratives
            base_domains = [
                "Identity & Access", "Information Protection", "SaaS Governance", "Asset Assurance",
                "Monitoring & Detection", "Supplier Assurance", "Third-Party Access", "Recovery Assurance",
                "Incident Response", "Network & Edge", "Email Security", "Endpoint Security", "Cloud Security",
                "Application Security", "AI Governance"
            ]
            domains = []
            # Map resiliency mapping to per-domain canonical label
            pillar_label = assembled["resiliency_matrix_mapping"]
            if pillar_label == "Pillar 1":
                domain_level = "Pillar 1: Reactive Cybersecurity"
            elif pillar_label == "Pillar 2":
                domain_level = "Pillar 2: Proactive Cybersecurity"
            else:
                domain_level = "Pillar 3: Adaptive Cybersecurity"
            for name in base_domains:
                # Always use uniform light per-domain enrichment (one JSON call per domain unless lean_mode)
                if _light_per_domain and not lean_mode:
                    r = _light_enrich_domain(name)
                    analysis_txt = r.get("analysis") or f"{name}: Technical analysis indicates baseline controls require uplift; monitoring/runbooks need hardening."
                    impact_txt = r.get("impact") or f"Business impact for {name}: downtime and data exposure risks present; uplift reduces MTTR and breach likelihood."
                    remediation_txt = r.get("remediation") or f"{name}: Prioritise identity, resilience, detection.\n- Enforce hygiene\n- Improve monitoring\n- Establish governance"
                else:
                    analysis_txt = (
                        f"{name}: Technical analysis indicates baseline controls require uplift; monitoring/runbooks need hardening."
                        if lean_mode else _gen_timed(f"domain[{name}]_analysis", f"Provide a multi-paragraph technical analysis for the domain: {name}. Use British English and a consultative tone.")
                    )
                    impact_txt = (
                        f"Business impact for {name}: downtime and data exposure risks present; uplift reduces MTTR and breach likelihood."
                        if lean_mode else _gen_timed(f"domain[{name}]_business_impact", f"Explain business impact for {name} in British English.")
                    )
                    remediation_txt = (
                        f"{name}: Prioritise hygiene stabilisation; sequence identity, resilience, detection."
                        if lean_mode else _gen_timed(f"domain[{name}]_remediation", f"Provide remediation rationale and prioritisation for {name}.")
                    )

                domains.append({
                    "domain_name": name,
                    "current_maturity_level": domain_level,
                    "current_state_analysis": analysis_txt,
                    "business_impact_narrative": impact_txt,
                    "critical_gaps": [
                        "Gap: Missing policies or controls",
                        "Gap: Coverage limited or untested"
                    ],
                    "vendor_agnostic_quick_wins": [
                        "Enable baseline hardening with native controls",
                        "Apply configuration baselines and periodic reviews"
                    ],
                    "recommended_solutions": [
                        "Deploy consultative improvements aligned to risk and operational context.",
                        "Adopt monitoring and validation to reduce dwell time.",
                        "Integrate governance cadence to sustain improvements."
                    ],
                    "remediation_rationale": remediation_txt,
                    "shared_responsibility": "Planet IT configures and guides best practice; the Client enforces policy and user adherence."
                })
            assembled["domain_assessments"] = domains

            # Phased roadmap (exactly three phases)
            assembled["phased_roadmap"] = [
                {
                    "phase_title": "Phase 1: Foundational Hygiene",
                    "timeline": "0-3 Months",
                    "primary_objective": "Stabilise hygiene foundations",
                    "key_deliverables": [
                        "Universal MFA enforced",
                        "Immutable backups deployed",
                        "Automated patching enabled",
                        "Critical SaaS MFA uplift"
                    ],
                    "estimated_effort": "Moderate",
                    "milestones": [
                        "Enforce universal MFA", "Establish immutable backups", "Automate patching", "SaaS MFA uplift"
                    ],
                    "resource_requirements": "Identity engineer, backup admin, RMM specialist",
                    "business_value_delivered": "Reduced risk of compromise and faster recovery"
                },
                {
                    "phase_title": "Phase 2: Active Managed Defence",
                    "timeline": "3-9 Months",
                    "primary_objective": "Strengthen detection and response",
                    "key_deliverables": [
                        "Expanded telemetry coverage",
                        "Runbook-driven incident handling",
                        "Quarterly tabletop exercises",
                        "24/7 escalation authority defined"
                    ],
                    "estimated_effort": "Moderate",
                    "milestones": [
                        "Expand telemetry coverage", "Runbook-driven incident handling", "Periodic tabletop exercises", "Define 24/7 escalation"
                    ],
                    "resource_requirements": "SOC analyst, IR lead",
                    "business_value_delivered": "Improved MTTR and organisational readiness"
                },
                {
                    "phase_title": "Phase 3: Adaptive Governance & Resilience",
                    "timeline": "10-18+ Months",
                    "primary_objective": "Adaptive security and automation",
                    "key_deliverables": [
                        "SOAR-driven remediation",
                        "Zero Trust Architecture uplift",
                        "Continuous BAS programme",
                        "Quarterly purple-team validation"
                    ],
                    "estimated_effort": "High",
                    "milestones": [
                        "SOAR-driven remediation", "Zero Trust Architecture uplift", "Continuous BAS programme", "Purple-team validation"
                    ],
                    "resource_requirements": "Automation engineer, security architect",
                    "business_value_delivered": "Operational efficiency and resilience"
                }
            ]

            # Validate into Pydantic model
            try:
                parsed = response_model.model_validate(assembled)
                return parsed
            except Exception as e:
                _logger.error("Composite validation failed: %s", e, exc_info=True)
                return None
        except Exception as e:
            _logger.error("Composite generation error: %s", e, exc_info=True)
            return None

    @staticmethod
    def generate_maturity_report_staged_v2(client, deployment, system_persona, client_inputs, header_model, report_model):
        """
        Resilient staged generator v2:
          - Header first (small prompt)
          - Deterministic composite body
          - Aggressive hydration of missing narratives and derived critical gaps from consultation inputs
        Azure-only; respects max_completion_tokens via _build_extra_params. No schema changes.
        """
        if not client:
            return None

        # Mode flags (Maturity-only; safe defaults)
        try:
            lean_mode = bool(client_inputs.get("lean_mode", False))
        except Exception:
            lean_mode = False
        try:
            default_batch = int(get_config("STAGED_V2_DOMAIN_BATCH_SIZE", 5))
            if default_batch <= 0:
                default_batch = 5
        except Exception:
            default_batch = 5

        # Helpers
        def _gen_text(instr: str) -> str:
            try:
                extra = LLMEngine._build_extra_params()
                resp = client.chat.completions.create(
                    model=deployment,
                    messages=[
                        {"role": "system", "content": system_persona},
                        {"role": "user", "content": f"{instr}\n\nCONTEXT:\n{client_inputs}"}
                    ],
                    **extra
                )
                return getattr(resp.choices[0].message, "content", "") or ""
            except Exception:
                return ""

        def _derive_domain_gaps(ci: dict) -> dict:
            """
            Map telemetry and assurance profiles to per-domain gap bullets.
            Best-effort deterministic logic; consultative phrasing.
            """
            gaps = {}
            mfa = str(ci.get("mfa_status", "Unknown"))
            patching = str(ci.get("patching", "Unknown"))
            backups = str(ci.get("backups", "Unknown"))
            remote = str(ci.get("remote_access", "Unknown"))
            saas_bkp = str(ci.get("saas_backup", "Unknown"))
            ir = str(ci.get("ir_readiness", "Unknown"))
            endpoint_cap = str(ci.get("endpoint_posture", "Unknown"))

            gaps["Identity & Access"] = []
            if mfa in ("None", "Privileged Accounts Only"):
                gaps["Identity & Access"].append("Universal MFA not enforced; legacy auth permitted")
            gaps["Identity & Access"].append("Break-glass governance unclear; service accounts not formally governed")

            gaps["Endpoint Security"] = []
            if endpoint_cap in ("Legacy AV Only (Signatures/Heuristics)"):
                gaps["Endpoint Security"].append("Legacy AV in use; fileless techniques not reliably detected")
            if patching == "Manual / Ad-hoc":
                gaps["Endpoint Security"].append("Automated patching absent; window for CVE exploitation")

            gaps["Network & Edge"] = []
            if remote in ("Legacy VPN (Client-based)", "None / Cloud Only"):
                gaps["Network & Edge"].append("Legacy remote access; insufficient segmentation and conditional controls")
            gaps["Network & Edge"].append("Flat internal network; lateral movement pathways insufficiently constrained")

            gaps["Operational Resilience & Backup"] = []
            if backups in ("No Formal Backups", "On-Premise Only"):
                gaps["Operational Resilience & Backup"].append("Immutable/offsite backups absent or untested")
            gaps["Operational Resilience & Backup"].append("Restore testing cadence unclear; evidence retention not defined")

            gaps["Security Operations & Response"] = []
            if ir in ("No Formal Plan", "Documented IR Plan (Untested)"):
                gaps["Security Operations & Response"].append("Incident response plan untested; authority pathways unclear")
            gaps["Security Operations & Response"].append("Detection runbooks incomplete; containment authority uncertain")

            gaps["Email Security"] = ["Advanced anti-phishing tuning required; OAuth consent governance limited"]
            gaps["Cloud Security"] = ["Conditional posture checks incomplete; workload baselines require review"]
            gaps["Data Security & Information Protection"] = ["Sensitivity labels/DLP coverage limited across data flows"]
            gaps["Supplier & Third-Party Security"] = ["Supplier risk reviews periodic only; access governance partial"]
            gaps["Security Validation & Testing"] = ["No continuous BAS; penetration testing cadence limited"]
            gaps["Security Culture & Awareness"] = ["Reporting routes and coaching inconsistent; role-based coverage incomplete"]
            gaps["Governance, Risk & Compliance"] = ["Policies not uniformly acknowledged; risk registers incomplete"]
            gaps["AI Governance & Security"] = ["Shadow AI monitoring absent; AI acceptable use policy not formalised"]
            return gaps

        # 1) Header
        header_obj = None
        try:
            from prompts import build_maturity_header_prompt
            header_prompt = build_maturity_header_prompt(client_inputs)
            header_obj = LLMEngine.generate_structured_report(
                client, deployment, system_persona, header_prompt, header_model
            )
        except Exception:
            header_obj = None

        # 2) Deterministic body
        body = LLMEngine.generate_maturity_report_composite(
            client, deployment, system_persona, client_inputs, report_model
        )

        if body is None and header_obj is None:
            return None

        # 3) Merge and hydrate
        try:
            base = {}
            if body:
                base = body.model_dump() if hasattr(body, "model_dump") else (body.dict() if hasattr(body, "dict") else dict(body))
            if header_obj:
                h = header_obj.model_dump() if hasattr(header_obj, "model_dump") else (header_obj.dict() if hasattr(header_obj, "dict") else {})
                for k in ("executive_summary", "executive_summary_action_blocks", "resiliency_matrix_mapping"):
                    if h.get(k):
                        base[k] = h[k]

            # Ensure consultative narratives exist
            if not base.get("executive_summary"):
                base["executive_summary"] = _gen_text("Write a 3-paragraph executive summary in British English with a consultative third-person tone. Avoid first/second person.")
            if not base.get("cost_of_inaction"):
                rto = client_inputs.get("rto", "Unknown")
                bkp = client_inputs.get("backups", "Unknown")
                mfa = client_inputs.get("mfa_status", "Unknown")
                base["cost_of_inaction"] = _gen_text(f"Explain cost of inaction across downtime tolerance (RTO: {rto}), backups ({bkp}), and MFA posture ({mfa}). British English; consultative tone.")
            if not base.get("executive_summary_action_blocks"):
                base["executive_summary_action_blocks"] = [
                    {
                        "heading": "Identity Hardening Required",
                        "finding": "Universal MFA enforcement absent; legacy authentication permitted.",
                        "risk": "Credential compromise enables lateral movement and business disruption.",
                        "remediation_actions": [
                            "Enforce Conditional Access MFA for all users",
                            "Disable legacy authentication protocols",
                            "Implement break‑glass governance with rotation",
                            "Define Just‑In‑Time privileged access with reviews"
                        ]
                    }
                ]
            # Ensure minimum executive_summary_actions list (≥3) to satisfy schema
            if (not base.get("executive_summary_actions")
                or not isinstance(base.get("executive_summary_actions"), list)
                or len(base.get("executive_summary_actions")) < 3):
                base["executive_summary_actions"] = [
                    "Enforce universal MFA (Conditional Access) across identities",
                    "Adopt immutable, offsite backups with representative restore testing",
                    "Automate patching across OS and third‑party applications with governance",
                ]

            # Derive domain gaps and enrich domain_assessments (batched; lean mode reduces LLM calls)
            derived = _derive_domain_gaps(client_inputs)
            da = base.get("domain_assessments") or []
            enriched = []
            # Batch size defaults to 5 if not provided
            batch_size = int(client_inputs.get("staged_v2_domain_batch_size", default_batch) or default_batch)
            for i in range(0, len(da), max(1, batch_size)):
                batch = da[i:i+batch_size]
                for item in batch:
                    d = item.model_dump() if hasattr(item, "model_dump") else (item if isinstance(item, dict) else {})
                    name = d.get("domain_name") or d.get("name")
                    # Critical gaps
                    cg = d.get("critical_gaps") or []
                    if not isinstance(cg, list):
                        cg = [cg] if cg else []
                    if (not cg) and name in derived:
                        d["critical_gaps"] = derived.get(name, [])[:2]
                    elif cg:
                        d["critical_gaps"] = [g for g in cg if str(g).strip() and str(g).strip().lower() not in ("n/a", "none", "unknown")]
                        if not d["critical_gaps"] and name in derived:
                            d["critical_gaps"] = derived.get(name, [])[:2]
                    # Business impact narrative
                    if not d.get("business_impact_narrative"):
                        d["business_impact_narrative"] = (
                            f"{name}: Business impact includes downtime exposure and potential breach-related costs."
                            if lean_mode else _gen_text(f"Describe business impact for domain: {name} in British English. Consultative tone.")
                        )
                    # Remediation rationale
                    if not d.get("remediation_rationale"):
                        d["remediation_rationale"] = (
                            f"{name}: Prioritise identity, resilience, detection; sequence quick wins and governance ceremonies."
                            if lean_mode else _gen_text(f"Provide remediation rationale and prioritisation for domain: {name}. British English; consultative.")
                        )
                    enriched.append(d)
            if enriched:
                base["domain_assessments"] = enriched

            # Validate
            return report_model.model_validate(base)
        except Exception:
            # prefer fuller body else header
            return body or header_obj

    @staticmethod
    def generate_maturity_report_staged_v3(client, deployment, system_persona, client_inputs, header_model, report_model):
        """
        Resilient staged generator v3 (Azure-only):
          - Header-first (compact prompt)
          - Deterministic composite body
          - Strict clamps on radar values and minimum domain count (>=15)
          - Hydrate missing narratives conservatively
        """
        if not client:
            return None

        # 1) Header (compact)
        header_obj = None
        try:
            disabled = str(get_config("STAGED_V3_HEADER_DISABLED", "true")).strip().lower() in ("1","true","yes","on")
        except Exception:
            disabled = True
        if disabled:
            LLMEngine._dbg_phase("Header disabled by default")
        else:
            try:
                from prompts import build_maturity_header_prompt
                header_prompt = build_maturity_header_prompt(client_inputs)
                LLMEngine._dbg_phase("Header start (structured)")
                _t0 = time.perf_counter()
                header_obj = LLMEngine.generate_structured_report(
                    client, deployment, system_persona, header_prompt, header_model
                )
                LLMEngine._dbg_phase(f"Header {'ok' if header_obj else 'none'} in {time.perf_counter() - _t0:.1f}s")
            except Exception:
                LLMEngine._dbg_phase("Header skipped (exception)")
                header_obj = None

        # 2) Deterministic body (composite)
        LLMEngine._dbg_phase("Composite body start")
        _t1 = time.perf_counter()
        body = LLMEngine.generate_maturity_report_composite(
            client, deployment, system_persona, client_inputs, report_model
        )
        LLMEngine._dbg_phase(f"Composite {'ok' if body else 'none'} in {time.perf_counter() - _t1:.1f}s")
        if body is None:
            LLMEngine._dbg_phase("Composite retry start")
            time.sleep(0.6)
            _t1b = time.perf_counter()
            body = LLMEngine.generate_maturity_report_composite(
                client, deployment, system_persona, client_inputs, report_model
            )
            LLMEngine._dbg_phase(f"Composite retry {'ok' if body else 'none'} in {time.perf_counter() - _t1b:.1f}s")

        if body is None and header_obj is None:
            return None

        # 3) Merge + clamps + hydration
        try:
            LLMEngine._dbg_phase("Merge+Clamp start")
            def _mdump(x):
                return x.model_dump() if hasattr(x, "model_dump") else (x.dict() if hasattr(x, "dict") else dict(x))

            base = {}
            if body:
                base = _mdump(body)
            if header_obj:
                h = _mdump(header_obj)
                for k in ("executive_summary", "executive_summary_action_blocks", "resiliency_matrix_mapping"):
                    if h.get(k):
                        base[k] = h[k]

            # Radar clamps (1..3)
            rd = base.get("radar_chart_data") or {}
            def _clamp(v):
                try:
                    iv = int(v)
                except Exception:
                    iv = 1
                return 1 if iv < 1 else 3 if iv > 3 else iv
            for k in ("iam","privileged_access","endpoint","network","email","cloud","saas","data_security","secops","testing","supplier","resilience","culture","grc","ai"):
                if k in rd:
                    rd[k] = _clamp(rd[k])
            base["radar_chart_data"] = rd

            # Ensure minimum domain count (>=15)
            doms = base.get("domain_assessments") or []
            if not isinstance(doms, list):
                doms = []
            if len(doms) < 15:
                fill_names = [
                    "Identity & Access Management","Privileged Access & Identity Governance","Endpoint & Device Security","Network & Remote Access Security",
                    "Email & Collaboration Security","Cloud & Infrastructure Security","SaaS & Application Governance","Data Security & Information Protection",
                    "Security Operations & Response","Security Validation & Testing","Supplier & Third-Party Security","Operational Resilience & Backup",
                    "Security Culture & Awareness","Governance, Risk & Compliance","AI Governance & Security"
                ]
                existing = {getattr(d, "domain_name", d.get("domain_name") if isinstance(d, dict) else None) for d in doms}
                for nm in fill_names:
                    if len(doms) >= 15:
                        break
                    if nm in existing:
                        continue
                    doms.append({
                        "domain_name": nm,
                        "current_maturity_level": base.get("resiliency_matrix_mapping","Pillar 2: Proactive Cybersecurity"),
                        "current_state_analysis": f"{nm}: Baseline assessment placeholder.",
                        "business_impact_narrative": f"{nm}: Business impact placeholder.",
                        "critical_gaps": ["Gap placeholder 1","Gap placeholder 2"],
                        "vendor_agnostic_quick_wins": ["Quick win placeholder 1","Quick win placeholder 2"],
                        "recommended_solutions": ["Solution placeholder 1","Solution placeholder 2","Solution placeholder 3"],
                        "remediation_rationale": f"{nm}: Rationale placeholder.",
                        "shared_responsibility": "Planet IT and Client shared accountability."
                    })

            base["domain_assessments"] = doms
            # Ensure threat_scenarios present for export; derive from scenario_selection/simulated block if missing
            if not base.get("threat_scenarios"):
                try:
                    from scenario_selection import select_scenario_candidate
                    cand = select_scenario_candidate(client_inputs) or {}
                    ts_name = cand.get("name") or "Multi‑Stage Intrusion via Business Email Compromise"
                    ts_path = cand.get("attack_vector") or "Adversary leverages social engineering and weak governance to gain foothold and escalate towards critical assets."
                except Exception:
                    ts_name = "Multi‑Stage Intrusion via Business Email Compromise"
                    ts_path = "Adversary leverages social engineering and weak governance to gain foothold and escalate towards critical assets."
                base["threat_scenarios"] = [{
                    "id": "ts-maturity-1",
                    "name": ts_name,
                    "incident_type": base.get("resiliency_matrix_mapping", "Pillar 2"),
                    "narrative": ts_path
                }]

            # Hydrate missing narratives minimally
            for k in ("cost_of_inaction","proactive_testing_programme","incident_response_plan_outline","disaster_recovery_plan_outline"):
                if not base.get(k):
                    base[k] = ""

            _t2 = time.perf_counter()
            out = report_model.model_validate(base)
            LLMEngine._dbg_phase(f"Validate OK in {time.perf_counter() - _t2:.1f}s")
            return out
        except Exception:
            LLMEngine._dbg_phase("Validate failed; returning body/header")
            return body or header_obj
