import React,{useMemo,useState}from"react";
import{Activity,BarChart3,BrainCircuit,Database,FileSearch,Gauge,Search,ShieldAlert,Sparkles,TrendingUp,Wifi,WifiOff}from"lucide-react";
import{demo}from"./demo";

const money=v=>v==null?"—":Math.abs(v)>=1e9?`$${(v/1e9).toFixed(2)}B`:Math.abs(v)>=1e6?`$${(v/1e6).toFixed(1)}M`:`$${Number(v).toLocaleString()}`;
const pct=v=>v==null?"—":`${(v*100).toFixed(1)}%`;
const num=v=>v==null?"—":Number(v).toFixed(2);
const tone=s=>{s=String(s||"").toUpperCase();if(s.includes("STRONG")||s==="PRIMARY_ONLY"||s==="COHERENT_CURRENT")return"good";if(s.includes("MATERIAL")||s==="MISSING"||s.includes("HIGH"))return"bad";if(s.includes("REVIEW")||s.includes("MISMATCH")||s.includes("MODERATE"))return"warn";return"neutral"};
const pretty=s=>String(s??"—").replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());

function Card({title,icon:Icon,children,className=""}){return <section className={`card ${className}`}><div className="cardTitle">{Icon&&<Icon size={17}/>}<span>{title}</span></div>{children}</section>}
function Stat({label,value,sub}){return <div className="stat"><div className="muted">{label}</div><div className="statValue">{value}</div>{sub&&<div className="tiny">{sub}</div>}</div>}
function Pill({children,kind="neutral"}){return <span className={`pill ${kind}`}>{children}</span>}
function Meter({value=0,max=100}){let p=Math.max(0,Math.min(100,(Number(value)||0)/max*100));return <div className="meter"><i style={{width:`${p}%`}}/></div>}

