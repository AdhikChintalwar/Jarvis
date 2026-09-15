from __future__ import annotations
import re
from dataclasses import dataclass, asdict


@dataclass
class FilingSemanticFinding:
    category: str
    status: str
    phrase: str
    context: str
    confidence: float

    def to_dict(self) -> dict:
        return asdict(self)


class SECFilingSemanticEngine:
    """
    Conservative text semantics for financing/dilution language.
    This does NOT claim issuance occurred unless completion/exercise/sale
    language is present in local context.
    """

    NEGATED_CONVERTIBLE = re.compile(
        r"\b(?:non[-\s]?convertible|not\s+convertible)\b",
        re.I,
    )
    CONVERTIBLE = re.compile(
        r"(?<!non-)(?<!non )\bconvertible\s+(?:debt|note|notes|securit(?:y|ies))\b",
        re.I,
    )
    WARRANT = re.compile(r"\bwarrants?\b", re.I)
    ATM = re.compile(r"\bat[-\s]the[-\s]market\b|\bATM\s+(?:program|offering|agreement)\b", re.I)
    SHELF = re.compile(r"\bshelf\s+registration\b|\bregistration\s+statement\b", re.I)
    PROPOSED = re.compile(r"\bproposed\b|\bmay\s+(?:offer|sell|issue)\b|\bfrom\s+time\s+to\s+time\b", re.I)
    COMPLETED = re.compile(
        r"\bcompleted\b|\bclosed\b|\bissued\b|\bsold\b|\bexercised\b|"
        r"\bproceeds\s+of\b|\bnet\s+proceeds\b|\bsettled\b",
        re.I,
    )

    def analyze(self, text: str) -> list[FilingSemanticFinding]:
        if not text:
            return []
        findings = []
        for category, pattern in [
            ("convertible", self.CONVERTIBLE),
            ("warrant", self.WARRANT),
            ("atm", self.ATM),
            ("registration", self.SHELF),
        ]:
            for match in pattern.finditer(text):
                context = self._context(text, match.start(), match.end())
                if category == "convertible" and self.NEGATED_CONVERTIBLE.search(context):
                    # Do not turn "non-convertible debt" into convertible risk.
                    continue

                completed = bool(self.COMPLETED.search(context))
                proposed = bool(self.PROPOSED.search(context))

                if completed:
                    status = "completed_or_executed"
                    confidence = 0.80
                elif proposed:
                    status = "possible_or_registered"
                    confidence = 0.75
                else:
                    status = "mentioned_only"
                    confidence = 0.55

                findings.append(FilingSemanticFinding(
                    category=category,
                    status=status,
                    phrase=match.group(0),
                    context=" ".join(context.split()),
                    confidence=confidence,
                ))
        return self._dedupe(findings)

    @staticmethod
    def _context(text: str, start: int, end: int, radius: int = 350) -> str:
        return text[max(0, start-radius):min(len(text), end+radius)]

    @staticmethod
    def _dedupe(findings):
        seen = set()
        out = []
        for x in findings:
            key = (x.category, x.status, x.phrase.lower(), x.context[:120].lower())
            if key not in seen:
                seen.add(key)
                out.append(x)
        return out

    @staticmethod
    def dilution_summary(findings: list[FilingSemanticFinding]) -> dict:
        completed = [x for x in findings if x.status == "completed_or_executed"]
        possible = [x for x in findings if x.status == "possible_or_registered"]
        mentioned = [x for x in findings if x.status == "mentioned_only"]

        score = min(
            100,
            len(completed) * 25 +
            len(possible) * 8 +
            len(mentioned) * 2
        )
        level = "low"
        if score >= 60:
            level = "high"
        elif score >= 25:
            level = "moderate"

        return {
            "dilution_risk_score": score,
            "dilution_risk_level": level,
            "completed_or_executed_count": len(completed),
            "possible_or_registered_count": len(possible),
            "mentioned_only_count": len(mentioned),
            "warning": (
                "Registration/ATM/warrant/convertible references do not by themselves prove dilution occurred."
            ),
        }
