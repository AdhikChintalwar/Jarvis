from __future__ import annotations


class PrimaryFinancialEvidenceAdapter:
    """
    Produces flattened evidence entries suitable for the existing
    EvidenceRegistry.

    IDs are stable and deterministic:
      primary_financial.revenue
      primary_financial.net_margin
      ...
    """

    def build(self, primary_report: dict) -> dict:
        verified = primary_report.get(
            "verified_financials",
            {}
        )

        evidence = {}

        for metric, item in verified.items():
            evidence_id = f"primary_financial.{metric}"

            evidence[evidence_id] = {
                "id": evidence_id,
                "value": item.get("value"),
                "source": item.get("source"),
                "status": item.get("status"),
                "confidence": item.get("confidence"),
                "period": item.get("period"),
                "evidence": item.get("evidence"),
            }

        bs = primary_report.get(
            "balance_sheet_snapshot",
            {}
        )

        evidence["primary_financial.balance_sheet_snapshot"] = {
            "id": "primary_financial.balance_sheet_snapshot",
            "value": bs.get("anchor_date"),
            "source": "SEC_XBRL",
            "status": bs.get("status"),
            "confidence": bs.get("confidence"),
            "period": bs.get("anchor_date"),
            "evidence": bs,
        }

        return evidence
