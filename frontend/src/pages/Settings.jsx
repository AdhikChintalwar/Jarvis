import React,{useEffect,useState} from 'react';

const getPref=(key,fallback)=>{
  try{const v=localStorage.getItem(key);return v==null?fallback:JSON.parse(v)}catch{return fallback}
};
const setPref=(key,value)=>{try{localStorage.setItem(key,JSON.stringify(value));window.dispatchEvent(new Event('baby-preferences-changed'))}catch{}};

function HealthRow({label,value,state='neutral',detail}){
  return <div className="settingsHealthRow">
    <div><b>{label}</b>{detail&&<small>{detail}</small>}</div>
    <span className={`settingsState ${state}`}>{value}</span>
  </div>
}

function SwitchRow({label,detail,value,onChange,locked=false}){
  return <div className="settingsSwitchRow">
    <div><b>{label}</b><small>{detail}</small></div>
    <button
      className={`settingsSwitch ${value?'on':''} ${locked?'locked':''}`}
      disabled={locked}
      onClick={()=>!locked&&onChange(!value)}
      aria-pressed={value}
    ><span/></button>
  </div>
}

export default function Settings(){
  const[broker,setBroker]=useState(null);
  const[scheduler,setScheduler]=useState(null);
  const[email,setEmail]=useState(null);
  const[monitored,setMonitored]=useState(null);
  const[events,setEvents]=useState([]);
  const[autoRefresh,setAutoRefresh]=useState(()=>getPref('baby_auto_refresh',true));
  const[showDev,setShowDev]=useState(()=>getPref('baby_show_developer_tools',false));
  const[showSeconds,setShowSeconds]=useState(()=>getPref('baby_clock_seconds',false));
  const[error,setError]=useState('');

  const load=async()=>{
    setError('');
    try{
      const safe=async url=>{const r=await fetch(url);if(!r.ok)throw new Error(`${url}: ${r.status}`);return r.json()};
      const results=await Promise.allSettled([
        safe('/api/broker/alpaca/status'),
        safe('/api/scheduler/status'),
        safe('/api/email/status'),
        safe('/api/portfolio/monitored-setups'),
        safe('/api/monitor/events?limit=6'),
      ]);
      const [b,s,e,m,ev]=results;
      if(b.status==='fulfilled')setBroker(b.value);
      if(s.status==='fulfilled')setScheduler(s.value);
      if(e.status==='fulfilled')setEmail(e.value);
      if(m.status==='fulfilled')setMonitored(m.value);
      if(ev.status==='fulfilled')setEvents(ev.value.events||[]);
      if(results.some(x=>x.status==='rejected'))setError('Some system-status sources are unavailable. Working sections are still shown.');
    }catch(err){setError(String(err))}
  };

  useEffect(()=>{load()},[]);
  useEffect(()=>{
    if(!autoRefresh)return;
    const t=setInterval(load,30000);
    return()=>clearInterval(t);
  },[autoRefresh]);

  const pref=(key,setter)=>(v)=>{setter(v);setPref(key,v)};

  const lastScan=scheduler?.last_scan_finished||scheduler?.last_scan_started;
  const lastReval=scheduler?.last_revalidation_finished||scheduler?.last_revalidation_started;
  const brokerHealthy=!!broker?.connected;
  const emailHealthy=email?.status==='READY'&&email?.smtp?.configured;
  const schedulerHealthy=!!scheduler?.thread_alive;

  return <main className="screenPage settingsPage">
    <section className="pageExplain compactExplain">
      <div>
        <span className="pageKicker">SETTINGS & STATUS</span>
        <h1>Baby system controls</h1>
        <p>Change safe interface preferences and see the health of research, monitoring, alerts and the Alpaca PAPER connection.</p>
      </div>
      <button className="settingsRefresh" onClick={load}>Refresh status</button>
    </section>

    {error&&<div className="notice">{error}</div>}

    <div className="settingsGrid">
      <section className="settingsPanel">
        <div className="settingsPanelHead"><div><span className="eyebrow">SYSTEM ACTIVITY</span><h2>Is Baby working?</h2></div></div>
        <HealthRow label="Research scheduler" value={schedulerHealthy?'RUNNING':'NOT CONFIRMED'} state={schedulerHealthy?'good':'review'} detail={scheduler?.timezone||'America/New_York'}/>
        <HealthRow label="Last scan" value={lastScan?new Date(lastScan).toLocaleString():'Not run since restart'} />
        <HealthRow label="Last revalidation" value={lastReval?new Date(lastReval).toLocaleString():'Not run since restart'} />
        <HealthRow label="Monitored setups" value={String(monitored?.setups?.length??scheduler?.monitored_setup_count??0)} />
        <HealthRow label="Currently checking" value={scheduler?.current_symbol||'NONE'} />
      </section>

      <section className="settingsPanel">
        <div className="settingsPanelHead"><div><span className="eyebrow">DATA HEALTH</span><h2>Connections</h2></div></div>
        <HealthRow label="Alpaca PAPER" value={brokerHealthy?'CONNECTED':'NOT CONNECTED'} state={brokerHealthy?'good':'review'} detail={broker?.environment||'PAPER'}/>
        <HealthRow label="Email alerts" value={emailHealthy?'READY':'NOT READY'} state={emailHealthy?'good':'review'} detail={email?.smtp?.host||'SMTP status unavailable'}/>
        <HealthRow label="Scheduler" value={schedulerHealthy?'HEALTHY':'CHECK'} state={schedulerHealthy?'good':'review'}/>
        <HealthRow label="Monitoring API" value={monitored?.status==='READY'?'HEALTHY':'CHECK'} state={monitored?.status==='READY'?'good':'review'}/>
      </section>

      <section className="settingsPanel">
        <div className="settingsPanelHead"><div><span className="eyebrow">INTERFACE</span><h2>Your Baby UI</h2></div></div>
        <SwitchRow label="Auto-refresh system status" detail="Refresh this page every 30 seconds." value={autoRefresh} onChange={pref('baby_auto_refresh',setAutoRefresh)}/>
        <SwitchRow label="Show Developer Tools" detail="Shows Raw Scanner, Backtests and Automations in the sidebar." value={showDev} onChange={pref('baby_show_developer_tools',setShowDev)}/>
        <SwitchRow label="Show clock seconds" detail="Display seconds in the sidebar Eastern Time clock." value={showSeconds} onChange={pref('baby_clock_seconds',setShowSeconds)}/>
      </section>

      <section className="settingsPanel safetyPanel">
        <div className="settingsPanelHead"><div><span className="eyebrow">SAFETY</span><h2>Locked controls</h2></div></div>
        <SwitchRow label="Real-money execution" detail="Locked by Baby's production safety boundary." value={false} locked/>
        <SwitchRow label="AI execution authority" detail="AI cannot submit broker orders." value={false} locked/>
        <SwitchRow label="Automatic broker orders" detail="A setup-ready alert still requires human review and explicit PAPER confirmation." value={false} locked/>
        <div className="settingsSafetyNote">These controls are intentionally not normal switches. V15.3 does not add live-money execution or automatic trading.</div>
      </section>
    </div>

    <section className="settingsPanel settingsWide">
      <div className="settingsPanelHead"><div><span className="eyebrow">RECENT MONITORING EVENTS</span><h2>Latest system activity</h2></div></div>
      {!events.length?<div className="panelEmpty">No recent monitoring events returned.</div>:
      <div className="settingsEventList">{events.map((e,i)=><div className="settingsEvent" key={e.id||i}>
        <div><b>{e.symbol||'SYSTEM'} · {e.event_type||e.status||'EVENT'}</b><span>{e.message||e.reason||''}</span></div>
        <time>{e.created_at||e.at||e.timestamp||''}</time>
      </div>)}</div>}
    </section>
  </main>
}
