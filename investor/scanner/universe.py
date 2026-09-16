from __future__ import annotations

import io
import re
import time

from pathlib import Path

import pandas as pd
import requests

from investor.scanner.models import (
    UniverseStock,
)


class USStockUniverse:

    NASDAQ_URL = (
        "https://www.nasdaqtrader.com/"
        "dynamic/SymDir/nasdaqlisted.txt"
    )

    OTHER_URL = (
        "https://www.nasdaqtrader.com/"
        "dynamic/SymDir/otherlisted.txt"
    )

    def __init__(
        self,
        cache_hours: int = 12,
    ):

        self.cache_hours = (
            cache_hours
        )

        self.cache_dir = Path(
            "data/scanner_cache"
        )

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def load(
        self,
        limit: int | None = None,
    ) -> list[UniverseStock]:

        nasdaq = self._load_file(
            name="nasdaq",
            url=self.NASDAQ_URL,
        )

        other = self._load_file(
            name="other",
            url=self.OTHER_URL,
        )

        stocks = []

        stocks.extend(
            self._parse_nasdaq(
                nasdaq
            )
        )

        stocks.extend(
            self._parse_other(
                other
            )
        )

        deduplicated = {}

        for stock in stocks:

            if not self._eligible(
                stock
            ):
                continue

            deduplicated[
                stock.symbol
            ] = stock

        result = sorted(
            deduplicated.values(),
            key=lambda item: item.symbol,
        )

        if limit is not None:

            result = result[
                :limit
            ]

        return result

    def _load_file(
        self,
        name,
        url,
    ):

        path = (
            self.cache_dir
            / f"{name}_listed.txt"
        )

        if path.exists():

            age_hours = (
                time.time()
                - path.stat().st_mtime
            ) / 3600

            if age_hours < (
                self.cache_hours
            ):

                return path.read_text(
                    errors="ignore"
                )

        response = requests.get(
            url,
            timeout=30,

            headers={
                "User-Agent":
                    "BabyInvestorScanner/1.1"
            },
        )

        response.raise_for_status()

        path.write_text(
            response.text
        )

        return response.text

    def _parse_nasdaq(
        self,
        text,
    ):

        frame = pd.read_csv(
            io.StringIO(text),
            sep="|",
            dtype=str,
        )

        results = []

        for _, row in (
            frame.iterrows()
        ):

            symbol = str(
                row.get(
                    "Symbol",
                    "",
                )
            ).strip()

            if (
                not symbol
                or symbol.startswith(
                    "File Creation Time"
                )
            ):
                continue

            name = str(
                row.get(
                    "Security Name",
                    "",
                )
            ).strip()

            etf = (
                str(
                    row.get(
                        "ETF",
                        "N",
                    )
                )
                .upper()
                == "Y"
            )

            test_issue = (
                str(
                    row.get(
                        "Test Issue",
                        "N",
                    )
                )
                .upper()
                == "Y"
            )

            results.append(
                UniverseStock(

                    symbol=symbol,

                    provider_symbol=(
                        self._provider_symbol(
                            symbol
                        )
                    ),

                    name=name,

                    exchange="NASDAQ",

                    is_etf=etf,

                    is_test_issue=(
                        test_issue
                    ),
                )
            )

        return results

    def _parse_other(
        self,
        text,
    ):

        frame = pd.read_csv(
            io.StringIO(text),
            sep="|",
            dtype=str,
        )

        exchange_map = {

            "A": "NYSE American",

            "N": "NYSE",

            "P": "NYSE Arca",

            "Z": "Cboe BZX",

            "V": "IEX",
        }

        results = []

        for _, row in (
            frame.iterrows()
        ):

            symbol = str(
                row.get(
                    "ACT Symbol",
                    "",
                )
            ).strip()

            if (
                not symbol
                or symbol.startswith(
                    "File Creation Time"
                )
            ):
                continue

            name = str(
                row.get(
                    "Security Name",
                    "",
                )
            ).strip()

            exchange_code = str(
                row.get(
                    "Exchange",
                    "",
                )
            ).strip()

            etf = (
                str(
                    row.get(
                        "ETF",
                        "N",
                    )
                )
                .upper()
                == "Y"
            )

            test_issue = (
                str(
                    row.get(
                        "Test Issue",
                        "N",
                    )
                )
                .upper()
                == "Y"
            )

            results.append(
                UniverseStock(

                    symbol=symbol,

                    provider_symbol=(
                        self._provider_symbol(
                            symbol
                        )
                    ),

                    name=name,

                    exchange=(
                        exchange_map.get(
                            exchange_code,
                            exchange_code,
                        )
                    ),

                    is_etf=etf,

                    is_test_issue=(
                        test_issue
                    ),
                )
            )

        return results

    def _eligible(
        self,
        stock,
    ):

        if stock.is_etf:
            return False

        if stock.is_test_issue:
            return False

        symbol = (
            stock.symbol
            .strip()
            .upper()
        )

        name = (
            stock.name
            .strip()
            .upper()
        )

        if not symbol:
            return False

        #
        # Remove preferred-share style
        # symbols such as:
        #
        # BAC$E
        # ALL$B
        #

        if "$" in symbol:
            return False

        #
        # Avoid other unsupported
        # punctuation.
        #
        # We keep:
        # ABC
        # BRK.B
        #
        # but reject strange exchange
        # metadata/special securities.
        #

        if not re.fullmatch(
            r"[A-Z0-9.\-/]+",
            symbol,
        ):
            return False

        excluded_name_terms = [

            "WARRANT",

            "WTS",

            "RIGHTS",

            "RIGHT ",

            "UNITS",

            "PREFERRED",

            "PREFERENCE",

            "DEPOSITARY SHARES",

            "DEPOSITARY SHARE",

            "BENEFICIAL INTEREST",

            "NEXTSHARES",

            "TEST ISSUE",

            "WHEN ISSUED",
        ]

        if any(
            term in name
            for term
            in excluded_name_terms
        ):
            return False

        #
        # Common special-security
        # ticker suffixes.
        #

        if len(symbol) >= 5:

            if symbol.endswith(
                (
                    "WS",
                    "WT",
                    "W",
                    "RT",
                    "R",
                    "U",
                )
            ):
                return False

        return True

    def _provider_symbol(
        self,
        symbol,
    ):

        return (
            symbol
            .replace(
                ".",
                "-",
            )
            .replace(
                "/",
                "-",
            )
        )