"use client";

import { useMemo, useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Release } from "@/lib/stories";
import { approveRelease, completeManualPublish, retryRelease } from "@/lib/stories";
import { ActionButton, EmptyState, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

function toLocalInputValue(value?: string | null): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  const normalized = new Date(date.getTime() - offset * 60_000);
  return normalized.toISOString().slice(0, 16);
}

function toIsoValue(value: string): string | null {
  if (!value) {
    return null;
  }
  return new Date(value).toISOString();
}

function releaseTone(status: Release["status"]): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "published") {
    return "success";
  }
  if (status === "errored") {
    return "danger";
  }
  if (status === "manual_handoff") {
    return "warning";
  }
  if (status === "publishing") {
    return "accent";
  }
  return "neutral";
}

function statusLabel(status: Release["status"]): string {
  if (status === "manual_handoff") {
    return "Manual handoff";
  }
  return status.replace("_", " ");
}

export default function PublishQueue({ releases }: { releases: Release[] }) {
  const queryClient = useQueryClient();
  const [titleDrafts, setTitleDrafts] = useState<Record<number, string>>({});
  const [descriptionDrafts, setDescriptionDrafts] = useState<Record<number, string>>({});
  const [hashtagDrafts, setHashtagDrafts] = useState<Record<number, string>>({});
  const [scheduleDrafts, setScheduleDrafts] = useState<Record<number, string>>({});
  const [videoIds, setVideoIds] = useState<Record<number, string>>({});
  const [manualNotes, setManualNotes] = useState<Record<number, string>>({});
  const [isPending, startTransition] = useTransition();

  const grouped = useMemo(
    () => ({
      ready: releases.filter((release) => release.status === "ready" || release.status === "approved"),
      scheduled: releases.filter((release) => release.status === "scheduled"),
      publishing: releases.filter((release) => release.status === "publishing"),
      errored: releases.filter((release) => release.status === "errored"),
      manual: releases.filter((release) => release.status === "manual_handoff"),
    }),
    [releases],
  );

  const mutate = (task: () => Promise<unknown>) => {
    startTransition(async () => {
      await task();
      await queryClient.invalidateQueries();
    });
  };

  const approve = (release: Release, scheduled: boolean) => {
    const publishAt = scheduled
      ? toIsoValue(scheduleDrafts[release.id] ?? toLocalInputValue(release.publish_at))
      : null;
    mutate(async () =>
      approveRelease(release.id, {
        title: titleDrafts[release.id] ?? release.title,
        description: descriptionDrafts[release.id] ?? release.description,
        hashtags: (hashtagDrafts[release.id] ?? (release.hashtags ?? []).join(", "))
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        publish_at: publishAt,
      }),
    );
  };

  const completeManual = (release: Release) => {
    mutate(async () =>
      completeManualPublish(release.id, {
        platform_video_id: videoIds[release.id] ?? "",
        notes: manualNotes[release.id],
      }),
    );
  };

  if (releases.length === 0) {
    return (
      <EmptyState
        title="No releases in this publish view"
        description="Rendered assets will land here once the renderer marks them ready for review, scheduling, or manual platform handoff."
      />
    );
  }

  const sections: Array<{ key: string; title: string; description: string; items: Release[] }> = [
    {
      key: "ready",
      title: "Ready for review",
      description: "Assets that have rendered cleanly and are waiting for approval or scheduling.",
      items: grouped.ready,
    },
    {
      key: "scheduled",
      title: "Scheduled",
      description: "Approved releases with a future publish time.",
      items: grouped.scheduled,
    },
    {
      key: "publishing",
      title: "Publishing",
      description: "Releases currently claimed by the publisher worker.",
      items: grouped.publishing,
    },
    {
      key: "errored",
      title: "Errored",
      description: "Items that need operator attention before another publish attempt.",
      items: grouped.errored,
    },
    {
      key: "manual",
      title: "Manual handoff",
      description: "Supervised releases waiting for a platform video id after operator posting.",
      items: grouped.manual,
    },
  ];

  return (
    <div className="space-y-6">
      {sections.map((section) => (
        <Panel key={section.key} className="space-y-4">
          <SectionHeading title={section.title} description={section.description} />
          {section.items.length === 0 ? (
            <div className="rounded-[1.2rem] border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-sm text-[var(--text-soft)]">
              Nothing in this lane right now.
            </div>
          ) : (
            <div className="space-y-4">
              {section.items.map((release) => (
                <Panel key={release.id} className="space-y-4 border-white/8 bg-black/10">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge tone={releaseTone(release.status)}>{statusLabel(release.status)}</StatusBadge>
                        <StatusBadge tone="neutral">{release.platform}</StatusBadge>
                        <StatusBadge tone="neutral">{release.variant}</StatusBadge>
                      </div>
                      <h2 className="text-xl font-semibold text-white">{release.title}</h2>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {release.signed_asset_url ? (
                        <a
                          href={release.signed_asset_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center justify-center rounded-full border border-white/12 bg-white/8 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/12"
                        >
                          Open asset
                        </a>
                      ) : null}
                    </div>
                  </div>

                  {release.signed_asset_url ? (
                    <video
                      controls
                      preload="metadata"
                      className="w-full rounded-[1.25rem] border border-white/10 bg-black/30"
                      src={release.signed_asset_url}
                    />
                  ) : null}

                  <div className="grid gap-3 xl:grid-cols-2">
                    <label className="space-y-2 text-sm text-[var(--text-soft)]">
                      <span className="block text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Title</span>
                      <input
                        value={titleDrafts[release.id] ?? release.title}
                        onChange={(event) =>
                          setTitleDrafts((current) => ({ ...current, [release.id]: event.target.value }))
                        }
                        className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                      />
                    </label>
                    <label className="space-y-2 text-sm text-[var(--text-soft)]">
                      <span className="block text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Hashtags</span>
                      <input
                        value={hashtagDrafts[release.id] ?? (release.hashtags ?? []).join(", ")}
                        onChange={(event) =>
                          setHashtagDrafts((current) => ({ ...current, [release.id]: event.target.value }))
                        }
                        placeholder="scarystories, nosleep"
                        className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                      />
                    </label>
                  </div>

                  <label className="space-y-2 text-sm text-[var(--text-soft)]">
                    <span className="block text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Description</span>
                    <textarea
                      value={descriptionDrafts[release.id] ?? release.description}
                      onChange={(event) =>
                        setDescriptionDrafts((current) => ({ ...current, [release.id]: event.target.value }))
                      }
                      rows={4}
                      className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                    />
                  </label>

                  {["ready", "approved", "scheduled"].includes(release.status) ? (
                    <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto]">
                      <label className="space-y-2 text-sm text-[var(--text-soft)]">
                        <span className="block text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Schedule</span>
                        <input
                          type="datetime-local"
                          value={scheduleDrafts[release.id] ?? toLocalInputValue(release.publish_at)}
                          onChange={(event) =>
                            setScheduleDrafts((current) => ({ ...current, [release.id]: event.target.value }))
                          }
                          className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                        />
                      </label>
                      <div className="flex items-end">
                        <ActionButton
                          onClick={() => approve(release, false)}
                          disabled={isPending || release.status === "publishing"}
                        >
                          Upload now
                        </ActionButton>
                      </div>
                      <div className="flex items-end">
                        <ActionButton
                          tone="secondary"
                          onClick={() => approve(release, true)}
                          disabled={isPending || !(scheduleDrafts[release.id] ?? toLocalInputValue(release.publish_at))}
                        >
                          Schedule
                        </ActionButton>
                      </div>
                    </div>
                  ) : null}

                  {release.status === "errored" ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[1rem] border border-rose-400/20 bg-rose-400/8 px-4 py-3">
                      <p className="text-sm text-rose-100">{release.last_error || "Last publish attempt failed."}</p>
                      <ActionButton tone="danger" onClick={() => mutate(async () => retryRelease(release.id))} disabled={isPending}>
                        Retry
                      </ActionButton>
                    </div>
                  ) : null}

                  {release.status === "manual_handoff" ? (
                    <div className="space-y-3 rounded-[1rem] border border-amber-400/18 bg-amber-400/10 p-4">
                      <p className="text-sm text-amber-100">
                        Manual post required. Finish the upload on-platform, then record the destination id here.
                      </p>
                      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                        <input
                          value={videoIds[release.id] ?? ""}
                          onChange={(event) =>
                            setVideoIds((current) => ({ ...current, [release.id]: event.target.value }))
                          }
                          placeholder="Platform video id"
                          className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                        />
                        <input
                          value={manualNotes[release.id] ?? ""}
                          onChange={(event) =>
                            setManualNotes((current) => ({ ...current, [release.id]: event.target.value }))
                          }
                          placeholder="Manual notes (optional)"
                          className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                        />
                        <ActionButton
                          onClick={() => completeManual(release)}
                          disabled={isPending || !(videoIds[release.id] ?? "").trim()}
                        >
                          Complete manual publish
                        </ActionButton>
                      </div>
                    </div>
                  ) : null}
                </Panel>
              ))}
            </div>
          )}
        </Panel>
      ))}
    </div>
  );
}
