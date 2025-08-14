import ReviewBar from "@/components/review-bar";
import { getStory } from "@/lib/stories";

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const story = await getStory(Number(id));
  return (
    <div>
      <p>{story.body_md}</p>
      <ReviewBar story={story} />
    </div>
  );
}
