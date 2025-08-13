export interface JobData {
  id: number;
  story_id: number;
  kind: string;
  status: string;
}

let jobs: JobData[] = [];
let nextId = 1;

export function listJobs(story_id?: number): JobData[] {
  return story_id ? jobs.filter((j) => j.story_id === story_id) : jobs;
}

export function addJobs(items: Omit<JobData, "id">[]): JobData[] {
  const created = items.map((it) => ({ id: nextId++, ...it }));
  jobs.push(...created);
  return created;
}
