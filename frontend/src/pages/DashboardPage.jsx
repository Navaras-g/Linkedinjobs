import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiClient } from "../api/client";
import JobList from "../components/JobList";

export default function DashboardPage() {
  const [jobs, setJobs] = useState([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState(null);
  const [keyword, setKeyword] = useState("");
  const [tab, setTab] = useState("all");
  const [loading, setLoading] = useState(true);
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [error, setError] = useState("");
  const [hideToast, setHideToast] = useState(null);
  const hideToastTimeoutRef = useRef(null);

  const UNDO_WINDOW_MS = 5000;

  const jobQuery = useMemo(() => {
    const base = { hidden: false, keyword, page: 1, per_page: 20 };
    if (tab === "unseen") {
      return { ...base, seen: false };
    }
    if (tab === "saved") {
      return { ...base, saved: true };
    }
    return base;
  }, [keyword, tab]);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiClient.getJobs(jobQuery);
      setJobs(data.items ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      setError(err.message || "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [jobQuery]);

  const loadStats = useCallback(async () => {
    try {
      const data = await apiClient.getStats();
      setStats(data);
    } catch {
      // Keep dashboard usable even if stats endpoint fails.
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(() => {
      loadJobs();
    }, 300);
    return () => clearTimeout(id);
  }, [loadJobs]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const handleTriggerScrape = async () => {
    setScrapeLoading(true);
    try {
      await apiClient.triggerScrape();
      await Promise.all([loadJobs(), loadStats()]);
    } catch (err) {
      setError(err.message || "Failed to trigger scrape");
    } finally {
      setScrapeLoading(false);
    }
  };

  const handleJobAction = async (jobId, payload) => {
    try {
      await apiClient.patchJob(jobId, payload);
      await Promise.all([loadJobs(), loadStats()]);
    } catch (err) {
      setError(err.message || "Failed to update job");
    }
  };

  const clearHideToastTimer = () => {
    if (hideToastTimeoutRef.current) {
      clearTimeout(hideToastTimeoutRef.current);
      hideToastTimeoutRef.current = null;
    }
  };

  const showHideToast = (job) => {
    clearHideToastTimer();
    setHideToast({ jobId: job.id, company: job.company, previousHidden: job.hidden });
    hideToastTimeoutRef.current = setTimeout(() => {
      setHideToast(null);
      hideToastTimeoutRef.current = null;
    }, UNDO_WINDOW_MS);
  };

  const handleHideJob = async (job) => {
    try {
      await apiClient.patchJob(job.id, { hidden: true });
      showHideToast(job);
      await Promise.all([loadJobs(), loadStats()]);
    } catch (err) {
      setError(err.message || "Failed to hide job");
    }
  };

  const handleUndoHide = async () => {
    if (!hideToast) {
      return;
    }

    const { jobId, previousHidden } = hideToast;
    clearHideToastTimer();
    setHideToast(null);

    try {
      await apiClient.patchJob(jobId, { hidden: previousHidden });
      await Promise.all([loadJobs(), loadStats()]);
    } catch (err) {
      setError(err.message || "Failed to undo hide");
    }
  };

  useEffect(() => () => clearHideToastTimer(), []);

  return (
    <main>
      <header>
        <h1>linkedin-jobs</h1>
        <p>Total: {stats?.total_jobs ?? total}</p>
        <p>Unseen: {stats?.unseen_count ?? "-"}</p>
        <p>Saved: {stats?.saved_count ?? "-"}</p>
        <p>Last Scraped: {stats?.last_scraped_at ?? "-"}</p>
        <button type="button" onClick={handleTriggerScrape} disabled={scrapeLoading}>
          {scrapeLoading ? "Scraping..." : "Scrape Now"}
        </button>
      </header>

      <section>
        <button type="button" onClick={() => setTab("all")}>
          All
        </button>
        <button type="button" onClick={() => setTab("unseen")}>
          Unseen
        </button>
        <button type="button" onClick={() => setTab("saved")}>
          Saved
        </button>
        <input
          type="search"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Search title or company"
        />
      </section>

      {hideToast ? (
        <div className="toast" role="status">
          <span>Hidden {hideToast.company}. </span>
          <button type="button" onClick={handleUndoHide}>
            Undo
          </button>
        </div>
      ) : null}

      {error ? <p>{error}</p> : null}
      {loading ? (
        <p>Loading jobs...</p>
      ) : (
        <JobList jobs={jobs} onJobAction={handleJobAction} onHideJob={handleHideJob} />
      )}
    </main>
  );
}
