import type {
  JobStatus,
  ReleaseStatus,
  RenderVariant,
  StoryStatus,
} from "@dark-life/shared-types";
import { apiFetch } from "./api";

export interface Story {
  id: number;
  title: string;
  body_md?: string | null;
  status: StoryStatus;
  source_url?: string | null;
  author?: string | null;
  active_script_version_id?: number | null;
  active_asset_bundle_id?: number | null;
}

export interface ScriptVersion {
  id: number;
  story_id: number;
  source_text: string;
  hook: string;
  narration_text: string;
  outro: string;
  model_name: string;
  prompt_version: string;
  is_active: boolean;
}

export interface StoryPart {
  id: number;
  story_id: number;
  script_version_id?: number | null;
  asset_bundle_id?: number | null;
  index: number;
  body_md: string;
  script_text: string;
  est_seconds: number;
  approved: boolean;
}

export interface Asset {
  id: number;
  story_id?: number | null;
  type: "image" | "video";
  local_path?: string | null;
  remote_url?: string | null;
  attribution?: string | null;
  orientation?: string | null;
  duration_ms?: number | null;
  tags?: string[] | null;
}

export interface AssetBundle {
  id: number;
  story_id: number;
  name: string;
  variant: RenderVariant;
  asset_ids: number[];
  music_policy: string;
  music_track?: string | null;
}

export interface RenderPreset {
  id: number;
  slug: string;
  name: string;
  variant: RenderVariant;
  width: number;
  height: number;
  fps: number;
  burn_subtitles: boolean;
  target_min_seconds: number;
  target_max_seconds: number;
}

export interface Release {
  id: number;
  story_id: number;
  story_part_id?: number | null;
  compilation_id?: number | null;
  render_artifact_id?: number | null;
  platform: string;
  variant: RenderVariant;
  title: string;
  description: string;
  hashtags?: string[] | null;
  status: ReleaseStatus;
}

export interface Compilation {
  id: number;
  story_id: number;
  title: string;
  status: StoryStatus;
  render_preset_id?: number | null;
}

export interface RenderArtifact {
  id: number;
  story_id: number;
  story_part_id?: number | null;
  compilation_id?: number | null;
  variant: RenderVariant;
  video_path: string;
  subtitle_path?: string | null;
  duration_ms?: number | null;
  bytes?: number | null;
  details?: Record<string, unknown> | null;
}

export interface Job {
  id: number;
  story_id?: number | null;
  story_part_id?: number | null;
  compilation_id?: number | null;
  kind: string;
  variant: RenderVariant;
  status: JobStatus;
  payload?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
}

export interface StoryOverview {
  story: Story;
  active_script: ScriptVersion | null;
  parts: StoryPart[];
  asset_bundles: AssetBundle[];
  releases: Release[];
  artifacts: RenderArtifact[];
}

export async function listStories(params: { status?: string } = {}): Promise<Story[]> {
  const searchParams = new URLSearchParams();
  if (params.status) {
    searchParams.set("status", params.status);
  }
  const search = searchParams.toString();
  return apiFetch<Story[]>(`/stories${search ? `?${search}` : ""}`);
}

export async function getStory(id: number): Promise<Story> {
  return apiFetch<Story>(`/stories/${id}`);
}

export async function getStoryOverview(id: number): Promise<StoryOverview> {
  return apiFetch<StoryOverview>(`/stories/${id}/overview`);
}

export async function updateStoryStatus(id: number, status: StoryStatus): Promise<Story> {
  return apiFetch<Story>(`/stories/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function generateScript(id: number): Promise<ScriptVersion> {
  return apiFetch<ScriptVersion>(`/stories/${id}/script`, { method: "POST" });
}

export async function replaceStoryParts(
  id: number,
  parts: Array<{ body_md: string; approved: boolean }>,
): Promise<StoryPart[]> {
  return apiFetch<StoryPart[]>(`/stories/${id}/parts`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parts),
  });
}

export async function listStoryAssets(id: number): Promise<Asset[]> {
  return apiFetch<Asset[]>(`/stories/${id}/assets`);
}

export async function indexStoryAssets(id: number): Promise<Asset[]> {
  return apiFetch<Asset[]>(`/stories/${id}/assets/index`, { method: "POST" });
}

export async function listLibraryAssets(params: {
  q?: string;
  type?: string;
} = {}): Promise<Asset[]> {
  const search = new URLSearchParams();
  if (params.q) {
    search.set("q", params.q);
  }
  if (params.type) {
    search.set("type", params.type);
  }
  const suffix = search.toString();
  return apiFetch<Asset[]>(`/assets/library${suffix ? `?${suffix}` : ""}`);
}

export async function createAssetBundle(
  id: number,
  payload: {
    name: string;
    asset_ids: number[];
    variant?: RenderVariant;
    music_policy?: string;
    music_track?: string | null;
  },
): Promise<AssetBundle> {
  return apiFetch<AssetBundle>(`/stories/${id}/asset-bundles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listRenderPresets(): Promise<RenderPreset[]> {
  return apiFetch<RenderPreset[]>("/render-presets");
}

export async function createShortReleases(
  id: number,
  payload: { platforms: string[]; preset_slug: string; asset_bundle_id?: number | null },
): Promise<Release[]> {
  return apiFetch<Release[]>(`/stories/${id}/releases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function createCompilation(
  id: number,
  payload: { preset_slug: string; platforms: string[] },
): Promise<Compilation> {
  return apiFetch<Compilation>(`/stories/${id}/compilations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listJobs(params: { story_id?: number } = {}): Promise<Job[]> {
  const search = new URLSearchParams();
  if (params.story_id) {
    search.set("story_id", String(params.story_id));
  }
  const qs = search.toString();
  return apiFetch<Job[]>(`/jobs${qs ? `?${qs}` : ""}`);
}

export async function listReleaseQueue(): Promise<Release[]> {
  return apiFetch<Release[]>("/releases/queue");
}

export async function publishRelease(
  releaseId: number,
  platformVideoId?: string,
): Promise<Release> {
  return apiFetch<Release>(`/releases/${releaseId}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ platform_video_id: platformVideoId }),
  });
}
