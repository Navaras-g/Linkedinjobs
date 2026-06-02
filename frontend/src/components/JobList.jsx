import { useMemo } from "react";

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
  const sortedJobs = useMemo(
    () => [...jobs].sort((a, b) => new Date(b.scraped_at || 0) - new Date(a.scraped_at || 0)),
    [jobs],
  );

  if (!sortedJobs.length) {
    return <p>No jobs found.</p>;
  }

  return (
    <section>
      <h2>Jobs</h2>
      {sortedJobs.map((job) => (
        <article key={job.id}>
          <h3>{job.title}</h3>
          <p>{job.company}</p>
          <p>{job.location}</p>
          <p>{job.posted_at}</p>
          <p>{job.easy_apply ? "Easy Apply" : "Standard Apply"}</p>
          <div>
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
        </article>
      ))}
    </section>
  );
}
