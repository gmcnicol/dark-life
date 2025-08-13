import ReviewBar from "@/components/review-bar";
import { getStory } from "@/lib/stories";

export default async function ReviewPage({ params }: { params: { id: string } }) {
  const story = await getStory(Number(params.id));
  return (
    <div>
      <p>{story.body_md}</p>
      <ReviewBar story={story} />
    </div>
  );
}
