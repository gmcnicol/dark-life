import EnqueueDialog from "@/components/EnqueueDialog";
import { getStory } from "@/lib/stories";

export default async function QueuePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const story = await getStory(Number(id));
  return <EnqueueDialog storyId={story.id} />;
}
