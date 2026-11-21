import { Beaker, FlaskConical, GitBranch, Inbox, LayoutDashboard, List, Network, Upload } from "lucide-react";
import { NavLink, Outlet } from "react-router";
import { USE_MOCKS } from "@/lib/env";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/incidents", label: "Incidents", icon: List },
  { to: "/campaigns", label: "Campaigns", icon: GitBranch },
  { to: "/graph", label: "Investigation graph", icon: Network },
  { to: "/classify", label: "Classify", icon: Upload },
  { to: "/review", label: "Review queue", icon: Inbox },
  { to: "/evaluation", label: "Evaluation", icon: FlaskConical },
] as const;

export function AppShell() {
  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="px-4 py-4">
          <div className="text-base font-bold tracking-tight">ScamGraph DNA</div>
          <div className="text-xs text-slate-500">Fraud campaign intelligence</div>
        </div>
        <nav aria-label="Main" className="flex flex-col gap-0.5 px-2">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn("flex items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-100", isActive && "bg-slate-100 font-medium text-slate-900")
              }
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        {USE_MOCKS && (
          <div role="note" className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-6 py-1.5 text-xs text-amber-900">
            <Beaker className="h-3.5 w-3.5" aria-hidden />
            Mock mode: synthetic data only (VITE_USE_MOCKS=true)
          </div>
        )}
        <main className="min-w-0 flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
