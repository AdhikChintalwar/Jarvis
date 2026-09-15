from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


# ============================================================
# PROJECT / ENVIRONMENT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(
    dotenv_path=ENV_PATH,
    override=False,
)


# ============================================================
# SEC ENDPOINTS
# ============================================================

SEC_BASE = "https://data.sec.gov"

SEC_TICKERS = (
    "https://www.sec.gov/files/"
    "company_tickers.json"
)


class SECCompanyFactsClient:

    def __init__(
        self,
        user_agent: str | None = None,
        cache_dir: str = "data/sec_companyfacts_cache",
        timeout: int = 30,
        min_request_interval: float = 0.12,
    ):

        self.user_agent = (
            user_agent
            or os.getenv(
                "SEC_USER_AGENT"
            )
        )

        if not self.user_agent:

            raise RuntimeError(
                "\nSEC_USER_AGENT is missing.\n\n"
                f"Baby checked:\n{ENV_PATH}\n\n"
                "Add this to your .env:\n\n"
                'SEC_USER_AGENT="'
                "BabyInvestor/3.0 "
                'your-email@example.com"\n'
            )

        self.cache_dir = Path(
            cache_dir
        )

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.timeout = timeout

        self.min_request_interval = (
            min_request_interval
        )

        self._last_request = 0.0

        self.session = (
            requests.Session()
        )

        self.session.headers.update(
            {
                "User-Agent":
                    self.user_agent,

                "Accept-Encoding":
                    "gzip, deflate",

                "Accept":
                    "application/json",
            }
        )

    # ========================================================
    # HTTP
    # ========================================================

    def _get_json(
        self,
        url: str,
    ) -> dict:

        elapsed = (
            time.monotonic()
            - self._last_request
        )

        if (
            elapsed
            < self.min_request_interval
        ):

            time.sleep(
                self.min_request_interval
                - elapsed
            )

        response = (
            self.session.get(
                url,
                timeout=self.timeout,
            )
        )

        self._last_request = (
            time.monotonic()
        )

        response.raise_for_status()

        return response.json()

    # ========================================================
    # TICKER → CIK
    # ========================================================

    def ticker_map(
        self,
        max_age_hours: float = 24,
    ) -> dict[str, int]:

        path = (
            self.cache_dir
            / "company_tickers.json"
        )

        if (
            path.exists()
            and (
                time.time()
                - path.stat().st_mtime
            )
            < max_age_hours * 3600
        ):

            raw = json.loads(
                path.read_text()
            )

        else:

            raw = self._get_json(
                SEC_TICKERS
            )

            path.write_text(
                json.dumps(
                    raw
                )
            )

        mapping = {}

        for row in raw.values():

            ticker = str(
                row["ticker"]
            ).upper()

            cik = int(
                row["cik_str"]
            )

            mapping[
                ticker
            ] = cik

        return mapping

    def cik_for_ticker(
        self,
        ticker: str,
    ) -> int | None:

        ticker = (
            ticker
            .upper()
            .strip()
        )

        mapping = (
            self.ticker_map()
        )

        # First try exactly as supplied.
        cik = mapping.get(
            ticker
        )

        if cik is not None:
            return cik

        # Some data vendors represent share classes
        # differently.
        alternatives = {
            ticker.replace(
                "-",
                ".",
            ),
            ticker.replace(
                ".",
                "-",
            ),
        }

        for alternative in alternatives:

            cik = mapping.get(
                alternative
            )

            if cik is not None:
                return cik

        return None

    # ========================================================
    # COMPANY FACTS
    # ========================================================

    def company_facts(
        self,
        ticker: str | None = None,
        cik: int | None = None,
        max_age_hours: float = 6,
    ) -> dict:

        if cik is None:

            if not ticker:

                raise ValueError(
                    "ticker or cik is required"
                )

            cik = (
                self.cik_for_ticker(
                    ticker
                )
            )

        if cik is None:

            raise LookupError(
                f"No SEC CIK found for "
                f"{ticker}"
            )

        path = (
            self.cache_dir
            / f"CIK{cik:010d}.json"
        )

        if (
            path.exists()
            and (
                time.time()
                - path.stat().st_mtime
            )
            < max_age_hours * 3600
        ):

            return json.loads(
                path.read_text()
            )

        url = (
            f"{SEC_BASE}/api/xbrl/"
            f"companyfacts/"
            f"CIK{cik:010d}.json"
        )

        data = self._get_json(
            url
        )

        path.write_text(
            json.dumps(
                data
            )
        )

        return data

    # ========================================================
    # XBRL HELPERS
    # ========================================================

    @staticmethod
    def concept(
        facts: dict,
        taxonomy: str,
        tag: str,
    ) -> dict | None:

        return (
            facts
            .get(
                "facts",
                {},
            )
            .get(
                taxonomy,
                {},
            )
            .get(
                tag
            )
        )

    @staticmethod
    def available_taxonomies(
        facts: dict,
    ) -> list[str]:

        return list(
            facts
            .get(
                "facts",
                {},
            )
            .keys()
        )

    @staticmethod
    def units_for(
        concept: dict | None,
    ) -> dict[str, list[dict]]:

        return (
            concept
            or {}
        ).get(
            "units",
            {},
        )

    @staticmethod
    def best_unit(
        concept: dict | None,
        preferred: tuple[str, ...],
    ) -> tuple[
        str | None,
        list[dict],
    ]:

        units = (
            SECCompanyFactsClient
            .units_for(
                concept
            )
        )

        for unit in preferred:

            if unit in units:

                return (
                    unit,
                    units[
                        unit
                    ],
                )

        if units:

            key = next(
                iter(
                    units
                )
            )

            return (
                key,
                units[
                    key
                ],
            )

        return (
            None,
            [],
        )