import MediaSelector from "@/components/MediaSelector";
import { getStory } from "@/lib/stories";
import { segmentSentences, splitSentences } from "@/lib/split";

export default async function MediaPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const story = await getStory(Number(id));
  const sentences = segmentSentences(story.body_md || "");
  const parts = splitSentences(sentences).map((p) => p.join(" ").trim());
  return <MediaSelector story={story} parts={parts} />;
}
