import React,{useEffect,useMemo,useState} from 'react';
import {api} from '../lib/api';
import RefreshClock from './RefreshClock';

const ranges=['1D','1W','1M','ALL'];

export default function PortfolioPerformanceChart(){
  const[d,setD]=useState(null),[range,setRange]=useState('1M');
  const load=()=>api.portfolioHistory().then(setD).catch(()=>{});
  useEffect(()=>{load();const t=setInterval(load,10000);return()=>clearInterval(t)},[]);

  const rows=useMemo(()=>{
    const all=d?.snapshots||[];
    if(range==='ALL')return all;
    const ms={ '1D':86400000,'1W':604800000,'1M':2592000000 }[range];
    const cutoff=Date.now()-ms;
    return all.filter(x=>new Date(x.created_at).getTime()>=cutoff);
  },[d,range]);

  const vals=rows.map(x=>Number(x.equity)).filter(Number.isFinite);
  const w=960,h=250,p=20,min=vals.length?Math.min(...vals):0,max=vals.length?Math.max(...vals):1,span=(max-min)||1;
  const path=vals.map((v,i)=>{
    const x=p+(i/Math.max(1,vals.length-1))*(w-2*p);
    const y=p+(1-(v-min)/span)*(h-2*p);
    return `${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ');
  const first=vals[0],last=vals.at(-1),delta=vals.length>1?last-first:null;

  return <section className="portfolioChartCard">
    <div className="chartToolbar">
      <div><span className="eyebrow">PORTFOLIO PERFORMANCE</span><h3>{last!=null?`$${last.toLocaleString(undefined,{maximumFractionDigits:2})}`:'Waiting for snapshots'}</h3>{delta!=null&&<p className={delta>=0?'chartUp':'chartDown'}>{delta>=0?'+':''}${delta.toFixed(2)}</p>}</div>
      <div className="chartActions"><RefreshClock seconds={10} label="Portfolio"/><div className="rangeTabs">{ranges.map(r=><button key={r} className={r===range?'active':''} onClick={()=>setRange(r)}>{r}</button>)}</div></div>
    </div>
    {!vals.length?<div className="chartEmpty">Baby is collecting portfolio snapshots.</div>:<svg className="portfolioSvg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"><line className="chartGrid" x1={p} x2={w-p} y1={h/2} y2={h/2}/><path className="portfolioLine" d={path}/></svg>}
    <div className="chartFoot"><span>{rows.length} snapshots</span><span>Tracked account equity</span></div>
  </section>
}
