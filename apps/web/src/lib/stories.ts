import type {
  JobStatus,
  ReleaseStatus,
  RenderVariant,
  StoryStatus,
} from "@dark-life/shared-types";
import { adminFetch, apiFetch } from "./api";

export interface Story {
  id: number;
  title: string;
  body_md?: string | null;
  status: StoryStatus;
  source_url?: string | null;
  author?: string | null;
  created_utc?: string | null;
  active_script_version_id?: number | null;
  active_asset_bundle_id?: number | null;
}

export interface ScriptVersion {
  id: number;
  story_id: number;
  batch_id?: number | null;
  concept_id?: number | null;
  source_text: string;
  hook: string;
  narration_text: string;
  outro: string;
  model_name: string;
  prompt_version: string;
  template_version?: string;
  critic_version?: string;
  selection_policy_version?: string;
  temperature?: number;
  selection_state?: string;
  critic_scores?: Record<string, unknown> | null;
  performance_metrics?: Record<string, unknown> | null;
  derived_metrics?: Record<string, unknown> | null;
  generation_metadata?: Record<string, unknown> | null;
  critic_rank?: number | null;
  performance_rank?: number | null;
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
  episode_type?: string;
  hook?: string;
  lines?: string[] | null;
  loop_line?: string;
  features?: Record<string, unknown> | null;
  critic_scores?: Record<string, unknown> | null;
  performance_metrics?: Record<string, unknown> | null;
  derived_metrics?: Record<string, unknown> | null;
}

export interface MediaRef {
  key: string;
  story_id?: number | null;
  type: "image" | "video";
  local_path?: string | null;
  remote_url?: string | null;
  provider?: string | null;
  provider_id?: string | null;
  attribution?: string | null;
  orientation?: string | null;
  duration_ms?: number | null;
  width?: number | null;
  height?: number | null;
  tags?: string[] | null;
}

export interface Asset extends MediaRef {
  id: number;
}

