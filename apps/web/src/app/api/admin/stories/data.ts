export interface StoryData {
  id: number;
  title: string;
  body_md?: string;
  status: string;
}

let stories: StoryData[] = [
  { id: 1, title: "First story", body_md: "Hello", status: "pending" },
  {
    id: 2,
    title: "Second story",
    body_md:
      "This is the first sentence. Here is the second one. And finally the third.",
    status: "pending",
  },
];

export function listStories(): StoryData[] {
  return stories;
}

export function findStory(id: number): StoryData | undefined {
  return stories.find((s) => s.id === id);
}

export function updateStory(
  id: number,
  data: Partial<Pick<StoryData, "status" | "body_md" | "title">> & { notes?: string },
): StoryData {
  const story = findStory(id);
  if (!story) {
    throw new Error("Not found");
  }
  Object.assign(story, data);
  return story;
}
