from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class NumericClaim:
    value: float
    suffix: str | None
    raw: str
    start: int
    end: int
    context: str


@dataclass
class NumericValidationResult:
    valid: bool
    reason: str
    numbers_checked: int = 0
    numbers_ignored: int = 0


class NumericValidator:
    """
    Baby Evidence Integrity V2.2.1

    Context-aware numeric validation.

    Goals
    -----
    Validate real financial numbers:

        Revenue growth is 48%
        RSI is 76.4
        Price is $25.30
        Relative volume is 2.4x

    Ignore structural numbers:

        89.5/100
             ^ denominator

        20-day breakout
        ^ window length

        EMA20
           ^ indicator period

        RSI14
           ^ indicator period

        Q2 2026
        ^ quarter / year metadata

    Verify common derived calculations:

        price vs EMA20
        price vs EMA50
        price vs SMA20
        price vs SMA50
        price vs SMA200

    Example:

        price = 26.18
        EMA20 = 23.80

        "Price is 10% above EMA20"

        Derived:
        (26.18 / 23.80 - 1) * 100
        ~= 10%

        -> valid
    """

    NUMBER_PATTERN = re.compile(
        r"""
        (?<![\w.])
        (?P<currency>\$)?
        (?P<number>-?\d+(?:,\d{3})*(?:\.\d+)?)
        \s*
        (?P<suffix>%|x|X|[KMBT])?
        """,
        re.VERBOSE,
    )

    INDICATOR_PERIOD_PATTERN = re.compile(
        r"""
        \b
        (
            EMA
            |
            SMA
            |
            RSI
            |
            ATR
            |
            VWAP
        )
        \s*
        \d+
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    TIME_WINDOW_PATTERN = re.compile(
        r"""
        \b
        \d+
        \s*
        -
        \s*
        (
            day
            |
            week
            |
            month
            |
            year
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    QUARTER_PATTERN = re.compile(
        r"""
        \bQ[1-4]\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    YEAR_PATTERN = re.compile(
        r"""
        \b
        (19|20)
        \d{2}
        \b
        """,
        re.VERBOSE,
    )

    SCORE_DENOMINATOR_PATTERN = re.compile(
        r"""
        /
        \s*
        100
        \b
        """,
        re.VERBOSE,
    )

    DERIVED_MA_PATTERN = re.compile(
        r"""
        (?P<pct>-?\d+(?:\.\d+)?)
        \s*%
        \s*
        (?P<direction>
            above
            |
            below
        )
        \s*
        (?P<indicator>
            EMA
            |
            SMA
        )
        \s*
        (?P<period>
            9
            |
            20
            |
            50
            |
            100
            |
            200
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    def validate(
        self,
        statement: str,
        evidence_ids: list[str],
        evidence_registry: dict,
    ) -> NumericValidationResult:

        statement = statement or ""

        claims = self._extract_claim_numbers(
            statement
        )

        if not claims:
            return NumericValidationResult(
                valid=True,
                reason=(
                    "Claim contains no explicit numeric "
                    "value requiring validation."
                ),
                numbers_checked=0,
                numbers_ignored=0,
            )

        ignored_claims = []
        direct_claims = []

        derived_matches = (
            self._extract_derived_ma_claims(
                statement
            )
        )

        derived_spans = [
            (
                item["number_start"],
                item["number_end"],
            )
            for item in derived_matches
        ]

        for claim in claims:

            if self._should_ignore_number(
                statement,
                claim,
            ):
                ignored_claims.append(
                    claim
                )
                continue

            if self._inside_spans(
                claim.start,
                claim.end,
                derived_spans,
            ):
                # This percentage will be checked
                # mathematically below.
                continue

            direct_claims.append(
                claim
            )

        evidence_numbers = (
            self._collect_evidence_numbers(
                evidence_ids,
                evidence_registry,
            )
        )

        unmatched = []

        for claim in direct_claims:

            if not evidence_numbers:
                unmatched.append(
                    claim.raw
                )
                continue

            matched = any(
                self._matches(
                    claim,
                    evidence_value,
                )
                for evidence_value
                in evidence_numbers
            )

            if not matched:
                unmatched.append(
                    claim.raw
                )

        derived_failures = []

        for derived in derived_matches:

            result = (
                self._validate_ma_derivation(
                    derived,
                    evidence_ids,
                    evidence_registry,
                )
            )

            if not result["valid"]:
                derived_failures.append(
                    result["reason"]
                )

        if unmatched or derived_failures:

            reasons = []

            if unmatched:
                reasons.append(
                    "Unmatched direct numeric value(s): "
                    + ", ".join(
                        unmatched
                    )
                )

            if derived_failures:
                reasons.extend(
                    derived_failures
                )

            return NumericValidationResult(
                valid=False,
                reason="; ".join(
                    reasons
                ),
                numbers_checked=(
                    len(direct_claims)
                    + len(derived_matches)
                ),
                numbers_ignored=len(
                    ignored_claims
                ),
            )

        return NumericValidationResult(
            valid=True,
            reason=(
                "Numeric values are consistent with "
                "referenced evidence or verified "
                "derived calculations."
            ),
            numbers_checked=(
                len(direct_claims)
                + len(derived_matches)
            ),
            numbers_ignored=len(
                ignored_claims
            ),
        )

    # ========================================================
    # Extraction
    # ========================================================

    def _extract_claim_numbers(
        self,
        text: str,
    ) -> list[NumericClaim]:

        results = []

        for match in self.NUMBER_PATTERN.finditer(
            text
        ):

            raw_number = (
                match.group(
                    "number"
                )
                .replace(",", "")
            )

            try:
                value = float(
                    raw_number
                )
            except Exception:
                continue

            suffix = match.group(
                "suffix"
            )

            currency = match.group(
                "currency"
            )

            raw = match.group(
                0
            ).strip()

            if currency:
                raw = "$" + raw.lstrip(
                    "$"
                )

            start = match.start()
            end = match.end()

            context_start = max(
                0,
                start - 30,
            )

            context_end = min(
                len(text),
                end + 30,
            )

            context = text[
                context_start:
                context_end
            ]

            results.append(
                NumericClaim(
                    value=value,
                    suffix=suffix,
                    raw=raw,
                    start=start,
                    end=end,
                    context=context,
                )
            )

        return results

    def _extract_derived_ma_claims(
        self,
        text: str,
    ) -> list[dict]:

        results = []

        for match in (
            self.DERIVED_MA_PATTERN
            .finditer(
                text
            )
        ):

            pct_start = (
                match.start(
                    "pct"
                )
            )

            pct_end = (
                match.end(
                    "pct"
                )
            )

            results.append(
                {
                    "percentage":
                        float(
                            match.group(
                                "pct"
                            )
                        ),

                    "direction":
                        match.group(
                            "direction"
                        ).lower(),

                    "indicator":
                        match.group(
                            "indicator"
                        ).upper(),

                    "period":
                        int(
                            match.group(
                                "period"
                            )
                        ),

                    "number_start":
                        pct_start,

                    "number_end":
                        pct_end,
                }
            )

        return results

    # ========================================================
    # Context filters
    # ========================================================

    def _should_ignore_number(
        self,
        statement: str,
        claim: NumericClaim,
    ) -> bool:

        start = claim.start
        end = claim.end

        # ----------------------------------------------------
        # Indicator periods
        #
        # EMA20
        # RSI14
        # SMA200
        # ----------------------------------------------------

        for match in (
            self.INDICATOR_PERIOD_PATTERN
            .finditer(
                statement
            )
        ):

            if self._overlaps(
                start,
                end,
                match.start(),
                match.end(),
            ):
                return True

        # ----------------------------------------------------
        # Time windows
        #
        # 20-day breakout
        # 30-day volume
        # ----------------------------------------------------

        for match in (
            self.TIME_WINDOW_PATTERN
            .finditer(
                statement
            )
        ):

            if self._overlaps(
                start,
                end,
                match.start(),
                match.end(),
            ):
                return True

        # ----------------------------------------------------
        # Quarter labels
        #
        # Q2
        # ----------------------------------------------------

        for match in (
            self.QUARTER_PATTERN
            .finditer(
                statement
            )
        ):

            if self._overlaps(
                start,
                end,
                match.start(),
                match.end(),
            ):
                return True

        # ----------------------------------------------------
        # Calendar years
        #
        # 2026
        # ----------------------------------------------------

        for match in (
            self.YEAR_PATTERN
            .finditer(
                statement
            )
        ):

            if self._overlaps(
                start,
                end,
                match.start(),
                match.end(),
            ):
                return True

        # ----------------------------------------------------
        # Score denominator
        #
        # 89.5/100
        #
        # Validate 89.5.
        # Ignore 100.
        # ----------------------------------------------------

        for match in (
            self.SCORE_DENOMINATOR_PATTERN
            .finditer(
                statement
            )
        ):

            denominator_start = (
                match.start()
            )

            denominator_end = (
                match.end()
            )

            if (
                start >= denominator_start
                and end <= denominator_end
            ):
                return True

        return False

    # ========================================================
    # Direct evidence
    # ========================================================

    def _collect_evidence_numbers(
        self,
        evidence_ids: list[str],
        evidence_registry: dict,
    ) -> list[float]:

        numbers = []

        for evidence_id in evidence_ids:

            item = evidence_registry.get(
                evidence_id
            )

            if item is None:
                continue

            value = getattr(
                item,
                "value",
                None,
            )

            numbers.extend(
                self._numbers_from_value(
                    value
                )
            )

        return numbers

    def _numbers_from_value(
        self,
        value: Any,
    ) -> list[float]:

        if value is None:
            return []

        if isinstance(
            value,
            bool,
        ):
            return []

        if isinstance(
            value,
            (int, float),
        ):

            numeric = float(
                value
            )

            if math.isfinite(
                numeric
            ):
                return [
                    numeric
                ]

            return []

        if isinstance(
            value,
            str,
        ):

            numbers = []

            for match in (
                self.NUMBER_PATTERN
                .finditer(
                    value
                )
            ):

                raw = (
                    match.group(
                        "number"
                    )
                    .replace(",", "")
                )

                try:
                    numbers.append(
                        float(
                            raw
                        )
                    )
                except Exception:
                    continue

            return numbers

        if isinstance(
            value,
            dict,
        ):

            numbers = []

            for child in (
                value.values()
            ):

                numbers.extend(
                    self._numbers_from_value(
                        child
                    )
                )

            return numbers

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            numbers = []

            for child in value:

                numbers.extend(
                    self._numbers_from_value(
                        child
                    )
                )

            return numbers

        return []

    def _matches(
        self,
        claim: NumericClaim,
        evidence_value: float,
    ) -> bool:

        claim_value = (
            claim.value
        )

        suffix = (
            claim.suffix
        )

        evidence_candidates = {
            evidence_value,
        }

        # Fraction ↔ percentage.
        #
        # evidence 0.48
        # claim 48%
        if (
            suffix == "%"
            and abs(
                evidence_value
            ) <= 2.0
        ):

            evidence_candidates.add(
                evidence_value
                * 100.0
            )

        # Also tolerate evidence already
        # expressed as percent.
        if suffix == "%":

            evidence_candidates.add(
                evidence_value
            )

        adjusted_claim = (
            claim_value
        )

        if suffix:

            suffix_upper = (
                suffix.upper()
            )

            multiplier = {
                "K":
                    1_000.0,

                "M":
                    1_000_000.0,

                "B":
                    1_000_000_000.0,

                "T":
                    1_000_000_000_000.0,
            }.get(
                suffix_upper
            )

            if multiplier:

                adjusted_claim = (
                    adjusted_claim
                    * multiplier
                )

        for candidate in (
            evidence_candidates
        ):

            if self._close(
                adjusted_claim,
                candidate,
            ):
                return True

        return False

    # ========================================================
    # Derived moving-average validation
    # ========================================================

    def _validate_ma_derivation(
        self,
        derived: dict,
        evidence_ids: list[str],
        evidence_registry: dict,
    ) -> dict:

        indicator = (
            derived[
                "indicator"
            ]
        )

        period = (
            derived[
                "period"
            ]
        )

        direction = (
            derived[
                "direction"
            ]
        )

        claimed_pct = (
            derived[
                "percentage"
            ]
        )

        price_value = (
            self._find_price_value(
                evidence_ids,
                evidence_registry,
            )
        )

        ma_value = (
            self._find_ma_value(
                indicator,
                period,
                evidence_ids,
                evidence_registry,
            )
        )

        if price_value is None:

            return {
                "valid": False,

                "reason": (
                    f"Cannot verify "
                    f"{claimed_pct:g}% "
                    f"{direction} "
                    f"{indicator}{period}: "
                    "referenced evidence does "
                    "not contain price."
                ),
            }

        if ma_value is None:

            return {
                "valid": False,

                "reason": (
                    f"Cannot verify "
                    f"{claimed_pct:g}% "
                    f"{direction} "
                    f"{indicator}{period}: "
                    "referenced evidence does "
                    f"not contain "
                    f"{indicator}{period}."
                ),
            }

        if ma_value == 0:

            return {
                "valid": False,

                "reason": (
                    f"Cannot derive distance "
                    f"from {indicator}{period} "
                    "because its value is zero."
                ),
            }

        signed_distance = (
            (
                price_value
                / ma_value
            )
            - 1.0
        ) * 100.0

        if direction == "above":

            actual_pct = (
                signed_distance
            )

        else:

            actual_pct = (
                -signed_distance
            )

        # Derived percentages can be rounded
        # aggressively in natural-language output.
        #
        # Allow:
        #   absolute difference <= 1.0 percentage point
        # OR
        #   relative difference <= 8%
        if self._derived_close(
            claimed_pct,
            actual_pct,
        ):

            return {
                "valid": True,

                "reason": (
                    f"Verified from price "
                    f"{price_value:.4f} and "
                    f"{indicator}{period} "
                    f"{ma_value:.4f}."
                ),
            }

        return {
            "valid": False,

            "reason": (
                f"Derived claim "
                f"{claimed_pct:g}% "
                f"{direction} "
                f"{indicator}{period} "
                "does not match evidence. "
                f"Calculated value is "
                f"{actual_pct:.2f}%."
            ),
        }

    def _find_price_value(
        self,
        evidence_ids: list[str],
        evidence_registry: dict,
    ) -> float | None:

        preferred_tokens = [
            ".price",
            ".current_price",
            ".close",
            ".last_price",
        ]

        # First search only cited evidence.
        value = self._find_value_by_tokens(
            evidence_ids,
            evidence_registry,
            preferred_tokens,
        )

        if value is not None:
            return value

        # Derived claims often cite the MA and
        # price separately. If Nemotron cited only
        # the MA, search the registered candidate
        # evidence for an authoritative price.
        return self._find_value_by_tokens(
            list(
                evidence_registry.keys()
            ),
            evidence_registry,
            preferred_tokens,
        )

    def _find_ma_value(
        self,
        indicator: str,
        period: int,
        evidence_ids: list[str],
        evidence_registry: dict,
    ) -> float | None:

        indicator_lower = (
            indicator.lower()
        )

        tokens = [
            f".{indicator_lower}_{period}",
            f".{indicator_lower}{period}",
            f"{indicator_lower}_{period}",
            f"{indicator_lower}{period}",
        ]

        value = self._find_value_by_tokens(
            evidence_ids,
            evidence_registry,
            tokens,
        )

        if value is not None:
            return value

        return self._find_value_by_tokens(
            list(
                evidence_registry.keys()
            ),
            evidence_registry,
            tokens,
        )

    def _find_value_by_tokens(
        self,
        evidence_ids: list[str],
        evidence_registry: dict,
        tokens: list[str],
    ) -> float | None:

        for evidence_id in (
            evidence_ids
        ):

            normalized_id = str(
                evidence_id
            ).lower()

            if not any(
                token in normalized_id
                for token in tokens
            ):
                continue

            item = evidence_registry.get(
                evidence_id
            )

            if item is None:
                continue

            value = getattr(
                item,
                "value",
                None,
            )

            if isinstance(
                value,
                bool,
            ):
                continue

            if isinstance(
                value,
                (int, float),
            ):

                numeric = float(
                    value
                )

                if math.isfinite(
                    numeric
                ):
                    return numeric

        return None

    # ========================================================
    # Utility
    # ========================================================

    def _inside_spans(
        self,
        start: int,
        end: int,
        spans: list[
            tuple[int, int]
        ],
    ) -> bool:

        for (
            span_start,
            span_end,
        ) in spans:

            if self._overlaps(
                start,
                end,
                span_start,
                span_end,
            ):
                return True

        return False

    def _overlaps(
        self,
        start_a: int,
        end_a: int,
        start_b: int,
        end_b: int,
    ) -> bool:

        return (
            start_a < end_b
            and end_a > start_b
        )

    def _close(
        self,
        a: float,
        b: float,
    ) -> bool:

        absolute_difference = abs(
            a - b
        )

        if absolute_difference <= 0.02:
            return True

        denominator = max(
            abs(a),
            abs(b),
            1.0,
        )

        relative_difference = (
            absolute_difference
            / denominator
        )

        return (
            relative_difference
            <= 0.02
        )

    def _derived_close(
        self,
        claimed: float,
        actual: float,
    ) -> bool:

        if (
            claimed < 0
            or actual < 0
        ):
            return False

        absolute_difference = abs(
            claimed
            - actual
        )

        if absolute_difference <= 1.0:
            return True

        denominator = max(
            abs(claimed),
            abs(actual),
            1.0,
        )

        relative_difference = (
            absolute_difference
            / denominator
        )

        return (
            relative_difference
            <= 0.08
        )