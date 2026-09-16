export const api={
 health:()=>fetch('/api/health').then(r=>r.json()),
 glossary:()=>fetch('/api/glossary').then(r=>r.json()),
 research:async s=>{const r=await fetch(`/api/research/${s}`); if(!r.ok) throw new Error(await r.text()); return r.json()},
 researchStatus:s=>fetch(`/api/research/${s}/status`).then(r=>r.json()),
 runResearch:(s,force=false)=>fetch(`/api/research/${s}/run?force=${force}`,{method:'POST'}).then(async r=>{if(!r.ok)throw new Error(await r.text());return r.json()}),
 alerts:()=>fetch('/api/alerts').then(r=>r.json()),
 control:()=>fetch('/api/control/status').then(r=>r.json()),
 backtest:()=>fetch('/api/backtests/v7_5').then(r=>r.json()),
 paper:()=>fetch('/api/portfolio/paper').then(r=>r.json()),
 automations:()=>fetch('/api/automations').then(r=>r.json()),
 scanner:()=>fetch('/api/scanner/latest').then(r=>r.json()),
};
export function marketSocket(symbol,onQuote){const proto=location.protocol==='https:'?'wss':'ws';const ws=new WebSocket(`${proto}://${location.host}/ws/market/${symbol}`);ws.onmessage=e=>onQuote(JSON.parse(e.data));return ws}
