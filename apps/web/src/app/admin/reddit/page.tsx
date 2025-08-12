"use client";

import { useEffect, useState } from "react";

interface Job {
  id: number;
  subreddit: string;
  kind: string;
  status: string;
  payload?: {
    subreddit?: string;
  };
}

interface StateRow {
  subreddit: string;
  last_fullname?: string | null;
  last_created_utc?: string | null;
  backfill_earliest_utc?: string | null;
  updated_at?: string | null;
}

interface PostRow {
  reddit_id: string;
  title: string;
  subreddit: string;
  created_utc: string;
}

export default function RedditAdminPage() {
  const [subs, setSubs] = useState("nosleep,confession");
  const [earliest, setEarliest] = useState("2008-01-01");
  const [state, setState] = useState<StateRow[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [posts, setPosts] = useState<PostRow[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});

  async function refresh() {
    const s = await fetch(`/api/admin/reddit/state`).then((r) => r.json());
    setState(s);
    const j = await fetch(`/api/admin/reddit/jobs`).then((r) => r.json());
    setJobs(j);
    const p = await fetch(`/api/admin/reddit/posts`).then((r) => r.json());
    setPosts(p);
  }

  useEffect(() => {
    refresh();
  }, []);

  async function runIncremental() {
    await fetch(`/api/admin/reddit/incremental`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subreddits: subs.split(",").map((s) => s.trim()).filter(Boolean) }),
    });
    refresh();
  }

  async function runBackfill() {
    await fetch(`/api/admin/reddit/backfill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subreddits: subs.split(",").map((s) => s.trim()).filter(Boolean), earliest }),
    });
    refresh();
  }

  function toggleSelect(id: string) {
    setSelected((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  async function promoteSelected() {
    const ids = Object.keys(selected).filter((k) => selected[k]);
    if (!ids.length) return;
    await fetch(`/api/admin/reddit/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reddit_ids: ids }),
    });
    refresh();
  }

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-xl font-bold">Reddit Admin</h1>
      <div className="space-x-2">
        <input
          className="border p-1"
          value={subs}
          onChange={(e) => setSubs(e.target.value)}
        />
        <button className="bg-blue-500 text-white px-2" onClick={runIncremental}>Run Incremental</button>
        <input
          className="border p-1"
          value={earliest}
          onChange={(e) => setEarliest(e.target.value)}
        />
        <button className="bg-blue-500 text-white px-2" onClick={runBackfill}>Run Backfill</button>
        <button className="bg-green-600 text-white px-2" onClick={promoteSelected}>Promote Selected</button>
        <button className="px-2" onClick={refresh}>Refresh</button>
      </div>

      <h2 className="font-semibold">State</h2>
      <table className="border">
        <thead>
          <tr><th>Subreddit</th><th>Last Fullname</th><th>Last Created</th><th>Backfill Earliest</th></tr>
        </thead>
        <tbody>
          {state.map((row) => (
            <tr key={row.subreddit}>
              <td>{row.subreddit}</td>
              <td>{row.last_fullname}</td>
              <td>{row.last_created_utc}</td>
              <td>{row.backfill_earliest_utc}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="font-semibold">Jobs</h2>
      <table className="border">
        <thead>
          <tr><th>ID</th><th>Subreddit</th><th>Kind</th><th>Status</th></tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>{job.id}</td>
              <td>{job.payload?.subreddit ?? job.subreddit}</td>
              <td>{job.kind}</td>
              <td>{job.status}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="font-semibold">Posts</h2>
      <table className="border">
        <thead>
          <tr><th></th><th>Reddit ID</th><th>Subreddit</th><th>Title</th><th>Created</th></tr>
        </thead>
        <tbody>
          {posts.map((p) => (
            <tr key={p.reddit_id}>
              <td>
                <input type="checkbox" checked={!!selected[p.reddit_id]} onChange={() => toggleSelect(p.reddit_id)} />
              </td>
              <td>{p.reddit_id}</td>
              <td>{p.subreddit}</td>
              <td>{p.title}</td>
              <td>{p.created_utc}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
