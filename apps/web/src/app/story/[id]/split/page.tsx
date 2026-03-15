import SplitEditor from "@/components/SplitEditor";
import { getStoryOverview } from "@/lib/stories";

export default async function SplitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const overview = await getStoryOverview(Number(id));
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">Part Timeline</p>
        <h1 className="text-3xl font-semibold text-zinc-50">{overview.story.title}</h1>
      </div>
      <SplitEditor story={overview.story} parts={overview.parts} />
    </div>
  );
}
