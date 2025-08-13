import MediaSelector from "@/components/MediaSelector";
import { getStory } from "@/lib/stories";
import { segmentSentences, splitSentences } from "@/lib/split";

export default async function MediaPage({ params }: { params: { id: string } }) {
  const story = await getStory(Number(params.id));
  const sentences = segmentSentences(story.body_md || "");
  const parts = splitSentences(sentences).map((p) => p.join(" ").trim());
  return <MediaSelector story={story} parts={parts} />;
}
