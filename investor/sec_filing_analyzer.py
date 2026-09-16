from __future__ import annotations

import re
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup


@dataclass
class SECTextFinding:
    category: str
    phrase: str
    severity: str

    filing_form: str
    filing_date: str
    filing_url: str

    context: str

    score: float


@dataclass
class DeepSECAnalysis:
    filings_scanned: int = 0

    offering_flags: list[SECTextFinding] = field(
        default_factory=list
    )

    warrant_flags: list[SECTextFinding] = field(
        default_factory=list
    )

    debt_flags: list[SECTextFinding] = field(
        default_factory=list
    )

    going_concern_flags: list[SECTextFinding] = field(
        default_factory=list
    )

    reverse_split_flags: list[SECTextFinding] = field(
        default_factory=list
    )

    all_findings: list[SECTextFinding] = field(
        default_factory=list
    )

    dilution_score: float = 0.0
    dilution_risk: str = "unknown"

    distress_score: float = 0.0
    distress_risk: str = "unknown"

    summary: list[str] = field(
        default_factory=list
    )


class SECFilingAnalyzer:

    RULES = {
        "offering": [
            {
                "pattern": r"\bat[- ]the[- ]market\b",
                "label": "at-the-market offering",
                "severity": "high",
                "weight": 18,
            },
            {
                "pattern": r"\bregistered direct offering\b",
                "label": "registered direct offering",
                "severity": "high",
                "weight": 18,
            },
            {
                "pattern": r"\bpublic offering\b",
                "label": "public offering",
                "severity": "high",
                "weight": 15,
            },
            {
                "pattern": r"\bshelf registration\b",
                "label": "shelf registration",
                "severity": "medium",
                "weight": 10,
            },
            {
                "pattern": r"\boffer and sell\b",
                "label": "offer and sell securities",
                "severity": "medium",
                "weight": 8,
            },
        ],

        "warrant": [
            {
                "pattern": r"\bwarrant exercise\b",
                "label": "warrant exercise",
                "severity": "high",
                "weight": 14,
            },
            {
                "pattern": r"\bwarrants?\b",
                "label": "warrants",
                "severity": "medium",
                "weight": 7,
            },
        ],

        "convertible_debt": [
            {
                "pattern": (
                    r"(?<!non-)"
                    r"(?<!non )"
                    r"\bconvertible notes?\b"
                ),
                "label": "convertible notes",
                "severity": "high",
                "weight": 15,
            },
            {
                "pattern": (
                    r"(?<!non-)"
                    r"(?<!non )"
                    r"\bconvertible debt\b"
                ),
                "label": "convertible debt",
                "severity": "high",
                "weight": 15,
            },
            {
                "pattern": (
                    r"(?<!non-)"
                    r"(?<!non )"
                    r"\bconvertible securities\b"
                ),
                "label": "convertible securities",
                "severity": "medium",
                "weight": 10,
            },
        ],

        "going_concern": [
            {
                "pattern": r"\bsubstantial doubt\b.{0,180}\bgoing concern\b",
                "label": "substantial doubt about going concern",
                "severity": "high",
                "weight": 25,
            },
            {
                "pattern": r"\bgoing concern\b",
                "label": "going-concern reference",
                "severity": "medium",
                "weight": 10,
            },
        ],

        "reverse_split": [
            {
                "pattern": r"\breverse stock split\b",
                "label": "reverse stock split",
                "severity": "medium",
                "weight": 8,
            },
            {
                "pattern": r"\breverse share split\b",
                "label": "reverse share split",
                "severity": "medium",
                "weight": 8,
            },
        ],
    }

    FORMS_TO_SCAN = {
        "F-1",
        "F-3",
        "S-1",
        "S-3",
        "424B3",
        "424B5",
        "6-K",
        "8-K",
        "20-F",
        "10-K",
        "10-Q",
    }

    OFFERING_FORMS = {
        "F-1",
        "F-3",
        "S-1",
        "S-3",
        "424B3",
        "424B5",
    }

    OPERATING_FORMS = {
        "10-K",
        "10-Q",
        "20-F",
        "6-K",
        "8-K",
    }

    def __init__(
        self,
        user_agent=(
            "BabyInvestor/0.31 "
            "adhikchintalwar12@gmail.com"
        ),
    ):
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    def analyze(
        self,
        sec_analysis,
        max_filings: int = 8,
    ) -> DeepSECAnalysis:

        result = DeepSECAnalysis()

        filings = [
            filing
            for filing in sec_analysis.recent_filings
            if (
                filing.form in self.FORMS_TO_SCAN
                and filing.filing_url
            )
        ][:max_filings]

        for filing in filings:

            try:
                text = self._download_text(
                    filing.filing_url
                )

            except Exception as error:
                print(
                    f"SEC document warning "
                    f"{filing.form}: {error}"
                )
                continue

            result.filings_scanned += 1

            findings = self._analyze_filing(
                text=text,
                filing=filing,
            )

            result.all_findings.extend(
                findings
            )

        self._categorize(
            result
        )

        result.dilution_score = round(
            self._dilution_score(
                result
            ),
            1,
        )

        result.distress_score = round(
            self._distress_score(
                result
            ),
            1,
        )

        result.dilution_risk = (
            self._risk_level(
                result.dilution_score
            )
        )

        result.distress_risk = (
            self._risk_level(
                result.distress_score
            )
        )

        result.summary = (
            self._build_summary(
                result
            )
        )

        return result

    def _download_text(
        self,
        url,
    ):

        response = requests.get(
            url,
            headers=self.headers,
            timeout=20,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        for tag in soup(
            [
                "script",
                "style",
                "noscript",
            ]
        ):
            tag.decompose()

        text = soup.get_text(
            " ",
            strip=True,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.lower()

    def _analyze_filing(
        self,
        text,
        filing,
    ):

        findings = []

        # Maximum ONE strongest finding
        # per category per filing.
        #
        # This prevents:
        #
        # F-3:
        #   public offering
        #   securities offering
        #   offer and sell
        #   shelf
        #
        # from being counted as four
        # independent risks.

        for category, rules in (
            self.RULES.items()
        ):

            category_matches = []

            for rule in rules:

                match = re.search(
                    rule["pattern"],
                    text,
                    flags=re.I | re.S,
                )

                if not match:
                    continue

                context = self._context(
                    text=text,
                    start=match.start(),
                    end=match.end(),
                )

                score = self._adjust_score(
                    category=category,
                    base_score=rule["weight"],
                    filing_form=filing.form,
                )

                category_matches.append(
                    SECTextFinding(
                        category=category,
                        phrase=rule["label"],
                        severity=rule[
                            "severity"
                        ],
                        filing_form=filing.form,
                        filing_date=(
                            filing.filing_date
                        ),
                        filing_url=(
                            filing.filing_url
                        ),
                        context=context,
                        score=score,
                    )
                )

            if category_matches:

                strongest = max(
                    category_matches,
                    key=lambda item: item.score,
                )

                findings.append(
                    strongest
                )

        return findings

    def _context(
        self,
        text,
        start,
        end,
        radius=260,
    ):

        left = max(
            0,
            start - radius,
        )

        right = min(
            len(text),
            end + radius,
        )

        snippet = text[
            left:right
        ]

        return (
            snippet
            .replace("\n", " ")
            .strip()
        )

    def _adjust_score(
        self,
        category,
        base_score,
        filing_form,
    ):

        score = float(
            base_score
        )

        # Offering language is more meaningful
        # inside an actual securities-registration /
        # prospectus filing.

        if (
            category
            in {
                "offering",
                "warrant",
                "convertible_debt",
            }
            and filing_form
            in self.OFFERING_FORMS
        ):
            score *= 1.25

        # Going concern has more meaning
        # in operating / annual financial filings
        # than merely being referenced in
        # a securities prospectus.

        if (
            category
            == "going_concern"
            and filing_form
            in self.OPERATING_FORMS
        ):
            score *= 1.35

        return min(
            score,
            30,
        )

    def _categorize(
        self,
        result,
    ):

        for finding in (
            result.all_findings
        ):

            if finding.category == "offering":

                result.offering_flags.append(
                    finding
                )

            elif finding.category == "warrant":

                result.warrant_flags.append(
                    finding
                )

            elif (
                finding.category
                == "convertible_debt"
            ):

                result.debt_flags.append(
                    finding
                )

            elif (
                finding.category
                == "going_concern"
            ):

                result.going_concern_flags.append(
                    finding
                )

            elif (
                finding.category
                == "reverse_split"
            ):

                result.reverse_split_flags.append(
                    finding
                )

    def _dilution_score(
        self,
        result,
    ):

        categories = {
            "offering":
                result.offering_flags,

            "warrant":
                result.warrant_flags,

            "convertible":
                result.debt_flags,

            "reverse_split":
                result.reverse_split_flags,
        }

        score = 0

        for findings in (
            categories.values()
        ):

            if not findings:
                continue

            # strongest occurrence
            score += max(
                item.score
                for item in findings
            )

            # repeated appearances add
            # some evidence, but not
            # full duplicate scoring.

            extra_count = max(
                0,
                len(findings) - 1,
            )

            score += min(
                extra_count * 3,
                9,
            )

        return min(
            score,
            100,
        )

    def _distress_score(
        self,
        result,
    ):

        if not result.going_concern_flags:

            return 0

        strongest = max(
            item.score
            for item
            in result.going_concern_flags
        )

        repeated = max(
            0,
            len(
                result.going_concern_flags
            ) - 1,
        )

        return min(
            100,
            strongest
            + min(
                repeated * 5,
                15,
            ),
        )

    def _risk_level(
        self,
        score,
    ):

        if score >= 70:
            return "very_high"

        if score >= 45:
            return "high"

        if score >= 20:
            return "moderate"

        return "low"

    def _build_summary(
        self,
        result,
    ):

        summary = []

        if result.offering_flags:

            forms = sorted(
                {
                    flag.filing_form
                    for flag
                    in result.offering_flags
                }
            )

            summary.append(
                "Offering-related language "
                f"was detected in: "
                f"{', '.join(forms)}."
            )

        if result.warrant_flags:

            summary.append(
                "Warrant language was detected; "
                "review context before treating "
                "it as active dilution."
            )

        if result.debt_flags:

            summary.append(
                "Convertible-financing language "
                "was detected."
            )

        if result.going_concern_flags:

            summary.append(
                "Going-concern language requires "
                "manual/contextual review."
            )

        if result.reverse_split_flags:

            summary.append(
                "Reverse-split terminology was "
                "detected, but may describe "
                "historical events."
            )

        if not summary:

            summary.append(
                "No major financing or distress "
                "language detected in scanned "
                "filings."
            )

        return summary