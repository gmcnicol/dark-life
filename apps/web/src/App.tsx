import { useAuth } from "@clerk/react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/app-shell";
import BoardRoute from "@/routes/board";
import DashboardRoute from "@/routes/dashboard";
import ExperimentsRoute from "@/routes/experiments";
import InboxRoute from "@/routes/inbox";
import InsightsRoute from "@/routes/insights";
import JobsRoute from "@/routes/jobs";
import PublishRoute from "@/routes/publish";
import SettingsRoute from "@/routes/settings";
import SignInRoute from "@/routes/sign-in";
import StoryLayoutRoute from "@/routes/story-layout";
import StoryJobsRoute from "@/routes/story-jobs";
import StoryMediaRoute from "@/routes/story-media";
import StoryQueueRoute from "@/routes/story-queue";
import StoryRefinementRoute from "@/routes/story-refinement";
import StoryReviewRoute from "@/routes/story-review";
import StorySplitRoute from "@/routes/story-split";
import { clerkEnabled } from "@/lib/auth-config";
import { LoadingState } from "@/components/ui-surfaces";

function ShellLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

function RequireClerkAuth() {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return <LoadingState label="Loading authentication…" className="m-4 min-h-[calc(100vh-2rem)]" />;
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />;
  }

  return <Outlet />;
}

function RequireNoAuth() {
  return <Outlet />;
}

export default function App() {
  const AuthGate = clerkEnabled ? RequireClerkAuth : RequireNoAuth;

  return (
    <Routes>
      <Route path="/sign-in/*" element={clerkEnabled ? <SignInRoute /> : <Navigate to="/dashboard" replace />} />
      <Route element={<AuthGate />}>
        <Route element={<ShellLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardRoute />} />
          <Route path="/inbox" element={<InboxRoute />} />
          <Route path="/experiments" element={<ExperimentsRoute />} />
          <Route path="/board" element={<BoardRoute />} />
          <Route path="/jobs" element={<JobsRoute />} />
          <Route path="/insights" element={<InsightsRoute />} />
          <Route path="/publish" element={<PublishRoute />} />
          <Route path="/settings" element={<SettingsRoute />} />
          <Route path="/story/:id" element={<StoryLayoutRoute />}>
            <Route path="review" element={<StoryReviewRoute />} />
            <Route path="refinement" element={<StoryRefinementRoute />} />
            <Route path="split" element={<StorySplitRoute />} />
            <Route path="media" element={<StoryMediaRoute />} />
            <Route path="queue" element={<StoryQueueRoute />} />
            <Route path="jobs" element={<StoryJobsRoute />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}
