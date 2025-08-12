export interface Image {
  id: number;
  remote_url: string;
  selected: boolean;
  rank: number;
}

export interface Story {
  id: number;
  title: string;
  body_md: string;
  status: "draft" | "approved";
  images: Image[];
}

export const stories: Story[] = [
  {
    id: 1,
    title: "First mock story",
    body_md: "Lorem ipsum dolor sit amet.",
    status: "draft",
    images: [
      { id: 1, remote_url: "https://placekitten.com/200/200", selected: false, rank: 0 },
      { id: 2, remote_url: "https://placekitten.com/210/200", selected: false, rank: 1 }
    ]
  },
  {
    id: 2,
    title: "Second mock story",
    body_md: "Another mock story body.",
    status: "approved",
    images: []
  }
];

export function nextStoryId(): number {
  return stories.length ? Math.max(...stories.map((s) => s.id)) + 1 : 1;
}

export function nextImageId(story: Story): number {
  return story.images.length
    ? Math.max(...story.images.map((i) => i.id)) + 1
    : 1;
}
