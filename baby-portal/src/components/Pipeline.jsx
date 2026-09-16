const stages = ["Voice", "Split", "Router", "Agent", "Tool", "MCP"];

export default function Pipeline({ active }) {
  return (
    <div className="pipeline">
      <h2>Pipeline</h2>

      {stages.map((stage) => (
        <div key={stage} className="pipeline-stage">
          {stage}
        </div>
      ))}
    </div>
  );
}