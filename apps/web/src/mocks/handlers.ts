import { http, HttpResponse } from "msw";
import type { StoryStatus } from "@dark-life/shared-types";
import { getState, getStoryOverview } from "./data";

function notFound(message = "Not found") {
  return HttpResponse.json({ detail: message }, { status: 404 });
}

function storyIdFrom(params: Record<string, string | readonly string[] | undefined>) {
  const value = params.id;
  if (Array.isArray(value)) {
    return Number(value[0]);
  }
  return Number(value);
}

function nextId(values: number[]) {
  return values.length ? Math.max(...values) + 1 : 1;
}

export const handlers = [
  http.get("/api/stories", ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") ?? "200");
    const status = url.searchParams.get("status");
    const state = getState();

    let stories = [...state.stories].sort((a, b) => a.id - b.id);
    if (status) {
      stories = stories.filter((story) => story.status === status);
    }

    return HttpResponse.json(stories.slice(0, limit));
  }),

  http.get("/api/stories/:id", ({ params }) => {
    const story = getState().stories.find((item) => item.id === storyIdFrom(params));
    return story ? HttpResponse.json(story) : notFound("Story not found");
  }),

  http.patch("/api/stories/:id", async ({ params, request }) => {
    const state = getState();
    const story = state.stories.find((item) => item.id === storyIdFrom(params));
    if (!story) {
      return notFound("Story not found");
    }

    const body = (await request.json()) as { status?: StoryStatus };
    if (body.status) {
      story.status = body.status;
    }

    return HttpResponse.json(story);
  }),

  http.get("/api/stories/:id/overview", ({ params }) => {
    const overview = getStoryOverview(storyIdFrom(params));
    return overview ? HttpResponse.json(overview) : notFound("Story overview not found");
  }),

  http.post("/api/stories/:id/script", ({ params }) => {
    const state = getState();
    const storyId = storyIdFrom(params);
    const story = state.stories.find((item) => item.id === storyId);
    if (!story) {
      return notFound("Story not found");
    }

    const existing = state.scripts.find((script) => script.story_id === storyId);
    if (existing) {
      story.status = "scripted";
      story.active_script_version_id = existing.id;
      return HttpResponse.json(existing);
    }

    const scriptId = nextId(state.scripts.map((script) => script.id));
    const sourceText = story.body_md ?? "";
    const script = {
      id: scriptId,
      story_id: storyId,
      source_text: sourceText,
      hook: `They told me ${story.title.toLowerCase()}, and I should have listened.`,
      narration_text: sourceText,
      outro: "By sunrise I understood why nobody else would take the shift.",
      model_name: "gpt-4.1-mini",
      prompt_version: "v5",
      is_active: true,
    };
    state.scripts.push(script);
    story.active_script_version_id = scriptId;
    story.status = "scripted";

    const chunks = sourceText
      .split(/\n{2,}/)
      .map((chunk) => chunk.trim())
      .filter(Boolean);
    state.parts = state.parts.filter((part) => part.story_id !== storyId);
    chunks.forEach((body_md, index) => {
      state.parts.push({
        id: storyId * 100 + index + 1,
        story_id: storyId,
        script_version_id: scriptId,
        asset_bundle_id: null,
        index: index + 1,
        body_md,
        script_text: body_md,
        est_seconds: Math.max(10, Math.round(body_md.split(/\s+/).length / 2.7)),
        approved: true,
      });
    });

    return HttpResponse.json(script, { status: 201 });
  }),

  http.put("/api/stories/:id/parts", async ({ params, request }) => {
    const state = getState();
    const storyId = storyIdFrom(params);
    const story = state.stories.find((item) => item.id === storyId);
    if (!story) {
      return notFound("Story not found");
    }

    const scriptVersionId = story.active_script_version_id;
    const body = (await request.json()) as Array<{ body_md: string; approved: boolean }>;
    state.parts = state.parts.filter((part) => part.story_id !== storyId);
    body.forEach((part, index) => {
      state.parts.push({
        id: storyId * 100 + index + 1,
        story_id: storyId,
        script_version_id: scriptVersionId ?? null,
        asset_bundle_id: story.active_asset_bundle_id ?? null,
        index: index + 1,
        body_md: part.body_md,
        script_text: part.body_md,
        est_seconds: Math.max(10, Math.round(part.body_md.split(/\s+/).length / 2.7)),
        approved: part.approved,
      });
    });

    return HttpResponse.json(
      state.parts.filter((part) => part.story_id === storyId).sort((a, b) => a.index - b.index),
    );
  }),

  http.get("/api/stories/:id/assets", ({ params }) => {
    const storyId = storyIdFrom(params);
    return HttpResponse.json(
      getState().assets.filter((asset) => asset.story_id === storyId || asset.story_id === 2),
    );
  }),

  http.post("/api/stories/:id/assets/index", ({ params }) => {
    const storyId = storyIdFrom(params);
    return HttpResponse.json(
      getState().assets.filter((asset) => asset.story_id === storyId || asset.story_id === 2),
    );
  }),

  http.post("/api/stories/:id/asset-bundles", async ({ params, request }) => {
    const state = getState();
    const storyId = storyIdFrom(params);
    const story = state.stories.find((item) => item.id === storyId);
    if (!story) {
      return notFound("Story not found");
    }

    const body = (await request.json()) as {
      name: string;
      asset_ids: number[];
      variant?: "short" | "weekly";
      music_policy?: string;
      music_track?: string | null;
    };

    const bundle = {
      id: nextId(state.bundles.map((item) => item.id)),
      story_id: storyId,
      name: body.name,
      variant: body.variant ?? "short",
      asset_ids: body.asset_ids,
      music_policy: body.music_policy ?? "first",
      music_track: body.music_track ?? null,
    };

    state.bundles = state.bundles.filter((item) => !(item.story_id === storyId && item.variant === bundle.variant));
    state.bundles.push(bundle);
    story.active_asset_bundle_id = bundle.id;
    story.status = "media_ready";
    state.parts = state.parts.map((part) =>
      part.story_id === storyId ? { ...part, asset_bundle_id: bundle.id } : part,
    );

    return HttpResponse.json(bundle, { status: 201 });
  }),

  http.get("/api/render-presets", () => HttpResponse.json(getState().presets)),

  http.post("/api/stories/:id/releases", async ({ params, request }) => {
    const state = getState();
    const storyId = storyIdFrom(params);
    const story = state.stories.find((item) => item.id === storyId);
    if (!story) {
      return notFound("Story not found");
    }

    const body = (await request.json()) as {
      platforms: string[];
      preset_slug: string;
      asset_bundle_id?: number | null;
    };

    const created = body.platforms.map((platform, index) => ({
      id: nextId(state.releases.map((item) => item.id)) + index,
      story_id: storyId,
      story_part_id: state.parts.find((part) => part.story_id === storyId)?.id ?? null,
      render_artifact_id: null,
      platform,
      variant: "short" as const,
      title: `${story.title} (${platform})`,
      description: `Generated from preset ${body.preset_slug}.`,
      hashtags: ["#darklife", "#horror"],
      status: "draft" as const,
    }));

    state.releases.push(...created);
    state.jobs.push(
      ...created.map((release, index) => ({
        id: nextId(state.jobs.map((job) => job.id)) + index,
        story_id: storyId,
        story_part_id: release.story_part_id ?? null,
        kind: "render",
        variant: "short" as const,
        status: "queued" as const,
        payload: {
          platform: release.platform,
          preset_slug: body.preset_slug,
          asset_bundle_id: body.asset_bundle_id ?? story.active_asset_bundle_id ?? null,
        },
        result: null,
      })),
    );
    story.status = "queued";

    return HttpResponse.json(created, { status: 201 });
  }),

  http.post("/api/stories/:id/compilations", async ({ params, request }) => {
    const state = getState();
    const storyId = storyIdFrom(params);
    const story = state.stories.find((item) => item.id === storyId);
    if (!story) {
      return notFound("Story not found");
    }

    const body = (await request.json()) as { preset_slug: string; platforms: string[] };
    const compilation = {
      id: nextId(state.compilations.map((item) => item.id)),
      story_id: storyId,
      title: `${story.title} Weekly`,
      status: "queued" as const,
      render_preset_id:
        state.presets.find((preset) => preset.slug === body.preset_slug)?.id ?? null,
    };
    state.compilations.push(compilation);
    state.jobs.push({
      id: nextId(state.jobs.map((job) => job.id)),
      story_id: storyId,
      compilation_id: compilation.id,
      kind: "weekly-render",
      variant: "weekly",
      status: "queued",
      payload: { platforms: body.platforms, preset_slug: body.preset_slug },
      result: null,
    });

    return HttpResponse.json(compilation, { status: 201 });
  }),

  http.get("/api/jobs", ({ request }) => {
    const url = new URL(request.url);
    const storyId = Number(url.searchParams.get("story_id"));
    const jobs = getState().jobs
      .filter((job) => (!Number.isFinite(storyId) ? true : job.story_id === storyId))
      .sort((a, b) => b.id - a.id);
    return HttpResponse.json(jobs);
  }),

  http.get("/api/releases/queue", () => {
    return HttpResponse.json(getState().releases.filter((release) => release.status === "ready"));
  }),

  http.post("/api/releases/:id/publish", async ({ params, request }) => {
    const state = getState();
    const releaseId = Number(params.id);
    const release = state.releases.find((item) => item.id === releaseId);
    if (!release) {
      return notFound("Release not found");
    }

    const body = (await request.json()) as { platform_video_id?: string };
    release.status = "published";
    release.description = body.platform_video_id
      ? `${release.description}\n\nPublished with platform id ${body.platform_video_id}.`
      : release.description;
    return HttpResponse.json(release);
  }),
];
