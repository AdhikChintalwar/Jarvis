import React,{useEffect,useState} from 'react';
import {api} from '../lib/api';
import PortfolioPerformanceChart from '../components/PortfolioPerformanceChart';

const money=x=>x==null?'UNKNOWN':Number(x).toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:2});

export default function Portfolio(){
 const[alpaca,setAlpaca]=useState(null);
 const[aPos,setAPos]=useState([]);
 const[aOrd,setAOrd]=useState([]);
 const[form,setForm]=useState({symbol:'AAPL',side:'BUY',quantity:'1',order_type:'MARKET',limit_price:''});
 const[msg,setMsg]=useState('');
 const[confirm,setConfirm]=useState('');

 const loadAlpaca=async()=>{
   const s=await api.alpacaStatus();
   setAlpaca(s);
   if(s.connected){
     setAPos((await api.alpacaPositions()).positions||[]);
     setAOrd((await api.alpacaOrders()).orders||[]);
   }else{
     setAPos([]);
     setAOrd([]);
   }
 };

 useEffect(()=>{loadAlpaca().catch(e=>setMsg(String(e)))},[]);

 async function submitAlpaca(e){
   e?.preventDefault();
   setMsg('');
   try{
     const r=await api.alpacaOrder({
       ...form,
       symbol:String(form.symbol||'').toUpperCase(),
       quantity:Number(form.quantity),
       limit_price:form.order_type==='LIMIT'?Number(form.limit_price):null,
       confirmation:confirm
     });
     setMsg(`ALPACA PAPER order submitted: ${r.order.id}. Simulated money only.`);
     setConfirm('');
     await loadAlpaca();
   }catch(e){setMsg(String(e))}
 }

 async function cancelAlpaca(id){
   try{
     await api.alpacaCancel(id);
     setMsg(`Alpaca PAPER cancel requested: ${id}`);
     await loadAlpaca();
   }catch(e){setMsg(String(e))}
 }

 return <main className="screenPage portfolioPage">
   <section className="pageExplain compactExplain">
     <div>
       <span className="pageKicker">PORTFOLIO</span>
       <h1>Your investments and Baby monitoring</h1>
       <p>Your connected Alpaca Paper account is the portfolio shown here. Local SQLite simulation is hidden from the normal interface.</p>
     </div>
   </section>

   <div className="plainHelpBox">
     <b>Tips &amp; info</b>
     <span><strong>Paper account</strong> = simulated Alpaca money, not real money.</span>
     <span><strong>Open positions</strong> = positions currently held in Alpaca Paper.</span>
     <span><strong>Monitoring</strong> starts automatically when Baby sees a held position.</span>
   </div>

   <PortfolioPerformanceChart/>

   <div className="authority portfolioAuthority">
     <b>REAL MONEY DISABLED</b>
     <span>Alpaca is PAPER-only. Ask Baby cannot execute orders. Research-driven submission still requires explicit confirmation.</span>
   </div>

   {msg&&<div className="notice">{msg}</div>}

   <section className="brokerZone alpacaZone">
     <div className="brokerZoneTitle">
       <div>
         <span className="eyebrow">CONNECTED BROKER</span>
         <h2>ALPACA PAPER</h2>
         <p>Baby's cloud paper-trading account. No real funds are used.</p>
       </div>
       <div className={`badge ${alpaca?.connected?'status-pass':'status-review'}`}>
         {alpaca?.connected?'CONNECTED · PAPER':alpaca?.configured?'CONNECTION ERROR':'NOT CONFIGURED'}
       </div>
     </div>

     {alpaca&&<div className="panelGrid">
       <Card n="Environment" v={alpaca.environment}/>
       <Card n="Paper Equity" v={money(alpaca.equity)}/>
       <Card n="Paper Cash" v={money(alpaca.cash)}/>
       <Card n="Paper Buying Power" v={money(alpaca.buying_power)}/>
       <Card n="Trading Blocked" v={String(alpaca.trading_blocked??'UNKNOWN')}/>
       <Card n="Account" v={alpaca.account_number_masked||'UNKNOWN'}/>
     </div>}

     {alpaca?.error&&<div className="notice">{alpaca.error}</div>}

     {alpaca?.connected&&<>
       <PortfolioTable title="Open positions" rows={aPos} emptyTitle="No paper positions yet" emptyText="When an Alpaca Paper position is opened, it will appear here and Baby can attach its persistent position monitor."/>
       <PortfolioTable title="Open / recent paper orders" rows={aOrd} emptyTitle="No paper orders yet" emptyText="Research-driven Alpaca Paper orders will appear here after explicit confirmation." action={r=>r.id?<button onClick={()=>cancelAlpaca(r.id)}>CANCEL PAPER ORDER</button>:null}/>

       <details className="advancedBrokerTools">
         <summary>Advanced · Manual Alpaca Paper test ticket</summary>
         <div className="manualBrokerWarning neutralBrokerInfo">
           <b>TESTING TOOL</b>
           <span>This bypasses Baby's research selection. Use Research → Trade Plan for the normal Baby workflow.</span>
         </div>
         <form className="paperForm manualPaperForm" onSubmit={submitAlpaca}>
           <input value={form.symbol} onChange={e=>setForm({...form,symbol:e.target.value.toUpperCase()})} placeholder="Ticker"/>
           <select value={form.side} onChange={e=>setForm({...form,side:e.target.value})}><option>BUY</option><option>SELL</option></select>
           <input type="number" min="0.000001" step="any" value={form.quantity} onChange={e=>setForm({...form,quantity:e.target.value})} placeholder="Quantity"/>
           <select value={form.order_type} onChange={e=>setForm({...form,order_type:e.target.value})}><option>MARKET</option><option>LIMIT</option></select>
           {form.order_type==='LIMIT'&&<input type="number" step="any" placeholder="Limit price" value={form.limit_price} onChange={e=>setForm({...form,limit_price:e.target.value})}/>}
           <input value={confirm} onChange={e=>setConfirm(e.target.value)} placeholder="Type: EXECUTE ALPACA PAPER"/>
           <button disabled={confirm!=='EXECUTE ALPACA PAPER'}>SUBMIT MANUAL PAPER TEST</button>
         </form>
       </details>
     </>}
   </section>
 </main>
}

function Card({n,v}){return <div className="metric"><span>{n}</span><strong>{v}</strong></div>}

function PortfolioTable({title,rows=[],action,emptyTitle,emptyText}){
 return <section className="stage brokerTable">
   <h2>{title}</h2>
   {!rows.length
     ?<div className="portfolioEmptyState"><strong>{emptyTitle}</strong><span>{emptyText}</span></div>
     :<div className="tableWrap"><table><thead><tr>{Object.keys(rows[0]).map(k=><th key={k}>{k}</th>)}{action&&<th>action</th>}</tr></thead><tbody>{rows.slice(0,100).map((r,i)=><tr key={r.id||r.symbol||i}>{Object.values(r).map((v,j)=><td key={j}>{v==null?'UNKNOWN':String(v)}</td>)}{action&&<td>{action(r)}</td>}</tr>)}</tbody></table></div>}
 </section>
}
