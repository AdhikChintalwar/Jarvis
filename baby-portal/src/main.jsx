import React from "react";
import ReactDOM from "react-dom/client";

import BabyTabs from "./components/BabyTabs.jsx";

import "./styles/globals.css";


ReactDOM
  .createRoot(
    document.getElementById("root")
  )
  .render(
    <React.StrictMode>
      <BabyTabs />
    </React.StrictMode>
  );