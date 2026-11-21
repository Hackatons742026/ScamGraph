import { PageHeader } from "@/components/layout/PageHeader";
import { ClassifyForm } from "@/features/classify/ClassifyForm";

export function Classify() {
  return (
    <>
      <PageHeader
        title="Classify new material"
        description="Known Campaign, New Campaign Candidate or Needs Review, with reasons."
      />
      <ClassifyForm />
    </>
  );
}
