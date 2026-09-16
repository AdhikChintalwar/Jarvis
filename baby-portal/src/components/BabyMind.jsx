import { motion } from "framer-motion";

const nodes = [
  { name: "desktop", x: -260, y: 0 },
  { name: "browser", x: 0, y: -230 },
  { name: "coding", x: 260, y: 0 },
  { name: "memory", x: 0, y: 230 },
  { name: "planner", x: -185, y: -165 },
];

const memoryNeurons = Array.from({ length: 18 }, (_, i) => {
  const angle = (i / 18) * Math.PI * 2;
  const radius = 145 + (i % 3) * 24;

  return {
    id: i,
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
    delay: i * 0.12,
  };
});

export default function BabyMind({ status, activeAgent }) {
  return (
    <div className={`baby-mind ${status}`}>
      {nodes.map((node) => (
        <div
          key={`line-${node.name}`}
          className={`mind-line ${activeAgent === node.name ? "active" : ""}`}
          style={{
            width: `${Math.sqrt(node.x * node.x + node.y * node.y)}px`,
            transform: `rotate(${Math.atan2(node.y, node.x)}rad)`,
          }}
        />
      ))}

      {memoryNeurons.map((n) => (
        <motion.div
          key={n.id}
          className="memory-neuron"
          style={{
            left: `calc(50% + ${n.x}px)`,
            top: `calc(50% + ${n.y}px)`,
          }}
          animate={{
            opacity: [0.25, 1, 0.25],
            scale: [0.8, 1.45, 0.8],
          }}
          transition={{
            duration: 3.2,
            delay: n.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}

      <motion.div
        className="mind-seed"
        animate={{ scale: [1, 1.08, 1] }}
        transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
      >
        <div className="seed-core">B</div>
        <div className="seed-ring ring-one" />
        <div className="seed-ring ring-two" />
        <div className="seed-ring ring-three" />
      </motion.div>

      {nodes.map((node) => (
        <motion.div
          key={node.name}
          className={`mind-node ${activeAgent === node.name ? "active" : ""}`}
          style={{
            left: `calc(50% + ${node.x}px)`,
            top: `calc(50% + ${node.y}px)`,
          }}
          animate={{
            scale: activeAgent === node.name ? 1.14 : 1,
          }}
        >
          {node.name}
        </motion.div>
      ))}

      <p className="mind-status">{status.replaceAll("_", " ")}</p>
    </div>
  );
}