"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { StoryStatus } from "@dark-life/shared-types";
import { listStories, updateStoryStatus, type Story } from "@/lib/stories";

const STATUSES: StoryStatus[] = [
  "ingested",
  "scripted",
  "media_ready",
  "queued",
  "publish_ready",
];

export default function KanbanBoard() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["stories"],
    queryFn: () => listStories(),
  });

  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: StoryStatus }) =>
      updateStoryStatus(id, status),
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ["stories"] });
      const previous = queryClient.getQueryData<Story[]>(["stories"]);
      queryClient.setQueryData<Story[]>(["stories"], (old) =>
        old ? old.map((story) => (story.id === id ? { ...story, status } : story)) : old,
      );
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["stories"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["stories"] });
    },
  });

  if (isLoading) return <p>Loading...</p>;
  if (isError) return <p>Failed to load stories.</p>;
  const stories = data ?? [];

  return (
    <div className="grid gap-4 xl:grid-cols-5" data-testid="kanban-board">
      {STATUSES.map((status) => (
        <div
          key={status}
          className="min-h-80 rounded-3xl border border-zinc-800 bg-zinc-950/70 p-4"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            const id = Number(event.dataTransfer.getData("text/plain"));
            if (id) {
              mutation.mutate({ id, status });
            }
          }}
        >
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.25em] text-zinc-400">
            {status}
          </h2>
          <ul className="space-y-3">
            {stories
              .filter((story) => story.status === status)
              .map((story) => (
                <li key={story.id}>
                  <div
                    draggable
                    onDragStart={(event) =>
                      event.dataTransfer.setData("text/plain", String(story.id))
                    }
                    tabIndex={0}
                    className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-3 text-sm text-zinc-100"
                  >
                    {story.title}
                  </div>
                </li>
              ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
