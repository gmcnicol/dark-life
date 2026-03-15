import ReviewBar from "@/components/review-bar";
import { getStoryOverview } from "@/lib/stories";

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const overview = await getStoryOverview(Number(id));
  const story = overview.story;
  const script = overview.active_script;

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <p className="text-xs uppercase tracking-[0.3em] text-zinc-400">Story Review</p>
        <h1 className="text-3xl font-semibold text-zinc-50">{story.title}</h1>
      </section>
      <ReviewBar story={story} activeScript={script} />
      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-3xl border border-zinc-800 bg-zinc-950/70 p-5">
          <p className="mb-3 text-xs uppercase tracking-[0.3em] text-zinc-500">Source</p>
          <div className="max-h-[32rem] overflow-auto whitespace-pre-wrap text-sm leading-7 text-zinc-300">
            {story.body_md || "No source body yet."}
          </div>
        </article>
        <article className="rounded-3xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-xs uppercase tracking-[0.3em] text-zinc-500">Narration Draft</p>
          {script ? (
            <div className="space-y-5 text-sm leading-7 text-zinc-200">
              <div>
                <h2 className="mb-1 text-xs uppercase tracking-[0.25em] text-zinc-500">Hook</h2>
                <p>{script.hook}</p>
              </div>
              <div>
                <h2 className="mb-1 text-xs uppercase tracking-[0.25em] text-zinc-500">Voiceover</h2>
                <p>{script.narration_text}</p>
              </div>
              <div>
                <h2 className="mb-1 text-xs uppercase tracking-[0.25em] text-zinc-500">Outro</h2>
                <p>{script.outro}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-zinc-400">
              Generate a narrator-ready first-person script to start the production workflow.
            </p>
          )}
        </article>
      </section>
    </div>
  );
}
