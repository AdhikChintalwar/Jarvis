from __future__ import annotations


def build_sec_validation_provenance(statements, trend_report):
    """
    Builds minimal SEC concept provenance required by semantic reconciliation.
    Safe to extend with more metrics later.
    """
    out = {}

    capex_series = statements.get("capex") if hasattr(statements, "get") else None
    if capex_series is not None:
        out["capex"] = {
            "concept": getattr(capex_series, "concept", None),
            "series_quality": getattr(capex_series, "series_quality", None),
        }

    return out
