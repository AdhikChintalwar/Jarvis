import React, { useState } from "react";

import App from "../App.jsx";
import MCPRequestsPage from "./MCPRequestsPage.jsx";


export default function BabyTabs() {
  const [activeTab, setActiveTab] =
    useState("dashboard");

  return (
    <div className="baby-tab-shell">

      <div className="baby-top-tabs">

        <button
          className={
            activeTab === "dashboard"
              ? "baby-tab active"
              : "baby-tab"
          }
          onClick={() =>
            setActiveTab("dashboard")
          }
        >
          Dashboard
        </button>

        <button
          className={
            activeTab === "mcp"
              ? "baby-tab active"
              : "baby-tab"
          }
          onClick={() =>
            setActiveTab("mcp")
          }
        >
          MCP Requests
        </button>

      </div>

      <div className="baby-tab-content">
        {activeTab === "dashboard" ? (
          <App />
        ) : (
          <MCPRequestsPage />
        )}
      </div>

    </div>
  );
}