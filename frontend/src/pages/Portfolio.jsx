import React,{useEffect,useState} from 'react';import {api} from '../lib/api';
import {PortfolioEquityChart} from '../components/MarketCharts';
import PortfolioPerformanceChart from '../components/PortfolioPerformanceChart';
const money=x=>x==null?'UNKNOWN':Number(x).toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:2});
const rr=x=>x==null?'UNKNOWN':`${Number(x).toFixed(2)}×`;
const when=x=>x?new Date(x).toLocaleString():'UNKNOWN';

export default function Portfolio({openResearch}){
 const[d,setD]=useState(null),[alpaca,setAlpaca]=useState(null),[aPos,setAPos]=useState([]),[aOrd,setAOrd]=useState([]),[watched,setWatched]=useState([]),[form,setForm]=useState({symbol:'AAPL',side:'BUY',quantity:'1',order_type:'MARKET',limit_price:''}),[msg,setMsg]=useState(''),[confirm,setConfirm]=useState('');
 const load=()=>api.paper().then(setD);
 const loadWatched=()=>api.monitoredSetups().then(x=>setWatched(x.setups||[]));
 const loadAlpaca=async()=>{const s=await api.alpacaStatus();setAlpaca(s);if(s.connected){setAPos((await api.alpacaPositions()).positions||[]);setAOrd((await api.alpacaOrders()).orders||[])}};
 const refresh=()=>{load();loadWatched().catch(()=>{});loadAlpaca().catch(e=>setMsg(String(e)))};
 useEffect(()=>{refresh();const t=setInterval(()=>loadWatched().catch(()=>{}),30000);return()=>clearInterval(t)},[]);

 async function submitLocal(e){e.preventDefault();setMsg('');try{const o=await api.paperOrder({...form,quantity:Number(form.quantity),limit_price:form.order_type==='LIMIT'?Number(form.limit_price):null});setMsg(`LOCAL SIMULATOR order created: ${o.id}. It remains PENDING until local execution.`);await load()}catch(e){setMsg(String(e))}}
 async function execLocal(id){try{await api.executePaperOrder(id);await load()}catch(e){setMsg(String(e))}}
 async function submitAlpaca(){setMsg('');try{const r=await api.alpacaOrder({...form,quantity:Number(form.quantity),limit_price:form.order_type==='LIMIT'?Number(form.limit_price):null,confirmation:confirm});setMsg(`ALPACA PAPER order submitted: ${r.order.id}. Simulated money only.`);setConfirm('');await loadAlpaca()}catch(e){setMsg(String(e))}}
 async function cancelAlpaca(id){try{await api.alpacaCancel(id);setMsg(`Alpaca PAPER cancel requested: ${id}`);await loadAlpaca()}catch(e){setMsg(String(e))}}
 async function stopWatching(symbol){try{await api.removeMonitoredSetup(symbol);setMsg(`${symbol} removed from Baby monitored setups.`);await loadWatched()}catch(e){setMsg(String(e))}}

 return <main className="screenPage portfolioPage">
 <section className="pageExplain compactExplain">
   <div>
     <span className="pageKicker">PORTFOLIO</span>
     <h1>Your investments and Baby monitoring</h1>
     <p>See actual Alpaca PAPER holdings separately from research setups Baby is watching for you.</p>
   </div>
 </section>

 <div className="plainHelpBox">
   <b>Actual position vs monitored setup</b>
   <span><strong>Active Alpaca PAPER position</strong> = a simulated broker holding already exists.</span>
   <span><strong>Baby monitored setup</strong> = research only. Baby is watching the deterministic setup; it is not a position or order.</span>
   <span><strong>Setup ready</strong> = review opportunity only. Baby still does not submit any order automatically.</span>
 </div>

 <PortfolioPerformanceChart/>
 <div className="topbar"><div><div className="brand">PAPER EXECUTION CONTROL CENTER</div><p>Research monitoring and broker positions remain separate.</p></div></div>
 <div className="authority"><b>REAL MONEY DISABLED</b><span>AI execution authority is NONE. A monitored setup can alert you, but it cannot place an order.</span></div>
 {msg&&<div className="notice">{msg}</div>}

 <section className="brokerZone monitoredZone">
   <div className="brokerZoneTitle">
     <div>
       <span className="eyebrow">BABY RESEARCH MONITOR</span>
       <h2>MONITORED SETUPS</h2>
       <p>Checking an Alpaca Paper Setup in Stock Research adds it here. Baby revalidates monitored symbols even if they later fall outside the scanner top 5.</p>
     </div>
     <div className="badge status-review">{watched.length} WATCHED</div>
   </div>

   {!watched.length?<div className="notice">No monitored setups yet. Open Stock Research → Trade Plan → Check Alpaca Paper Setup to add one.</div>:
   <div className="monitoredSetupGrid">{watched.map(x=><article className={`monitoredSetupCard ${x.ready?'ready':''}`} key={x.symbol}>
      <div className="monitoredSetupHead">
        <div><span className="eyebrow">{x.ready?'SETUP READY':'BABY IS WATCHING'}</span><h3>{x.symbol}</h3></div>
        <div className={`badge ${x.ready?'status-pass':'status-review'}`}>{x.ready?'READY FOR REVIEW':(x.state||'WAITING')}</div>
      </div>
      <p className="monitoredReason">{x.reason||'Waiting for the deterministic setup conditions to become eligible.'}</p>
      <div className="monitoredLevels">
        <Card n="Current" v={money(x.quote_price)}/>
        <Card n="Planned Entry" v={money(x.entry_price)}/>
        <Card n="Invalidation" v={money(x.invalidation)}/>
        <Card n="Target 1" v={money(x.target_1)}/>
        <Card n="Target 2" v={money(x.target_2)}/>
        <Card n="Risk" v={x.risk_level||'UNKNOWN'}/>
        <Card n="R/R T1" v={rr(x.rr_target_1)}/>
        <Card n="R/R T2" v={rr(x.rr_target_2)}/>
      </div>
      <div className="monitoredMeta">Last checked: {when(x.updated_at)} · Quote: {x.quote_provider||'UNKNOWN'} {x.quote_quality?`· ${x.quote_quality}`:''}</div>
      <div className="monitoredActions">
        {openResearch&&<button onClick={()=>openResearch(x.symbol)}>{x.ready?'REVIEW TRADE PLAN':'OPEN RESEARCH'}</button>}
        <button className="secondaryButton" onClick={()=>stopWatching(x.symbol)}>STOP MONITORING</button>
      </div>
      {x.ready&&<div className="setupReadyNote">Setup ready for your review. No order has been placed.</div>}
   </article>)}</div>}
 </section>

 <section className="brokerZone alpacaZone"><div className="brokerZoneTitle"><div><span className="eyebrow">EXTERNAL PAPER BROKER</span><h2>ALPACA PAPER</h2><p>These are actual simulated broker positions and orders. Monitored setups above are not included here until you explicitly submit and an order fills.</p></div><div className={`badge ${alpaca?.connected?'status-pass':'status-review'}`}>{alpaca?.connected?'CONNECTED · PAPER':alpaca?.configured?'CONNECTION ERROR':'NOT CONFIGURED'}</div></div>{alpaca&&<div className="panelGrid"><Card n="Environment" v={alpaca.environment}/><Card n="Paper Equity" v={money(alpaca.equity)}/><Card n="Paper Cash" v={money(alpaca.cash)}/><Card n="Paper Buying Power" v={money(alpaca.buying_power)}/><Card n="Trading Blocked" v={String(alpaca.trading_blocked??'UNKNOWN')}/><Card n="Account" v={alpaca.account_number_masked||'UNKNOWN'}/></div>}{alpaca?.error&&<div className="notice">{alpaca.error}</div>}{alpaca?.connected&&<><div className="manualBrokerWarning"><b>MANUAL ALPACA PAPER TEST TICKET</b><span>This ticket bypasses Baby research selection but still uses simulated money and explicit confirmation. Normal Baby investing should use Research → Trade Plan → Alpaca Paper Proposal.</span></div><div className="paperForm"><input value={confirm} onChange={e=>setConfirm(e.target.value)} placeholder="Type: EXECUTE ALPACA PAPER"/><button disabled={confirm!=='EXECUTE ALPACA PAPER'} onClick={submitAlpaca}>SUBMIT MANUAL ALPACA PAPER</button></div><Table title="Alpaca Paper Positions" rows={aPos}/><Table title="Alpaca Paper Orders" rows={aOrd} action={r=>r.id?<button onClick={()=>cancelAlpaca(r.id)}>CANCEL PAPER ORDER</button>:null}/></>}</section>

 <section className="brokerZone localZone"><div className="brokerZoneTitle"><div><span className="eyebrow">BABY LOCAL SIMULATOR</span><h2>LOCAL SQLITE PAPER ACCOUNT</h2><p>Private local simulation stored in baby_paper_trading.db. Nothing here is sent to Alpaca.</p></div><div className="badge status-review">LOCAL SIMULATION ONLY</div></div>{!d?<div className="notice">Loading local simulator…</div>:<><div className="panelGrid"><Card n="Local Equity" v={money(d.account?.equity)}/><Card n="Local Cash" v={money(d.account?.cash)}/><Card n="Positions Value" v={money(d.account?.positions_value)}/><Card n="Unrealized P&L" v={money(d.account?.unrealized_pnl)}/><Card n="Realized P&L" v={money(d.account?.realized_pnl)}/></div><form onSubmit={submitLocal} className="paperForm localTicket"><input value={form.symbol} onChange={e=>setForm({...form,symbol:e.target.value.toUpperCase()})}/><select value={form.side} onChange={e=>setForm({...form,side:e.target.value})}><option>BUY</option><option>SELL</option></select><input type="number" min="0.000001" step="any" value={form.quantity} onChange={e=>setForm({...form,quantity:e.target.value})}/><select value={form.order_type} onChange={e=>setForm({...form,order_type:e.target.value})}><option>MARKET</option><option>LIMIT</option></select>{form.order_type==='LIMIT'&&<input type="number" step="any" placeholder="Limit price" value={form.limit_price} onChange={e=>setForm({...form,limit_price:e.target.value})}/>}<button>CREATE LOCAL PAPER ORDER</button></form><Table title="Local Simulator Positions" rows={d.positions}/><Table title="Local Simulator Orders" rows={d.orders} action={r=>r.status==='PENDING'?<button onClick={()=>execLocal(r.id)}>EXECUTE LOCAL SIMULATION</button>:null}/><Table title="Local Simulator Fills" rows={d.fills}/></>}</section>
 </main>
}

function Card({n,v}){return <div className="metric"><span>{n}</span><strong>{v}</strong></div>}
function Table({title,rows=[],action}){return <section className="stage brokerTable"><h2>{title}</h2>{!rows.length?<div className="notice">No {title.toLowerCase()} yet.</div>:<div className="tableWrap"><table><thead><tr>{Object.keys(rows[0]).map(k=><th key={k}>{k}</th>)}{action&&<th>action</th>}</tr></thead><tbody>{rows.slice(0,100).map((r,i)=><tr key={r.id||r.symbol||i}>{Object.values(r).map((v,j)=><td key={j}>{v==null?'UNKNOWN':String(v)}</td>)}{action&&<td>{action(r)}</td>}</tr>)}</tbody></table></div>}</section>}
