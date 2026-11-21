// Route placeholders; each is replaced by its own task (see the task number shown on screen).
import { ComingSoon, PageHeader } from "@/components/layout/PageHeader";

export function Campaigns() {
  return (<><PageHeader title="Campaigns" description="Campaigns and networks with their strongest evidence." /><ComingSoon task="#5" /></>);
}

export function Graph() {
  return (<><PageHeader title="Investigation graph" description="Links between incidents; edge style shows evidence strength." /><ComingSoon task="#5" /></>);
}

export function Classify() {
  return (<><PageHeader title="Classify new material" description="Known Campaign, New Campaign Candidate or Needs Review, with reasons." /><ComingSoon task="#6" /></>);
}

export function Review() {
  return (<><PageHeader title="Review queue" description="Unassigned and Needs Review incidents." /><ComingSoon task="#6" /></>);
}

export function Evaluation() {
  return (<><PageHeader title="Evaluation" description="Validation scenarios, pair metrics and leave-one-out routing." /><ComingSoon task="#8" /></>);
}

export function NotFound() {
  return <PageHeader title="Page not found" description="Use the navigation on the left." />;
}
