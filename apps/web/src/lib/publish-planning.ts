import type { PublishPlatformSettings, Release, Story } from "./stories";

const DEFAULT_SHORTS_PER_STORY = 5;
const TARGET_QUEUE_DAYS = 30;

function isQueuedShort(release: Release): boolean {
  return (
    release.variant === "short" &&
    ["ready", "approved", "scheduled", "publishing", "manual_handoff", "errored"].includes(release.status)
  );
}

export interface QueueRunwaySummary {
  slotsPerDay: number;
  queuedShorts: number;
  queuedDays: number;
  targetDays: number;
  targetShorts: number;
  shortageShorts: number;
  averageShortsPerStory: number;
  storiesNeededApprox: number;
  reviewableStoriesNow: number;
}

export function buildQueueRunwaySummary(
  releases: Release[],
  stories: Story[],
  publishSettings?: PublishPlatformSettings | null,
): QueueRunwaySummary {
  const slotsPerDay = Math.max(publishSettings?.short_slots_utc?.length ?? 0, 1);
  const queuedShorts = releases.filter(isQueuedShort).length;
  const queuedStoryIds = new Set(releases.filter(isQueuedShort).map((release) => release.story_id));
  const averageShortsPerStory =
    queuedStoryIds.size > 0 ? queuedShorts / queuedStoryIds.size : DEFAULT_SHORTS_PER_STORY;
  const targetShorts = TARGET_QUEUE_DAYS * slotsPerDay;
  const shortageShorts = Math.max(targetShorts - queuedShorts, 0);
  const storiesNeededApprox = Math.ceil(shortageShorts / Math.max(averageShortsPerStory, 1));
  const reviewableStoriesNow = stories.filter((story) => story.status === "ingested").length;

  return {
    slotsPerDay,
    queuedShorts,
    queuedDays: queuedShorts / slotsPerDay,
    targetDays: TARGET_QUEUE_DAYS,
    targetShorts,
    shortageShorts,
    averageShortsPerStory,
    storiesNeededApprox,
    reviewableStoriesNow,
  };
}
