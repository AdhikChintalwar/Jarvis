import React,{useEffect,useMemo,useRef,useState} from 'react';import {api} from '../lib/api';import LiveQuote from '../components/LiveQuote';import Pipeline from '../components/Pipeline';import MetricCard from '../components/MetricCard';import ResearchLegend from '../components/ResearchLegend';import {ShieldAlert,RefreshCw,Play,CheckCircle2,AlertTriangle,Info,BookOpen,ChevronDown} from 'lucide-react';
import {StockPriceChart} from '../components/MarketCharts';
import CandlestickChart from '../components/CandlestickChart';
import PipelineScoreboard from '../components/PipelineScoreboard';
export default function Research({initialSymbol="AAPL",onContext}){
 const [symbol,setSymbol]=useState(initialSymbol),[draft,setDraft]=useState(initialSymbol),[report,setReport]=useState(null),[glossary,setGlossary]=useState({}),[active,setActive]=useState('data'),[error,setError]=useState(''),[job,setJob]=useState(null),[busy,setBusy]=useState(false),[proposal,setProposal]=useState(null),[proposalMsg,setProposalMsg]=useState(''),[legend,setLegend]=useState(false),[explain,setExplain]=useState(null),[explainOpen,setExplainOpen]=useState(true),[tradeOpen,setTradeOpen]=useState(false);const poll=useRef(null);
 const load=async s=>{setError('');try{const r=await api.research(s);if(r.research_status==='NOT_RESEARCHED'){setReport(null);setJob(r.job);return false}setReport(r);setJob({status:'READY'});setActive(r.stages?.[0]?.id||'data');return true}catch(e){setError(String(e));return false}};
 const watch=async s=>{clearInterval(poll.current);poll.current=setInterval(async()=>{const st=await api.researchStatus(s);setJob(st);if(st.status==='READY'){clearInterval(poll.current);setBusy(false);await load(s)}else if(st.status==='ERROR'){clearInterval(poll.current);setBusy(false);setError(st.error||'Research failed')}},1200)};
 const run=async(force=false)=>{setBusy(true);setError('');try{const st=await api.runResearch(symbol,force);setJob(st);if(st.status==='READY'){setBusy(false);await load(symbol)}else watch(symbol)}catch(e){setBusy(false);setError(String(e))}};
 useEffect(()=>{api.glossary().then(setGlossary);load(symbol);return()=>clearInterval(poll.current)},[]);
 const open=async s=>{s=s.toUpperCase();setSymbol(s);setReport(null);setJob(null);setProposal(null);setProposalMsg('');await load(s)};
 const checkProposal=async()=>{setProposalMsg('');try{setProposal(await api.paperProposal(symbol))}catch(e){setProposalMsg(String(e))}};
 const createProposalOrder=async()=>{setProposalMsg('');try{const r=await api.createProposalOrder(symbol);setProposalMsg(`PENDING paper order created: ${r.order.id}. It has NOT been executed.`);setProposal(r.proposal)}catch(e){setProposalMsg(String(e))}};
 const stage=useMemo(()=>report?.stages?.find(s=>s.id===active),[report,active]);
 useEffect(()=>{onContext?.({page:'research',symbol,stage_id:active,stage_label:stage?.label})},[symbol,active,stage?.label]);
 useEffect(()=>{if(report&&active)api.explainStage(symbol,active).then(setExplain).catch(()=>setExplain(null))},[report,active,symbol]);
 return <main className="screenPage researchPage">
<section className="pageExplain compactExplain researchExplain">
  <div>
    <span className="pageKicker">STOCK RESEARCH</span>
    <h1>Understand one stock before making a decision</h1>
    <p>Start with the chart and Baby's simple research view. Technical V11/V12 details are supporting information, not the first thing you need to read.</p>
  </div>
</section>
<CandlestickChart symbol={symbol}/><ResearchLegend open={legend} onClose={()=>setLegend(false)}/><header className="topbar"><div><div className="brand">BABY <span>INVESTMENT INTELLIGENCE</span></div><p>Production research · auditable evidence · AI scoring authority 0%</p></div><div className="topActions"><button onClick={()=>setLegend(true)}><BookOpen size={16}/> Research Legend</button><form onSubmit={e=>{e.preventDefault();open(draft)}}><input value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Ticker"/><button>Open research</button></form></div></header>
 {error&&<div className="notice"><AlertTriangle size={18}/>{error}</div>}
 <section className="hero"><div><div className="researchStockIdentity"><h1>{symbol}</h1>{report?.company_name&&<small className="stockCompanyName researchCompanyName">{report.company_name}</small>}</div><LiveQuote symbol={symbol}/></div><div className="scoreGrid"><K label="BABY STATUS" v={report?.decision||'NOT RESEARCHED'}/><K label="RESEARCH SCORE" v={report?.score!=null?`${Number(report.score).toFixed(1)}/100`:'UNKNOWN'}/><K label="CONFIDENCE" v={report?.confidence!=null?`${report.confidence}%`:'UNKNOWN'}/><K label="EVIDENCE COVERAGE" v={report?.coverage!=null?`${report.coverage}%`:'UNKNOWN'}/><K label="UNIFIED RISK" v={report?.risk||'UNKNOWN'} danger={report?.hard_risk_override}/><K label="VALIDATION" v={report?.validation_status||'UNKNOWN'}/></div><div className="snapshot">Research snapshot: {report?.generated_at?new Date(report.generated_at).toLocaleString():'not generated'} · Quote timestamp is independent.</div><div className="researchActions">{!report&&<button className="primaryAction" disabled={busy||job?.status==='RUNNING'} onClick={()=>run(false)}><Play size={17}/> Run full Baby research</button>}{report&&<button className="primaryAction" disabled={busy} onClick={()=>run(true)}><RefreshCw size={17} className={busy?'spin':''}/> Refresh full research</button>}<Job job={job}/></div></section>
 {!report&&<section className="emptyResearch"><h2>{job?.status==='RUNNING'||job?.status==='QUEUED'?'Baby is researching '+symbol:`${symbol} has not been researched yet`}</h2><p>{job?.stage||'Run the production Baby Investor pipeline. The UI will populate automatically when it finishes.'}</p></section>}
 {report&&<PipelineScoreboard report={report}/>}{report&&<div className="layout"><aside><div className="asideTitle"><h3>RESEARCH PIPELINE</h3><button title="Open complete legend" onClick={()=>setLegend(true)}><Info size={15}/></button></div><Pipeline stages={report.stages||[]} active={active} onSelect={id=>{setActive(id);if(id==='trade')setTradeOpen(true)}}/></aside><section className="stage"><div className="stageHead"><div><span className="eyebrow">STAGE {String((report.stages||[]).findIndex(x=>x.id===active)+1).padStart(2,'0')}</span><h2>{stage?.label}</h2><p>{stage?.summary}</p></div><div className="stageHeadActions"><button className="infoButton" onClick={()=>setExplainOpen(v=>!v)}><Info size={15}/> Explain this stage</button><div className={`badge status-${stage?.status?.toLowerCase()}`}>{stage?.status}</div></div></div>{explainOpen&&explain&&<StageExplain x={explain}/>}<div className="metrics">{(stage?.metrics||[]).map(m=><MetricCard key={m.key} m={m} glossary={glossary}/>)}</div><Reasoning stage={stage}/>{active==='trade'&&<TradePlanPreview data={report.trade_plan} onOpen={()=>setTradeOpen(true)}/>}{active==='portfolio'&&<JsonPanel title="PORTFOLIO IMPACT" data={report.portfolio_impact}/>} {active==='history'&&<JsonPanel title="HISTORICAL VALIDATION" data={report.historical_validation}/>}<details className="advancedRaw"><summary>Advanced · Raw production data <ChevronDown size={14}/></summary><pre>{JSON.stringify(active==='trade'?report.trade_plan:stage,null,2)}</pre></details><div className="authority"><ShieldAlert size={18}/><div><b>Authority boundary</b><span>AI scoring authority: {report.ai_scoring_authority??0}% · AI execution authority: {report.ai_execution_authority||'NONE'} · Real-money execution is disabled.</span></div></div></section></div>}{tradeOpen&&report&&<TradePlanSheet symbol={symbol} data={report.trade_plan} onClose={()=>setTradeOpen(false)}/>}</main>}
