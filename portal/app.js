const eventsPath = "../data/events.jsonl";

const statusText = document.getElementById("statusText");
const coreState = document.getElementById("coreState");
const userText = document.getElementById("userText");
const babyText = document.getElementById("babyText");

let lastEventCount = 0;

async function loadEvents() {
  try {
    const response = await fetch(eventsPath + "?t=" + Date.now());
    const text = await response.text();

    const events = text
      .trim()
      .split("\n")
      .filter(Boolean)
      .map(line => JSON.parse(line));

    if (events.length === 0) return;

    const latest = events[events.length - 1];
    updateFromEvent(latest);
    updateTimeline(events.slice(-10));

    lastEventCount = events.length;
  } catch (err) {
    statusText.textContent = "offline";
    coreState.textContent = "OFFLINE";
  }
}

function updateFromEvent(event) {
  const type = event.type;
  const data = event.data || {};

  statusText.textContent = type.replaceAll("_", " ");
  coreState.textContent = type.replaceAll("_", " ").toUpperCase();

  if (type === "speech_recognized") {
    userText.textContent = data.text || "";
    babyText.textContent = "Understanding command...";
  }

  if (type === "tasks_split") {
    babyText.textContent = `Split into ${(data.tasks || []).length} task(s).`;
  }

  if (type === "agent_selected") {
    babyText.textContent = `Routing to ${data.agent} agent.`;
    activateAgent(data.agent);
  }

  if (type === "tool_started") {
    babyText.textContent = `Executing ${data.tool}...`;
  }

  if (type === "tool_finished") {
    babyText.textContent = "Task completed. Ready for next command.";
    clearAgents();
  }

  if (type === "session_started") {
    babyText.textContent = "Listening...";
    clearAgents();
  }

  if (type === "session_ended") {
    babyText.textContent = "Waiting for wake word...";
    clearAgents();
  }
}

function activateAgent(agent) {
  clearAgents();
  const node = document.querySelector(`.node-${agent}`);
  if (node) node.classList.add("node-active");
}

function clearAgents() {
  document.querySelectorAll(".agent-node").forEach(node => {
    node.classList.remove("node-active");
  });
}

function updateTimeline(events) {
  let timeline = document.getElementById("eventTimeline");

  if (!timeline) {
    timeline = document.createElement("div");
    timeline.id = "eventTimeline";
    timeline.className = "event-timeline";
    document.querySelector(".left-panel").appendChild(timeline);
  }

  timeline.innerHTML = "<p class='label'>EVENT STREAM</p>";

  events.reverse().forEach(event => {
    const item = document.createElement("div");
    item.className = "event-item";

    const time = new Date(event.timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });

    item.innerHTML = `
      <span>${time}</span>
      <strong>${event.type.replaceAll("_", " ")}</strong>
    `;

    timeline.appendChild(item);
  });
}

setInterval(loadEvents, 800);
loadEvents();