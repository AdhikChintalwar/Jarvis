import React, { useEffect, useState } from 'react';
import Dashboard from './pages/Dashboard';
import Ideas from './pages/Ideas';
import Research from './pages/Research';
import Portfolio from './pages/Portfolio';
import Alerts from './pages/Alerts';
import Backtests from './pages/Backtests';
import Automations from './pages/Automations';
import Markets from './pages/Markets';
import Settings from './pages/Settings';
import Documentation from './pages/Documentation';
import About from './pages/About';
import AskBaby from './components/AskBaby';
import BabyLogo from './components/BabyLogo';
import SidebarClock from './components/SidebarClock';
import {
  Home, Sparkles, BriefcaseBusiness, Bell, Search,
  Settings as SettingsIcon, BookOpen, Info, Wrench,
  Activity, FlaskConical, Workflow, ChevronDown, ChevronRight,
  Menu, X
} from 'lucide-react';
import './styles/app.css';

const pref = (key, fallback) => { try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v) } catch { return fallback } };

const mainNav = [
  { id: 'home', label: 'Home', desc: 'Daily overview', icon: Home },
  { id: 'ideas', label: 'Ideas', desc: 'Stocks Baby found', icon: Sparkles },
  { id: 'portfolio', label: 'Portfolio', desc: 'Positions & monitored setups', icon: BriefcaseBusiness },
  { id: 'alerts', label: 'Alerts', desc: 'Important changes', icon: Bell },
];

const researchNav = [
  { id: 'research', label: 'Stock Research', desc: 'Open one stock deeply', icon: Search },
];

const systemNav = [
  { id: 'settings', label: 'Settings & Status', desc: 'Health, safety & preferences', icon: SettingsIcon },
];

const learnNav = [
  { id: 'docs', label: 'Documentation', desc: 'How Baby works', icon: BookOpen },
  { id: 'about', label: 'About Baby', desc: 'Purpose & boundaries', icon: Info },
];

const developerNav = [
  { id: 'markets', label: 'Raw Scanner', desc: 'Scanner output', icon: Activity },
  { id: 'backtests', label: 'Backtests', desc: 'Historical validation', icon: FlaskConical },
  { id: 'automations', label: 'Automations', desc: 'Schedules & jobs', icon: Workflow },
];

function NavItem({ item, page, go }) {
  const Icon = item.icon;
  return <button className={`babyV15NavItem ${page === item.id ? 'active' : ''}`} onClick={() => go(item.id)}>
    <span className="babyV15NavIcon"><Icon size={17} /></span>
    <span className="babyV15NavCopy"><b>{item.label}</b><small>{item.desc}</small></span>
  </button>
}

export default function App() {
  const [page, setPage] = useState('home');
  const [symbol, setSymbol] = useState('AAPL');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [askBabyOpen, setAskBabyOpen] = useState(false);
  const [devOpen, setDevOpen] = useState(false);
  const [showDev, setShowDev] = useState(() => pref('baby_show_developer_tools', false));
  const [clockSeconds, setClockSeconds] = useState(() => pref('baby_clock_seconds', false));

  useEffect(() => {
    const refreshPrefs = () => {
      setShowDev(pref('baby_show_developer_tools', false));
      setClockSeconds(pref('baby_clock_seconds', false));
    };
    window.addEventListener('baby-preferences-changed', refreshPrefs);
    window.addEventListener('storage', refreshPrefs);
    return () => { window.removeEventListener('baby-preferences-changed', refreshPrefs); window.removeEventListener('storage', refreshPrefs) }
  }, []);

  const go = id => { setPage(id); setMobileOpen(false) };
  const openResearch = s => { if (s) setSymbol(String(s).toUpperCase()); setPage('research'); setMobileOpen(false) };

  const renderPage = () => {
    switch (page) {
      case 'home': return <Dashboard openResearch={openResearch} go={go} />;
      case 'ideas': return <Ideas openResearch={openResearch} />;
      case 'portfolio': return <Portfolio openResearch={openResearch} />;
      case 'alerts': return <Alerts />;
      case 'research': return <Research initialSymbol={symbol} />;
      case 'settings': return <Settings />;
      case 'docs': return <Documentation />;
      case 'about': return <About />;
      case 'markets': return <Markets openResearch={openResearch} />;
      case 'backtests': return <Backtests />;
      case 'automations': return <Automations />;
      default: return <Dashboard openResearch={openResearch} go={go} />;
    }
  };

  const section = (label, items) => <>
    <div className="babyV15NavLabel">{label}</div>
    <nav className="babyV15NavGroup">{items.map(item => <NavItem key={item.id} item={item} page={page} go={go} />)}</nav>
  </>;

  const pageLabel = [...mainNav, ...researchNav, ...systemNav, ...learnNav, ...developerNav].find(x => x.id === page)?.label || 'Baby';

  return <div className="babyV15Shell">
    <aside className={`babyV15Sidebar ${mobileOpen ? 'mobileOpen' : ''}`}>
      <button className="babyV15Brand" onClick={() => go('home')}>
        <BabyLogo compact />
      </button>

      <SidebarClock showSeconds={clockSeconds} />

      <div className="babyV15SidebarScroll">
        {section('MAIN', mainNav)}
        {section('RESEARCH', researchNav)}
        {section('SYSTEM', systemNav)}
        {section('LEARN', learnNav)}

        {showDev && <>
          <button className="babyV15DeveloperToggle" onClick={() => setDevOpen(v => !v)}>
            <span><Wrench size={15} />Developer Tools</span>
            {devOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          </button>
          {devOpen && <nav className="babyV15DeveloperNav">
            {developerNav.map(item => <NavItem key={item.id} item={item} page={page} go={go} />)}
          </nav>}
        </>}
      </div>

      <div className="babyV15SidebarFooter">
        <span><b>Baby V15.3</b><small>Research · Monitoring · PAPER</small></span>
        <button onClick={() => go('docs')}>What's new</button>
      </div>
    </aside>

    <div className="babyV15Main">
      <header className="babyV15MobileHeader">
        <button onClick={() => setMobileOpen(v => !v)}>{mobileOpen ? <X size={20} /> : <Menu size={20} />}</button>
        <BabyLogo compact />
        <div><small>{pageLabel}</small></div>
      </header>
      <div className="babyV15Content">{renderPage()}</div>
    </div>

    {mobileOpen && <button className="babyV15Backdrop" aria-label="Close menu" onClick={() => setMobileOpen(false)} />}

    <button className="babyAskLauncher" onClick={() => setAskBabyOpen(true)}>
      <span className="babyAskSpark">✦</span>
      <span className="babyAskLauncherCopy"><b>Ask Baby</b><small>Ask about anything here</small></span>
    </button>

    {askBabyOpen && <>
      <button className="babyAskBackdrop" aria-label="Close Ask Baby" onClick={() => setAskBabyOpen(false)} />
      <aside className="babyAskDrawer">
        <div className="babyAskHeader">
          <div><span className="pageKicker">BABY ASSISTANT</span><h2>Ask Baby</h2><p>Ask about a stock, your portfolio, an alert, or Baby's research.</p></div>
          <button className="babyAskClose" onClick={() => setAskBabyOpen(false)}>×</button>
        </div>
        <div className="babyAskContext"><span>Current context</span><b>{page === 'research' ? `Stock Research · ${symbol}` : pageLabel}</b></div>
        <div className="babyAskBody"><AskBaby symbol={page === 'research' ? symbol : undefined} /></div>
      </aside>
    </>}
  </div>
}
