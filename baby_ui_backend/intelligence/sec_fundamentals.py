from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from .common import Evidence, metric, stage, num, pct, safe_div

TICKERS = 'https://www.sec.gov/files/company_tickers.json'
FACTS = 'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'

# Ordered from narrow/preferred to broader but still defensible standardized aliases.
# Selection is period-first, then concept-priority. A stale preferred concept must never
# beat a current-period lower-priority alias.
CONCEPTS = {
    'revenue': [
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'RevenueFromContractWithCustomerIncludingAssessedTax',
        'SalesRevenueNet',
        'SalesRevenueGoodsNet',
        'SalesRevenueServicesNet',
        'Revenues',
    ],
    'net_income': [
        'NetIncomeLoss',
        'ProfitLoss',
        'NetIncomeLossAvailableToCommonStockholdersBasic',
    ],
    'ocf': [
        'NetCashProvidedByUsedInOperatingActivities',
        'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
    ],
    'capex': [
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'PaymentsForPropertyPlantAndEquipment',
        'PaymentsToAcquireProductiveAssets',
        'PaymentsForProceedsFromOtherPropertyPlantAndEquipment',
        # Broader than pure PP&E. Allowed only as an explicitly identified fallback.
        'PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets',
        'PaymentsToAcquireOtherPropertyPlantAndEquipment',
    ],
    'cash': [
        'CashAndCashEquivalentsAtCarryingValue',
        'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
    ],
    'assets': ['Assets'],
    'liabilities': ['Liabilities'],
    'equity': [
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
    ],
    'debt_current': ['ShortTermBorrowings', 'LongTermDebtCurrent', 'DebtCurrent'],
    'debt_long': ['LongTermDebtNoncurrent', 'LongTermDebt'],
    'gross_profit': ['GrossProfit'],
    'operating_income': ['OperatingIncomeLoss'],
}

DURATION = {'revenue', 'net_income', 'ocf', 'capex', 'gross_profit', 'operating_income'}
ANNUAL_FORMS = {'10-K', '20-F', '40-F'}
ALLOWED_FORMS = ANNUAL_FORMS | {'10-Q'}
BROAD_CAPEX = {
    'PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets',
    'PaymentsToAcquireOtherPropertyPlantAndEquipment',
}


class SecFundamentalProvider:
    def __init__(self, cache_dir='data/sec_cache', ttl=21600):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.ua = os.getenv('SEC_USER_AGENT', '').strip()

    def _get(self, url, key):
        p = self.cache / f'{key}.json'
        if p.exists() and time.time() - p.stat().st_mtime < self.ttl:
            return json.loads(p.read_text())
        if not self.ua:
            raise RuntimeError('SEC_USER_AGENT is required for SEC automated access.')
        req = urllib.request.Request(
            url,
            headers={'User-Agent': self.ua, 'Host': urllib.parse.urlparse(url).netloc},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(data))
        tmp.replace(p)
        return data

    def cik(self, symbol):
        for x in self._get(TICKERS, 'company_tickers').values():
            if str(x.get('ticker', '')).upper() == symbol.upper():
                return int(x['cik_str'])

    def companyfacts(self, symbol):
        cik = self.cik(symbol)
        return None if cik is None else self._get(FACTS.format(cik=cik), f'companyfacts_{cik:010d}')


def _days(r):
    try:
        return (date.fromisoformat(r['end']) - date.fromisoformat(r['start'])).days
    except Exception:
        return None


def _concept_entries(facts, concept):
    out = []
    # Company Facts may contain multiple standardized taxonomies. Prefer us-gaap,
    # but inspect all namespaces so a standards namespace migration does not silently
    # turn a metric UNKNOWN. Custom issuer extensions are intentionally not guessed.
    namespaces = facts.get('facts') or {}
    for taxonomy, taxonomy_node in namespaces.items():
        node = (taxonomy_node or {}).get(concept, {})
        for unit, rows in (node.get('units') or {}).items():
            for r in rows:
                v = num(r.get('val'))
                if r.get('form') not in ALLOWED_FORMS or v is None:
                    continue
                out.append({**r, 'val': v, 'unit': unit, 'concept': concept, 'taxonomy': taxonomy})
    return out


