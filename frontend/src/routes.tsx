import type { RouteObject } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { Campaigns } from "@/pages/Campaigns";
import { Classify } from "@/pages/Classify";
import { Evaluation } from "@/pages/Evaluation";
import { Graph } from "@/pages/Graph";
import { IncidentDetail } from "@/pages/IncidentDetail";
import { Incidents } from "@/pages/Incidents";
import { Overview } from "@/pages/Overview";
import { Review } from "@/pages/Review";
import { NotFound } from "@/pages/placeholders";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Overview /> },
      { path: "incidents", element: <Incidents /> },
      { path: "incidents/:id", element: <IncidentDetail /> },
      { path: "campaigns", element: <Campaigns /> },
      { path: "graph", element: <Graph /> },
      { path: "classify", element: <Classify /> },
      { path: "review", element: <Review /> },
      { path: "evaluation", element: <Evaluation /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];
