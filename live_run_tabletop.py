from __future__ import annotations

# Live run using an injected runner that returns a valid TabletopSourcePlan to exercise the full pipeline
from typing import Any, Callable, Optional, List, Dict

from tabletop_source import (
    TabletopSourcePlan,
    StageSource,
    SourceDecision,
    SourceQuestion,
    SourceFactRef,
    ArtefactSpec,
    FacilitatorIntent,
)
from tabletop_generation import generate_tabletop_plan


def make_stage(
    stage_number: int,
    facts: List[str],
    unknowns: List[str],
    decisions: List[dict],
    questions: List[dict],
    artefact_spec: dict,
    facilitator_intent: dict,
) -> StageSource:
    sd = [SourceDecision(**d) for d in decisions]
    sq = []
    for q in questions:
        refs = q.get("anchor_refs", [])
        sq.append(
            SourceQuestion(
                prompt=q["prompt"],
                authority=q["authority"],
                anchor_refs=refs,
                decision_options=q["decision_options"],
                deadline_minutes=q["deadline_minutes"],
                competing_consequences=q["competing_consequences"],
            )
        )
    return StageSource(
        stage_number=stage_number,
        participant_situation_summary=(
            "Service Desk reports unexpected behaviour observed by dispatch supervisors; "
            "operations request guidance under time pressure." if stage_number == 1 else
            "Operational updates continue with uncertainty and decision pressure building."
        ),
        new_confirmed_facts=facts,
        remaining_unknowns=unknowns,
        decisions=sd,
        participant_questions=sq,
        artefact_spec=ArtefactSpec(**artefact_spec),
        facilitator_intent=FacilitatorIntent(**facilitator_intent),
    )


