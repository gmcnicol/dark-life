import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import EnqueueDialog from "@/components/EnqueueDialog";
import { LoadingState } from "@/components/ui-surfaces";
import { getStoryOverview, listRenderPresets } from "@/lib/stories";

export default function StoryQueueRoute() {
  const params = useParams();
  const storyId = Number(params.id);
  const overviewQuery = useQuery({
    queryKey: ["story-overview", storyId],
    queryFn: () => getStoryOverview(storyId),
    enabled: Number.isFinite(storyId),
  });
  const presetsQuery = useQuery({
    queryKey: ["render-presets"],
    queryFn: listRenderPresets,
  });

  if (overviewQuery.isLoading || presetsQuery.isLoading || !overviewQuery.data || !presetsQuery.data) {
    return <LoadingState label="Loading render queue setup…" className="min-h-56" />;
  }

  return (
    <EnqueueDialog
      story={overviewQuery.data.story}
      storyId={storyId}
      bundles={overviewQuery.data.asset_bundles}
      presets={presetsQuery.data}
    />
  );
}
