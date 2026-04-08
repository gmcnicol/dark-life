import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  activatePromptVersion,
  archivePromptVersion,
  getPublishPlatformSettings,
  listPromptVersions,
  updatePublishPlatformSettings,
} from "@/lib/stories";
import { ActionButton, LoadingState, PageHeader, Panel, SectionHeading, StatusBadge } from "@/components/ui-surfaces";

export default function SettingsRoute() {
  const queryClient = useQueryClient();
  const platformSettingsQuery = useQuery({
    queryKey: ["publish-platform-settings"],
    queryFn: getPublishPlatformSettings,
  });
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

  const updatePlatformsMutation = useMutation({
    mutationFn: (activePlatforms: string[]) => updatePublishPlatformSettings({ active_platforms: activePlatforms }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["publish-platform-settings"] });
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
  const platformSettings = platformSettingsQuery.data;
  const activePlatforms = platformSettings?.active_platforms ?? [];

  const togglePlatform = (platform: string) => {
    const nextPlatforms = activePlatforms.includes(platform)
      ? activePlatforms.filter((candidate) => candidate !== platform)
      : [...activePlatforms, platform];
    updatePlatformsMutation.mutate(nextPlatforms);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operating defaults"
        title="Studio settings"
        description="Prompt registry governance now lives here. Review active and draft generator, critic, analyst, template, and selection-policy versions before activating changes."
      />
      <Panel className="space-y-4">
        <SectionHeading
          eyebrow="Targets"
          title="Publish platforms"
          description="Choose which short-form destinations the queue should target by default. Weekly compilation remains YouTube-only."
        />
        {platformSettings ? (
          <div className="grid gap-3 md:grid-cols-3">
            {platformSettings.available_platforms.map((platform) => {
              const active = activePlatforms.includes(platform);
              const isOnlyActive = active && activePlatforms.length === 1;
              const label = platform === "youtube" ? "YouTube" : platform === "instagram" ? "Instagram" : "TikTok";
              return (
                <button
                  key={platform}
                  type="button"
                  onClick={() => togglePlatform(platform)}
                  disabled={updatePlatformsMutation.isPending || isOnlyActive}
                  className={[
                    "rounded-[1.2rem] border px-4 py-4 text-left transition",
                    active
                      ? "border-cyan-300/35 bg-cyan-300/[0.12]"
                      : "border-white/8 bg-white/[0.03] hover:border-white/14 hover:bg-white/[0.05]",
                    updatePlatformsMutation.isPending || isOnlyActive ? "opacity-70" : "",
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-white">{label}</p>
                    <StatusBadge tone={active ? "success" : "neutral"}>{active ? "Active" : "Inactive"}</StatusBadge>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-soft)]">
                    {platform === "youtube"
                      ? "Supports automated shorts and the weekly compilation."
                      : platform === "instagram"
                        ? "Supports automated short-form publishing."
                        : "Uses the manual handoff flow after render approval."}
                  </p>
                </button>
              );
            })}
          </div>
        ) : (
          <LoadingState label="Loading publish platforms…" className="min-h-28" />
        )}
        {updatePlatformsMutation.isError ? (
          <p className="text-sm text-rose-200">
            {updatePlatformsMutation.error instanceof Error
              ? updatePlatformsMutation.error.message
              : "Unable to update publish platforms."}
          </p>
        ) : null}
      </Panel>
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
