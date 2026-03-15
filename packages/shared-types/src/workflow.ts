export const STORY_STATUSES = [
  "ingested",
  "scripted",
  "approved",
  "media_ready",
  "queued",
  "rendering",
  "rendered",
  "publish_ready",
  "published",
  "rejected",
  "errored",
] as const;

export type StoryStatus = (typeof STORY_STATUSES)[number];

export const JOB_STATUSES = [
  "queued",
  "claimed",
  "rendering",
  "rendered",
  "publish_ready",
  "published",
  "errored",
] as const;

export type JobStatus = (typeof JOB_STATUSES)[number];

export const RELEASE_STATUSES = ["draft", "ready", "published", "failed"] as const;
export type ReleaseStatus = (typeof RELEASE_STATUSES)[number];

export const RENDER_VARIANTS = ["short", "weekly"] as const;
export type RenderVariant = (typeof RENDER_VARIANTS)[number];

export const ASSET_KINDS = ["image", "video"] as const;
export type AssetKind = (typeof ASSET_KINDS)[number];
