import { useEffect, useState } from "react";

const EVENTS_PATH = "/events.jsonl";

const initialRuntime = {
  backend: "Unknown",
  wake: "Idle",
  asr: "Idle",
  lastHeard: "",
  activeAgent: null,
  activeTool: null,
};

export default function useEvents() {
  const [events, setEvents] = useState([]);
  const [latestEvent, setLatestEvent] = useState(null);
  const [activeAgent, setActiveAgent] = useState(null);
  const [status, setStatus] = useState("idle");
  const [runtime, setRuntime] = useState(initialRuntime);

  useEffect(() => {
    let clearAgentTimer;

    async function loadEvents() {
      try {
        const res = await fetch(EVENTS_PATH + "?t=" + Date.now());
        const text = await res.text();

        const parsed = text
          .trim()
          .split("\n")
          .filter(Boolean)
          .map((line) => JSON.parse(line));

        setEvents(parsed.slice(-40));

        const latest = parsed[parsed.length - 1];
        if (!latest) return;

        setLatestEvent(latest);
        setStatus(latest.type);

        setRuntime((prev) => {
          const next = { ...prev };

          if (latest.type === "app_started") next.backend = "Running";
          if (latest.type === "app_closed") next.backend = "Stopped";

          if (latest.type === "wake_listening") next.wake = "Listening";
          if (latest.type === "wake_detected") next.wake = "Detected";

          if (latest.type === "session_started") {
            next.asr = "Ready";
            next.activeAgent = null;
            next.activeTool = null;
          }

          if (latest.type === "asr_listening") next.asr = "Listening";
          if (latest.type === "asr_processing") next.asr = "Processing";

          if (latest.type === "speech_recognized") {
            next.lastHeard = latest.data?.text || "";
            next.asr = "Recognized";
          }

          if (latest.type === "agent_selected") {
            next.activeAgent = latest.data?.agent || null;
          }

          if (latest.type === "tool_started") {
            next.activeTool = latest.data?.tool || null;
          }

          if (latest.type === "tool_finished") {
            next.activeTool = null;
            next.asr = "Ready";
          }

          if (latest.type === "session_ended") {
            next.wake = "Listening";
            next.asr = "Idle";
            next.activeAgent = null;
            next.activeTool = null;
          }

          return next;
        });

        if (latest.type === "agent_selected") {
          clearTimeout(clearAgentTimer);
          setActiveAgent(latest.data?.agent || null);
        }

        if (latest.type === "tool_finished") {
          clearTimeout(clearAgentTimer);
          clearAgentTimer = setTimeout(() => {
            setActiveAgent(null);
          }, 2500);
        }

        if (latest.type === "session_started") {
          clearTimeout(clearAgentTimer);
          setActiveAgent(null);
        }
      } catch {
        setStatus("offline");
        setRuntime((prev) => ({
          ...prev,
          backend: "Offline",
        }));
      }
    }

    loadEvents();
    const interval = setInterval(loadEvents, 800);

    return () => {
      clearInterval(interval);
      clearTimeout(clearAgentTimer);
    };
  }, []);

  return {
    events,
    latestEvent,
    activeAgent,
    status,
    runtime,
  };
}