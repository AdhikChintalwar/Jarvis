import React,{useEffect,useState} from 'react';import {api} from '../lib/api';
export default function Alerts(){const [a,setA]=useState([]);useEffect(()=>{api.alerts().then(setA)},[]);return <main>
<section className="pageExplain compactExplain">
  <div>
    <span className="pageKicker">ALERTS</span>
    <h1>Important changes Baby wants you to see</h1>
    <p>This page should answer one question: has anything changed enough that you should review it?</p>
  </div>
</section>
<div className="plainHelpBox">
  <b>Use this page for</b>
  <span>Position invalidation, target events, setup changes, research changes, or data problems.</span>
  <span>You do not need to act on every alert. Open the related stock to understand why it appeared.</span>
</div>
<header className="topbar"><div><div className="brand">BABY <span>ALERT CENTER</span></div><p>Deduplicated market, research, SEC, setup and risk events.</p></div></header><div className="alertList">{a.map(x=><div className={`alert severity-${x.severity?.toLowerCase()}`} key={x.id}><small>{x.severity} · {x.symbol||'SYSTEM'} · {new Date(x.created_at).toLocaleString()}</small><h3>{x.title}</h3><p>{x.message}</p></div>)}{!a.length&&<div className="notice">No alerts yet.</div>}</div></main>}
