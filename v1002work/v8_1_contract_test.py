from pathlib import Path
from tempfile import TemporaryDirectory
from baby_ui_backend.research_service import ResearchService
from baby_ui_backend.quote_service import QuoteService

with TemporaryDirectory() as d:
    s=ResearchService(report_dir=Path(d)/'reports',state_dir=Path(d)/'jobs')
    assert s.status('AAPL')['status']=='NOT_RESEARCHED'
q=QuoteService(provider=lambda s:{'price':123.45,'quality':'LIVE','provider':'TEST_EXCHANGE','timestamp':'2026-09-16T10:00:00+00:00'}).get('AAPL')
assert q.price==123.45 and q.quality=='LIVE'
q2=QuoteService(provider=lambda s:None).get('AAPL')
assert q2.quality in {'UNKNOWN','DELAYED'}
print('BABY V8.1 production research integration contract: PASS')
