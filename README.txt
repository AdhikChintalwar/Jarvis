BABY V13 UI + POSITION MONITORING

Apply from Baby project root:
python ~/Downloads/Baby_V13_UI_Monitoring/apply_v13.py

Verify:
PYTHONPATH=. python ~/Downloads/Baby_V13_UI_Monitoring/verify_v13.py

Then restart Baby backend/frontend using your normal commands.

New monitoring endpoints:
GET    /api/monitor/jobs
GET    /api/monitor/events
POST   /api/monitor/jobs/{symbol}
POST   /api/monitor/jobs/{symbol}/run
DELETE /api/monitor/jobs/{symbol}

Example: register monitoring for a position you actually hold:
curl -sS -X POST http://localhost:8787/api/monitor/jobs/AAPL   -H "Content-Type: application/json"   -d '{"interval_minutes":5,"thesis_review_minutes":30,"baseline":{"thesis_state":"STABLE","stop":314.89,"target_1":340,"target_2":360}}'   | python -m json.tool

The monitor:
- keeps one persistent schedule record per symbol
- checks quote/setup/production state
- records setup/status changes
- records invalidation/target events
- records trade-quality degradation
- never changes the plan automatically
- never submits an order automatically

Git after verification:
git status
git diff
git add investor/production/investment_monitor.py baby_ui_backend/app.py frontend/src/App.jsx frontend/src/lib/api.js frontend/src/pages/Ideas.jsx frontend/src/pages/Production.jsx frontend/src/components/MiniLineChart.jsx frontend/src/styles/app.css
git commit -m "Add Baby V13 ideas UI and position monitoring"
