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
    PRIMARY_PRESERVING = {
        "STRONG_AGREEMENT", "AGREEMENT", "MINOR_DIFFERENCE", "REVIEW",
        "PRIMARY_ONLY", "PERIOD_MISMATCH",
        "VALUE_AGREEMENT_PERIOD_UNVERIFIED",
        "VALUE_DISAGREEMENT_PERIOD_UNVERIFIED",
        "DEFINITION_MISMATCH", "DEFINITION_UNVERIFIED",
    }

    def build(self, sec_metrics, validation, periods):
        output = {}
        for metric, sec_value in sec_metrics.items():
            check = validation.get(metric) if validation else None

            if check is None:
                output[metric] = VerifiedMetric(
                    metric, sec_value,
                    "SEC_XBRL" if sec_value is not None else "none",
                    "PRIMARY_ONLY" if sec_value is not None else "MISSING",
                    .85 if sec_value is not None else 0.0,
                    periods.get(metric),
                    {"primary_value": sec_value},
                )
                continue

            status = check.get("status", "UNKNOWN")

            if status == "MATERIAL_DISAGREEMENT":
                value, source = None, "unresolved"
            elif status == "SECONDARY_ONLY":
                value, source = check.get("secondary_value"), "YAHOO_FINANCE_FALLBACK"
            elif status in self.PRIMARY_PRESERVING:
                value, source = sec_value, "SEC_XBRL"
            else:
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
