import Link from "next/link";
import { listReleaseQueue, listStories } from "@/lib/stories";

export default async function DashboardPage() {
  const [stories, releaseQueue] = await Promise.all([listStories(), listReleaseQueue()]);
  const counts = stories.reduce<Record<string, number>>((acc, story) => {
    acc[story.status] = (acc[story.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">Control Room</p>
        <h1 className="text-4xl font-semibold text-zinc-50">Dark Life Studio</h1>
        <p className="max-w-2xl text-sm leading-7 text-zinc-300">
          Ingest Reddit stories, adapt them into first-person narration, pair them with local
          background visuals, render Shorts, and stage weekly compilations for manual publishing.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        {[
          ["Stories", stories.length],
          ["Queued", counts.queued ?? 0],
          ["Rendering", counts.rendering ?? 0],
          ["Publish Ready", releaseQueue.length],
        ].map(([label, value]) => (
          <div key={label} className="rounded-3xl border border-zinc-800 bg-zinc-950/70 p-5">
            <p className="text-xs uppercase tracking-[0.25em] text-zinc-500">{label}</p>
            <p className="mt-3 text-4xl font-semibold text-zinc-50">{value}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-3xl border border-zinc-800 bg-zinc-950/70 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-100">Recent Stories</h2>
            <Link href="/inbox" className="text-sm text-amber-200 underline underline-offset-4">
              Open inbox
            </Link>
          </div>
          <div className="space-y-3">
            {stories.slice(0, 6).map((story) => (
              <Link
                key={story.id}
                href={`/story/${story.id}/review`}
                className="flex items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3"
              >
                <span className="text-zinc-100">{story.title}</span>
                <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-300">
                  {story.status}
                </span>
              </Link>
            ))}
          </div>
        </div>
        <div className="rounded-3xl border border-zinc-800 bg-zinc-950/70 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-100">Publish Queue</h2>
            <Link href="/publish" className="text-sm text-amber-200 underline underline-offset-4">
              Open queue
            </Link>
          </div>
          <div className="space-y-3">
            {releaseQueue.slice(0, 5).map((release) => (
              <div key={release.id} className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                <p className="text-sm text-zinc-100">{release.title}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.25em] text-zinc-500">
                  {release.platform} · {release.variant}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