export default function App(){
 const[data,setData]=useState(demo),[ticker,setTicker]=useState("CRWD"),[loading,setLoading]=useState(false),[error,setError]=useState("");
 const pf=data.primary_financial?.verified_financials||{};
 const metrics=useMemo(()=>Object.entries(pf),[pf]);
 async function analyze(e){e?.preventDefault();setLoading(true);setError("");try{let r=await fetch(`http://127.0.0.1:8766/api/analyze/${ticker.trim().toUpperCase()}`);let j=await r.json();if(!r.ok)throw new Error(j.detail||"Analysis failed");setData(j)}catch(x){setError(x.message)}finally{setLoading(false)}}
 return <div className="shell">
  <aside className="sidebar">
   <div className="brand"><div className="orb">B</div><div><b>BABY</b><span>INVESTOR OS</span></div></div>
   <nav>
    <a className="active"><BarChart3/>Research</a><a><TrendingUp/>Scanner</a><a><BrainCircuit/>Committee</a><a><FileSearch/>Evidence</a><a><ShieldAlert/>Risk</a>
   </nav>
   <div className="sideFoot"><div><Wifi size={15}/> Local engine</div><small>Primary financial schema {data.primary_financial?.schema_version||"—"}</small></div>
  </aside>

  <main>
   <header>
    <div><div className="eyebrow">LOCAL INVESTMENT INTELLIGENCE</div><h1>{data.ticker||ticker} <span>{data.company_name||""}</span></h1></div>
    <form onSubmit={analyze} className="search"><Search size={18}/><input value={ticker} onChange={e=>setTicker(e.target.value.toUpperCase())} placeholder="Ticker"/><button disabled={loading}>{loading?"Analyzing…":"Analyze"}</button></form>
   </header>
   {error&&<div className="error"><WifiOff size={17}/>{error} — demo data remains visible.</div>}

   <div className="heroGrid">
    <Card title="Market Snapshot" icon={Activity}>
     <div className="stats4"><Stat label="Price" value={money(data.market?.current_price)}/><Stat label="Daily" value={data.market?.daily_change_pct==null?"—":`${Number(data.market.daily_change_pct).toFixed(2)}%`}/><Stat label="Volume" value={data.market?.volume?.toLocaleString?.()||"—"}/><Stat label="Rel. Volume" value={num(data.technical?.relative_volume)}/></div>
    </Card>
    <Card title="BABY Score" icon={Sparkles}>
      <div className="scoreRow"><div className="bigScore">{num(data.score?.overall_score)}</div><div><Pill kind={tone(data.score?.signal)}>{pretty(data.score?.signal)}</Pill><div className="tiny">Current deterministic score</div></div></div>
      <Meter value={data.score?.overall_score}/><div className="split"><span>Financial health</span><b>{num(data.financial_health?.score)}</b></div>
    </Card>
    <Card title="Risk" icon={ShieldAlert}>
      <div className="scoreRow"><div className="riskWord">{pretty(data.risk?.overall_risk)}</div><Pill kind={tone(data.risk?.overall_risk)}>{pretty(data.risk?.overall_risk)}</Pill></div>
      <div className="split"><span>Annual volatility</span><b>{pct(data.risk?.annualized_volatility)}</b></div><div className="split"><span>Max drawdown</span><b>{pct(data.risk?.max_drawdown)}</b></div>
    </Card>
   </div>

   <div className="contentGrid">
    <Card title="Verified Financial Intelligence" icon={Database} className="wide">
      <div className="sourceLine"><span>Primary: {data.primary_financial?.primary_source||"SEC/XBRL"}</span><Pill kind={tone(data.primary_financial?.balance_sheet_snapshot?.status)}>{pretty(data.primary_financial?.balance_sheet_snapshot?.status)}</Pill></div>
      <div className="tableWrap"><table><thead><tr><th>Metric</th><th>Value</th><th>Status</th><th>Confidence</th><th>Period</th><th>Source</th></tr></thead><tbody>
       {metrics.map(([k,x])=><tr key={k}><td>{pretty(k)}</td><td className="mono">{k.includes("margin")||k.includes("growth")||k.includes("shares_change")?pct(x.value):money(x.value)}</td><td><Pill kind={tone(x.status)}>{pretty(x.status)}</Pill></td><td><div className="confidence"><span>{Math.round((x.confidence||0)*100)}%</span><Meter value={(x.confidence||0)*100}/></div></td><td className="mono">{x.period||"—"}</td><td>{x.source||"—"}</td></tr>)}
      </tbody></table></div>
    </Card>

    <Card title="Technical State" icon={Gauge}>
      <div className="technicalGauge"><span>RSI 14</span><b>{num(data.technical?.rsi_14)}</b><Meter value={data.technical?.rsi_14}/></div>
      {[["Trend",data.technical?.trend_signal],["Momentum",data.technical?.momentum_signal],["SMA 20",money(data.technical?.sma_20)],["SMA 50",money(data.technical?.sma_50)],["SMA 200",money(data.technical?.sma_200)],["ATR %",data.technical?.atr_percent==null?"—":`${Number(data.technical.atr_percent).toFixed(2)}%`]].map(([a,b])=><div className="split" key={a}><span>{a}</span><b>{pretty(b)}</b></div>)}
    </Card>

    <Card title="Evidence & Integrity" icon={FileSearch}>
      <div className="evidenceHero"><b>{metrics.filter(([,x])=>x.value!=null).length}/{metrics.length}</b><span>verified metrics currently usable</span></div>
      {["STRONG_AGREEMENT","PRIMARY_ONLY","REVIEW","PERIOD_MISMATCH","MATERIAL_DISAGREEMENT","MISSING"].map(s=>{let n=metrics.filter(([,x])=>x.status===s).length;return <div className="split" key={s}><span>{pretty(s)}</span><Pill kind={tone(s)}>{n}</Pill></div>})}
    </Card>

    <Card title="Investment Thesis" icon={BrainCircuit} className="wide">
      <p className="thesis">{data.thesis?.summary||data.thesis?.thesis||"The deterministic research pipeline is ready. Committee synthesis can be layered on top without changing the evidence contract."}</p>
      <div className="thesisCols"><div><h3>Bull case</h3>{(data.thesis?.bull_case||data.score?.strengths||[]).slice(0,5).map((x,i)=><p key={i}>+ {typeof x==="string"?x:JSON.stringify(x)}</p>)}</div><div><h3>Bear case</h3>{(data.thesis?.bear_case||data.score?.weaknesses||[]).slice(0,5).map((x,i)=><p key={i}>− {typeof x==="string"?x:JSON.stringify(x)}</p>)}</div></div>
    </Card>

    <Card title="Committee Readiness" icon={BrainCircuit}>
      <div className="committee"><div className="brain">AI</div><div><b>Nemotron Committee</b><p>Evidence-first synthesis layer</p></div></div>
      <div className="split"><span>Financial provenance</span><Pill kind="good">READY</Pill></div>
      <div className="split"><span>Explicit unresolved facts</span><Pill kind="good">PRESERVED</Pill></div>
      <div className="split"><span>Real-money execution</span><Pill kind="warn">APPROVAL REQUIRED</Pill></div>
      <button className="secondary" disabled>Committee run — wire later</button>
    </Card>
   </div>
   <footer>Baby Investor Command Center · Local research interface · No automatic real-money order submission</footer>
  </main>
 </div>
}