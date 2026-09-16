from __future__ import annotations

from investor.committee.models import (
    AnalystVerdict,
)

from investor.committee.nemotron_client import (
    NemotronClient,
)


ANALYST_SYSTEM_PROMPT = """
You are Baby Investor's senior equity analyst.

You will receive MULTIPLE stocks in one request.

Analyze every stock independently using only the supplied evidence,
while also comparing evidence quality and opportunity strength across
the batch.

Do NOT assume the highest scanner score is the best investment.

Never invent:
- financial figures
- prices
- filings
- catalysts
- analyst targets
- institutional buying
- company events
- news

If information is not present, treat it as unknown.

Important distinctions:

Strong price action is not the same as:
- a good company
- attractive valuation
- low risk
- a good entry

High relative volume does NOT prove institutional accumulation.

SEC registration does NOT prove shares were actually issued.

SEC language can represent:
- active financing
- historical financing
- boilerplate
- hypothetical financing
- future authorization

Use context carefully.

For every candidate evaluate:

1. price and volume behavior
2. trend quality
3. momentum and extension
4. fundamental quality
5. financial health
6. liquidity
7. dilution risk
8. distress risk
9. catalysts
10. volatility
11. drawdown
12. entry structure
13. evidence completeness
14. contradictions

Allowed decisions:

STRONG_CANDIDATE
CANDIDATE
WATCH
WAIT
AVOID
INSUFFICIENT_DATA

Return ONLY valid JSON.

Schema:

{
  "candidates": [
    {
      "symbol": "ABC",
      "decision": "WATCH",
      "conviction": 0,
      "evidence_quality": 0,

      "thesis": "...",

      "bull_case": [
        "..."
      ],

      "bear_case": [
        "..."
      ],

      "key_risks": [
        "..."
      ],

      "catalysts": [
        "..."
      ],

      "entry_view": "...",

      "invalidation": [
        "..."
      ],

      "missing_information": [
        "..."
      ],

      "reasoning_summary": "..."
    }
  ]
}

Return exactly one candidate result for every supplied symbol.

Be concise.

The purpose of this stage is structured investment screening,
not long-form investment research.

Keep:
- thesis <= 120 words
- reasoning_summary <= 100 words
- each list <= 5 items
- each list item <= 35 words

Return compact valid JSON.
Do not include commentary outside JSON.
"""


class NemotronAnalyst:

    def __init__(
        self,
        client: NemotronClient,
    ):

        self.client = client

    def analyze(
        self,
        symbol: str,
        evidence: dict,
    ) -> AnalystVerdict:

        results = self.analyze_batch(
            [
                {
                    "symbol": symbol,
                    "evidence": evidence,
                }
            ]
        )

        if symbol not in results:

            raise RuntimeError(
                f"Nemotron omitted {symbol}"
            )

        return results[symbol]

    def analyze_batch(
        self,
        candidates: list[dict],
    ) -> dict[str, AnalystVerdict]:

        symbols = [
            str(
                item["symbol"]
            ).upper()
            for item in candidates
        ]

        payload = {
            "task": (
                "Analyze every supplied security. "
                "Return one result per ticker."
            ),

            "candidate_count": len(
                candidates
            ),

            "candidates": candidates,
        }

        task_suffix = "_".join(
            symbols
        )

        result = self.client.reason_json(
            system_prompt=ANALYST_SYSTEM_PROMPT,
            payload=payload,
            task_name=f"batch_analyst_{task_suffix}",

            temperature=0.05,

            # Enough room for 5 concise stock reports.
            max_tokens=max(
                3000,
                min(
                    6500,
                    len(candidates) * 1100,
                ),
            ),

            # Pipeline handles failures more intelligently.
            retries=1,

            # IMPORTANT:
            # Extended Nemotron reasoning is not needed here.
            enable_thinking=False,
        )

        output = {}

        raw_candidates = result.get(
            "candidates",
            []
        )

        if not isinstance(
            raw_candidates,
            list,
        ):

            raise ValueError(
                "Analyst response did not "
                "contain candidates list."
            )

        for item in raw_candidates:

            if not isinstance(
                item,
                dict,
            ):
                continue

            symbol = str(
                item.get(
                    "symbol",
                    "",
                )
            ).upper()

            if not symbol:
                continue

            output[
                symbol
            ] = AnalystVerdict(

                symbol=symbol,

                decision=str(
                    item.get(
                        "decision",
                        "WATCH",
                    )
                ).upper(),

                conviction=self._number(
                    item.get(
                        "conviction"
                    )
                ),

                evidence_quality=self._number(
                    item.get(
                        "evidence_quality"
                    )
                ),

                thesis=str(
                    item.get(
                        "thesis",
                        "",
                    )
                ),

                bull_case=self._list(
                    item.get(
                        "bull_case"
                    )
                ),

                bear_case=self._list(
                    item.get(
                        "bear_case"
                    )
                ),

                key_risks=self._list(
                    item.get(
                        "key_risks"
                    )
                ),

                catalysts=self._list(
                    item.get(
                        "catalysts"
                    )
                ),

                entry_view=str(
                    item.get(
                        "entry_view",
                        "",
                    )
                ),

                invalidation=self._list(
                    item.get(
                        "invalidation"
                    )
                ),

                missing_information=self._list(
                    item.get(
                        "missing_information"
                    )
                ),

                reasoning_summary=str(
                    item.get(
                        "reasoning_summary",
                        "",
                    )
                ),

                raw=item,
            )

        return output

    def _number(
        self,
        value,
    ):

        try:

            return max(
                0.0,
                min(
                    100.0,
                    float(
                        value
                    ),
                ),
            )

        except Exception:

            return 0.0

    def _list(
        self,
        value,
    ):

        if not isinstance(
            value,
            list,
        ):
            return []

        return [
            str(item)
            for item
            in value
        ]