export interface AssetBundle {
  id: number;
  story_id: number;
  name: string;
  variant: RenderVariant;
  asset_refs: MediaRef[];
  part_asset_map: Array<{ story_part_id: number; asset: MediaRef }>;
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
  script_version_id?: number | null;
  compilation_id?: number | null;
  render_artifact_id?: number | null;
  platform: string;
  variant: RenderVariant;
  title: string;
  description: string;
  hashtags?: string[] | null;
  status: ReleaseStatus;
  publish_status: ReleaseStatus;
  approval_status: "pending" | "approved";
  delivery_mode: "automated" | "manual";
  platform_video_id?: string | null;
  publish_at?: string | null;
  approved_at?: string | null;
  published_at?: string | null;
  last_error?: string | null;
  attempt_count: number;
  provider_metadata?: Record<string, unknown> | null;
  artifact_path?: string | null;
  signed_asset_url?: string | null;
  publish_job_id?: number | null;
  early_signal?: {
    window_hours: number;
    state: "monitor" | "flat" | "winner" | string;
    score: number;
    recommended_action: string;
    summary: string;
    evaluated_at?: string | null;
    metrics: Record<string, number>;
  } | null;
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
  error_class?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface StoryOverview {
  story: Story;
  active_script: ScriptVersion | null;
  script_versions: ScriptVersion[];
  script_batches: ScriptBatch[];
  parts: StoryPart[];
  asset_bundles: AssetBundle[];
  releases: Release[];
  artifacts: RenderArtifact[];
}

export interface StoryConcept {
  id: number;
  story_id: number;
  concept_key: string;
  concept_label: string;
  anomaly_type: string;
  object_focus?: string | null;
  specificity: string;
}

export interface ScriptBatch {
  id: number;
  story_id: number;
  concept_id?: number | null;
  status: string;
  candidate_count: number;
  shortlisted_count: number;
  template_version: string;
  prompt_version: string;
  critic_version: string;
  selection_policy_version: string;
  analyst_version: string;
  model_name: string;
  temperature: number;
  config?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  error_message?: string | null;
}

export interface ScriptBatchDetail {
  batch: ScriptBatch;
  concept: StoryConcept | null;
  candidates: Array<ScriptVersion & { parts: StoryPart[] }>;
  report: AnalysisReport | null;
}

export interface MetricsSnapshot {
  id: number;
  release_id?: number | null;
  story_id: number;
  script_version_id: number;
  story_part_id?: number | null;
  window_hours: number;
  source: string;
  metrics: Record<string, unknown>;
  derived_metrics?: Record<string, unknown> | null;
}

export interface AnalysisReport {
  id: number;
  batch_id?: number | null;
  story_id: number;
  concept_id?: number | null;
  analyst_version: string;
  status: string;
  summary: string;
  insights?: Record<string, unknown> | null;
  recommendations?: Record<string, unknown> | null;
  prompt_proposals?: Record<string, unknown> | null;
  metrics_window_hours: number;
}

export interface PromptVersion {
  id: number;
  kind: string;
  version_label: string;
  status: string;
  body: string;
  config?: Record<string, unknown> | null;
  notes?: string | null;
}

export interface ScriptGenerationRequest {
  batch_id: number;
  status: string;
}

export interface RedditIngestJob {
  id: number;
  subreddit: string;
  kind: string;
  status: string;
}

export interface RedditIngestResult {
  subreddit: string;
  inserted: number;
}

export interface RedditIngestResponse {
  results: RedditIngestResult[];
  total_inserted: number;
}

export interface PublishPlatformSettings {
  available_platforms: string[];
  active_platforms: string[];
  weekly_supported_platforms: string[];
}

export async function listStories(params: { status?: string; page?: number; limit?: number } = {}): Promise<Story[]> {
  const searchParams = new URLSearchParams();
  if (params.status) {
    searchParams.set("status", params.status);
  }
  if (params.page) {
    searchParams.set("page", String(params.page));
  }
  if (params.limit) {
    searchParams.set("limit", String(params.limit));
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

export async function generateScript(id: number): Promise<ScriptGenerationRequest> {
  return apiFetch<ScriptGenerationRequest>(`/stories/${id}/script`, { method: "POST" });
}

export async function createScriptBatch(
  id: number,
  payload: { candidate_count?: number; shortlisted_count?: number; temperature?: number } = {},
): Promise<ScriptBatchDetail> {
  return apiFetch<ScriptBatchDetail>(`/stories/${id}/script-batches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listScriptBatches(id: number): Promise<ScriptBatch[]> {
  return apiFetch<ScriptBatch[]>(`/stories/${id}/script-batches`);
}

export async function getScriptBatch(id: number): Promise<ScriptBatchDetail> {
  return apiFetch<ScriptBatchDetail>(`/script-batches/${id}`);
}

export async function selectScriptVersion(
  id: number,
  payload: { state: string },
): Promise<ScriptVersion> {
  return apiFetch<ScriptVersion>(`/script-versions/${id}/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function activateScriptVersion(id: number): Promise<ScriptVersion> {
  return apiFetch<ScriptVersion>(`/script-versions/${id}/activate`, { method: "POST" });
}

export async function listScriptVersionParts(id: number): Promise<StoryPart[]> {
  return apiFetch<StoryPart[]>(`/script-versions/${id}/parts`);
}

export async function createScriptVersionReleases(
  id: number,
  payload: { platforms: string[]; preset_slug: string; asset_bundle_id?: number | null },
): Promise<Release[]> {
  return apiFetch<Release[]>(`/script-versions/${id}/releases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getScriptVersionMetrics(
  id: number,
): Promise<{ script: ScriptVersion; snapshots: MetricsSnapshot[] }> {
  return apiFetch<{ script: ScriptVersion; snapshots: MetricsSnapshot[] }>(
    `/script-versions/${id}/metrics`,
  );
}

export async function listAnalysisReports(params: {
  story_id?: number;
  batch_id?: number;
} = {}): Promise<AnalysisReport[]> {
  const search = new URLSearchParams();
  if (params.story_id) {
    search.set("story_id", String(params.story_id));
  }
  if (params.batch_id) {
    search.set("batch_id", String(params.batch_id));
  }
  const suffix = search.toString();
  return apiFetch<AnalysisReport[]>(`/analysis-reports${suffix ? `?${suffix}` : ""}`);
}

export async function listPromptVersions(kind?: string): Promise<PromptVersion[]> {
  const suffix = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return apiFetch<PromptVersion[]>(`/prompt-versions${suffix}`);
}

export async function createPromptVersion(
  payload: {
    kind: string;
    version_label: string;
    body: string;
    config?: Record<string, unknown>;
    notes?: string;
    status?: string;
  },
): Promise<PromptVersion> {
  return apiFetch<PromptVersion>("/prompt-versions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function activatePromptVersion(id: number): Promise<PromptVersion> {
  return apiFetch<PromptVersion>(`/prompt-versions/${id}/activate`, { method: "POST" });
}

export async function archivePromptVersion(id: number): Promise<PromptVersion> {
  return apiFetch<PromptVersion>(`/prompt-versions/${id}/archive`, { method: "POST" });
}

export async function enqueueRedditIncremental(
  payload: { subreddits?: string[] } = {},
): Promise<RedditIngestResponse> {
  return adminFetch<RedditIngestResponse>("/api/admin/reddit/incremental", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getPublishPlatformSettings(): Promise<PublishPlatformSettings> {
  return adminFetch<PublishPlatformSettings>("/api/admin/settings/publish-platforms");
}

export async function updatePublishPlatformSettings(
  payload: { active_platforms: string[] },
): Promise<PublishPlatformSettings> {
  return adminFetch<PublishPlatformSettings>("/api/admin/settings/publish-platforms", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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

export async function listStoryAssets(id: number): Promise<MediaRef[]> {
  return apiFetch<MediaRef[]>(`/stories/${id}/assets`);
}

export async function indexStoryAssets(id: number): Promise<MediaRef[]> {
  return apiFetch<MediaRef[]>(`/stories/${id}/assets/index`, { method: "POST" });
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
    asset_refs: MediaRef[];
    part_asset_map?: Array<{ story_part_id: number; asset: MediaRef }>;
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

export async function approveRelease(
  releaseId: number,
  payload: {
    title?: string;
    description?: string;
    hashtags?: string[];
    publish_at?: string | null;
  },
): Promise<Release> {
  return apiFetch<Release>(`/releases/${releaseId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function retryRelease(releaseId: number): Promise<Release> {
  return apiFetch<Release>(`/releases/${releaseId}/retry`, {
    method: "POST",
  });
}

export async function completeManualPublish(
  releaseId: number,
  payload: { platform_video_id: string; notes?: string },
): Promise<Release> {
  return apiFetch<Release>(`/releases/${releaseId}/complete-manual-publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function clearRelease(releaseId: number): Promise<Release> {
  return apiFetch<Release>(`/releases/${releaseId}/clear`, {
    method: "POST",
  });
}
