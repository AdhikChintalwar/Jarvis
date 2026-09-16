from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Catalyst:
    title: str
    source: str
    published_at: str
    url: str | None

    category: str
    importance: str


@dataclass
class CatalystAnalysis:
    catalysts: list[Catalyst] = field(
        default_factory=list
    )

    positive_count: int = 0
    negative_count: int = 0
    high_importance_count: int = 0

    catalyst_score: float = 50


class CatalystEngine:

    POSITIVE_TERMS = {
        "beats",
        "approval",
        "approved",
        "contract",
        "partnership",
        "record revenue",
        "upgrade",
        "raises guidance",
        "acquisition",
        "growth",
    }

    NEGATIVE_TERMS = {
        "offering",
        "dilution",
        "downgrade",
        "lawsuit",
        "investigation",
        "misses",
        "cuts guidance",
        "bankruptcy",
        "delisting",
        "reverse split",
    }

    HIGH_IMPORTANCE_TERMS = {
        "earnings",
        "fda",
        "offering",
        "merger",
        "acquisition",
        "bankruptcy",
        "guidance",
        "contract",
    }

    def analyze(
        self,
        news_items,
    ) -> CatalystAnalysis:

        catalysts = []

        positive = 0
        negative = 0
        important = 0

        for item in (
            news_items or []
        )[:30]:

            content = item.get(
                "content",
                item,
            )

            title = (
                content.get("title")
                or item.get("title")
                or ""
            )

            if not title:
                continue

            provider = (
                content
                .get(
                    "provider",
                    {},
                )
                .get(
                    "displayName",
                    ""
                )
            )

            if not provider:
                provider = (
                    item.get("publisher")
                    or "Unknown"
                )

            url = self._extract_url(
                content,
                item,
            )

            published = (
                content.get(
                    "pubDate"
                )
                or item.get(
                    "providerPublishTime"
                )
            )

            published_text = (
                self._format_date(
                    published
                )
            )

            lowered = title.lower()

            category = "neutral"

            if any(
                term in lowered
                for term
                in self.POSITIVE_TERMS
            ):
                positive += 1
                category = "positive"

            if any(
                term in lowered
                for term
                in self.NEGATIVE_TERMS
            ):
                negative += 1
                category = "negative"

            importance = "normal"

            if any(
                term in lowered
                for term
                in self.HIGH_IMPORTANCE_TERMS
            ):
                importance = "high"
                important += 1

            catalysts.append(
                Catalyst(
                    title=title,
                    source=provider,
                    published_at=(
                        published_text
                    ),
                    url=url,
                    category=category,
                    importance=importance,
                )
            )

        score = 50

        score += min(
            positive * 5,
            25,
        )

        score -= min(
            negative * 7,
            35,
        )

        score = max(
            0,
            min(100, score),
        )

        return CatalystAnalysis(
            catalysts=catalysts,
            positive_count=positive,
            negative_count=negative,
            high_importance_count=(
                important
            ),
            catalyst_score=score,
        )

    def _extract_url(
        self,
        content,
        item,
    ):

        canonical = content.get(
            "canonicalUrl",
            {},
        )

        if isinstance(
            canonical,
            dict,
        ):
            url = canonical.get("url")
            if url:
                return url

        clickthrough = content.get(
            "clickThroughUrl",
            {},
        )

        if isinstance(
            clickthrough,
            dict,
        ):
            url = clickthrough.get("url")
            if url:
                return url

        return item.get("link")

    def _format_date(
        self,
        value,
    ):

        if value is None:
            return ""

        if isinstance(
            value,
            str,
        ):
            return value

        try:

            return (
                datetime.fromtimestamp(
                    value,
                    tz=timezone.utc,
                )
                .isoformat()
            )

        except Exception:
            return str(value)