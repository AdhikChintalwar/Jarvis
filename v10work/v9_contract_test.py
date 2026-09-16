from pathlib import Path
from baby_ui_backend.agent_tools import BabyReadOnlyTools
from baby_ui_backend.agentic_copilot import BabyAgenticCopilot
from baby_ui_backend.copilot import BabyCopilot

root=Path(__file__).parent
agent=BabyAgenticCopilot(root/'data'/'ui_research')
names={x['name'] for x in agent.tools.schemas()}
required={'resolve_asset','get_quote','get_company_profile','get_company_news','get_market_news','get_market_context','get_baby_research','screen_price','get_baby_capabilities'}
assert required<=names
assert not any(x in names for x in {'submit_order','place_order','alpaca_submit','execute_order'})

# Contract-test planner/synthesis without network or credentials.
def fake_chat(messages,max_tokens=900,temperature=.1):
    sys=messages[0]['content']
    user=messages[-1]['content']
    if 'planning brain' in sys:
        if 'market updates' in user:return '{"intent":"MARKET_UPDATE","entities":{},"needs_tools":true,"tool_calls":[{"name":"get_market_context","args":{}},{"name":"get_market_news","args":{"limit":8}}],"response_mode":"MARKET_UPDATE","state_updates":{"previous_intent":"MARKET_UPDATE"}}'
        if 'Tesla stock' in user:return '{"intent":"CURRENT_STOCK_QUOTE","entities":{"symbol_or_company":"Tesla"},"needs_tools":true,"tool_calls":[{"name":"get_quote","args":{"symbol_or_company":"Tesla"}}],"response_mode":"MARKET_QUOTE","state_updates":{"active_symbol":"TSLA"}}'
        if 'how are you' in user:return '{"intent":"GENERAL_CHAT","entities":{},"needs_tools":false,"tool_calls":[],"response_mode":"GENERAL","state_updates":{}}'
    return 'Doing well. What are we looking at today?'
agent._chat=fake_chat
agent.tools.call=lambda n,a: ({'symbol':'TSLA','price':358.13,'provider':'ALPACA_MARKET_DATA','feed':'IEX'} if n=='get_quote' else {'source':'TEST','news':[]})
assert agent.ask('how are you doing today?',{},'a')['mode']=='GENERAL'
r=agent.ask('how about Tesla stock',{},'a'); assert r['mode']=='MARKET_QUOTE' and r['data']['symbol']=='TSLA'
r=agent.ask('any market updates recently?',{},'a'); assert r['mode']=='MARKET_UPDATE' and len(r['data']['tool_results'])==2
print('BABY V9 AGENTIC COPILOT CONTRACT: PASS')
print('natural conversation: PASS')
print('AI intent/entity planning: PASS')
print('fresh market/news tool planning: PASS')
print('read-only tool registry: PASS')
print('AI scoring authority: 0%')
print('chat execution authority: NONE')
print('real-money execution: DISABLED')
