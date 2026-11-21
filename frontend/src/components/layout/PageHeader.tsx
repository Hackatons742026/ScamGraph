import type { ReactNode } from "react";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions}
    </header>
  );
}

/** Temporary body for screens whose task has not landed yet. */
export function ComingSoon({ task }: { task: string }) {
  return <p className="rounded-md border border-dashed border-slate-300 p-6 text-sm text-slate-500">This screen is built in {task}.</p>;
}
