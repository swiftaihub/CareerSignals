const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function getJson(path: string) {
  const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    return null;
  }
  return response.json();
}

export default async function HomePage() {
  const [status, topMatches, categorySummary] = await Promise.all([
    getJson("/api/data/status"),
    getJson("/api/top-matches"),
    getJson("/api/category-summary")
  ]);

  const matches = Array.isArray(topMatches) ? topMatches.slice(0, 10) : [];
  const categories = Array.isArray(categorySummary) ? categorySummary : [];

  return (
    <main className="page">
      <div className="topbar">
        <div>
          <h1>CareerSignal</h1>
          <p>Targeted job-search intelligence from the FastAPI layer.</p>
        </div>
        <a href="/settings">Settings</a>
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
          <h2>Mart Tables</h2>
          <div className="value">{status?.mart_tables_available ? "yes" : "no"}</div>
        </div>
      </section>

      <h2>Top Matches</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Role</th>
            <th>Company</th>
            <th>Score</th>
            <th>Visa</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((job: any) => (
            <tr key={job.job_id || `${job.Company}-${job["Job Title"]}`}>
              <td>{job.job_title || job["Job Title"]}</td>
              <td>{job.company || job.Company}</td>
              <td>{job.match_score || job["Match Score"]}</td>
              <td>{job.visa_signal || job["Visa Signal"]}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Category Summary</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Jobs</th>
            <th>Average Score</th>
          </tr>
        </thead>
        <tbody>
          {categories.map((row: any) => (
            <tr key={row.category_name || row.Category}>
              <td>{row.category_name || row.Category}</td>
              <td>{row.jobs_found || row["Jobs Found"]}</td>
              <td>{row.average_match_score || row["Average Match Score"]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
