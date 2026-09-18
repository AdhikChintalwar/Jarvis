import React from 'react';
export default function MiniLineChart({points=[],height=220,label='Series'}){
 const vals=(points||[]).map(x=>Number(x.value??x.close??x.equity)).filter(Number.isFinite);
 if(vals.length<2)return <div className="chartEmpty">Not enough history for chart.</div>;
 const w=900,h=height,p=18,min=Math.min(...vals),max=Math.max(...vals),span=(max-min)||1;
 const path=vals.map((v,i)=>{const x=p+(i/(vals.length-1))*(w-2*p);const y=p+(1-(v-min)/span)*(h-2*p);return `${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`}).join(' ');
 return <div className="miniChart"><div className="chartHead"><span>{label}</span><strong>{vals.at(-1).toLocaleString(undefined,{maximumFractionDigits:2})}</strong></div><svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"><path className="chartGrid" d={`M${p},${h/2} L${w-p},${h/2}`}/><path className="chartLine" d={path}/></svg><div className="chartRange"><span>{min.toFixed(2)}</span><span>{max.toFixed(2)}</span></div></div>
}
