import SplitEditor from "@/components/SplitEditor";
import { getStory } from "@/lib/stories";

export default async function SplitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const story = await getStory(Number(id));
  return <SplitEditor story={story} />;
}
