from __future__ import annotations
from dataclasses import dataclass, field
import re

@dataclass
class SECContextClassification:
    stage: str = "MENTION"
    direction: str = "unknown"
    confidence: float = 0.0
    actionable: bool = False
    reasons: list[str] = field(default_factory=list)

class SECEventContextClassifier:
    """
    Conservative semantic gate for financing/capital-structure phrases.

    A keyword hit is never enough to establish a transaction.
    Stages:
      MENTION < HISTORICAL_REFERENCE / RISK_DISCLOSURE < REGISTRATION
      < ANNOUNCED_TRANSACTION < ACTIVE_TRANSACTION < COMPLETED_TRANSACTION
    """

    HISTORICAL = (
        r"\b(previously|historically|in prior periods?|during fiscal|in \d{4}|"
        r"previous offering|prior offering|had issued|were issued|was issued)\b"
    )
    RISK = (
        r"\b(risk factors?|may issue|could issue|might issue|potential dilution|"
        r"could dilute|may dilute|future issuance|if we issue)\b"
    )
    REGISTRATION = (
        r"\b(register(?:ed|ing)?|registration statement|shelf registration|"
        r"prospectus|may offer|may sell)\b"
    )
    ANNOUNCED = (
        r"\b(announced|entered into|agreed to|commenced|launch(?:ed)?|"
        r"priced an?|pricing of|intends to offer)\b"
    )
    ACTIVE = (
        r"\b(is offering|are offering|currently offering|at-the-market program|"
        r"sales agreement|purchase agreement|placement agent)\b"
    )
    COMPLETED = (
        r"\b(completed|closed|closing of|sold \d|issued \d|net proceeds|"
        r"gross proceeds|received proceeds)\b"
    )

    NEGATIVE_CATEGORIES={"offering","warrant","convertible_debt","reverse_split"}

    def classify(self, finding):
        context=(getattr(finding,"context","") or "").lower()
        form=(getattr(finding,"filing_form","") or "").upper()
        category=(getattr(finding,"category","") or "").lower()
        reasons=[]

        # Explicit completed/active language is strongest, but generic phrase matches
        # still remain non-actionable unless the context supports transaction state.
        if re.search(self.COMPLETED,context,re.I):
            stage,conf="COMPLETED_TRANSACTION",.94
            reasons.append("Completion/proceeds language detected in filing context.")
        elif re.search(self.ACTIVE,context,re.I):
            stage,conf="ACTIVE_TRANSACTION",.90
            reasons.append("Active transaction/program language detected in filing context.")
        elif re.search(self.ANNOUNCED,context,re.I):
            stage,conf="ANNOUNCED_TRANSACTION",.86
            reasons.append("Announcement/agreement/pricing language detected in filing context.")
        elif form in {"S-1","S-3","F-1","F-3","424B3","424B5"} and re.search(self.REGISTRATION,context,re.I):
            stage,conf="REGISTRATION",.92
            reasons.append("Registration/prospectus context detected.")
        elif re.search(self.HISTORICAL,context,re.I):
            stage,conf="HISTORICAL_REFERENCE",.82
            reasons.append("Historical-reference language detected.")
        elif re.search(self.RISK,context,re.I):
            stage,conf="RISK_DISCLOSURE",.82
            reasons.append("Conditional/risk-disclosure language detected.")
        else:
            stage,conf="MENTION",.65
            reasons.append("Phrase detected without sufficient transaction-state evidence.")

        actionable=stage in {"ANNOUNCED_TRANSACTION","ACTIVE_TRANSACTION","COMPLETED_TRANSACTION"}
        direction="negative" if actionable and category in self.NEGATIVE_CATEGORIES else "unknown"

        # Registration is evidence of financing capacity/intent, not completed dilution.
        if stage=="REGISTRATION":
            reasons.append("Registration does not prove securities were issued or dilution occurred.")
        if stage in {"MENTION","HISTORICAL_REFERENCE","RISK_DISCLOSURE"}:
            reasons.append("Non-actionable context cannot create directional event pressure.")

        return SECContextClassification(stage,direction,conf,actionable,reasons)
