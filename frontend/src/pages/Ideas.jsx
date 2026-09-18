import React,{useEffect,useState} from 'react';import {api} from '../lib/api';
export default function Ideas({openResearch}){
 const[d,setD]=useState(null),[rows,setRows]=useState([]),[busy,setBusy]=useState(false);
 useEffect(()=>{api.scanner().then(setD)},[]);
 const evaluate=async()=>{setBusy(true);const out=[];for(const c of (d?.candidates||[]).slice(0,20)){try{const x=await api.productionDecision(c.symbol,{force:false,record_v11:false});out.push({...c,production:x.status,v11:x.research_decision?.state,v11score:x.research_decision?.score,failures:x.bridge_failures||[]})}catch(e){out.push({...c,production:'ERROR',failures:[String(e)]})}}setRows(out);setBusy(false)};
 const show=rows.length?rows:(d?.candidates||[]).slice(0,20);
 return <main><div className="topbar"><div><div className="brand">BABY <span>IDEAS</span></div><p>Research candidates, not automatic buy instructions.</p></div><button className="primaryAction" disabled={busy||!d} onClick={evaluate}>{busy?'EVALUATING...':'EVALUATE TOP 20'}</button></div><div className="ideaGrid">{show.map((x,i)=><button className="ideaCard" key={x.symbol||i} onClick={()=>openResearch(x.symbol)}><div><b>{x.symbol}</b><span className={`ideaState ${x.production==='ELIGIBLE_PROPOSAL'?'good':''}`}>{x.production||'SCANNER'}</span></div><strong>{x.opportunity_score??x.score??'--'}</strong><small>Scanner score</small><p>{x.v11?`V11 ${x.v11} / ${x.v11score??'--'}`:(x.flow_type||'')}</p>{x.failures?.length>0&&<em>{x.failures.join(' / ')}</em>}</button>)}</div></main>
}
