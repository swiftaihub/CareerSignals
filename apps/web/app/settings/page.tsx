"use client";

import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function postAction(path: string) {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export default function SettingsPage() {
  const [status, setStatus] = useState<any>(null);
  const [message, setMessage] = useState("");

  async function refreshStatus() {
    const response = await fetch(`${API_BASE_URL}/api/data/status`);
    setStatus(await response.json());
  }

  async function run(label: string, path: string) {
    setMessage(`${label} running...`);
    try {
      await postAction(path);
      setMessage(`${label} completed.`);
      await refreshStatus();
    } catch (error: any) {
      setMessage(`${label} failed: ${error.message}`);
    }
  }

  useEffect(() => {
    refreshStatus();
  }, []);

  return (
    <main className="page">
      <div className="topbar">
        <div>
          <h1>Settings</h1>
          <p>Data mode and pipeline controls.</p>
        </div>
        <a href="/">Dashboard</a>
      </div>

      <section className="grid">
        <div className="card">
          <h2>Data Mode</h2>
          <div className="value">{status?.data_mode || "unknown"}</div>
        </div>
        <div className="card">
          <h2>Database</h2>
          <div className="value">{status?.database || "unknown"}</div>
        </div>
        <div className="card">
          <h2>Last dbt Run</h2>
          <div>{status?.last_dbt_run || "unknown"}</div>
        </div>
        <div className="card">
          <h2>Last Pipeline Run</h2>
          <div>{status?.last_pipeline_run || "unknown"}</div>
        </div>
        <div className="card">
          <h2>Mart Tables Available</h2>
          <div className="value">{status?.mart_tables_available ? "yes" : "no"}</div>
        </div>
        <div className="card">
          <h2>Excel Source</h2>
          <div>{status?.excel_source || "unknown"}</div>
        </div>
      </section>

      <div className="actions">
        <button onClick={() => run("Pipeline", "/api/pipeline/run")}>Run Pipeline</button>
        <button onClick={() => run("dbt Models", "/api/dbt/run")}>Run dbt Models</button>
        <button onClick={() => run("dbt Tests", "/api/dbt/test")}>Run dbt Tests</button>
        <button onClick={() => run("Excel Export", "/api/excel/export")}>Export Excel</button>
        <a className="button" href={`${API_BASE_URL}/api/excel/download`}>Download Excel</a>
      </div>

      <p>{message}</p>
      {status?.excel_path ? <p>Latest Excel: {status.excel_path}</p> : null}
    </main>
  );
}
