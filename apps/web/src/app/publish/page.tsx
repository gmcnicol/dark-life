import PublishQueue from "@/components/publish-queue";
import { listReleaseQueue } from "@/lib/stories";

export default async function PublishPage() {
  const releases = await listReleaseQueue();
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">Publish Queue</p>
        <h1 className="text-3xl font-semibold text-zinc-50">Ready for manual posting</h1>
      </div>
      <PublishQueue releases={releases} />
    </div>
  );
}
