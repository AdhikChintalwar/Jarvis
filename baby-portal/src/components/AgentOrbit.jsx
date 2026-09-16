export default function AgentOrbit({ activeAgent }) {
    const agents = [
      { name: "desktop", label: "Desktop", className: "node-left" },
      { name: "browser", label: "Browser", className: "node-top" },
      { name: "coding", label: "Coding", className: "node-right" },
      { name: "memory", label: "Memory", className: "node-bottom" },
    ];
  
    return (
      <div className="orbit-layer">
        <div className="beam beam-horizontal" />
        <div className="beam beam-vertical" />
  
        {agents.map((agent) => (
          <div
            key={agent.name}
            className={`orbit-node ${agent.className} ${
              activeAgent === agent.name ? "node-active" : ""
            }`}
          >
            {agent.label}
          </div>
        ))}
      </div>
    );
  }