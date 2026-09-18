from __future__ import annotations
import hashlib, json, os, sqlite3, uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION='12.0-production-candidate'
REAL_MONEY='DISABLED'

def now(): return datetime.now(timezone.utc).isoformat()
def f(x,d=0.0):
    try:return float(x)
    except:return d

def stable_hash(x): return hashlib.sha256(json.dumps(x,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

@dataclass(frozen=True)
class PortfolioPolicy:
    max_positions:int=10
    max_position_pct:float=10.0
    max_sector_pct:float=30.0
    max_correlated_pct:float=35.0
    max_portfolio_risk_pct:float=6.0
    max_single_trade_risk_pct:float=0.5
    min_cash_reserve_pct:float=10.0
    correlation_threshold:float=0.75

class PortfolioRiskEngine:
    '''Deterministic portfolio admission gate. Missing portfolio evidence cannot increase size.'''
    def evaluate(self, *, equity, cash, positions, candidate, proposed_notional, proposed_risk, policy=PortfolioPolicy()):
        equity=max(f(equity),0); cash=max(f(cash),0); proposed_notional=max(f(proposed_notional),0); proposed_risk=max(f(proposed_risk),0)
        failures=[]; warnings=[]
        if equity<=0: failures.append('INVALID_EQUITY')
        symbol=str(candidate.get('symbol','')).upper(); sector=candidate.get('sector') or 'UNKNOWN'
        if any(str(p.get('symbol','')).upper()==symbol for p in positions): warnings.append('EXISTING_POSITION_REQUIRES_RECONCILIATION')
        if len([p for p in positions if f(p.get('quantity',p.get('qty',0)))>0])>=policy.max_positions: failures.append('MAX_POSITIONS')
        pct=100*proposed_notional/equity if equity else 999
        if pct>policy.max_position_pct+1e-9: failures.append('MAX_POSITION_PCT')
        sector_value=sum(f(p.get('market_value')) for p in positions if (p.get('sector') or 'UNKNOWN')==sector)
        if sector!='UNKNOWN' and equity and 100*(sector_value+proposed_notional)/equity>policy.max_sector_pct: failures.append('MAX_SECTOR_PCT')
        corr_value=sum(f(p.get('market_value')) for p in positions if f(p.get('correlation_to_candidate'))>=policy.correlation_threshold)
        if equity and 100*(corr_value+proposed_notional)/equity>policy.max_correlated_pct: failures.append('MAX_CORRELATED_EXPOSURE')
        existing_risk=sum(max(0,f(p.get('risk_dollars'))) for p in positions)
        if equity and 100*(existing_risk+proposed_risk)/equity>policy.max_portfolio_risk_pct: failures.append('MAX_PORTFOLIO_RISK')
        if equity and 100*proposed_risk/equity>policy.max_single_trade_risk_pct: failures.append('MAX_SINGLE_TRADE_RISK')
        if equity and 100*max(0,cash-proposed_notional)/equity<policy.min_cash_reserve_pct: failures.append('MIN_CASH_RESERVE')
        return {'status':'PASS' if not failures else 'BLOCKED','eligible':not failures,'failures':failures,'warnings':warnings,'policy':asdict(policy),'candidate_position_pct':round(pct,4),'sector':sector,'evaluated_at':now()}

class ETFResearchEngine:
    '''ETF-specific thesis: never invents company fundamentals.'''
    def evaluate(self, symbol, intelligence):
        tech=(intelligence or {}).get('technical') or {}; macro=(intelligence or {}).get('macro_sector') or {}; events=(intelligence or {}).get('events') or {}
        bull=[]; bear=[]; unknown=[]
        vals=tech.get('metrics') or tech
        price=f(vals.get('price'),None); sma50=f(vals.get('sma50'),None); sma200=f(vals.get('sma200'),None); rsi=f(vals.get('rsi14'),None)
        if price is not None and sma50 is not None: (bull if price>sma50 else bear).append({'claim':'Price above 50-day trend' if price>sma50 else 'Price below 50-day trend','domain':'TECHNICAL','weight':8})
        else: unknown.append('50-day trend')
        if price is not None and sma200 is not None: (bull if price>sma200 else bear).append({'claim':'Price above 200-day trend' if price>sma200 else 'Price below 200-day trend','domain':'TECHNICAL','weight':10})
        else: unknown.append('200-day trend')
        if rsi is not None:
            if 50<=rsi<=70: bull.append({'claim':'Positive momentum regime','domain':'MOMENTUM','weight':5})
            elif rsi<40: bear.append({'claim':'Weak momentum regime','domain':'MOMENTUM','weight':5})
        regime=macro.get('regime') or macro.get('market_regime')
        if regime in ('RISK_ON','BULLISH'): bull.append({'claim':'Supportive market regime','domain':'MACRO','weight':7})
        elif regime in ('RISK_OFF','BEARISH'): bear.append({'claim':'Adverse market regime','domain':'MACRO','weight':7})
        else: unknown.append('macro regime')
        return {'asset_type':'ETF','fundamentals':'NOT_APPLICABLE','company_valuation':'NOT_APPLICABLE','bull_case':bull,'bear_case':bear,'unknowns':unknown,'bull_weight':sum(x['weight'] for x in bull),'bear_weight':sum(x['weight'] for x in bear),'status':'PASS' if bull or bear else 'INSUFFICIENT_EVIDENCE','causality':'NOT_ESTABLISHED'}

class ProductionLedger:
    '''Durable idempotency/audit ledger with schema migrations.'''
    VERSION=1
    def __init__(self,path='data/baby_production.db'):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def db(self):
        d=sqlite3.connect(self.path,timeout=30); d.row_factory=sqlite3.Row; return d
    def _init(self):
        with self.db() as d:
            d.executescript('''CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE NOT NULL,symbol TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,entity_id TEXT,payload TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS position_plans(symbol TEXT PRIMARY KEY,payload TEXT NOT NULL,status TEXT NOT NULL,updated_at TEXT NOT NULL);''')
            d.execute('INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(?,?)',(self.VERSION,now())); d.commit()
    def proposal(self,symbol,payload,key=None):
        key=key or stable_hash({'symbol':symbol,'payload':payload}); t=now()
        with self.db() as d:
            row=d.execute('SELECT * FROM proposals WHERE idempotency_key=?',(key,)).fetchone()
            if row:return {**dict(row),'payload':json.loads(row['payload']),'duplicate':True}
            pid='PROP-'+uuid.uuid4().hex[:16]; d.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?,?)',(pid,key,symbol,json.dumps(payload,default=str),'PROPOSED',t,t)); d.execute('INSERT INTO audit_log(event_type,entity_id,payload,created_at) VALUES(?,?,?,?)',('PROPOSAL_CREATED',pid,json.dumps({'symbol':symbol}),t)); d.commit()
            return {'id':pid,'idempotency_key':key,'symbol':symbol,'payload':payload,'status':'PROPOSED','created_at':t,'duplicate':False}
    def audit(self,event_type,entity_id,payload):
        with self.db() as d:d.execute('INSERT INTO audit_log(event_type,entity_id,payload,created_at) VALUES(?,?,?,?)',(event_type,entity_id,json.dumps(payload,default=str),now())); d.commit()
    def health(self):
        with self.db() as d:
            return {'database':str(self.path),'schema_version':d.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0],'proposals':d.execute('SELECT COUNT(*) FROM proposals').fetchone()[0],'audit_events':d.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]}