function StageExplain({x}){return <div className="stageExplain"><div><small>WHAT IS THIS?</small><p>{x.what}</p></div><div><small>WHY DOES BABY CHECK IT?</small><p>{x.why}</p></div><div><small>WHAT DOES IT CHECK?</small><ul>{(x.checks||[]).map(v=><li key={v}>{v}</li>)}</ul></div><div><small>HOW DO I READ THE RESULT?</small><p>{x.result}</p></div></div>}

function TradePlanPreview({data,onOpen}){
 const c=data?.current_setup||{};
 return <div className="tradePlanPreview">
   <div>
     <span className="eyebrow">TRADE PLAN</span>
     <h3>{c.status||data?.status||'WAITING'}</h3>
     <p>{c.reason||'Open the full trade plan to review entry, invalidation, targets and deterministic risk sizing.'}</p>
   </div>
   <button className="primaryAction" onClick={onOpen}>VIEW FULL TRADE PLAN</button>
 </div>
}

function TradePlanSheet({symbol,data,onClose}){
 useEffect(()=>{
   const onKey=e=>{if(e.key==='Escape')onClose()};
   window.addEventListener('keydown',onKey);
   const previous=document.body.style.overflow;
   document.body.style.overflow='hidden';
   return()=>{window.removeEventListener('keydown',onKey);document.body.style.overflow=previous}
 },[onClose]);
 const c=data?.current_setup||{};
 return <div className="tradeSheetShade" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}>
   <section className="tradeSheet" role="dialog" aria-modal="true" aria-label={`${symbol} trade plan`}>
     <header className="tradeSheetHead">
       <div>
         <span className="eyebrow">{symbol} · DETERMINISTIC TRADE PLAN</span>
         <h2>{c.status||data?.status||'Trade Plan'}</h2>
         <p>{c.reason||'Review the complete setup, risk and paper-execution checks.'}</p>
       </div>
       <button className="tradeSheetClose" onClick={onClose} aria-label="Close trade plan">×</button>
     </header>
     <div className="tradeSheetBody">
       <TradePlan data={data}/>
       <PaperProposalPanel symbol={symbol}/>
     </div>
     <footer className="tradeSheetFoot">
       <span>Research only · AI execution authority: NONE · Real-money execution disabled</span>
       <button className="secondaryButton" onClick={onClose}>CLOSE</button>
     </footer>
   </section>
 </div>
}