def build_valid_source_plan() -> TabletopSourcePlan:
    # Hidden root cause (facilitator-only); must not appear in participant fields
    hidden = "Identity session hijack via application credential"
    wrap_up = "Controlled reveal aligns with identity session hijack via application credential."
    # Stage facts (2 per stage, minimal)
    s1_facts = [
        "Dispatch supervisors receive unexpected sign-in prompts during morning planning",
        "Northstar dispatch dashboard shows intermittent slow responses"
    ]
    s2_facts = [
        "Unusual session tokens observed for dispatch supervisor identity",
        "New application credential detected in administrative audit logs"
    ]
    s3_facts = [
        "Priority route assignments show out-of-window adjustments requiring re‑approval",
        "Manual dispatch process causes delivery-window risk for strategic customers"
    ]
    s4_facts = [
        "Executive incident owner requests positions for customers and regulators",
        "Media enquiry received regarding delays on Northstar deliveries"
    ]
    # Unknowns
    s1_unknowns = [
        "Whether identity prompts are related to policy changes or anomalies in the service",
        "Which services are impacted beyond the dispatch dashboard during peak operations"
    ]
    s2_unknowns = [
        "Which sessions should be revoked to contain risk while maintaining operations",
        "What authority is required to remove the newly detected application credential"
    ]
    s3_unknowns = [
        "Which services require priority restoration versus controlled recovery",
        "What data-access events must be assessed for customer-impact classification"
    ]
    s4_unknowns = [
        "Which external communications require approval and timing under regulatory pressure",
        "What executive decisions remain outstanding to conclude controlled recovery"
    ]
    # Decisions
    s1_decisions = [
        {
            "category": "other",
            "decision": "Initiate incident triage and confirm authority boundaries for immediate steps",
            "authority": "Incident Manager",
            "affected_operation": "Dispatch planning",
            "deadline_minutes": 15,
            "accepted_consequence": "Accepting reduced planning capacity during initial evidence collection"
        }
    ]
    s2_decisions = [
        {
            "category": "session_identity_containment",
            "decision": "Revoke suspicious sessions and enforce re‑authentication for affected identities",
            "authority": "Incident Manager",
            "affected_operation": "Identity sessions",
            "deadline_minutes": 15,
            "accepted_consequence": "Accepting user disruption during enforcement and potential planning delays"
        },
        {
            "category": "containment_authority",
            "decision": "Authorise credential removal and session controls for affected applications",
            "authority": "Executive Incident Owner",
            "affected_operation": "API administration",
            "deadline_minutes": 10,
            "accepted_consequence": "Accepting reduced administrative throughput and heightened governance checks"
        },
        {
            "category": "affected_service_continuity",
            "decision": "Continue dispatch operations in controlled mode with manual verification of route changes",
            "authority": "Operations Manager",
            "affected_operation": "Dispatch operations",
            "deadline_minutes": 20,
            "accepted_consequence": "Accepting throughput degradation and longer delivery‑window variance"
        },
        {
            "category": "escalation_scope",
            "decision": "Declare confirmed‑compromise path and engage communications and legal for standby",
            "authority": "Executive Incident Owner",
            "affected_operation": "Executive escalation",
            "deadline_minutes": 30,
            "accepted_consequence": "Accepting increased external scrutiny and formal governance overhead"
        },
    ]
    s3_decisions = [
        {
            "category": "other",
            "decision": "Approve controlled recovery for priority routes while initiating data‑impact assessment",
            "authority": "Executive Incident Owner",
            "affected_operation": "Dispatch operations",
            "deadline_minutes": 30,
            "accepted_consequence": "Accepting deferred lower‑priority routes and audit workload growth"
        }
    ]
    s4_decisions = [
        {
            "category": "other",
            "decision": "Approve holding statements and regulatory notice preparation under executive oversight",
            "authority": "Executive Incident Owner",
            "affected_operation": "External communications",
            "deadline_minutes": 45,
            "accepted_consequence": "Accepting reputational exposure and need for formal classification language"
        }
    ]

    # Questions: build with anchor_refs referencing current or previous stage facts by index (1‑based)
    def q(prompt, authority, anchors, options):
        return {
            "prompt": prompt,
            "authority": authority,
            "anchor_refs": anchors,
            "decision_options": options,
            "deadline_minutes": 10,
            "competing_consequences": ["Throughput degradation", "Customer delay risk"]
        }

    s1_q = [
        q("Authorize triage and define evidence threshold for action?",
          "Incident Manager",
          [SourceFactRef(stage_offset=0, fact_index=1), SourceFactRef(stage_offset=0, fact_index=2)],
          ["Proceed with triage", "Defer to operations"]),
        q("Should operations record manual checks for priority changes?",
          "Operations Manager",
          [SourceFactRef(stage_offset=0, fact_index=2), SourceFactRef(stage_offset=0, fact_index=1)],
          ["Record checks", "Rely on system state"]),
        q("Will you timebox initial investigation and set decision windows?",
          "Incident Manager",
          [SourceFactRef(stage_offset=0, fact_index=1), SourceFactRef(stage_offset=0, fact_index=2)],
          ["15 minutes", "30 minutes"]),
    ]
    s2_q = [
        q("Approve session containment considering current identity observations?",
          "Incident Manager",
          [SourceFactRef(stage_offset=0, fact_index=1), SourceFactRef(stage_offset=-1, fact_index=1)],
          ["Revoke sessions", "Monitor only"]),
        q("Authorise application credential removal under governance?",
          "Executive Incident Owner",
          [SourceFactRef(stage_offset=0, fact_index=2), SourceFactRef(stage_offset=-1, fact_index=2)],
          ["Remove credential", "Defer action"]),
        q("Continue controlled operations while approvals are pending?",
          "Operations Manager",
          [SourceFactRef(stage_offset=-1, fact_index=2), SourceFactRef(stage_offset=0, fact_index=1)],
          ["Continue controlled", "Pause operations"]),
    ]
    s3_q = [
        q("Approve controlled recovery for priority routes?",
          "Executive Incident Owner",
          [SourceFactRef(stage_offset=0, fact_index=1), SourceFactRef(stage_offset=-1, fact_index=1)],
          ["Continue recovery", "Pause recovery"]),
        q("Initiate data‑impact assessment referencing current operational impact?",
          "Communications Lead",
          [SourceFactRef(stage_offset=0, fact_index=2), SourceFactRef(stage_offset=-1, fact_index=2)],
          ["Start assessment", "Delay assessment"]),
        q("Confirm dual‑approval path for changes affecting customers?",
          "Executive Incident Owner",
          [SourceFactRef(stage_offset=-1, fact_index=1), SourceFactRef(stage_offset=0, fact_index=2)],
          ["Enforce dual‑approval", "Relax temporarily"]),
    ]
    s4_q = [
        q("Approve holding statements and regulatory engagement?",
          "Executive Incident Owner",
          [SourceFactRef(stage_offset=0, fact_index=1), SourceFactRef(stage_offset=0, fact_index=2)],
          ["Approve now", "Wait for more evidence"]),
        q("Set approval deadlines for external communications under pressure?",
          "Executive Incident Owner",
          [SourceFactRef(stage_offset=-1, fact_index=1), SourceFactRef(stage_offset=0, fact_index=1)],
          ["30 minutes", "60 minutes"]),
        q("Confirm executive ownership for final positions?",
          "Executive Incident Owner",
          [SourceFactRef(stage_offset=0, fact_index=2), SourceFactRef(stage_offset=-1, fact_index=2)],
          ["Assign owner", "Defer owner"]),
    ]

    # Artefact specs and intents
    def aspec(atype, author, audience, system, purpose):
        return {
            "artefact_type": atype,
            "author_role": author,
            "audience_role": audience,
            "source_system": system,
            "purpose": purpose,
            "required_details": ["Grounded evidence relevant to the stage"],
            "rendering_hint": "monospace" if atype in ("log", "configuration", "code") else "wrap-80",
        }

    def fintent(tension, release, failure):
        return {
            "intended_decision_tension": tension,
            "optional_probe_topics": ["Authority", "Evidence"],
            "information_release_intent": release,
            "failure_modes_to_watch": [failure],
        }

    s1 = make_stage(
        1, s1_facts, s1_unknowns, s1_decisions, s1_q,
        aspec("ticket", "Service Desk Analyst", "Incident Manager", "Service Desk", "Initial incident ticket"),
        fintent("Establish triage boundaries", "None", "Assuming evidence without validation")
    )
    s2 = make_stage(
        2, s2_facts, s2_unknowns, s2_decisions, s2_q,
        aspec("log", "Security Analyst", "Incident Manager", "Identity provider sign-in logs", "Identity/security update"),
        fintent("Containment approvals", "None", "Skipping authority checks")
    )
    s3 = make_stage(
        3, s3_facts, s3_unknowns, s3_decisions, s3_q,
        aspec("exec_email", "Head of Dispatch", "Executive Incident Owner", "Dispatch operations", "Operational impact update"),
        fintent("Continuity vs recovery trade-offs", "None", "Unclear ownership")
    )
    s4 = make_stage(
        4, s4_facts, s4_unknowns, s4_decisions, s4_q,
        aspec("customer_email", "Communications Lead", "Executive Incident Owner", "Communications platform", "Holding response"),
        fintent("Regulatory and media pressure", "None", "Premature conclusions")
    )

    tsp = TabletopSourcePlan(
        scenario_title="Northstar Dispatch Anomaly",
        audience="Blended",
        hidden_root_cause_context=hidden,
        wrap_up_reveal=wrap_up,
        stages=[s1, s2, s3, s4],
    )
    return tsp


