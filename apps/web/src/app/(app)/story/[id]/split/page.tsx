import SplitEditor from "@/components/SplitEditor";
import { getStory } from "@/lib/stories";

export default async function SplitPage({ params }: { params: { id: string } }) {
  const story = await getStory(Number(params.id));
  return <SplitEditor story={story} />;
}
