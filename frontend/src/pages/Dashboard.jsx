import React,{useEffect,useState} from 'react';
import {api} from '../lib/api';
import RefreshClock from '../components/RefreshClock';

function Money({value}){
  if(value==null)return <>--</>;
  return <>${Number(value).toLocaleString(undefined,{maximumFractionDigits:2})}</>;
}

function SimpleStatus({value}){
  const v=String(value||'UNKNOWN').toUpperCase();
  let cls='neutral';
  if(['READY','PASS','OPEN','OK','CONTINUE'].some(x=>v.includes(x)))cls='good';
  if(['WATCH','WAIT','REVIEW','CANARY'].some(x=>v.includes(x)))cls='warn';
  if(['BLOCK','ERROR','FAIL','URGENT'].some(x=>v.includes(x)))cls='bad';
  return <span className={`simpleStatus ${cls}`}>{v}</span>
}

export default function Dashboard({openResearch,go}){
  const[health,setHealth]=useState(null);
  const[scan,setScan]=useState(null);
  const[jobs,setJobs]=useState(null);
  const[events,setEvents]=useState(null);
  const[portfolio,setPortfolio]=useState(null);

  const load=()=>{
    api.productionHealth?.().then(setHealth).catch(()=>{});
    api.scanner?.().then(setScan).catch(()=>{});
    api.monitorJobs?.().then(setJobs).catch(()=>{});
    api.monitorEvents?.().then(setEvents).catch(()=>{});
    api.portfolioHistory?.().then(setPortfolio).catch(()=>{});
  };

  useEffect(()=>{
    load();
    const t=setInterval(load,15000);
    return()=>clearInterval(t);
  },[]);

  const candidates=(scan?.candidates||[]).slice(0,5);
  const activeJobs=(jobs?.jobs||[]).filter(x=>x.enabled);
  const recent=(events?.events||[]).slice(0,5);
  const snaps=portfolio?.snapshots||[];
  const latest=snaps.at(-1);

  return <main className="simplePage homePage">
    <section className="pageExplain">
      <div>
        <span className="pageKicker">HOME</span>
        <h1>Your daily Baby overview</h1>
        <p>Start here. See what Baby found, how your portfolio is doing, and whether anything needs your attention.</p>
      </div>
      <div className="pageExplainActions">
        <RefreshClock seconds={15} label="Update"/>
        <button className="secondaryButton" onClick={load}>Refresh now</button>
      </div>
    </section>

    <section className="homeSummary">
      <div className="summaryCard heroMetric">
        <span>Portfolio value</span>
        <strong><Money value={latest?.equity}/></strong>
        <small>{snaps.length} saved snapshots</small>
      </div>
      <div className="summaryCard">
        <span>Stocks Baby found</span>
        <strong>{scan?.candidates?.length??0}</strong>
        <small>latest scanner results</small>
      </div>
      <div className="summaryCard">
        <span>Positions monitored</span>
        <strong>{activeJobs.length}</strong>
        <small>checked automatically</small>
      </div>
      <div className="summaryCard">
        <span>System status</span>
        <SimpleStatus value={health?.status||'READY'}/>
        <small>research platform</small>
      </div>
    </section>

    <section className="homeTwoCol">
      <div className="simplePanel">
        <div className="simplePanelHead">
          <div><span>WHAT BABY FOUND</span><h2>Research ideas</h2><p>Stocks Baby noticed because something interesting appeared in the data.</p></div>
          <button className="linkButton" onClick={()=>go?.('ideas')}>See all ideas →</button>
        </div>
        <div className="homeIdeaRows">
          {candidates.map((x,i)=><button className="homeIdeaRow" key={x.symbol||i} onClick={()=>openResearch?.(x.symbol)}>
            <div className="stockIdentity"><b>{x.symbol}</b><span>{x.flow_type||x.setup||'Research candidate'}</span></div>
            <div className="stockScore"><small>Scanner score</small><b>{x.opportunity_score??x.score??'--'}</b></div>
            <span className="openButton">View research</span>
          </button>)}
          {!candidates.length&&<div className="friendlyEmpty">No current ideas. Baby will add them after the next scan.</div>}
        </div>
      </div>

      <div className="simplePanel">
        <div className="simplePanelHead">
          <div><span>YOUR POSITIONS</span><h2>Automatic monitoring</h2><p>Baby checks each open position separately and only flags meaningful changes.</p></div>
          <button className="linkButton" onClick={()=>go?.('portfolio')}>Open portfolio →</button>
        </div>
        <div className="positionRows">
          {activeJobs.slice(0,5).map(j=><div className="positionRow" key={j.symbol}>
            <div><b>{j.symbol}</b><span>Every {j.interval_minutes||5} min</span></div>
            <SimpleStatus value={j.last_status||'MONITORING'}/>
          </div>)}
          {!activeJobs.length&&<div className="friendlyEmpty">No open positions are being monitored right now.</div>}
        </div>
      </div>
    </section>

    <section className="simplePanel attentionPanel">
      <div className="simplePanelHead">
        <div><span>NEEDS YOUR ATTENTION</span><h2>Recent important changes</h2><p>You do not need to watch every internal event. Baby surfaces meaningful changes here.</p></div>
        <button className="linkButton" onClick={()=>go?.('alerts')}>Open alerts →</button>
      </div>
      <div className="friendlyTimeline">
        {recent.map((e,i)=><div className="friendlyEvent" key={e.id||i}>
          <span className={`friendlyEventDot severity-${String(e.severity||'INFO').toLowerCase()}`}/>
          <div><b>{e.symbol||'Baby'} — {String(e.event_type||'Update').replaceAll('_',' ')}</b><p>{e.summary}</p></div>
          <time>{e.created_at?new Date(e.created_at).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'}):''}</time>
        </div>)}
        {!recent.length&&<div className="friendlyEmpty">Nothing needs your attention right now.</div>}
      </div>
    </section>
  </main>
}
