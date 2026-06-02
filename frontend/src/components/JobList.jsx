import { useMemo, useState } from "react";

import { apiClient } from "../api/client";

function buildPatchPayload(job, action) {
  if (action === "seen") {
    return { seen: !job.seen };
  }
  if (action === "saved") {
    return { saved: !job.saved };
  }
  if (action === "hidden") {
    return { hidden: true };
  }
  return {};
}

export default function JobList({ jobs, onJobAction }) {
  const [expandedJobId, setExpandedJobId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  const sortedJobs = useMemo(
    () => [...jobs].sort((a, b) => new Date(b.scraped_at || 0) - new Date(a.scraped_at || 0)),
    [jobs],
  );

  const handleJobClick = async (jobId) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null);
      setDetail(null);
      setDetailError("");
      return;
    }

    setExpandedJobId(jobId);
    setDetail(null);
    setDetailLoading(true);
    setDetailError("");

    try {
      const data = await apiClient.getJob(jobId);
      setDetail(data);
    } catch (err) {
      setDetailError(err.message || "Failed to load job details");
    } finally {
      setDetailLoading(false);
    }
  };

  if (!sortedJobs.length) {
    return <p>No jobs found.</p>;
  }

  return (
    <section>
      <h2>Jobs</h2>
      {sortedJobs.map((job) => (
        <article
          key={job.id}
          className={expandedJobId === job.id ? "job-card-expanded" : ""}
          onClick={() => handleJobClick(job.id)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              handleJobClick(job.id);
            }
          }}
        >
          <h3>{job.title}</h3>
          <p>{job.company}</p>
          <p>{job.location}</p>
          <p>{job.posted_at}</p>
          <p>{job.easy_apply ? "Easy Apply" : "Standard Apply"}</p>
          <div onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
            <button type="button" onClick={() => onJobAction(job.id, buildPatchPayload(job, "seen"))}>
              {job.seen ? "Mark Unseen" : "Mark Seen"}
            </button>
            <button type="button" onClick={() => onJobAction(job.id, buildPatchPayload(job, "saved"))}>
              {job.saved ? "Unsave" : "Save"}
            </button>
            <button type="button" onClick={() => onJobAction(job.id, buildPatchPayload(job, "hidden"))}>
              Hide
            </button>
            <a href={job.url} target="_blank" rel="noreferrer">
              Open
            </a>
          </div>

          {expandedJobId === job.id ? (
            <div className="job-detail" onClick={(e) => e.stopPropagation()}>
              {detailLoading ? <p>Loading job details...</p> : null}
              {detailError ? <p>{detailError}</p> : null}
              {!detailLoading && !detailError && detail?.id === job.id ? (
                detail.description_html ? (
                  <div
                    className="job-description"
                    dangerouslySetInnerHTML={{ __html: detail.description_html }}
                  />
                ) : (
                  <p>No description available.</p>
                )
              ) : null}
            </div>
          ) : null}
        </article>
      ))}
    </section>
  );
}
