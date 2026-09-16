from __future__ import annotations

from investor.committee.models import (
    AnalystVerdict,
    CriticVerdict,
)

from investor.committee.nemotron_client import (
    NemotronClient,
)


CRITIC_SYSTEM_PROMPT = """
You are Baby Investor's adversarial investment-risk committee.

You will receive MULTIPLE securities.

Each security includes:
- factual evidence
- an analyst's investment thesis

Your job is to challenge each thesis.

Do NOT simply agree with the analyst.

For every security search for:

- unsupported conclusions
- confirmation bias
- momentum chasing
- misleading interpretation of abnormal volume
- extreme extension
- weak liquidity
- excessive volatility
- severe drawdown
- poor financial health
- negative free cash flow
- weak cash runway
- financing dependence
- dilution risk
- warrants
- convertible financing
- going-concern risk
- stale or weak catalysts
- poor entry structure
- weak risk/reward
- incomplete evidence
- contradictions between price and business quality

High relative volume does NOT prove institutional accumulation.

Registration statements do NOT prove dilution has already occurred.

Never invent facts.

Return ONLY valid JSON.

Schema:

{
  "candidates": [
    {
      "symbol": "ABC",

      "thesis_survives": true,

      "adjusted_conviction": 0,

      "strongest_objection": "...",

      "hidden_risks": [
        "..."
      ],

      "unsupported_claims": [
        "..."
      ],

      "contradictions": [
        "..."
      ],

      "what_would_change_view": [
        "..."
      ],

      "final_warning": "..."
    }
  ]
}

Return exactly one result for every supplied symbol.

Be concise.

This is an adversarial screening stage.

For each company:
- strongest_objection <= 80 words
- final_warning <= 80 words
- each list <= 5 items
- each list item <= 30 words

Return compact valid JSON only.
"""


class NemotronCritic:

    def __init__(
        self,
        client: NemotronClient,
    ):

        self.client = client

    def critique(
        self,
        symbol: str,
        evidence: dict,
        analyst: AnalystVerdict,
    ) -> CriticVerdict:

        results = self.critique_batch(
            [
                {
                    "symbol": symbol,
                    "evidence": evidence,
                    "analyst": analyst.to_dict(),
                }
            ]
        )

        if symbol not in results:

            raise RuntimeError(
                f"Nemotron critic omitted {symbol}"
            )

        return results[symbol]

    def critique_batch(
        self,
        candidates: list[dict],
    ) -> dict[str, CriticVerdict]:

        symbols = [
            str(
                item["symbol"]
            ).upper()
            for item in candidates
        ]

        payload = {
            "task": (
                "Adversarially review every "
                "analyst thesis."
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
            system_prompt=CRITIC_SYSTEM_PROMPT,
            payload=payload,
            task_name=f"batch_critic_{task_suffix}",

            temperature=0.03,

            max_tokens=max(
                2500,
                min(
                    5500,
                    len(candidates) * 900,
                ),
            ),

            retries=1,

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
                "Critic response did not "
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

            survives = item.get(
                "thesis_survives",
                False,
            )

            if isinstance(
                survives,
                str,
            ):

                survives = (
                    survives
                    .strip()
                    .lower()
                    in {
                        "true",
                        "yes",
                        "1",
                    }
                )

            output[
                symbol
            ] = CriticVerdict(

                symbol=symbol,

                thesis_survives=bool(
                    survives
                ),

                adjusted_conviction=self._number(
                    item.get(
                        "adjusted_conviction"
                    )
                ),

                strongest_objection=str(
                    item.get(
                        "strongest_objection",
                        "",
                    )
                ),

                hidden_risks=self._list(
                    item.get(
                        "hidden_risks"
                    )
                ),

                unsupported_claims=self._list(
                    item.get(
                        "unsupported_claims"
                    )
                ),

                contradictions=self._list(
                    item.get(
                        "contradictions"
                    )
                ),

                what_would_change_view=self._list(
                    item.get(
                        "what_would_change_view"
                    )
                ),

                final_warning=str(
                    item.get(
                        "final_warning",
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