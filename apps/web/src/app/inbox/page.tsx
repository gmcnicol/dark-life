import InboxList from "@/components/inbox-list";
import { listStories } from "@/lib/stories";

export default async function InboxPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const params = await searchParams;
  const stories = await listStories({ status: params.status });
  return (
    <div>
      <form>
        <select name="status" defaultValue={params.status ?? ""}>
          <option value="">All</option>
          <option value="ingested">Ingested</option>
          <option value="scripted">Scripted</option>
          <option value="approved">Approved</option>
          <option value="media_ready">Media Ready</option>
          <option value="queued">Queued</option>
          <option value="publish_ready">Publish Ready</option>
          <option value="rejected">Rejected</option>
        </select>
        <button type="submit">Filter</button>
      </form>
      <InboxList stories={stories} />
    </div>
  );
}
