import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  activatePromptVersion,
  archivePromptVersion,
  listPromptVersions,
} from "@/lib/stories";
import { ActionButton, LoadingState, PageHeader, Panel, SectionHeading, StatusBadge } from "@/components/ui-surfaces";

export default function SettingsRoute() {
  const queryClient = useQueryClient();
  const promptsQuery = useQuery({
    queryKey: ["prompt-versions"],
    queryFn: () => listPromptVersions(),
  });

  const activateMutation = useMutation({
    mutationFn: (id: number) => activatePromptVersion(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["prompt-versions"] });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: (id: number) => archivePromptVersion(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["prompt-versions"] });
    },
  });

  if (promptsQuery.isLoading) {
    return <LoadingState label="Loading settings…" className="min-h-56" />;
  }

  const prompts = promptsQuery.data ?? [];
  const grouped = prompts.reduce<Record<string, typeof prompts>>((acc, prompt) => {
    const bucket = acc[prompt.kind] ?? [];
    bucket.push(prompt);
    acc[prompt.kind] = bucket;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operating defaults"
        title="Studio settings"
        description="Prompt registry governance now lives here. Review active and draft generator, critic, analyst, template, and selection-policy versions before activating changes."
      />
      <div className="grid gap-4 xl:grid-cols-2">
        {Object.entries(grouped).map(([kind, versions]) => (
          <Panel key={kind} className="space-y-4">
            <SectionHeading
              eyebrow="Prompt registry"
              title={kind}
              description="Drafts come from the analyst loop. Activation is explicit and never automatic."
            />
            <div className="space-y-3">
              {versions.map((version) => (
                <div key={version.id} className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{version.version_label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                        {version.status}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <StatusBadge tone={version.status === "active" ? "success" : version.status === "draft" ? "warning" : "neutral"}>
                        {version.status}
                      </StatusBadge>
                      {version.status !== "active" ? (
                        <ActionButton
                          tone="secondary"
                          onClick={() => activateMutation.mutate(version.id)}
                          disabled={activateMutation.isPending}
                        >
                          Activate
                        </ActionButton>
                      ) : null}
                      {version.status !== "archived" ? (
                        <ActionButton
                          tone="ghost"
                          onClick={() => archiveMutation.mutate(version.id)}
                          disabled={archiveMutation.isPending}
                        >
                          Archive
                        </ActionButton>
                      ) : null}
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[var(--text-soft)]">{version.body}</p>
                </div>
              ))}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
