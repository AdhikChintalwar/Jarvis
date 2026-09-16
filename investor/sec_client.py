from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests


@dataclass
class SECFiling:
    form: str
    filing_date: str
    accession_number: str
    primary_document: str
    description: str = ""
    filing_url: Optional[str] = None


@dataclass
class SECAnalysis:
    cik: Optional[str]

    recent_filings: list[SECFiling] = field(
        default_factory=list
    )

    dilution_flags: list[str] = field(
        default_factory=list
    )

    governance_flags: list[str] = field(
        default_factory=list
    )

    risk_flags: list[str] = field(
        default_factory=list
    )

    dilution_risk: str = "unknown"


class SECClient:

    BASE_DATA = "https://data.sec.gov"
    BASE_SEC = "https://www.sec.gov"

    IMPORTANT_FORMS = {
        "10-K",
        "10-Q",
        "8-K",
        "20-F",
        "6-K",
        "S-1",
        "S-3",
        "424B3",
        "424B5",
        "F-1",
        "F-3",
        "DEF 14A",
        "SC 13D",
        "SC 13G",
        "3",
        "4",
        "5",
    }

    DILUTION_FORMS = {
        "S-1",
        "S-3",
        "F-1",
        "F-3",
        "424B3",
        "424B5",
    }

    def __init__(
        self,
        user_agent: str = (
            "BabyInvestor/0.2 "
            "adhikchintalwar12@gmail.com"
        ),
    ):

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "data.sec.gov",
            }
        )

        self.cache_dir = Path(
            "data/sec_cache"
        )

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._ticker_map = None

    def analyze_ticker(
        self,
        ticker: str,
    ) -> SECAnalysis:

        cik = self.get_cik(
            ticker
        )

        if cik is None:
            return SECAnalysis(
                cik=None
            )

        submissions = (
            self.get_submissions(
                cik
            )
        )

        filings = (
            self._extract_filings(
                cik,
                submissions,
            )
        )

        dilution_flags = []
        governance_flags = []
        risk_flags = []

        for filing in filings:

            if filing.form in self.DILUTION_FORMS:
                dilution_flags.append(
                    f"{filing.form} filed "
                    f"{filing.filing_date}"
                )

            if filing.form == "4":
                governance_flags.append(
                    f"Insider transaction filing "
                    f"on {filing.filing_date}"
                )

            if filing.form in {
                "8-K",
                "6-K",
            }:
                risk_flags.append(
                    f"Recent event filing "
                    f"{filing.form} on "
                    f"{filing.filing_date}"
                )

        dilution_risk = (
            self._dilution_risk(
                filings
            )
        )

        return SECAnalysis(
            cik=cik,
            recent_filings=filings,
            dilution_flags=(
                dilution_flags
            ),
            governance_flags=(
                governance_flags
            ),
            risk_flags=risk_flags,
            dilution_risk=(
                dilution_risk
            ),
        )

    def get_cik(
        self,
        ticker: str,
    ) -> Optional[str]:

        mapping = (
            self._get_ticker_map()
        )

        ticker = ticker.upper()

        item = mapping.get(
            ticker
        )

        if item is None:
            return None

        return str(
            item["cik"]
        ).zfill(10)

    def _get_ticker_map(
        self,
    ):

        if self._ticker_map is not None:
            return self._ticker_map

        cache_file = (
            self.cache_dir
            / "company_tickers.json"
        )

        data = None

        if cache_file.exists():

            age = (
                time.time()
                - cache_file.stat().st_mtime
            )

            if age < 86_400:
                data = json.loads(
                    cache_file.read_text()
                )

        if data is None:

            response = requests.get(
                "https://www.sec.gov/files/"
                "company_tickers.json",
                headers={
                    "User-Agent":
                        self.session.headers[
                            "User-Agent"
                        ]
                },
                timeout=20,
            )

            response.raise_for_status()

            data = response.json()

            cache_file.write_text(
                json.dumps(data)
            )

        result = {}

        for item in data.values():

            ticker = (
                str(
                    item.get(
                        "ticker",
                        "",
                    )
                )
                .upper()
            )

            if ticker:
                result[ticker] = {
                    "cik":
                        item.get("cik_str"),
                    "title":
                        item.get("title"),
                }

        self._ticker_map = result

        return result

    def get_submissions(
        self,
        cik: str,
    ):

        url = (
            f"{self.BASE_DATA}"
            f"/submissions/"
            f"CIK{cik}.json"
        )

        response = (
            self.session.get(
                url,
                timeout=20,
            )
        )

        response.raise_for_status()

        return response.json()

    def _extract_filings(
        self,
        cik,
        submissions,
    ):

        recent = (
            submissions
            .get("filings", {})
            .get("recent", {})
        )

        forms = recent.get(
            "form",
            [],
        )

        dates = recent.get(
            "filingDate",
            [],
        )

        accessions = recent.get(
            "accessionNumber",
            [],
        )

        documents = recent.get(
            "primaryDocument",
            [],
        )

        descriptions = recent.get(
            "primaryDocDescription",
            [],
        )

        filings = []

        total = min(
            len(forms),
            len(dates),
            len(accessions),
        )

        cik_no_zero = str(
            int(cik)
        )

        for index in range(total):

            form = forms[index]

            if (
                form
                not in self.IMPORTANT_FORMS
            ):
                continue

            accession = (
                accessions[index]
            )

            document = (
                documents[index]
                if index < len(documents)
                else ""
            )

            clean_accession = (
                accession.replace(
                    "-",
                    "",
                )
            )

            filing_url = None

            if document:
                filing_url = (
                    "https://www.sec.gov/"
                    "Archives/edgar/data/"
                    f"{cik_no_zero}/"
                    f"{clean_accession}/"
                    f"{document}"
                )

            filings.append(
                SECFiling(
                    form=form,
                    filing_date=dates[index],
                    accession_number=accession,
                    primary_document=document,
                    description=(
                        descriptions[index]
                        if index
                        < len(descriptions)
                        else ""
                    ),
                    filing_url=filing_url,
                )
            )

            if len(filings) >= 30:
                break

        return filings

    def _dilution_risk(
        self,
        filings,
    ):

        recent = filings[:20]

        dilution_count = sum(
            1
            for filing in recent
            if filing.form
            in self.DILUTION_FORMS
        )

        if dilution_count >= 4:
            return "very_high"

        if dilution_count >= 2:
            return "high"

        if dilution_count == 1:
            return "moderate"

        return "low"