function TradePlan({data}){if(!data||!Object.keys(data).length)return <div className="notice">Trade plan was not produced.</div>;const p=data.pullback||{},b=data.breakout||{},c=data.current_setup||{};return <section className="tradeVisual"><div className="tradeBanner"><div><small>CURRENT SETUP</small><strong>{c.status||data.status}</strong><p>{c.reason}</p></div><div><small>CURRENT PRICE</small><strong>${fmt(data.current_price)}</strong></div></div><div className="tradeColumns"><Scenario title="PULLBACK" status={p.status} rows={[['Entry zone',`${money(p.entry_low)} – ${money(p.entry_high)}`],['Planned entry',money(p.planned_entry)],['Invalidation',money(p.invalidation)],['Target 1',money(p.target_1)],['Target 2',money(p.target_2)],['R/R T1',ratio(p.risk_reward_1)],['R/R T2',ratio(p.risk_reward_2)]]}/><Scenario title="BREAKOUT" status={b.status} rows={[['Trigger',money(b.trigger)],['Invalidation',money(b.invalidation)],['Target 1',money(b.target_1)],['Target 2',money(b.target_2)],['R/R T1',ratio(b.risk_reward_1)],['R/R T2',ratio(b.risk_reward_2)]]}/></div><div className="notice">Baby determines the trade plan only. You choose the Alpaca PAPER quantity when you explicitly submit an order.</div>{data.notes?.map((n,i)=><div className="notice" key={i}>{n}</div>)}</section>}
function Scenario({title,status,rows}){return <div className="scenario"><div><small>{title} SETUP</small><b>{status||'UNKNOWN'}</b></div>{rows.map(([k,v])=><p key={k}><span>{k}</span><strong>{v}</strong></p>)}</div>}
const fmt=x=>x==null?'UNKNOWN':Number(x).toFixed(2);const money=x=>x==null?'UNKNOWN':`$${fmt(x)}`;const ratio=x=>x==null?'UNKNOWN':`${Number(x).toFixed(2)}×`;
function Job({job}){if(!job)return null;const running=['QUEUED','RUNNING'].includes(job.status);return <div className={`jobState ${job.status?.toLowerCase()}`}>{running?<RefreshCw size={16} className="spin"/>:<CheckCircle2 size={16}/>}<span>{job.status}{job.stage?` · ${job.stage}`:''}</span></div>}
function K({label,v,danger}){return <div className={`kpi ${danger?'danger':''}`}><small>{label}</small><strong>{v}</strong></div>}
function Reasoning({stage}){const groups=[['Positive evidence',stage?.positives,'good'],['Negative evidence',stage?.negatives,'bad'],['Unknown evidence',stage?.unknowns,'unknown'],['Conflicting evidence',stage?.conflicts,'conflict']];return <div className="reason"><h3>AUDITABLE REASONING OUTPUT</h3><p className="muted">Inspectable evidence, formulas and rule outputs — not hidden LLM chain-of-thought.</p>{groups.map(([n,a,c])=>(a?.length?<div key={n}><b>{n}</b>{a.map((x,i)=><p className={c} key={i}>• {x}</p>)}</div>:null))}{!groups.some(x=>x[1]?.length)&&<p className="muted">No structured reasons exported for this stage. Missing evidence remains UNKNOWN.</p>}</div>}
function JsonPanel({title,data}){return <div className="jsonPanel"><h3>{title}</h3><pre>{JSON.stringify(data||{},null,2)}</pre></div>}
function PaperProposalPanel({symbol}){
 const[confirm,setConfirm]=useState(''),[quantity,setQuantity]=useState('1'),[brokerMsg,setBrokerMsg]=useState(''),[alpacaProposal,setAlpacaProposal]=useState(null),[checking,setChecking]=useState(false);
 const checkAlpaca=async()=>{setBrokerMsg('');setChecking(true);try{const p=await api.alpacaResearchProposal(symbol);setAlpacaProposal(p);setBrokerMsg(p.eligible?`Baby is monitoring ${symbol}. SETUP READY for review; no order was placed.`:`Baby is now monitoring ${symbol}. Current state: ${p.setup_status||p.status}. ${p.reason||''}`)}catch(e){setBrokerMsg(String(e))}finally{setChecking(false)}};
 const sendAlpaca=async()=>{setBrokerMsg('');const q=Number(quantity);if(!Number.isFinite(q)||q<=0){setBrokerMsg('Enter a positive PAPER quantity.');return}try{const r=await api.alpacaResearchOrder(symbol,q,confirm);setBrokerMsg(`Submitted ${q} user-selected shares to Alpaca PAPER: ${r.order.id}`);setAlpacaProposal(r.proposal);setConfirm('')}catch(e){setBrokerMsg(String(e))}};
 return <div className="proposalPanel">
   <div className="stageHead">
     <div>
       <span className="eyebrow">ALPACA PAPER · EXECUTION BRIDGE</span>
       <h2>Server-verified trade plan</h2>
       <p>Baby decides the setup, entry, invalidation, targets and readiness. You decide the PAPER order quantity.</p>
     </div>
     {alpacaProposal&&<div className={`badge ${alpacaProposal.eligible?'status-pass':'status-review'}`}>{alpacaProposal.status}</div>}
   </div>
   <div className="researchActions">
     <button className="primaryAction" disabled={checking} onClick={checkAlpaca}>{checking?'CHECKING…':'CHECK ALPACA PAPER SETUP'}</button>
   </div>
   {alpacaProposal&&<div className="alpacaResearchExec">
     <div className="panelGrid">
       <PP n="Status" v={alpacaProposal.status}/>
       <PP n="Setup" v={alpacaProposal.setup_status}/>
       <PP n="Quote" v={money(alpacaProposal.quote_price)}/>
       <PP n="Risk" v={alpacaProposal.risk_level}/>
       <PP n="Entry" v={money(alpacaProposal.entry_price)}/>
       <PP n="Invalidation" v={money(alpacaProposal.invalidation)}/>
       <PP n="Target 1" v={money(alpacaProposal.target_1)}/>
       <PP n="Target 2" v={money(alpacaProposal.target_2)}/>
     </div>
     <div className={`proposalReason ${alpacaProposal.eligible?'good':'unknown'}`}>
       <b>{alpacaProposal.eligible?'SETUP READY FOR YOUR REVIEW':'ALPACA PAPER WAITING / BLOCKED'}</b>
       <span>{alpacaProposal.reason}</span>
     </div>
     {alpacaProposal.eligible&&<>
       <p>Enter the simulated PAPER quantity you want. Baby does not choose this number. The server revalidates the setup again before submission.</p>
       <div className="paperForm userQuantityForm">
         <input type="number" min="0.000001" step="any" value={quantity} onChange={e=>setQuantity(e.target.value)} placeholder="Quantity"/>
         <input value={confirm} onChange={e=>setConfirm(e.target.value)} placeholder="EXECUTE ALPACA PAPER"/>
         <button disabled={confirm!=='EXECUTE ALPACA PAPER'||!(Number(quantity)>0)} onClick={sendAlpaca}>SUBMIT USER QUANTITY TO ALPACA PAPER</button>
       </div>
     </>}
   </div>}
   {brokerMsg&&<div className="notice">{brokerMsg}</div>}
 </div>
}
function PP({n,v}){return <div className="controlCard"><small>{n}</small><strong>{v}</strong></div>}
