import type { StoryStatus } from "@dark-life/shared-types";

export const WORKFLOW_STEPS: StoryStatus[] = [
  "ingested",
  "scripted",
  "approved",
  "media_ready",
  "queued",
  "rendering",
  "rendered",
  "publish_ready",
  "published",
];

export const STATUS_LABELS: Record<StoryStatus, string> = {
  ingested: "Ingested",
  scripted: "Scripted",
  approved: "Approved",
  media_ready: "Media Ready",
  queued: "Queued",
  rendering: "Rendering",
  rendered: "Rendered",
  publish_ready: "Publish Ready",
  published: "Published",
  rejected: "Rejected",
  errored: "Errored",
};

const STORY_STATUS_TRANSITIONS: Record<StoryStatus, StoryStatus[]> = {
  ingested: ["scripted", "rejected", "errored"],
  scripted: ["approved", "rejected", "errored"],
  approved: ["media_ready", "rejected", "errored"],
  media_ready: ["queued", "rejected", "errored"],
  queued: ["rendering", "errored"],
  rendering: ["rendered", "errored"],
  rendered: ["publish_ready", "errored"],
  publish_ready: ["published", "errored"],
  published: [],
  rejected: [],
  errored: ["ingested", "scripted", "approved"],
};

export function canTransitionStory(current: StoryStatus, next: StoryStatus): boolean {
  return STORY_STATUS_TRANSITIONS[current].includes(next);
}

export function canGenerateScript(status: StoryStatus): boolean {
  return ["ingested", "scripted", "approved", "errored"].includes(status);
}

export function canApproveStory(
  status: StoryStatus,
  hasActiveScript: boolean,
): boolean {
  return hasActiveScript && canTransitionStory(status, "approved");
}

export function canRejectStory(status: StoryStatus): boolean {
  return canTransitionStory(status, "rejected");
}

export function canEditParts(status: StoryStatus, hasActiveScript: boolean): boolean {
  return hasActiveScript && ["scripted", "approved"].includes(status);
}

export function canManageMedia(status: StoryStatus): boolean {
  return ["approved", "media_ready"].includes(status);
}

export function canQueueRenders(status: StoryStatus): boolean {
  return status === "media_ready";
}

export function isReviewableStatus(status: StoryStatus): boolean {
  return !["rejected", "published"].includes(status);
}

export function findNextReviewStoryId(
  stories: Array<{ id: number; status: StoryStatus }>,
  currentId: number,
): number | null {
  const currentIndex = stories.findIndex((story) => story.id === currentId);
  const ordered =
    currentIndex >= 0
      ? [...stories.slice(currentIndex + 1), ...stories.slice(0, currentIndex)]
      : stories;
  return ordered.find((story) => story.id !== currentId && isReviewableStatus(story.status))?.id ?? null;
}

export function workflowStepState(
  current: StoryStatus,
  step: StoryStatus,
): "done" | "active" | "upcoming" | "terminal" {
  if (current === "rejected" || current === "errored") {
    return step === current ? "terminal" : "upcoming";
  }
  const currentIndex = WORKFLOW_STEPS.indexOf(current);
  const stepIndex = WORKFLOW_STEPS.indexOf(step);
  if (stepIndex < 0 || currentIndex < 0) {
    return "upcoming";
  }
  if (stepIndex < currentIndex) {
    return "done";
  }
  if (stepIndex === currentIndex) {
    return "active";
  }
  return "upcoming";
}

export function statusTone(
  status: StoryStatus,
): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (["publish_ready", "published", "rendered"].includes(status)) {
    return "success";
  }
  if (["approved", "media_ready", "queued", "rendering"].includes(status)) {
    return "accent";
  }
  if (status === "rejected" || status === "errored") {
    return "danger";
  }
  if (status === "scripted") {
    return "warning";
  }
  return "neutral";
}

export function nextWorkspaceRoute(
  status: StoryStatus,
  storyId: number,
  hasBundle = false,
): string {
  if (status === "ingested" || status === "scripted") {
    return `/story/${storyId}/review`;
  }
  if (status === "approved") {
    return `/story/${storyId}/media`;
  }
  if (status === "media_ready") {
    return `/story/${storyId}/queue`;
  }
  if (status === "queued" || status === "rendering" || status === "rendered") {
    return `/story/${storyId}/jobs`;
  }
  if (status === "publish_ready" || status === "published") {
    return hasBundle ? `/story/${storyId}/jobs` : `/story/${storyId}/review`;
  }
  return `/story/${storyId}/review`;
}
