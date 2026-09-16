import json,sqlite3,uuid
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import dataclass,asdict

@dataclass
class PaperOrder:
    id:str; symbol:str; side:str; quantity:float; order_type:str
    submitted_at:str; status:str="PENDING"; limit_price:float=None
    fill_price:float=None; filled_at:str=None; fee:float=0.0

class PaperPortfolio:
    def __init__(self,cash=100000.0):
        self.cash=float(cash); self.positions={}; self.realized_pnl=0.0

    def equity(self,prices):
        return self.cash+sum(q*float(prices.get(s,0)) for s,q in self.positions.items())

class PaperBroker:
    """Local simulation only. Contains NO brokerage API and cannot submit real orders."""
    def __init__(self,path="data/baby_paper_trading.db",starting_cash=100000.0,fee_bps=0.0):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS paper_orders(
          id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS paper_state(
          key TEXT PRIMARY KEY,payload TEXT NOT NULL)"""); self.db.commit()
        self.fee_bps=float(fee_bps); self.portfolio=self._load(starting_cash)

    def _load(self,cash):
        row=self.db.execute("SELECT payload FROM paper_state WHERE key='portfolio'").fetchone()
        if not row:return PaperPortfolio(cash)
        d=json.loads(row[0]); p=PaperPortfolio(d["cash"]); p.positions=d["positions"]; p.realized_pnl=d.get("realized_pnl",0); return p

    def _save(self):
        d={"cash":self.portfolio.cash,"positions":self.portfolio.positions,"realized_pnl":self.portfolio.realized_pnl}
        self.db.execute("INSERT OR REPLACE INTO paper_state(key,payload) VALUES('portfolio',?)",(json.dumps(d),)); self.db.commit()

    def submit(self,symbol,side,quantity,order_type="MARKET",limit_price=None):
        if side not in {"BUY","SELL"}:raise ValueError("side must be BUY/SELL")
        if quantity<=0:raise ValueError("quantity must be positive")
        o=PaperOrder(str(uuid.uuid4()),symbol.upper(),side,float(quantity),order_type,
                     datetime.now(timezone.utc).isoformat(),limit_price=limit_price)
        self.db.execute("INSERT INTO paper_orders(id,payload) VALUES(?,?)",(o.id,json.dumps(asdict(o)))); self.db.commit()
        return o

    def fill(self,order,market_price):
        px=float(market_price)
        if order.order_type=="LIMIT":
            if order.limit_price is None:raise ValueError("limit price required")
            if order.side=="BUY" and px>order.limit_price:return order
            if order.side=="SELL" and px<order.limit_price:return order
        notional=order.quantity*px; fee=notional*self.fee_bps/10000
        if order.side=="BUY":
            if notional+fee>self.portfolio.cash:
                order.status="REJECTED_INSUFFICIENT_CASH"
            else:
                self.portfolio.cash-=notional+fee
                self.portfolio.positions[order.symbol]=self.portfolio.positions.get(order.symbol,0)+order.quantity
                order.status="FILLED"
        else:
            held=self.portfolio.positions.get(order.symbol,0)
            if order.quantity>held: order.status="REJECTED_INSUFFICIENT_POSITION"
            else:
                self.portfolio.positions[order.symbol]=held-order.quantity
                self.portfolio.cash+=notional-fee; order.status="FILLED"
        if order.status=="FILLED":
            order.fill_price=px; order.fee=fee; order.filled_at=datetime.now(timezone.utc).isoformat()
        self.db.execute("INSERT OR REPLACE INTO paper_orders(id,payload) VALUES(?,?)",(order.id,json.dumps(asdict(order)))); self.db.commit()
        self._save(); return order