def _dedupe(rows):
    """Remove duplicate frames/amendment echoes without merging economic periods."""
    best = {}
    for r in rows:
        k = (r.get('concept'), r.get('taxonomy'), r.get('start'), r.get('end'), r.get('fp'), r.get('fy'), r.get('unit'))
        old = best.get(k)
        if old is None or (r.get('filed', ''), r.get('accn', '')) > (old.get('filed', ''), old.get('accn', '')):
            best[k] = r
    return list(best.values())


def _candidates(facts, names):
    rows = []
    for priority, concept in enumerate(names):
        for r in _concept_entries(facts, concept):
            rows.append({**r, '_concept_priority': priority})
    return _dedupe(rows)


def _annual_candidates(facts, names):
    rows = [
        r for r in _candidates(facts, names)
        if r.get('start') and r.get('form') in ANNUAL_FORMS and (_days(r) or 0) >= 300
    ]
    # Economic period dominates concept preference. This is the key stale-alias fix.
    return sorted(rows, key=lambda r: (r.get('end', ''), -int(r.get('_concept_priority', 999)), r.get('filed', ''), r.get('accn', '')))


def _instant_candidates(facts, names):
    return sorted(
        (r for r in _candidates(facts, names) if not r.get('start')),
        key=lambda r: (r.get('end', ''), -int(r.get('_concept_priority', 999)), r.get('filed', ''), r.get('accn', '')),
    )


def _selection_meta(rows, selected, basis, reason):
    return {
        'basis': basis,
        'end': selected.get('end') if selected else None,
        'selected_concept': selected.get('concept') if selected else None,
        'selected_taxonomy': selected.get('taxonomy') if selected else None,
        'selected_form': selected.get('form') if selected else None,
        'selected_accession': selected.get('accn') if selected else None,
        'selected_filed': selected.get('filed') if selected else None,
        'candidate_count': len(rows),
        'selection_reason': reason,
    }


def _instant(facts, names):
    rows = _instant_candidates(facts, names)
    if not rows:
        return None
    latest_end = max(r.get('end', '') for r in rows)
    period_rows = [r for r in rows if r.get('end', '') == latest_end]
    selected = min(period_rows, key=lambda r: (int(r.get('_concept_priority', 999)), -int(str(r.get('filed', '0')).replace('-', '') or 0)))
    return {
        'val': selected['val'], 'rows': [selected],
        **_selection_meta(rows, selected, 'LATEST_INSTANT', 'Latest economic date first; concept priority breaks same-period ties.'),
    }


def _quarter_rows(facts, names):
    rows = [r for r in _candidates(facts, names) if r.get('start') and 70 <= (_days(r) or -1) <= 120]
    # One best fact per quarter-end: current period first, preferred alias within period.
    by_end = {}
    for r in rows:
        end = r.get('end')
        old = by_end.get(end)
        if old is None or (int(r.get('_concept_priority', 999)), r.get('filed', '')) < (int(old.get('_concept_priority', 999)), old.get('filed', '')):
            by_end[end] = r
    return sorted(by_end.values(), key=lambda r: r.get('end', ''))


def _duration(facts, names):
    """Resolve a duration metric to TTM when four coherent quarters exist, else latest FY."""
    all_rows = _candidates(facts, names)
    qs = _quarter_rows(facts, names)
    if len(qs) >= 4:
        q = qs[-4:]
        ends = [date.fromisoformat(x['end']) for x in q]
        # Four unique quarter ends spanning roughly one fiscal year. Do not require the
        # same alias across quarters; provenance preserves each selected concept.
        if len(set(ends)) == 4 and 245 <= (ends[-1] - ends[0]).days <= 310:
            selected = q[-1]
            return {
                'val': sum(x['val'] for x in q), 'rows': q, 'basis': 'TTM_RECONSTRUCTED', 'end': q[-1]['end'],
                **{k: v for k, v in _selection_meta(all_rows, selected, 'TTM_RECONSTRUCTED', 'Four coherent quarterly periods; period-first alias resolution.').items() if k not in {'basis', 'end'}},
            }
    annual = _annual_candidates(facts, names)
    if not annual:
        return None
    latest_end = max(r.get('end', '') for r in annual)
    same_period = [r for r in annual if r.get('end', '') == latest_end]
    selected = min(same_period, key=lambda r: int(r.get('_concept_priority', 999)))
    reason = 'Latest annual economic period first; preferred standardized concept breaks same-period ties.'
    if selected.get('concept') in BROAD_CAPEX:
        reason += ' Broader CapEx alias used because no narrower alias exists for the selected annual period.'
    return {
        'val': selected['val'], 'rows': [selected], 'basis': 'LATEST_FY_FALLBACK', 'end': selected['end'],
        **{k: v for k, v in _selection_meta(all_rows, selected, 'LATEST_FY_FALLBACK', reason).items() if k not in {'basis', 'end'}},
    }


