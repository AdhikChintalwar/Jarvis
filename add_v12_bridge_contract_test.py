from pathlib import Path

path = Path("production_candidate_contract_test.py")
if not path.exists():
    raise SystemExit("ERROR: production_candidate_contract_test.py not found. Run this from the Jarvis voice project root.")

text = path.read_text()
marker = "    etf=p.etf.evaluate('SPY',"

if marker not in text:
    raise SystemExit("ERROR: Could not find ETF test insertion point. No changes were made.")

if "production decision eligible" in text:
    print("Bridge contract test already present. No changes made.")
    raise SystemExit(0)

addition = """
    # V12 V11 -> production decision bridge contract
    v11_sample={
        'symbol':'AAPL',
        'schema_version':'11.0.1',
        'decision':{
            'state':'CANDIDATE',
            'score':68,
            'confidence':72,
            'decision_grade_coverage':80,
            'constraints':[]
        },
        'trade_intelligence':{
            'setup_status':'AT_PULLBACK_ZONE',
            'entry_triggered':True,
            'paper_proposal':{
                'notional':5000,
                'risk_dollars':300,
                'sector':'Technology'
            },
            'position':{}
        },
        'thesis':{
            'hard_risk_override':False
        },
        'thesis_state':{
            'state':'STABLE'
        }
    }

    portfolio_state={
        'account':{
            'equity':100000,
            'cash':50000
        },
        'positions':[]
    }

    pd=p.decision.evaluate(v11_sample,portfolio_state)

    ok(pd['status']=='ELIGIBLE_PROPOSAL','production decision eligible')
    ok(pd['portfolio_gate']['eligible'],'production decision gate')
    ok(pd['execution']=='NONE','production decision execution')
    ok(pd['real_money']=='DISABLED','production decision real money')
    ok(pd['proposal']['symbol']=='AAPL','production decision proposal symbol')

"""

backup = path.with_suffix(path.suffix + ".before_bridge_test.bak")
backup.write_text(text)
path.write_text(text.replace(marker, addition + marker, 1))

print("Updated:", path)
print("Backup :", backup)
print("Inserted V11 -> V12 bridge contract test immediately before ETF test.")
