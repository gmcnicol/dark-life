import EnqueueDialog from "@/components/EnqueueDialog";
import { getStory } from "@/lib/stories";

export default async function QueuePage({ params }: { params: { id: string } }) {
  const story = await getStory(Number(params.id));
  return <EnqueueDialog storyId={story.id} />;
}