def _annual_series(facts, names):
    rows = _annual_candidates(facts, names)
    by_end = {}
    for r in rows:
        end = r.get('end')
        old = by_end.get(end)
        if old is None or int(r.get('_concept_priority', 999)) < int(old.get('_concept_priority', 999)):
            by_end[end] = r
    return [by_end[k] for k in sorted(by_end)]


def _yoy(facts, names):
    a = _annual_series(facts, names)
    return (pct(a[-1]['val'], a[-2]['val']), a[-1], a[-2]) if len(a) >= 2 else (None, None, None)


def _ev(r, note=None):
    if not r:
        return []
    period = f"INSTANT {r.get('end')}" if not r.get('start') else f"{r.get('start')}->{r.get('end')}"
    return [Evidence(
        r['val'], 'SEC EDGAR Company Facts', 'PRIMARY', r.get('filed'), period,
        r.get('form'), r.get('accn'), verified=True, status='VERIFIED',
        concept=r.get('concept'), note=note,
    )]


def _evs(x):
    out = []
    for r in (x or {}).get('rows', []):
        out += _ev(r, (x or {}).get('basis'))
    return out


def _aligned(a, b):
    return bool(a and b and a.get('basis') == b.get('basis') and a.get('end') == b.get('end'))


def _resolver_inputs(x):
    x = x or {}
    return {
        'period_basis': x.get('basis'), 'period_end': x.get('end'),
        'selected_concept': x.get('selected_concept'), 'selected_taxonomy': x.get('selected_taxonomy'),
        'selected_form': x.get('selected_form'), 'selected_accession': x.get('selected_accession'),
        'selected_filed': x.get('selected_filed'), 'candidate_count': x.get('candidate_count', 0),
        'selection_reason': x.get('selection_reason'),
    }


