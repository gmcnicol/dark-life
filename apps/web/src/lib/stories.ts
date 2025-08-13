import { z } from "zod";
import { apiFetch } from "./api";

export const StorySchema = z.object({
  id: z.number(),
  title: z.string(),
  body_md: z.string().nullish(),
  status: z.string(),
});

export type Story = z.infer<typeof StorySchema>;

const StoryPartSchema = z.object({
  index: z.number(),
  body_md: z.string(),
  est_seconds: z.number(),
});

export type StoryPart = z.infer<typeof StoryPartSchema>;

export async function listStories(params: { status?: string } = {}): Promise<Story[]> {
  const searchParams = new URLSearchParams();
  if (params.status) {
    searchParams.set("status", params.status);
  }
  const search = searchParams.toString();
  const data = await apiFetch<unknown>(`/admin/stories${search ? `?${search}` : ""}`);
  return z.array(StorySchema).parse(data);
}

export async function getStory(id: number): Promise<Story> {
  const data = await apiFetch<unknown>(`/admin/stories/${id}`);
  return StorySchema.parse(data);
}

export async function updateStoryStatus(
  id: number,
  status: string,
  notes?: string,
): Promise<Story> {
  const data = await apiFetch<unknown>(`/admin/stories/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes }),
  });
  return StorySchema.parse(data);
}

export async function splitStory(
  id: number,
  parts: string[],
): Promise<StoryPart[]> {
  const data = await apiFetch<unknown>(`/admin/stories/${id}/split`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parts }),
  });
  return z.array(StoryPartSchema).parse(data);
}
