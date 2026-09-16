export function formatStatus(status = "idle") {
    const map = {
      app_started: "Online",
      wake_detected: "Awake",
      session_started: "Listening",
      speech_recognized: "Understanding",
      tasks_split: "Organizing",
      agent_selected: "Routing",
      tool_started: "Helping",
      tool_finished: "Ready",
      session_ended: "Sleeping",
      error: "Needs attention",
      offline: "Offline",
      idle: "Idle",
    };
  
    return map[status] || status.replaceAll("_", " ");
  }