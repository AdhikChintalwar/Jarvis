from fastapi import APIRouter
from .v1515_paper_autopilot import PaperAutopilot
router=APIRouter(prefix="/api/v1515",tags=["V15.15 Paper Autopilot"])
svc=PaperAutopilot()

@router.get("/health")
def health():
    return {
      "status":"READY",
      "feature":"V15.15_PAPER_AUTOPILOT",
      "paper_only":True,
      "real_money_execution":"DISABLED",
      "max_allocation_pct":svc.cfg.max_allocation_pct,
      "max_new_trades_per_day":svc.cfg.max_new_trades_per_day,
    }

@router.get("/episodes/open")
def open_episodes():
    with svc.store._connect() as db:
        rows=db.execute("SELECT * FROM v1515_setup_episodes WHERE state='OPEN' ORDER BY opened_at DESC").fetchall()
        return {"episodes":[dict(r) for r in rows]}
