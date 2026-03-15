import type {
  Asset,
  AssetBundle,
  Compilation,
  Job,
  Release,
  RenderArtifact,
  RenderPreset,
  ScriptVersion,
  Story,
  StoryOverview,
  StoryPart,
} from "@/lib/stories";

type MockState = {
  stories: Story[];
  scripts: ScriptVersion[];
  parts: StoryPart[];
  assets: Asset[];
  bundles: AssetBundle[];
  releases: Release[];
  artifacts: RenderArtifact[];
  jobs: Job[];
  compilations: Compilation[];
  presets: RenderPreset[];
};

function splitIntoParts(text: string, storyId: number, scriptVersionId: number): StoryPart[] {
  const chunks = text
    .split(/\n{2,}/)
    .map((chunk) => chunk.trim())
    .filter(Boolean);

  return chunks.map((body_md, index) => ({
    id: storyId * 100 + index + 1,
    story_id: storyId,
    script_version_id: scriptVersionId,
    asset_bundle_id: null,
    index: index + 1,
    body_md,
    script_text: body_md,
    est_seconds: Math.max(10, Math.round(body_md.split(/\s+/).length / 2.7)),
    approved: true,
  }));
}

function createStories(): MockState {
  const stories: Story[] = [
    {
      id: 2,
      title: "I Took the Last Night Shift at Blackwater Lake",
      status: "ingested",
      author: "u/midnightfisher",
      source_url: "https://reddit.com/r/nosleep/comments/example1",
      body_md:
        "The locals said the old launch station should have sunk twenty winters ago, but the lamps still came on every night at 11:47.\n\nI only took the shift because the county paid double for anyone willing to log the shoreline cameras until sunrise.\n\nAt 1:12 a.m. the monitors showed a woman on the dock, waist-deep in fog, holding a lantern under the water.",
      active_script_version_id: null,
      active_asset_bundle_id: null,
    },
    {
      id: 3,
      title: "My Brother Left Me a Tape That Knows the Future",
      status: "approved",
      author: "u/echoarchive",
      source_url: "https://reddit.com/r/nosleep/comments/example2",
      body_md:
        "My brother vanished three years ago, but every birthday a cassette arrives with his handwriting on the label.\n\nThis year's tape included tomorrow's weather, the exact train delay that stranded me downtown, and my own voice begging me not to answer the basement door.",
      active_script_version_id: 301,
      active_asset_bundle_id: null,
    },
    {
      id: 4,
      title: "The Apartment Above Mine Has Been Empty Since 1986",
      status: "media_ready",
      author: "u/hallwaystatic",
      source_url: "https://reddit.com/r/nosleep/comments/example3",
      body_md:
        "The lease office swears nobody has rented 4C in forty years, but every Thursday someone drags furniture across the ceiling for exactly seven minutes.\n\nTonight the noise stopped, and a typed note slid under my door asking why I had missed last week's meeting.",
      active_script_version_id: 401,
      active_asset_bundle_id: 41,
    },
    {
      id: 5,
      title: "We Found a Town on No Map During the Storm",
      status: "queued",
      author: "u/longroadhome",
      source_url: "https://reddit.com/r/nosleep/comments/example4",
      body_md:
        "Our GPS died on the mountain pass and rerouted us onto a road the state trooper later insisted did not exist.\n\nAt the bottom of the valley sat a church, a diner, and a welcome sign listing the population as 'still counting.'",
      active_script_version_id: 501,
      active_asset_bundle_id: 51,
    },
    {
      id: 6,
      title: "The Weekly Cut: Signals From the Dead Air Mile",
      status: "publish_ready",
      author: "ops",
      source_url: null,
      body_md:
        "A stitched weekly compilation is ready with subtitles, music, and metadata. Final operator pass only.",
      active_script_version_id: 601,
      active_asset_bundle_id: 61,
    },
  ];

  const story3 = stories.find((story) => story.id === 3)!;
  const story4 = stories.find((story) => story.id === 4)!;
  const story5 = stories.find((story) => story.id === 5)!;
  const story6 = stories.find((story) => story.id === 6)!;

  const scripts: ScriptVersion[] = [
    {
      id: 301,
      story_id: 3,
      source_text: story3.body_md ?? "",
      hook: "My missing brother still mails me cassette tapes on my birthday.",
      narration_text:
        "He disappeared three years ago, but every birthday another tape arrives with tomorrow's date and his handwriting on the label. This time it predicted the train delay, the rain, and my own voice begging me not to answer the basement door.",
      outro: "When the knocking started early, I already knew what the tape would say next.",
      model_name: "gpt-4.1-mini",
      prompt_version: "v5",
      is_active: true,
    },
    {
      id: 401,
      story_id: 4,
      source_text: story4.body_md ?? "",
      hook: "My upstairs neighbor has been dead since 1986, so who keeps moving furniture at 2 a.m.?",
      narration_text:
        "Nobody has rented 4C in forty years, but every Thursday someone drags furniture across my ceiling for seven exact minutes. Tonight the noise stopped, and a typed note slid under my door asking why I missed the meeting.",
      outro: "The return address on the envelope was my own apartment number.",
      model_name: "gpt-4.1-mini",
      prompt_version: "v5",
      is_active: true,
    },
    {
      id: 501,
      story_id: 5,
      source_text: story5.body_md ?? "",
      hook: "We got lost in a storm and drove into a town that officially does not exist.",
      narration_text:
        "The GPS died first. Then the radio. Then we found a valley town with a diner, a church, and a welcome sign that said the population was still counting. By dawn, the road back was gone.",
      outro: "The sheriff's report listed our car as recovered three counties away with no passengers inside.",
      model_name: "gpt-4.1-mini",
      prompt_version: "v5",
      is_active: true,
    },
    {
      id: 601,
      story_id: 6,
      source_text: story6.body_md ?? "",
      hook: "This week’s compilation is staged and ready for operator release.",
      narration_text:
        "Five stories rendered cleanly, the subtitle pass is aligned, and the weekly cut is waiting for final posting metadata.",
      outro: "All that remains is the publish handoff.",
      model_name: "gpt-4.1-mini",
      prompt_version: "v5",
      is_active: true,
    },
  ];

  const script301 = scripts.find((script) => script.id === 301)!;
  const script401 = scripts.find((script) => script.id === 401)!;
  const script501 = scripts.find((script) => script.id === 501)!;
  const script601 = scripts.find((script) => script.id === 601)!;

  const parts = [
    ...splitIntoParts(script301.narration_text, 3, 301),
    ...splitIntoParts(script401.narration_text, 4, 401),
    ...splitIntoParts(script501.narration_text, 5, 501),
    ...splitIntoParts(script601.narration_text, 6, 601),
  ];

  const assets: Asset[] = [
    {
      id: 11,
      story_id: 3,
      type: "image",
      remote_url:
        "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80",
      orientation: "vertical",
      tags: ["hallway", "basement", "tape"],
    },
    {
      id: 12,
      story_id: 3,
      type: "image",
      remote_url:
        "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?auto=format&fit=crop&w=900&q=80",
      orientation: "vertical",
      tags: ["rain", "platform", "night"],
    },
    {
      id: 21,
      story_id: 4,
      type: "image",
      remote_url:
        "https://images.unsplash.com/photo-1482192596544-9eb780fc7f66?auto=format&fit=crop&w=900&q=80",
      orientation: "vertical",
      tags: ["apartment", "door", "empty"],
    },
    {
      id: 22,
      story_id: 4,
      type: "image",
      remote_url:
        "https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=900&q=80",
      orientation: "vertical",
      tags: ["stairwell", "meeting", "paper"],
    },
    {
      id: 31,
      story_id: 5,
      type: "image",
      remote_url:
        "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=900&q=80",
      orientation: "vertical",
      tags: ["storm", "road", "valley"],
    },
    {
      id: 32,
      story_id: 5,
      type: "image",
      remote_url:
        "https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=900&q=80",
      orientation: "vertical",
      tags: ["diner", "neon", "night"],
    },
    {
      id: 41,
      story_id: 2,
      type: "image",
      remote_url:
        "https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=900&q=80",
      orientation: "vertical",
      tags: ["lake", "fog", "dock"],
    },
    {
      id: 42,
      story_id: 2,
      type: "image",
      remote_url:
        "https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=900&q=80",
      orientation: "vertical",
      tags: ["lantern", "shoreline", "night"],
    },
  ];

  const bundles: AssetBundle[] = [
    {
      id: 41,
      story_id: 4,
      name: "Primary night bundle",
      variant: "short",
      asset_ids: [21, 22],
      music_policy: "first",
      music_track: "low-tide.mp3",
    },
    {
      id: 51,
      story_id: 5,
      name: "Storm road bundle",
      variant: "short",
      asset_ids: [31, 32],
      music_policy: "first",
      music_track: "red-mile.mp3",
    },
    {
      id: 61,
      story_id: 6,
      name: "Weekly compilation bundle",
      variant: "weekly",
      asset_ids: [21, 31, 32],
      music_policy: "first",
      music_track: "ghost-radio.mp3",
    },
  ];

  const releases: Release[] = [
    {
      id: 701,
      story_id: 6,
      render_artifact_id: 801,
      platform: "youtube",
      variant: "weekly",
      title: "Dark Life Weekly: Signals From the Dead Air Mile",
      description:
        "Five rendered stories stitched for the weekly YouTube upload. Metadata approved and waiting for manual publish.",
      hashtags: ["#darklife", "#nosleep", "#horror"],
      status: "ready",
    },
  ];

  const artifacts: RenderArtifact[] = [
    {
      id: 801,
      story_id: 6,
      compilation_id: 901,
      variant: "weekly",
      video_path: "/output/weekly-dead-air-mile.mp4",
      subtitle_path: "/output/weekly-dead-air-mile.srt",
      duration_ms: 293000,
      bytes: 145000000,
      details: { preset: "weekly-full" },
    },
  ];

  const jobs: Job[] = [
    {
      id: 1001,
      story_id: 5,
      story_part_id: parts.find((part) => part.story_id === 5)?.id,
      kind: "render",
      variant: "short",
      status: "queued",
      payload: { preset_slug: "short-form" },
      result: null,
    },
    {
      id: 1002,
      story_id: 5,
      kind: "subtitles",
      variant: "short",
      status: "rendering",
      payload: { part_count: 2 },
      result: null,
    },
    {
      id: 1003,
      story_id: 6,
      compilation_id: 901,
      kind: "weekly-render",
      variant: "weekly",
      status: "rendered",
      payload: { preset_slug: "weekly-full" },
      result: { artifact_path: "/output/weekly-dead-air-mile.mp4" },
    },
  ];

  const compilations: Compilation[] = [
    {
      id: 901,
      story_id: 6,
      title: "Dark Life Weekly: Signals From the Dead Air Mile",
      status: "publish_ready",
      render_preset_id: 2,
    },
  ];

  const presets: RenderPreset[] = [
    {
      id: 1,
      slug: "short-form",
      name: "Shorts 9:16",
      variant: "short",
      width: 1080,
      height: 1920,
      fps: 30,
      burn_subtitles: false,
      target_min_seconds: 35,
      target_max_seconds: 58,
    },
    {
      id: 2,
      slug: "weekly-full",
      name: "Weekly Compilation",
      variant: "weekly",
      width: 1920,
      height: 1080,
      fps: 30,
      burn_subtitles: false,
      target_min_seconds: 240,
      target_max_seconds: 420,
    },
  ];

  return { stories, scripts, parts, assets, bundles, releases, artifacts, jobs, compilations, presets };
}

function ensureState(): MockState {
  const globalState = globalThis as typeof globalThis & { __darkLifeMockState?: MockState };
  if (!globalState.__darkLifeMockState) {
    globalState.__darkLifeMockState = createStories();
  }
  return globalState.__darkLifeMockState;
}

export function resetMockState() {
  const globalState = globalThis as typeof globalThis & { __darkLifeMockState?: MockState };
  globalState.__darkLifeMockState = createStories();
}

export function getState(): MockState {
  return ensureState();
}

export function getStoryOverview(storyId: number): StoryOverview | null {
  const state = ensureState();
  const story = state.stories.find((item) => item.id === storyId);
  if (!story) {
    return null;
  }

  const activeScript = state.scripts.find(
    (script) => script.story_id === storyId && script.id === story.active_script_version_id,
  );

  return {
    story,
    active_script: activeScript ?? null,
    parts: state.parts
      .filter((part) => part.story_id === storyId)
      .sort((a, b) => a.index - b.index),
    asset_bundles: state.bundles.filter((bundle) => bundle.story_id === storyId),
    releases: state.releases.filter((release) => release.story_id === storyId),
    artifacts: state.artifacts.filter((artifact) => artifact.story_id === storyId),
  };
}
