import InboxList from "@/components/inbox-list";
import { listStories } from "@/lib/stories";

interface InboxPageProps {
  searchParams: { status?: string };
}

export default async function InboxPage({ searchParams }: InboxPageProps) {
  const stories = await listStories({ status: searchParams.status });
  return (
    <div>
      <form>
        <select name="status" defaultValue={searchParams.status ?? ""}>
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