def injected_runner(client: Any, deployment: str, system_persona: str, prompt: str, model_class: Any) -> Any:
    # Return a valid TabletopSourcePlan instance
    plan = build_valid_source_plan()
    return plan


if __name__ == "__main__":
    client = object()
    deployment = "dev"
    client_inputs = {
        "customer_name": "Northstar Logistics",
        "industry": "Logistics",
        "critical_infra": "Dispatch Platform",
        "identity": "Microsoft Entra",
        "firewall": "FortiGate",
        "endpoint": "Microsoft Defender",
        "mfa_status": "Enforced",
        "patching": "Automated",
        "backups": "Immutable",
    }
    selected_themes = ["Identity Attack", "Operational Impact"]
    # Run live generation with single injected runner call
    master = generate_tabletop_plan(
        client,
        deployment,
        client_inputs,
        selected_themes,
        audience="Blended",
        model_runner=injected_runner,
        blueprint=None,
    )
    # Print additional final summary markers for convenience
    try:
        scns = master.get("scenarios", []) if isinstance(master, dict) else []
        injects = scns[0].get("injects", []) if scns and isinstance(scns[0], dict) else []
        pa_count = sum(1 for inj in injects if isinstance(inj.get("participant_artefact"), dict))
        print(f"PARTICIPANT_ARTEFACT_COUNT={pa_count}", flush=True)
        # Root cause presence on participant surfaces
        hrc = ""
        try:
            hrc = str(injects[0].get("inject_state", {}).get("hidden_root_cause_context") or "").strip().lower()
        except Exception:
            pass
        participant_text = []
        for inj in injects:
            pa = inj.get("participant_artefact") or {}
            participant_text.append(str(pa.get("purpose","")))
            participant_text.append(str(pa.get("content","")))
        participant_full = "\n".join(participant_text).lower()
        print(f"FACILITATOR_ROOT_CAUSE_PRESENT={'true' if bool(hrc) else 'false'}", flush=True)
        print(f"PARTICIPANT_ROOT_CAUSE_PRESENT={'true' if (hrc and hrc in participant_full) else 'false'}", flush=True)
    except Exception:
        pass