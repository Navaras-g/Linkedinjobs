const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) {
        message = body.detail;
      }
    } catch {
      // Keep fallback error message.
    }
    throw new Error(message);
  }

  return response.json();
}

export const apiClient = {
  getJobs(params = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        searchParams.set(key, String(value));
      }
    });
    const query = searchParams.toString();
    return request(`/jobs${query ? `?${query}` : ""}`);
  },

  getStats() {
    return request("/stats");
  },

  triggerScrape() {
    return request("/scrape/trigger", { method: "POST" });
  },

  patchJob(jobId, payload) {
    return request(`/jobs/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
};
