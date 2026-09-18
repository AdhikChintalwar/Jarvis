import React,{useEffect,useState} from 'react';
import {api} from '../lib/api';

const ranges=['1D','5D','1M','3M','6M','1Y'];

export function StockPriceChart({symbol}){
 const[range,setRange]=useState('1M'),[d,setD]=useState(null);
 useEffect(()=>{if(symbol)api.stockHistory(symbol,range).then(setD).catch(()=>setD(null))},[symbol,range]);
 const bars=d?.bars||[],vals=bars.map(x=>Number(x.close)).filter(Number.isFinite);
 const w=900,h=260,p=18,min=vals.length?Math.min(...vals):0,max=vals.length?Math.max(...vals):1,span=(max-min)||1;
 const path=vals.map((v,i)=>`${i?'L':'M'}${(p+i/(Math.max(1,vals.length-1))*(w-2*p)).toFixed(1)},${(p+(1-(v-min)/span)*(h-2*p)).toFixed(1)}`).join(' ');
 return <section className="marketChart">
   <div className="chartToolbar"><div><span className="eyebrow">PRICE HISTORY</span><h3>{symbol}</h3></div><div className="rangeTabs">{ranges.map(x=><button className={x===range?'active':''} onClick={()=>setRange(x)} key={x}>{x}</button>)}</div></div>
   {!vals.length?<div className="chartEmpty">History is not available yet.</div>:<>
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"><path className="chartGrid" d={`M${p},${h/2}L${w-p},${h/2}`}/><path className="chartLine" d={path}/></svg>
    <div className="chartFoot"><span>Research/display data: {d?.provider||'--'}</span><span>{min.toFixed(2)} - {max.toFixed(2)}</span></div>
   </>}
 </section>
}

export function PortfolioEquityChart(){
 const[d,setD]=useState(null);
 useEffect(()=>{const load=()=>api.portfolioHistory().then(setD).catch(()=>{});load();const t=setInterval(load,10000);return()=>clearInterval(t)},[]);
 const rows=d?.snapshots||[],vals=rows.map(x=>Number(x.equity)).filter(Number.isFinite);
 const w=900,h=220,p=18,min=vals.length?Math.min(...vals):0,max=vals.length?Math.max(...vals):1,span=(max-min)||1;
 const path=vals.map((v,i)=>`${i?'L':'M'}${(p+i/(Math.max(1,vals.length-1))*(w-2*p)).toFixed(1)},${(p+(1-(v-min)/span)*(h-2*p)).toFixed(1)}`).join(' ');
 return <section className="marketChart"><div className="chartToolbar"><div><span className="eyebrow">PORTFOLIO EQUITY</span><h3>Tracked account history</h3></div><span className="refreshPill">10s refresh</span></div>{!vals.length?<div className="chartEmpty">Portfolio snapshots will appear as Baby monitors the account.</div>:<svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"><path className="chartLine" d={path}/></svg>}</section>
}
