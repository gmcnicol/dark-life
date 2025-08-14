import JobTable from "@/components/JobTable";

export default async function StoryJobsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <JobTable storyId={Number(id)} />;
}
