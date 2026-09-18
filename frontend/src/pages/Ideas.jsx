import React,{useEffect,useState} from 'react';
import {api} from '../lib/api';
import RefreshClock from '../components/RefreshClock';

function friendlyStatus(x){
  const s=String(x||'').toUpperCase();
  if(s.includes('ELIGIBLE'))return {label:'Setup ready',tone:'good'};
  if(s.includes('BLOCK'))return {label:'Not ready',tone:'warn'};
  if(s.includes('WATCH'))return {label:'Watch',tone:'warn'};
  if(s.includes('ERROR'))return {label:'Data issue',tone:'bad'};
  return {label:s||'Researching',tone:'neutral'};
}

function reasonText(failures=[]){
  if(!failures?.length)return 'No major blocker shown yet.';
  const map={
    ENTRY_NOT_TRIGGERED:'Entry condition has not happened yet.',
    PAPER_PROPOSAL_NOT_ELIGIBLE:'Current setup is not ready for a paper proposal.',
    HARD_RISK_OVERRIDE:'Risk rules rejected the setup.',
    EXECUTION_QUOTE_NOT_ELIGIBLE:'Current quote is not fresh enough for execution checks.',
    MISSING_PROPOSED_RISK:'Risk estimate is missing.',
    MISSING_PROPOSED_NOTIONAL:'Position size estimate is missing.'
  };
  return map[failures[0]]||String(failures[0]).replaceAll('_',' ').toLowerCase();
}

export default function Ideas({openResearch}){
  const[scan,setScan]=useState(null);
  const[rows,setRows]=useState([]);
  const[busy,setBusy]=useState(false);
  const[last,setLast]=useState(null);

  const load=()=>api.scanner().then(setScan).catch(()=>{});
  useEffect(()=>{load();const t=setInterval(load,60000);return()=>clearInterval(t)},[]);

  const evaluate=async()=>{
    setBusy(true);
    const out=[];
    for(const c of (scan?.candidates||[]).slice(0,20)){
      try{
        const x=await api.productionDecision(c.symbol,{force:false,record_v11:false});
        out.push({...c,
          production:x.status,
          v11:x.research_decision?.state,
          v11score:x.research_decision?.score,
          confidence:x.research_decision?.confidence,
          failures:x.bridge_failures||[]
        });
      }catch(e){out.push({...c,production:'ERROR',failures:[String(e)]})}
    }
    setRows(out);
    setLast(new Date());
    setBusy(false);
  };

  const show=rows.length?rows:(scan?.candidates||[]).slice(0,20);

  return <main className="simplePage ideasPage">
    <section className="pageExplain">
      <div>
        <span className="pageKicker">IDEAS</span>
        <h1>Stocks Baby found worth researching</h1>
        <p>These are research candidates, not automatic buy recommendations. Open any stock to see the chart, reasons, risks, and current setup.</p>
      </div>
      <div className="pageExplainActions">
        <RefreshClock seconds={60} label="Scanner"/>
        <button className="primaryButton" disabled={busy||!scan} onClick={evaluate}>{busy?'Checking ideas…':'Analyze top 20'}</button>
      </div>
    </section>

    <div className="plainHelpBox">
      <b>How to read this page</b>
      <span><strong>Scanner score</strong> = how unusual/interesting the stock looked to the scanner.</span>
      <span><strong>Research score</strong> = Baby's research attractiveness score, not a probability and not a buy signal.</span>
      <span><strong>Confidence</strong> = how complete/consistent the research evidence is.</span>
    </div>

    {last&&<div className="lastChecked">Last analyzed: {last.toLocaleString()}</div>}

    <section className="cleanIdeaGrid">
      {show.map((x,i)=>{
        const status=friendlyStatus(x.production||x.v11);
        return <article className="cleanIdeaCard" key={x.symbol||i}>
          <div className="cleanIdeaTop">
            <div><b className="stockTicker">{x.symbol}</b><span className={`simpleStatus ${status.tone}`}>{status.label}</span></div>
            <button className="viewResearchButton" onClick={()=>openResearch?.(x.symbol)}>View research →</button>
          </div>

          <div className="cleanMetrics">
            <div><span>Scanner score</span><strong>{x.opportunity_score??x.score??'--'}</strong></div>
            <div><span>Research score</span><strong>{x.v11score??'--'}</strong></div>
            <div><span>Confidence</span><strong>{x.confidence??'--'}{x.confidence!=null?'%':''}</strong></div>
          </div>

          <div className="ideaExplanation">
            <span>Current state</span>
            <b>{x.v11||'Waiting for deeper analysis'}</b>
            <p>{reasonText(x.failures)}</p>
          </div>
        </article>
      })}
    </section>
  </main>
}
