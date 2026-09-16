export function formatEventName(type = "") {
    const names = {
      app_started: "Baby woke up",
      wake_detected: "Wake word detected",
      session_started: "Listening started",
      speech_recognized: "Heard your command",
      tasks_split: "Tasks separated",
      agent_selected: "Agent selected",
      tool_started: "Tool started",
      tool_finished: "Task completed",
      session_ended: "Sleeping",
      error: "Something went wrong",
    };
  
    return names[type] || type.replaceAll("_", " ");
  }