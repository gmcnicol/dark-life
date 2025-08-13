"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listStories, updateStoryStatus, type Story } from "@/lib/stories";
import { logEvent } from "@/lib/log";

const STATUSES = ["pending", "approved", "rejected"] as const;

export default function KanbanBoard() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["stories"],
    queryFn: () => listStories(),
  });

  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      updateStoryStatus(id, status),
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ["stories"] });
      const previous = queryClient.getQueryData<Story[]>(["stories"]);
      queryClient.setQueryData<Story[]>(["stories"], (old) =>
        old ? old.map((s) => (s.id === id ? { ...s, status } : s)) : old,
      );
      logEvent("status_change", { id, status });
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(["stories"], ctx.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["stories"] });
    },
  });

  if (isLoading) return <p>Loading...</p>;
  if (isError) return <p>Failed to load stories.</p>;
  const stories = data ?? [];
  if (stories.length === 0) return <p>No stories.</p>;

  return (
    <div className="flex gap-4" data-testid="kanban-board">
      {STATUSES.map((status) => (
        <div
          key={status}
          className="flex-1 bg-muted p-2 rounded"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            const id = Number(e.dataTransfer.getData("text/plain"));
            if (id) {
              mutation.mutate({ id, status });
            }
          }}
        >
          <h2 className="font-semibold mb-2 capitalize">{status}</h2>
          <ul className="space-y-2 min-h-32">
            {stories
              .filter((s) => s.status === status)
              .map((story) => (
                <li key={story.id}>
                  <div
                    draggable
                    onDragStart={(e) =>
                      e.dataTransfer.setData("text/plain", String(story.id))
                    }
                    tabIndex={0}
                    className="p-2 bg-background rounded shadow cursor-move focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
