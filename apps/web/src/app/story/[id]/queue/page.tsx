import EnqueueDialog from "@/components/EnqueueDialog";
import { getStoryOverview, listRenderPresets } from "@/lib/stories";

export default async function QueuePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const storyId = Number(id);
  const [overview, presets] = await Promise.all([
    getStoryOverview(storyId),
    listRenderPresets(),
  ]);
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">Render Queue</p>
        <h1 className="text-3xl font-semibold text-zinc-50">{overview.story.title}</h1>
      </div>
      <EnqueueDialog storyId={storyId} bundles={overview.asset_bundles} presets={presets} />
    </div>
  );
}
