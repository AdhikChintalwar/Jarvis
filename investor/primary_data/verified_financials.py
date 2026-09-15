from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class VerifiedMetric:
    metric: str
    value: float | None
    source: str
    status: str
    confidence: float
    period: str | None
    evidence: dict

    def to_dict(self):
        return asdict(self)


class VerifiedFinancialBuilder:
    """
    Converts SEC + cross-validation output into the facts Baby is allowed
    to pass downstream.

    MATERIAL_DISAGREEMENT remains unresolved.
    PRIMARY_ONLY is allowed, but with lower confidence than cross-validated
    primary evidence.
    """

    def build(
        self,
        sec_metrics: dict,
        validation: dict | None,
        periods: dict[str, str | None],
    ) -> dict[str, VerifiedMetric]:
        output = {}

        for metric, sec_value in sec_metrics.items():
            check = (
                validation.get(metric)
                if validation else None
            )

            if check is None:
                output[metric] = VerifiedMetric(
                    metric=metric,
                    value=sec_value,
                    source="SEC_XBRL",
                    status="PRIMARY_ONLY" if sec_value is not None else "MISSING",
                    confidence=0.85 if sec_value is not None else 0.0,
                    period=periods.get(metric),
                    evidence={"primary_value": sec_value},
                )
                continue

            status = check.get("status", "UNKNOWN")
            selected = check.get("selected_value")

            if status == "MATERIAL_DISAGREEMENT":
                value = None
                source = "unresolved"
            elif selected is not None:
                value = selected
                source = check.get("selected_source", "SEC_XBRL")
            else:
                # SEC remains usable when comparison cannot confirm it due
                # only to secondary-source period uncertainty.
                value = sec_value
                source = "SEC_XBRL" if sec_value is not None else "none"

            output[metric] = VerifiedMetric(
                metric=metric,
                value=value,
                source=source,
                status=status,
                confidence=float(check.get("confidence", 0.0)),
                period=periods.get(metric),
                evidence=check,
            )

        return output
