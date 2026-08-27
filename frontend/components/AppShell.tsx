"use client";

import { useEffect, useState } from "react";

import { CatalystDashboard } from "@/components/CatalystDashboard";
import { Cockpit } from "@/components/Cockpit";
import { api } from "@/lib/api";

export function AppShell() {
  const [tab, setTab] = useState<"journal" | "catalyst">("journal");
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    let active = true;
    const check = () =>
      api
        .me()
        .then(() => active && setAuthenticated(true))
        .catch(() => active && setAuthenticated(false));
    void check();
    const timer = window.setInterval(check, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!authenticated && tab !== "journal") {
      setTab("journal");
    }
  }, [authenticated, tab]);

  return (
    <div className="app-shell">
      <nav
        className={`app-tabs${authenticated ? "" : " app-tabs-pending"}`}
        aria-label="Primary workspace"
        aria-hidden={!authenticated}
      >
        <div className="app-tabs-brand">
          TRADER&apos;S <span>/ COCKPIT</span>
        </div>
        <div className="app-tabs-switch">
          <button
            type="button"
            className={tab === "journal" ? "active" : ""}
            onClick={() => setTab("journal")}
            tabIndex={authenticated ? 0 : -1}
          >
            JOURNAL
          </button>
          <button
            type="button"
            className={tab === "catalyst" ? "active" : ""}
            onClick={() => setTab("catalyst")}
            tabIndex={authenticated ? 0 : -1}
          >
            CATALYST
          </button>
        </div>
      </nav>
      <div className={tab === "journal" ? "app-view active" : "app-view hidden"}>
        <Cockpit />
      </div>
      {authenticated ? (
        <div className={tab === "catalyst" ? "app-view active" : "app-view hidden"}>
          <CatalystDashboard />
        </div>
      ) : null}
    </div>
  );
}
