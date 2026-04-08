import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import SplitEditor from "@/components/SplitEditor";
import { LoadingState } from "@/components/ui-surfaces";
import { getStoryOverview } from "@/lib/stories";

export default function StorySplitRoute() {
  const params = useParams();
  const storyId = Number(params.id);
  const overviewQuery = useQuery({
    queryKey: ["story-overview", storyId],
    queryFn: () => getStoryOverview(storyId),
    enabled: Number.isFinite(storyId),
  });
  const overview = overviewQuery.data;

  if (overviewQuery.isLoading || !overview) {
    return <LoadingState label="Loading script blocks…" className="min-h-56" />;
  }

  return <SplitEditor story={overview.story} parts={overview.parts} />;
}
