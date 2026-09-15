from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from investor.integrity.claim_models import (
    EvidenceItem,
)


class EvidenceRegistry:

    SOURCE_MAP = {
        "scanner":
            "Baby quantitative scanner",

        "technical":
            "Baby technical engine",

        "market":
            "Yahoo/yfinance prototype market data",

        "fundamentals":
            "Yahoo/yfinance prototype fundamentals",

        "financial_health":
            "Baby financial health engine",

        "primary_financial":
            "SEC EDGAR/XBRL primary financial intelligence with dated Yahoo annual-statement validation",

        "risk":
            "Baby risk engine",

        "classification":
            "Baby stock classifier",

        "sec":
            "SEC EDGAR",

        "deep_sec":
            "SEC EDGAR + Baby SEC analyzer",

        "catalysts":
            "Yahoo news prototype",

        "market_context":
            "Baby market-context engine",

        "data_quality":
            "Baby data-quality engine",

        "deterministic_thesis":
            "Baby deterministic thesis engine",

        "trade_plan":
            "Baby trade-plan engine",

        "abnormal_volume":
            "Baby volume-flow engine",
    }

    RELIABILITY_MAP = {
        "sec":
            "high",

        "deep_sec":
            "high",

        "technical":
            "high",

        "risk":
            "high",

        "financial_health":
            "high",

        "primary_financial":
            "high",

        "scanner":
            "high",

        "trade_plan":
            "high",

        "abnormal_volume":
            "high",

        "classification":
            "high",

        "data_quality":
            "high",

        "market":
            "medium",

        "fundamentals":
            "medium",

        "catalysts":
            "medium",

        "market_context":
            "medium",

        "deterministic_thesis":
            "medium",
    }

    def build(
        self,
        evidence: dict,
        generated_at: str | None = None,
    ) -> dict[str, EvidenceItem]:

        cleaned = self._serialize(
            evidence
        )

        registry: dict[
            str,
            EvidenceItem
        ] = {}

        self._flatten(
            value=cleaned,
            path="",
            registry=registry,
            generated_at=generated_at,
        )

        return registry

    def to_prompt_payload(
        self,
        registry: dict[str, EvidenceItem],
    ) -> list[dict]:

        rows = []

        for evidence_id, item in sorted(
            registry.items()
        ):

            rows.append(
                {
                    "id":
                        evidence_id,

                    "value":
                        item.value,

                    "source":
                        item.source,

                    "retrieved_at":
                        item.retrieved_at,

                    "reliability":
                        item.reliability,
                }
            )

        return rows

    def _flatten(
        self,
        value,
        path,
        registry,
        generated_at,
    ):

        if isinstance(
            value,
            dict,
        ):

            for key, child in value.items():

                new_path = (
                    f"{path}.{key}"
                    if path
                    else str(key)
                )

                self._flatten(
                    child,
                    new_path,
                    registry,
                    generated_at,
                )

            return

        if isinstance(
            value,
            list,
        ):

            #
            # Store simple lists directly.
            #

            if all(
                not isinstance(
                    item,
                    (dict, list),
                )
                for item in value
            ):

                if value:
                    self._add(
                        registry,
                        path,
                        value,
                        generated_at,
                    )

                return

            #
            # Structured lists get indexed.
            #

            for index, child in enumerate(
                value
            ):

                new_path = (
                    f"{path}.{index}"
                )

                self._flatten(
                    child,
                    new_path,
                    registry,
                    generated_at,
                )

            return

        if value is None:
            return

        self._add(
            registry,
            path,
            value,
            generated_at,
        )

    def _add(
        self,
        registry,
        evidence_id,
        value,
        generated_at,
    ):

        if not evidence_id:
            return

        root = evidence_id.split(
            ".",
            1,
        )[0]

        source = self.SOURCE_MAP.get(
            root,
            "Baby research pipeline",
        )

        reliability = (
            self.RELIABILITY_MAP.get(
                root,
                "medium",
            )
        )

        registry[evidence_id] = (
            EvidenceItem(
                evidence_id=evidence_id,
                value=value,
                source=source,
                retrieved_at=generated_at,
                reliability=reliability,
            )
        )

    def _serialize(
        self,
        value: Any,
    ):

        if value is None:
            return None

        if isinstance(
            value,
            Enum,
        ):
            return value.value

        if is_dataclass(
            value
        ):
            return self._serialize(
                asdict(value)
            )

        if isinstance(
            value,
            dict,
        ):
            return {
                str(key):
                    self._serialize(child)

                for key, child
                in value.items()
            }

        if isinstance(
            value,
            (list, tuple, set),
        ):
            return [
                self._serialize(child)
                for child
                in value
            ]

        return value