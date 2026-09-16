import {
  Monitor,
  Globe,
  Code2,
  Brain,
  Map,
  Mic,
  Eye,
  Wrench,
  Leaf,
  Activity,
  Cpu,
  Heart,
  Home,
  Sparkles,
  Database,
  Wifi,
  Settings,
} from "lucide-react";

import BabyThreeMind from "./components/BabyThreeMind";
import EventTimeline from "./components/EventTimeline";
import BackgroundParticles from "./components/BackgroundParticles";
import useEvents from "./hooks/useEvents";

const agents = [
  { id: "desktop", label: "Desktop", role: "Apps, files, system control", Icon: Monitor },
  { id: "browser", label: "Browser", role: "Search, websites, YouTube", Icon: Globe },
  { id: "coding", label: "Coding", role: "Debugging, code help", Icon: Code2 },
  { id: "memory", label: "Memory", role: "Preferences, recall, context", Icon: Brain },
  { id: "planner", label: "Planner", role: "Multi-step reasoning", Icon: Map },
];

const capabilities = [
  { label: "Voice", sub: "Listening", Icon: Mic },
  { label: "Vision", sub: "Watching", Icon: Eye },
  { label: "Memory", sub: "Recollecting", Icon: Brain },
  { label: "Reasoning", sub: "Thinking", Icon: Sparkles },
  { label: "Tools", sub: "Using", Icon: Wrench },
  { label: "Learning", sub: "Growing", Icon: Leaf },
];

export default function App() {
  const { events, activeAgent, status, runtime } = useEvents();

  return (
    <div className="app-shell">
      <BackgroundParticles />

      <header className="top-bar">
        <div className="brand">
          <h1>BABY</h1>
          <p>GROWING DIGITAL MIND</p>
        </div>

        <div className="stat-strip">
          <div className="stat-card"><Home size={18} /><span>Age</span><strong>14 days</strong></div>
          <div className="stat-card"><Wrench size={18} /><span>Skills</span><strong>17</strong></div>
          <div className="stat-card"><Sparkles size={18} /><span>Neurons</span><strong>{events.length + 1248}</strong></div>
          <div className="stat-card"><Database size={18} /><span>Memories</span><strong>326</strong></div>
          <div className="stat-card"><Activity size={18} /><span>Status</span><strong>{status}</strong></div>
        </div>

        <div className="connection-card">
          <Wifi size={28} />
          <div>
            <span>Backend</span>
            <strong>{runtime.backend} ●</strong>
          </div>
          <Settings size={20} />
        </div>
      </header>

      <main className="dashboard-grid">
        <aside className="left-stack">
          <section className="panel event-panel">
            <EventTimeline events={events} />
          </section>

          <section className="panel compact-panel">
            <h2>System Health</h2>
            <div className="runtime-box">
              <div><span>Wake</span><strong>{runtime.wake}</strong></div>
              <div><span>ASR</span><strong>{runtime.asr}</strong></div>
              <div><span>Agent</span><strong>{runtime.activeAgent || "None"}</strong></div>
              <div><span>Tool</span><strong>{runtime.activeTool || "None"}</strong></div>
            </div>

            <div className="last-heard">
              <span>Last Heard</span>
              <strong>{runtime.lastHeard || "Waiting..."}</strong>
            </div>
            {[
              ["CPU", "23"],
              ["Memory", "41"],
              ["Learning", "87"],
              ["Neurons", "62"],
              ["Energy", "93"],
            ].map(([label, value]) => (

              <div className="health-row" key={label}>
                <span>{label}</span>
                <div className="health-bar"><div style={{ width: `${value}%` }} /></div>
                <strong>{value}%</strong>
              </div>
            ))}
          </section>

          <section className="panel compact-panel">
            <h2>Baby Stats</h2>
            <div className="mini-stats">
              <div><Activity size={18} /><strong>24</strong><span>Tasks</span></div>
              <div><Heart size={18} /><strong>96%</strong><span>Success</span></div>
              <div><Leaf size={18} /><strong>5</strong><span>Learned</span></div>
            </div>
          </section>
        </aside>

        <section className="center-world">
          <div className="mind-title">
            <h2>BABY'S MIND</h2>
            <p>CONSCIOUSNESS SPACE</p>
          </div>

          <BabyThreeMind status={status} activeAgent={activeAgent} />

          <div className="objective-card">
            <div>
              <span>Current Objective</span>
              <strong>{events.at(-1)?.data?.target || "Standing by"}</strong>
            </div>
            <div>
              <span>Active Agent</span>
              <strong>{activeAgent || "None"}</strong>
            </div>
            <div>
              <span>Progress</span>
              <strong>100%</strong>
            </div>
          </div>

          <div className="voice-card">
            <div className="baby-face">☺</div>
            <div>
              <h3>Listening...</h3>
              <p>How can I help you today?</p>
            </div>
            <div className="wave-line" />
            <div className="mic-orb"><Mic size={28} /></div>
          </div>
        </section>

        <aside className="right-stack">
          <section className="panel agent-panel">
            <h2>Agent Network</h2>
            <div className="agent-list">
              {agents.map(({ id, label, role, Icon }) => (
                <div key={id} className={`agent-card ${activeAgent === id ? "active" : ""}`}>
                  <div className="agent-icon"><Icon size={22} /></div>
                  <div>
                    <strong>{label}</strong>
                    <small>{role}</small>
                  </div>
                  <span>{activeAgent === id ? "Active" : "Idle"} ●</span>
                </div>
              ))}
            </div>
          </section>
          <section className="panel activity-panel">
            <h2>Live Activity</h2>

            <div className="activity-row">
              <span className={`dot ${runtime.wake === "Listening" ? "live" : ""}`} />
              <div>
                <strong>Wake Engine</strong>
                <small>{runtime.wake}</small>
              </div>
            </div>

            <div className="activity-row">
              <span className={`dot ${runtime.asr === "Listening" ? "live" : ""}`} />
              <div>
                <strong>Speech Recognition</strong>
                <small>{runtime.asr}</small>
              </div>
            </div>

            <div className="activity-row">
              <span className={`dot ${runtime.activeAgent ? "live" : ""}`} />
              <div>
                <strong>Agent</strong>
                <small>{runtime.activeAgent || "Waiting"}</small>
              </div>
            </div>

            <div className="activity-row">
              <span className={`dot ${runtime.activeTool ? "live" : ""}`} />
              <div>
                <strong>Tool</strong>
                <small>{runtime.activeTool || "Idle"}</small>
              </div>
            </div>
          </section>

          <section className="panel capability-panel">
            <h2>Capabilities</h2>
            <div className="capability-grid">
              {capabilities.map(({ label, sub, Icon }) => (
                <div className="capability-card" key={label}>
                  <Icon size={28} />
                  <strong>{label}</strong>
                  <span>{sub}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel energy-panel">
            <h2>Energy Flow <span>● Live</span></h2>
            <div className="energy-wave" />
            <p>Real-time neural activity</p>
          </section>
        </aside>
      </main>
    </div>
  );
}