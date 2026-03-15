import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import MediaSelector from "@/components/MediaSelector";
import { LoadingState } from "@/components/ui-surfaces";
import { getStoryOverview, listStoryAssets } from "@/lib/stories";

export default function StoryMediaRoute() {
  const params = useParams();
  const storyId = Number(params.id);
  const overviewQuery = useQuery({
    queryKey: ["story-overview", storyId],
    queryFn: () => getStoryOverview(storyId),
    enabled: Number.isFinite(storyId),
  });
  const assetsQuery = useQuery({
    queryKey: ["story-assets", storyId],
    queryFn: () => listStoryAssets(storyId),
    enabled: Number.isFinite(storyId),
  });

  if (overviewQuery.isLoading || assetsQuery.isLoading || !overviewQuery.data || !assetsQuery.data) {
    return <LoadingState label="Loading media library…" className="min-h-56" />;
  }

  return (
    <MediaSelector
      story={overviewQuery.data.story}
      parts={overviewQuery.data.parts}
      assets={assetsQuery.data}
    />
  );
}
