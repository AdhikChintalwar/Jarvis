import { motion } from "framer-motion";

export default function NeuralCore({ status }) {
  return (
    <div className="neural-wrap">
      <motion.div
        className={`neural-core core-${status}`}
        animate={{
          scale: status === "listening" ? [1, 1.06, 1] : [1, 1.12, 1],
          rotate: [0, 360],
        }}
        transition={{
          scale: { duration: 2, repeat: Infinity },
          rotate: { duration: 18, repeat: Infinity, ease: "linear" },
        }}
      >
        <div className="core-center" />
        <div className="core-ring ring-one" />
        <div className="core-ring ring-two" />
        <div className="core-ring ring-three" />
      </motion.div>

      <div className="core-label">{status.toUpperCase()}</div>
    </div>
  );
}