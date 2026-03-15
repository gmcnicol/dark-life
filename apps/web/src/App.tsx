import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/app-shell";
import BoardRoute from "@/routes/board";
import DashboardRoute from "@/routes/dashboard";
import InboxRoute from "@/routes/inbox";
import JobsRoute from "@/routes/jobs";
import PublishRoute from "@/routes/publish";
import SettingsRoute from "@/routes/settings";
import StoryLayoutRoute from "@/routes/story-layout";
import StoryJobsRoute from "@/routes/story-jobs";
import StoryMediaRoute from "@/routes/story-media";
import StoryQueueRoute from "@/routes/story-queue";
import StoryReviewRoute from "@/routes/story-review";
import StorySplitRoute from "@/routes/story-split";

function ShellLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<ShellLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardRoute />} />
        <Route path="/inbox" element={<InboxRoute />} />
        <Route path="/board" element={<BoardRoute />} />
        <Route path="/jobs" element={<JobsRoute />} />
        <Route path="/publish" element={<PublishRoute />} />
        <Route path="/settings" element={<SettingsRoute />} />
        <Route path="/story/:id" element={<StoryLayoutRoute />}>
          <Route path="review" element={<StoryReviewRoute />} />
          <Route path="split" element={<StorySplitRoute />} />
          <Route path="media" element={<StoryMediaRoute />} />
          <Route path="queue" element={<StoryQueueRoute />} />
          <Route path="jobs" element={<StoryJobsRoute />} />
        </Route>
      </Route>
    </Routes>
  );
}
