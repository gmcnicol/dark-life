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
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <button type="submit">Filter</button>
      </form>
      <InboxList stories={stories} />
    </div>
  );
}