class PositionManager:
    '''Creates deterministic EXIT PROPOSALS only; never executes.''' 
    def evaluate(self,position,plan,current):
        qty=f(position.get('quantity',position.get('qty'))); price=f(current.get('price'),None); stop=f(plan.get('invalidation'),None); t1=f(plan.get('target1'),None); t2=f(plan.get('target2'),None)
        hard=bool(current.get('hard_risk_override')); thesis=str(current.get('thesis_state',''))
        action='HOLD'; reason='NO_EXIT_TRIGGER'; exit_qty=0
        if qty<=0 or price is None:return {'status':'UNKNOWN','action':'NONE','reason':'MISSING_POSITION_OR_PRICE','execution':'NONE'}
        if hard or thesis in ('BROKEN','BROKEN_OR_CONSTRAINED'): action='EXIT_PROPOSAL'; reason='THESIS_OR_HARD_RISK'; exit_qty=qty
        elif stop is not None and price<=stop: action='EXIT_PROPOSAL'; reason='INVALIDATION_REACHED'; exit_qty=qty
        elif t2 is not None and price>=t2: action='PARTIAL_EXIT_PROPOSAL'; reason='TARGET_2_REACHED'; exit_qty=max(1,int(qty*.25))
        elif t1 is not None and price>=t1: action='PARTIAL_EXIT_PROPOSAL'; reason='TARGET_1_REACHED'; exit_qty=max(1,int(qty*.50))
        return {'status':'READY','action':action,'reason':reason,'quantity':exit_qty,'price_observed':price,'execution':'EXPLICIT_CONFIRMATION_REQUIRED','real_money':REAL_MONEY}

