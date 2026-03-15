import MediaSelector from "@/components/MediaSelector";
import { getStoryOverview, listStoryAssets } from "@/lib/stories";

export default async function MediaPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const storyId = Number(id);
  const [overview, assets] = await Promise.all([
    getStoryOverview(storyId),
    listStoryAssets(storyId),
  ]);
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">Media Library</p>
        <h1 className="text-3xl font-semibold text-zinc-50">{overview.story.title}</h1>
      </div>
      <MediaSelector story={overview.story} parts={overview.parts} assets={assets} />
    </div>
  );
}
