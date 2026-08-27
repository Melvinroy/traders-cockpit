"use client";

import { useState } from "react";

import { CatalystDashboard } from "@/components/CatalystDashboard";
import { Cockpit } from "@/components/Cockpit";

export function AppShell() {
  const [tab, setTab] = useState<"journal" | "catalyst">("journal");

  return (
    <div className="app-shell">
      <nav className="app-tabs" aria-label="Primary workspace">
        <div className="app-tabs-brand">TRADER&apos;S <span>/ COCKPIT</span></div>
        <div className="app-tabs-switch">
          <button type="button" className={tab === "journal" ? "active" : ""} onClick={() => setTab("journal")}>JOURNAL</button>
          <button type="button" className={tab === "catalyst" ? "active" : ""} onClick={() => setTab("catalyst")}>CATALYST</button>
        </div>
      </nav>
      <div className={tab === "journal" ? "app-view active" : "app-view hidden"}><Cockpit /></div>
      <div className={tab === "catalyst" ? "app-view active" : "app-view hidden"}><CatalystDashboard /></div>
    </div>
  );
}
