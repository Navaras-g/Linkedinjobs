import { useEffect, useState } from "react";

import { apiClient } from "../api/client";

export default function SettingsPage() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      setLoading(true);
      setError("");
      try {
        const data = await apiClient.getScrapeStatus();
        if (!cancelled) {
          setStatus(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load scrape schedule");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  const formatDateTime = (value) => {
    if (!value) {
      return "—";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString();
  };

  return (
    <main>
      <header>
        <h1>Settings</h1>
      </header>

      <section>
        <h2>Scrape schedule</h2>
        <p>Automatic scrapes run on an interval configured by <code>SCRAPE_INTERVAL_HOURS</code> in <code>.env</code> (default: every 6 hours).</p>
        {loading ? <p>Loading schedule...</p> : null}
        {error ? <p>{error}</p> : null}
        {!loading && !error ? (
          <>
            <p>Next scheduled run: {formatDateTime(status?.next_run_time)}</p>
            {status?.last_run ? (
              <>
                <p>Last run status: {status.last_run.status}</p>
                <p>Last run finished: {formatDateTime(status.last_run.finished_at)}</p>
              </>
            ) : (
              <p>No scrape runs recorded yet.</p>
            )}
          </>
        ) : null}
      </section>

      <section>
        <h2>LinkedIn session cookies</h2>
        <p>If scraping fails with a session expired error, re-export your browser cookies:</p>
        <ol>
          <li>Log into LinkedIn in Chrome.</li>
          <li>Install the &quot;EditThisCookie&quot; or &quot;Cookie-Editor&quot; browser extension.</li>
          <li>Export cookies as JSON.</li>
          <li>Save the file as <code>cookies.json</code> in the project root.</li>
          <li>Ensure <code>cookies.json</code> is listed in <code>.gitignore</code> and never commit it.</li>
        </ol>
      </section>
    </main>
  );
}
