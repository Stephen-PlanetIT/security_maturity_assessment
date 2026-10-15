Objective: Fix Security Rating dual-source conflict by preventing generic maturity_gauge_caption from being injected when specialist security_rating is active.

---

Action 1:

FILE: export.py

SEARCH:
        if "maturity_gauge_caption" not in context:
            context["maturity_gauge_caption"] = maturity_gauge_caption

REPLACE:
        if "maturity_gauge_caption" not in context:
            if _sr_is_specialist:
                context["maturity_gauge_caption"] = ""
            else:
                context["maturity_gauge_caption"] = maturity_gauge_caption

VERIFICATION: python -c "print('patch applied')"