def build_fundamentals(symbol, facts, *, not_applicable_reason=None):
    if not_applicable_reason:
        z = stage(
            'fundamentals_v101', 'V10.1 Financial & Fundamental Intelligence', [],
            status='NOT_APPLICABLE', warnings=[not_applicable_reason],
            summary='Operating-company SEC/XBRL fundamentals are not applicable to this asset type.',
        )
        z['temporal_integrity'] = 'NOT_APPLICABLE'
        z['asset_scope'] = 'NOT_APPLICABLE'
        return z
    if not facts:
        return stage('fundamentals_v101', 'V10.1 Financial & Fundamental Intelligence', [], status='UNKNOWN', warnings=['SEC Company Facts unavailable.'])

    d = {k: _duration(facts, v) for k, v in CONCEPTS.items() if k in DURATION}
    i = {k: _instant(facts, v) for k, v in CONCEPTS.items() if k not in DURATION}
    dv = lambda k: (d.get(k) or {}).get('val')
    iv = lambda k: (i.get(k) or {}).get('val')
    rev, ni, ocf, capex, gp, opi = map(dv, ['revenue', 'net_income', 'ocf', 'capex', 'gross_profit', 'operating_income'])

    fcf = ocf - abs(capex) if _aligned(d.get('ocf'), d.get('capex')) and None not in (ocf, capex) else None
    debt = ((num(iv('debt_current')) or 0) + (num(iv('debt_long')) or 0)) if iv('debt_current') is not None or iv('debt_long') is not None else None
    net_cash = iv('cash') - debt if iv('cash') is not None and debt is not None else None

    ry, rn, rp = _yoy(facts, CONCEPTS['revenue'])
    ny, nn, np = _yoy(facts, CONCEPTS['net_income'])
    oy, on, op = _yoy(facts, CONCEPTS['ocf'])

    def dm(k, label):
        return metric(k, label, dv(k), inputs=_resolver_inputs(d.get(k)), evidence=_evs(d.get(k)))

    fcf_inputs = {
        'ocf': ocf, 'capex': capex,
        'ocf_resolver': _resolver_inputs(d.get('ocf')),
        'capex_resolver': _resolver_inputs(d.get('capex')),
        'period_end': (d.get('ocf') or {}).get('end'),
    }
    ms = [
        dm('revenue', 'Revenue (TTM/FY)'),
        metric('revenue_growth_yoy', 'Revenue Growth YoY', ry, unit='%', formula='Latest FY / prior FY - 1', inputs={'latest': rn and rn['val'], 'prior': rp and rp['val']}, evidence=_ev(rn) + _ev(rp)),
        metric('gross_margin', 'Gross Margin', 100 * safe_div(gp, rev) if _aligned(d.get('gross_profit'), d.get('revenue')) and safe_div(gp, rev) is not None else None, unit='%'),
        metric('operating_margin', 'Operating Margin', 100 * safe_div(opi, rev) if _aligned(d.get('operating_income'), d.get('revenue')) and safe_div(opi, rev) is not None else None, unit='%'),
        dm('net_income', 'Net Income (TTM/FY)'),
        metric('net_margin', 'Net Margin', 100 * safe_div(ni, rev) if _aligned(d.get('net_income'), d.get('revenue')) and safe_div(ni, rev) is not None else None, unit='%'),
        metric('net_income_growth_yoy', 'Net Income Growth YoY', ny, unit='%', evidence=_ev(nn) + _ev(np)),
        dm('ocf', 'Operating Cash Flow (TTM/FY)'),
        metric('ocf_growth_yoy', 'OCF Growth YoY', oy, unit='%', evidence=_ev(on) + _ev(op)),
        dm('capex', 'Capital Expenditure (TTM/FY)'),
        metric('fcf', 'Free Cash Flow (aligned)', fcf, formula='Aligned OCF - abs(Aligned CapEx)', inputs=fcf_inputs, evidence=_evs(d.get('ocf')) + _evs(d.get('capex')), status='PASS' if fcf is not None else 'INVALID_PERIOD_ALIGNMENT' if None not in (ocf, capex) else 'UNKNOWN'),
        metric('cash', 'Cash', iv('cash'), inputs=_resolver_inputs(i.get('cash')), evidence=_evs(i.get('cash'))),
        metric('debt', 'Total Debt', debt, formula='Current debt + long-term debt', inputs={'current': iv('debt_current'), 'long_term': iv('debt_long')}, evidence=_evs(i.get('debt_current')) + _evs(i.get('debt_long'))),
        metric('net_cash', 'Net Cash', net_cash, formula='Cash - Debt', inputs={'cash': iv('cash'), 'debt': debt}, evidence=_evs(i.get('cash')) + _evs(i.get('debt_current')) + _evs(i.get('debt_long'))),
        metric('assets', 'Assets', iv('assets'), inputs=_resolver_inputs(i.get('assets')), evidence=_evs(i.get('assets'))),
        metric('liabilities', 'Liabilities', iv('liabilities'), inputs=_resolver_inputs(i.get('liabilities')), evidence=_evs(i.get('liabilities'))),
        metric('equity', 'Stockholders Equity', iv('equity'), inputs=_resolver_inputs(i.get('equity')), evidence=_evs(i.get('equity'))),
    ]

    warnings = []
    if None not in (ocf, capex) and fcf is None:
        warnings.append('FCF blocked: OCF and CapEx temporal bases/end dates are incompatible.')
    if d.get('capex') and d['capex'].get('selected_concept') in BROAD_CAPEX:
        warnings.append(f"CapEx uses broader standardized alias {d['capex'].get('selected_concept')}; provenance retained for review.")

    z = stage(
        'fundamentals_v101', 'V10.1 Financial & Fundamental Intelligence', ms,
        summary='SEC/XBRL with period-first alias resolution, explicit selection provenance, and aligned TTM/FY derived metrics.',
        warnings=warnings,
    )
    z['temporal_integrity'] = 'PASS' if not any('FCF blocked' in w for w in warnings) else 'REVIEW'
    z['resolver_version'] = '10.6.2'
    return z
