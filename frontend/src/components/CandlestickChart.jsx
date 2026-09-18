import React,{useEffect,useMemo,useState} from 'react';
import {api} from '../lib/api';
import RefreshClock from './RefreshClock';

const views=[
 {label:'5m',range:'1D',note:'5-minute candles'},
 {label:'15m',range:'5D',note:'15-minute candles'},
 {label:'1h',range:'1M',note:'1-hour candles'},
 {label:'3M',range:'3M',note:'daily candles'},
 {label:'6M',range:'6M',note:'daily candles'},
 {label:'1Y',range:'1Y',note:'daily candles'},
 {label:'MAX',range:'MAX',note:'full available history'},
];

const money=v=>Number.isFinite(Number(v))?`$${Number(v).toFixed(2)}`:'--';
const compact=v=>{
 const n=Number(v); if(!Number.isFinite(n))return '--';
 if(n>=1e9)return `${(n/1e9).toFixed(2)}B`;
 if(n>=1e6)return `${(n/1e6).toFixed(2)}M`;
 if(n>=1e3)return `${(n/1e3).toFixed(1)}K`;
 return Math.round(n).toLocaleString();
};
const timeLabel=(ts,intraday)=>{
 const d=new Date(ts);
 return intraday
  ? d.toLocaleTimeString([],{hour:'numeric',minute:'2-digit'})
  : d.toLocaleDateString([],{month:'short',day:'numeric'});
};
const fullTime=ts=>new Date(ts).toLocaleString([],{
 year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit'
});

