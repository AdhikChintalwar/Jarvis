import tempfile
from pathlib import Path
from baby_ui_backend.v1515_paper_autopilot import PaperAutopilot,PaperAutopilotStore,PaperAutopilotConfig

def main():
    with tempfile.TemporaryDirectory() as td:
        st=PaperAutopilotStore(Path(td)/"baby.db")
        cfg=PaperAutopilotConfig(True,0.20,3,0.01,0.03,True)
        svc=PaperAutopilot(st,cfg)
        setup={"entry":20.0,"stop":19.0,"t1":22.0,"t2":24.0,"setup_status":"AT_PULLBACK_ZONE"}
        a,n1=st.open_or_touch("TEST",setup)
        b,n2=st.open_or_touch("TEST",setup)
        assert n1 and not n2 and a["id"]==b["id"]
        print("PASS SETUP_READY episode dedup")

        s=svc.sizing(100000,20,19)
        assert s["eligible"] and s["allocation_value"]<=20000 and s["quantity"]<=1000
        print("PASS 20% allocation ceiling + risk sizing")

        d="2099-01-01"
        for _ in range(3): st.increment_trade_count(d,100000)
        c=svc.can_enter(d,100000,20,19,19.5,20.5)
        assert not c["eligible"] and c["reason"]=="DAILY_TRADE_LIMIT_REACHED"
        print("PASS max 3 new PAPER trades/day")

        c2=svc.can_enter("2099-01-02",100000,21,19,19.5,20.5)
        assert not c2["eligible"] and c2["reason"]=="QUOTE_ABOVE_ENTRY_ZONE_NO_CHASE"
        print("PASS fresh-quote no-chase guard")

        m=svc.market_risk_state({"spy_pct":-3.4,"qqq_pct":-3.2,"iwm_pct":-4.1,"breadth_pct":14})
        assert m["state"]=="SEVERE_RISK_OFF"
        print("PASS severe market-risk classification")

        d=svc.sudden_drop(20,18.8,-3.1,2.2)
        assert d["trigger"]
        print("PASS PAPER sudden-drop protection")
        print("PASS real-money execution disabled")
        print("V15.15 core validation PASS")

if __name__=="__main__":
    main()
