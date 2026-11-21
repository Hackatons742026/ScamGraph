import type { RouteObject } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { Incidents } from "@/pages/Incidents";
import { Overview } from "@/pages/Overview";
import { Campaigns, Classify, Evaluation, Graph, IncidentDetail, NotFound, Review } from "@/pages/placeholders";

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