class ProviderHealth:
    def assess(self,providers):
        rows=[]
        for name,p in providers.items():
            ok=bool(p.get('configured',True)) and p.get('error') in (None,'')
            rows.append({'provider':name,'state':'HEALTHY' if ok else 'DEGRADED','error':p.get('error'),'authority':p.get('authority','SECONDARY')})
        primary_ok=any(x['state']=='HEALTHY' and x['authority']=='PRIMARY' for x in rows)
        return {'status':'PASS' if primary_ok else 'DEGRADED','providers':rows,'fail_closed_for_execution':not primary_ok,'checked_at':now()}

class ProductionDecisionEngine:
    """
    Bridges a V11 deterministic research report into the V12 production
    candidate layer.

    Creates proposals and portfolio decisions only.
    Never executes a trade.
    """

    def __init__(self, ledger, portfolio):
        self.ledger = ledger
        self.portfolio = portfolio

    def evaluate(self, v11, portfolio_state=None):
        v11 = v11 or {}
        portfolio_state = portfolio_state or {}

        symbol = str(v11.get('symbol') or '').upper()
        decision = v11.get('decision') or {}
        trade = v11.get('trade_intelligence') or {}
        thesis = v11.get('thesis') or {}

        paper = trade.get('paper_proposal') or {}
        position = trade.get('position') or {}

        account = portfolio_state.get('account') or {}
        positions = portfolio_state.get('positions') or []

        equity = account.get('equity')
        cash = account.get('cash')

        # Production sizing must come from deterministic trade-plan evidence.
        proposed_notional = (
            paper.get('proposed_notional')
            if paper.get('proposed_notional') is not None
            else paper.get('notional')
            if paper.get('notional') is not None
            else position.get('position_value')
            if position.get('position_value') is not None
            else position.get('notional')
        )

        proposed_risk = (
            paper.get('risk_budget_dollars')
            if paper.get('risk_budget_dollars') is not None
            else paper.get('risk_dollars')
            if paper.get('risk_dollars') is not None
            else position.get('maximum_loss')
            if position.get('maximum_loss') is not None
            else position.get('risk_dollars')
        )

        sector = (
            paper.get('sector')
            or position.get('sector')
            or 'UNKNOWN'
        )

        proposal_payload = {
            'source_schema': v11.get('schema_version'),
            'decision_state': decision.get('state'),
            'decision_score': decision.get('score'),
            'confidence': decision.get('confidence'),
            'coverage': decision.get('decision_grade_coverage'),
            'constraints': decision.get('constraints') or [],
            'setup_status': trade.get('setup_status'),
            'entry_triggered': bool(trade.get('entry_triggered')),
            'paper_proposal': paper,
            'position_plan': position,
            'thesis_state': (v11.get('thesis_state') or {}).get('state'),
            'hard_risk_override': bool(thesis.get('hard_risk_override')),
            'real_money': 'DISABLED',
            'execution': 'NONE',
        }

        proposal = self.ledger.proposal(symbol, proposal_payload)

        gate = self.portfolio.evaluate(
            equity=equity,
            cash=cash,
            positions=positions,
            candidate={
                'symbol': symbol,
                'sector': sector,
            },
            proposed_notional=proposed_notional,
            proposed_risk=proposed_risk,
        )

        bridge_failures = []
        if not symbol:
            bridge_failures.append('MISSING_SYMBOL')
        if proposed_notional is None or f(proposed_notional) <= 0:
            bridge_failures.append('MISSING_PROPOSED_NOTIONAL')
        if proposed_risk is None:
            bridge_failures.append('MISSING_PROPOSED_RISK')
        if bool(thesis.get('hard_risk_override')):
            bridge_failures.append('HARD_RISK_OVERRIDE')
        if not bool(trade.get('entry_triggered')):
            bridge_failures.append('ENTRY_NOT_TRIGGERED')
        if paper and paper.get('eligible') is False:
            bridge_failures.append('PAPER_PROPOSAL_NOT_ELIGIBLE')

        status = 'ELIGIBLE_PROPOSAL' if gate.get('eligible') and not bridge_failures else 'BLOCKED'

        result = {
            'symbol': symbol,
            'status': status,
            'proposal': proposal,
            'portfolio_gate': gate,
            'bridge_failures': bridge_failures,
            'research_decision': {
                'state': decision.get('state'),
                'score': decision.get('score'),
                'confidence': decision.get('confidence'),
            },
            'execution': 'NONE',
            'real_money': 'DISABLED',
        }

        self.ledger.audit(
            'PRODUCTION_DECISION',
            proposal.get('id'),
            {
                'symbol': symbol,
                'status': status,
                'gate_failures': gate.get('failures') or [],
                'gate_warnings': gate.get('warnings') or [],
                'bridge_failures': bridge_failures,
            },
        )

        return result


