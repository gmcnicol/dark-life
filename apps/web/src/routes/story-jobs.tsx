import { useParams } from "react-router-dom";
import JobTable from "@/components/JobTable";

export default function StoryJobsRoute() {
  const params = useParams();
  return <JobTable storyId={Number(params.id)} />;
}