export default function CandlestickChart({symbol}){
 const[view,setView]=useState(views[0]);
 const[data,setData]=useState(null);
 const[loading,setLoading]=useState(false);
 const[error,setError]=useState('');
 const[hover,setHover]=useState(null);

 const load=async()=>{
   if(!symbol)return;
   setLoading(true);setError('');
   try{setData(await api.stockHistory(symbol,view.range))}
   catch(e){setError(String(e))}
   finally{setLoading(false)}
 };

 useEffect(()=>{
   load();
   const t=setInterval(load,60000);
   return()=>clearInterval(t);
 },[symbol,view.range]);

 const bars=useMemo(()=>data?.bars||[],[data]);
 const clean=bars.filter(b=>[b.open,b.high,b.low,b.close].every(x=>Number.isFinite(Number(x))));
 const w=1040,h=430,left=58,right=74,top=22,priceBottom=300,volumeTop=322,volumeBottom=390;
 const plotW=w-left-right,priceH=priceBottom-top,volH=volumeBottom-volumeTop;
 const lows=clean.map(b=>Number(b.low)),highs=clean.map(b=>Number(b.high)),vols=clean.map(b=>Number(b.volume)||0);
 const min=lows.length?Math.min(...lows):0,max=highs.length?Math.max(...highs):1,span=(max-min)||1,maxVol=vols.length?Math.max(...vols):1;
 const step=clean.length?plotW/clean.length:1,bodyW=Math.max(1.2,Math.min(9,step*.62));
 const y=v=>top+(1-(Number(v)-min)/span)*priceH;
 const x=i=>left+step*i+step/2;
 const last=clean.at(-1),first=clean[0];
 const change=last&&first?Number(last.close)-Number(first.close):null;
 const changePct=last&&first&&Number(first.close)?change/Number(first.close)*100:null;
 const active=hover!=null?clean[hover]:last;
 const activeX=hover!=null?x(hover):null;
 const intraday=['1D','5D'].includes(view.range);

 const priceTicks=Array.from({length:5},(_,i)=>max-(span*i/4));
 const volTicks=[maxVol, maxVol/2, 0];
 const timeIdx=clean.length?Array.from(new Set([0,Math.floor((clean.length-1)*.25),Math.floor((clean.length-1)*.5),Math.floor((clean.length-1)*.75),clean.length-1])):[];

 const onMove=e=>{
   if(!clean.length)return;
   const r=e.currentTarget.getBoundingClientRect();
   const svgX=(e.clientX-r.left)/r.width*w;
   const idx=Math.max(0,Math.min(clean.length-1,Math.floor((svgX-left)/step)));
   setHover(idx);
 };

 return <section className="candleCard">
  <div className="chartToolbar">
   <div>
    <span className="eyebrow">PRICE + VOLUME</span>
    <div className="chartTitleLine"><h3>{symbol} {last?money(last.close):''}</h3>{data?.bars?.length>0&&<span className="intervalTag">{view.note}</span>}</div>
    {change!=null&&<p className={change>=0?'chartUp':'chartDown'}>{change>=0?'+':''}{change.toFixed(2)} ({changePct>=0?'+':''}{changePct.toFixed(2)}%)</p>}
   </div>
   <div className="chartActions"><RefreshClock seconds={60} label="Chart"/><div className="rangeTabs">{views.map(v=><button key={v.label} className={v.label===view.label?'active':''} onClick={()=>{setView(v);setHover(null)}}>{v.label}</button>)}</div></div>
  </div>

  {active&&<div className="ohlcStrip">
    <span><b>{fullTime(active.timestamp)}</b></span>
    <span>O <b>{money(active.open)}</b></span>
    <span>H <b>{money(active.high)}</b></span>
    <span>L <b>{money(active.low)}</b></span>
    <span>C <b>{money(active.close)}</b></span>
    <span>Vol <b>{compact(active.volume)}</b></span>
  </div>}

  {error&&<div className="notice">{error}</div>}
  {loading&&!clean.length?<div className="chartEmpty">Loading {symbol} history...</div>:!clean.length?<div className="chartEmpty">No chart history is available.</div>:<>
   <div className="candleWrap">
    <svg className="candleSvg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" onMouseMove={onMove} onMouseLeave={()=>setHover(null)}>
     {priceTicks.map((v,i)=><g key={`p${i}`}><line className="chartGrid" x1={left} x2={w-right} y1={y(v)} y2={y(v)}/><text className="axisText priceAxis" x={w-right+8} y={y(v)+4}>{Number(v).toFixed(2)}</text></g>)}
     {volTicks.map((v,i)=>{const yy=volumeTop+(i/2)*volH;return <text className="axisText volumeAxis" key={`v${i}`} x={6} y={yy+4}>{compact(v)}</text>})}
     <text className="axisTitle" x={8} y={volumeTop-7}>VOLUME</text>
     {clean.map((b,i)=>{
       const xx=x(i),o=y(b.open),c=y(b.close),hi=y(b.high),lo=y(b.low),up=Number(b.close)>=Number(b.open);
       const bodyTop=Math.min(o,c),bodyH=Math.max(1,Math.abs(c-o));
       const vh=(Number(b.volume)||0)/maxVol*volH;
       return <g key={i}>
        <line className={up?'wickUp':'wickDown'} x1={xx} x2={xx} y1={hi} y2={lo}/>
        <rect className={up?'candleUp':'candleDown'} x={xx-bodyW/2} y={bodyTop} width={bodyW} height={bodyH}/>
        <rect className={up?'volumeUp':'volumeDown'} x={xx-bodyW/2} y={volumeBottom-vh} width={bodyW} height={vh}/>
       </g>
     })}
     {timeIdx.map((i,k)=><g key={`t${i}`}><line className="timeTick" x1={x(i)} x2={x(i)} y1={volumeBottom+2} y2={volumeBottom+7}/><text className="axisText timeAxis" textAnchor={k===0?'start':k===timeIdx.length-1?'end':'middle'} x={x(i)} y={volumeBottom+22}>{timeLabel(clean[i].timestamp,intraday)}</text></g>)}
     {activeX!=null&&<><line className="crosshair" x1={activeX} x2={activeX} y1={top} y2={volumeBottom}/><circle className="crossDot" cx={activeX} cy={y(clean[hover].close)} r="3.5"/></>}
    </svg>
   </div>
   <div className="chartFoot"><span>{data?.provider} · research/display only</span><span>Last bar: {fullTime(last.timestamp)} · {clean.length} bars</span></div>
  </>}
 </section>
}
