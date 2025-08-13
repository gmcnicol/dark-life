import JobTable from "@/components/JobTable";

export default function StoryJobsPage({ params }: { params: { id: string } }) {
  return <JobTable storyId={Number(params.id)} />;
}
