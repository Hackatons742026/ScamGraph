// Route placeholders; each is replaced by its own task (see the task number shown on screen).
import { ComingSoon, PageHeader } from "@/components/layout/PageHeader";

export function Evaluation() {
  return (<><PageHeader title="Evaluation" description="Validation scenarios, pair metrics and leave-one-out routing." /><ComingSoon task="#8" /></>);
}

export function NotFound() {
  return <PageHeader title="Page not found" description="Use the navigation on the left." />;
}
