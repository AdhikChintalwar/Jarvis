import React,{useState} from 'react';
import Dashboard from './pages/Dashboard';
import Ideas from './pages/Ideas';
import Research from './pages/Research';
import Portfolio from './pages/Portfolio';
import Alerts from './pages/Alerts';
import Production from './pages/Production';
import Backtests from './pages/Backtests';
import Automations from './pages/Automations';
import Markets from './pages/Markets';
import './styles/app.css';
import AskBaby from './components/AskBaby';

const mainNav=[
  {id:'home',label:'Home',desc:'Daily overview',icon:'⌂'},
  {id:'ideas',label:'Ideas',desc:'Stocks Baby found',icon:'✦'},
  {id:'portfolio',label:'Portfolio',desc:'Your investments',icon:'▣'},
  {id:'alerts',label:'Alerts',desc:'Important changes',icon:'!'},
];

const advancedNav=[
  {id:'research',label:'Stock Research',desc:'Open one stock deeply'},
  {id:'production',label:'System Checks',desc:'Technical gate details'},
  {id:'markets',label:'Raw Scanner',desc:'Scanner output'},
  {id:'backtests',label:'Backtests',desc:'Historical testing'},
  {id:'automations',label:'Automations',desc:'Schedules and jobs'},
];

export default function App(){
  const[page,setPage]=useState('home');
  const[symbol,setSymbol]=useState(()=>{
    try{return localStorage.getItem('baby:lastResearchSymbol')||'AAPL'}catch{return 'AAPL'}
  });
  const[advancedOpen,setAdvancedOpen]=useState(false);
  const[mobileOpen,setMobileOpen]=useState(false);
  const [askBabyOpen,setAskBabyOpen]=useState(false);

  const go=id=>{
    setPage(id);
    setMobileOpen(false);
  };

  const rememberResearchSymbol=s=>{
    const next=String(s||'').trim().toUpperCase();
    if(!next)return;
    setSymbol(next);
    try{localStorage.setItem('baby:lastResearchSymbol',next)}catch{}
  };

  const openResearch=s=>{
    if(s)rememberResearchSymbol(s);
    setPage('research');
    setMobileOpen(false);
  };

  const renderPage=()=>{
    switch(page){
      case 'home':return <Dashboard openResearch={openResearch} go={go}/>;
      case 'ideas':return <Ideas openResearch={openResearch}/>;
      case 'portfolio':return <Portfolio openResearch={openResearch}/>;
      case 'alerts':return <Alerts/>;
      case 'research':return <Research initialSymbol={symbol} onContext={ctx=>ctx?.symbol&&rememberResearchSymbol(ctx.symbol)}/>;
      case 'production':return <Production/>;
      case 'markets':return <Markets openResearch={openResearch}/>;
      case 'backtests':return <Backtests/>;
      case 'automations':return <Automations/>;
      default:return <Dashboard openResearch={openResearch} go={go}/>;
    }
  };

  return <div className="babyV14Shell">
    <aside className={`babyV14Sidebar ${mobileOpen?'mobileOpen':''}`}>
      <button className="babyV14Logo" onClick={()=>go('home')}>
        <span className="babyV14LogoMark">B</span>
        <span className="babyV14LogoCopy">
          <b>Baby</b>
          <small>Investment Research</small>
        </span>
      </button>

      <div className="babyV14NavLabel">MAIN</div>
      <nav className="babyV14Nav">
        {mainNav.map(n=><button
          key={n.id}
          className={`babyV14NavItem ${page===n.id?'active':''}`}
          onClick={()=>go(n.id)}
        >
          <span className="babyV14NavIcon">{n.icon}</span>
          <span className="babyV14NavCopy">
            <b>{n.label}</b>
            <small>{n.desc}</small>
          </span>
        </button>)}
      </nav>

      <button className="babyV14AdvancedToggle" onClick={()=>setAdvancedOpen(v=>!v)}>
        <span>ADVANCED</span>
        <b>{advancedOpen?'−':'+'}</b>
      </button>

      {advancedOpen&&<nav className="babyV14AdvancedNav">
        {advancedNav.map(n=><button
          key={n.id}
          className={`babyV14AdvancedItem ${page===n.id?'active':''}`}
          onClick={()=>go(n.id)}
        >
          <b>{n.label}</b>
          <small>{n.desc}</small>
        </button>)}
      </nav>}

      <div className="babyV14SidebarHelp">
        <b>Where should I start?</b>
        <p>Open <strong>Home</strong> first. Use <strong>Ideas</strong> to see stocks Baby found.</p>
      </div>
    </aside>

    <div className="babyV14Main">
      <header className="babyV14MobileHeader">
        <button className="babyV14MenuBtn" onClick={()=>setMobileOpen(v=>!v)}>☰</button>
        <div><b>Baby</b><small>{mainNav.find(x=>x.id===page)?.label||'Research'}</small></div>
      </header>
      <div className="babyV14Content">{renderPage()}</div>
    </div>

    {mobileOpen&&<button className="babyV14Backdrop" aria-label="Close menu" onClick={()=>setMobileOpen(false)}/>}

    <button className="babyAskLauncher" onClick={()=>setAskBabyOpen(true)}>
      <span className="babyAskSpark">✦</span>
      <span className="babyAskLauncherCopy">
        <b>Ask Baby</b>
        <small>Ask about anything here</small>
      </span>
    </button>

    {askBabyOpen&&<>
      <button className="babyAskBackdrop" aria-label="Close Ask Baby" onClick={()=>setAskBabyOpen(false)}/>
      <aside className="babyAskDrawer">
        <div className="babyAskHeader">
          <div>
            <span className="pageKicker">BABY ASSISTANT</span>
            <h2>Ask Baby</h2>
            <p>Ask about a stock, your portfolio, an alert, or Baby's research.</p>
          </div>
          <button className="babyAskClose" onClick={()=>setAskBabyOpen(false)}>×</button>
        </div>
        <div className="babyAskContext">
          <span>Current context</span>
          <b>{page==='research'?`Stock Research · ${symbol}`:page}</b>
        </div>
        <div className="babyAskBody">
          <AskBaby symbol={page==='research'?symbol:undefined}/>
        </div>
      </aside>
    </>}
  </div>
}
