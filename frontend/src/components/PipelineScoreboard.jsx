import React from 'react';

function metricValue(m){
  const v=m?.value??m?.display_value??m?.score;
  if(v==null)return '--';
  return typeof v==='number'?Number(v).toFixed(1):String(v);
}

export default function PipelineScoreboard({report}){
  const stages=report?.stages||[];
  if(!stages.length)return null;
  return <section className="pipelineBoard">
    <div className="pipelineBoardHead">
      <div><span className="eyebrow">RESEARCH PIPELINE</span><h3>How Baby reached the research state</h3></div>
      <span className="researchBoundary">Research score != buy signal</span>
    </div>
    <div className="pipelineStageGrid">
      {stages.map((s,i)=>{
        const score=(s.metrics||[]).find(m=>/score/i.test(m.key||m.label||''));
        return <div className={`pipeStage status-${String(s.status||'').toLowerCase()}`} key={s.id||i}>
          <small>{String(i+1).padStart(2,'0')}</small>
          <b>{s.label||s.id}</b>
          <strong>{score?metricValue(score):s.status||'--'}</strong>
          <span>{s.summary||''}</span>
        </div>
      })}
    </div>
  </section>
}