class RealMoneyCanaryGate:
    """Explicit, capped admission gate for a manually confirmed live-money canary."""
    def evaluate(self, decision, order, confirmation):
        mode=os.getenv('BABY_REAL_MONEY_EXECUTION','DISABLED').upper()
        max_notional=max(0.0,f(os.getenv('BABY_CANARY_MAX_NOTIONAL','5'),5.0))
        failures=[]

        if mode!='CANARY':
            failures.append('REAL_MONEY_MODE_NOT_CANARY')
        if confirmation!='CONFIRM_LIVE_CANARY':
            failures.append('EXPLICIT_LIVE_CONFIRMATION_REQUIRED')
        if (decision or {}).get('status')!='ELIGIBLE_PROPOSAL':
            failures.append('PRODUCTION_DECISION_NOT_ELIGIBLE')

        symbol=str((order or {}).get('symbol') or '').upper()
        decision_symbol=str((decision or {}).get('symbol') or '').upper()
        if not symbol or symbol!=decision_symbol:
            failures.append('ORDER_SYMBOL_MISMATCH')

        side=str((order or {}).get('side') or '').lower()
        if side!='buy':
            failures.append('CANARY_BUY_ONLY')

        notional=f((order or {}).get('notional'),0)
        if notional<=0:
            failures.append('INVALID_CANARY_NOTIONAL')
        elif notional>max_notional:
            failures.append('CANARY_NOTIONAL_LIMIT')

        order_type=str((order or {}).get('type') or 'market').lower()
        if order_type!='market':
            failures.append('CANARY_MARKET_ORDER_ONLY')

        tif=str((order or {}).get('time_in_force') or 'day').lower()
        if tif not in {'day','gtc'}:
            failures.append('INVALID_TIME_IN_FORCE')

        return {
            'status':'READY' if not failures else 'BLOCKED',
            'eligible':not failures,
            'failures':failures,
            'mode':mode,
            'max_notional':max_notional,
            'execution_requires_explicit_confirmation':True,
            'order':{
                'symbol':symbol,
                'notional':notional,
                'side':side,
                'type':order_type,
                'time_in_force':tif,
            },
        }

class ProductionCandidate:
    def __init__(self, db='data/baby_production.db'):
        self.ledger = ProductionLedger(db)
        self.portfolio = PortfolioRiskEngine()
        self.etf = ETFResearchEngine()
        self.positions = PositionManager()
        self.providers = ProviderHealth()
        self.canary = RealMoneyCanaryGate()
        self.decision = ProductionDecisionEngine(
            self.ledger,
            self.portfolio,
        )

    def startup(self):
        mode=os.getenv('BABY_REAL_MONEY_EXECUTION','DISABLED').upper()
        required={
            'BABY_REAL_MONEY_EXECUTION':'DISABLED by default; CANARY only for explicit capped execution testing'
        }
        issues=[]
        if mode not in {'DISABLED','CANARY'}:
            issues.append('INVALID_EXECUTION_MODE')
        return {
            'schema_version':SCHEMA_VERSION,
            'status':'PASS' if not issues else 'FAIL',
            'issues':issues,
            'required':required,
            'ledger':self.ledger.health(),
            'ai_authority':{
                'facts':'NONE',
                'score':0,
                'price_levels':0,
                'risk_override':0,
                'execution':'NONE'
            },
            'execution_mode':mode,
            'real_money':'DISABLED' if mode=='DISABLED' else 'CANARY_EXPLICIT_ONLY'
        }

