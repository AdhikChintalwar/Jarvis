const states = ["Listening", "Thinking", "Routing", "Executing"];
const statusText = document.getElementById("statusText");
const coreState = document.getElementById("coreState");

let index = 0;

setInterval(() => {
  index = (index + 1) % states.length;
  statusText.textContent = states[index];
  coreState.textContent = states[index].toUpperCase();
}, 2500);